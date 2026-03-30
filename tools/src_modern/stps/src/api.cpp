// api.cpp — High-level STPS API implementation
#include "stps/api.hpp"
#include "stps/io.hpp"
#include "stps/warp_engine.hpp"
#include "stps/logger.hpp"
#include <chrono>
#include <cmath>

namespace stps {

static void compute_marker_distance(const std::vector<Point3D>& a,
                                     const std::vector<Point3D>& b,
                                     double& mean, double& stddev) {
    if (a.size() != b.size() || a.empty()) {
        mean = stddev = 0;
        return;
    }
    int n = static_cast<int>(a.size());
    std::vector<double> dists(n);
    for (int i = 0; i < n; i++) {
        double dx = a[i].x - b[i].x;
        double dy = a[i].y - b[i].y;
        double dz = a[i].z - b[i].z;
        dists[i] = std::sqrt(dx*dx + dy*dy + dz*dz);
    }
    double sum = 0;
    for (double d : dists) sum += d;
    mean = sum / n;
    double var = 0;
    for (double d : dists) { double diff = d - mean; var += diff * diff; }
    stddev = std::sqrt(var / n);
}

static std::vector<Point3D> markers_to_points(const std::vector<Marker>& markers) {
    std::vector<Point3D> pts;
    pts.reserve(markers.size());
    for (const auto& m : markers)
        pts.emplace_back(m.x, m.y, m.z);
    return pts;
}

ResultSummary run_single_warp(
    const std::string& subject_image_path,
    const std::string& target_marker_path,
    const std::string& subject_marker_path,
    const std::string& output_path,
    const StpsConfig& config,
    const ImageDims* output_size_override)
{
    ResultSummary result;
    auto t0 = std::chrono::steady_clock::now();

    // 1. Load image
    LOG_INFO("=== Single-sample STPS warp mode ===");
    std::vector<uint8_t> img_data;
    ImageDims img_dims;
    if (!io::load_v3draw(subject_image_path, img_data, img_dims)) {
        result.error_message = "Failed to load subject image: " + subject_image_path;
        LOG_ERROR("%s", result.error_message.c_str());
        return result;
    }
    result.input_dims = img_dims;
    LOG_INFO("Image: [w=%lld, h=%lld, d=%lld, c=%lld]",
             (long long)img_dims.w, (long long)img_dims.h,
             (long long)img_dims.d, (long long)img_dims.c);

    // 2. Read markers
    auto markers_tar = io::read_markers(target_marker_path);
    auto markers_sub = io::read_markers(subject_marker_path);
    LOG_INFO("Markers: tar=%zu, sub=%zu", markers_tar.size(), markers_sub.size());

    if (markers_tar.empty() || markers_sub.empty()) {
        result.error_message = "Marker files empty or unreadable";
        LOG_ERROR("%s", result.error_message.c_str());
        return result;
    }
    if (markers_tar.size() != markers_sub.size()) {
        result.error_message = "Marker count mismatch: tar=" +
            std::to_string(markers_tar.size()) + " sub=" +
            std::to_string(markers_sub.size());
        LOG_ERROR("%s", result.error_message.c_str());
        return result;
    }

    auto target_pts = markers_to_points(markers_tar);
    auto subject_pts = markers_to_points(markers_sub);
    result.num_control_points = static_cast<int>(target_pts.size());

    // Compute marker distance statistics
    compute_marker_distance(target_pts, subject_pts,
                            result.mean_marker_distance,
                            result.std_marker_distance);
    LOG_INFO("Marker distance: mean=%.3f, std=%.3f",
             result.mean_marker_distance, result.std_marker_distance);

    // 3. Determine output dimensions
    ImageDims out_dims;
    if (output_size_override) {
        out_dims = *output_size_override;
    } else {
        out_dims = { img_dims.w, img_dims.h, img_dims.d, 1 };
    }
    result.output_dims = out_dims;
    LOG_INFO("Output size: [%lld, %lld, %lld]",
             (long long)out_dims.w, (long long)out_dims.h, (long long)out_dims.d);

    // 4. Warp
    // Note marker order: sub→target param, tar→subject param
    // This defines warp direction from subject space → target space
    // (identical to original code)
    auto warped = warp_image(img_data.data(), img_dims,
                              subject_pts, target_pts,
                              out_dims, config);
    if (warped.empty()) {
        result.error_message = "Warp computation failed";
        LOG_ERROR("%s", result.error_message.c_str());
        return result;
    }

    // 5. Save output
    if (!io::save_v3draw(output_path, warped.data(), out_dims)) {
        result.error_message = "Failed to save output: " + output_path;
        LOG_ERROR("%s", result.error_message.c_str());
        return result;
    }

    auto t1 = std::chrono::steady_clock::now();
    result.elapsed_seconds = std::chrono::duration<double>(t1 - t0).count();
    result.success = true;
    result.output_file = output_path;
    LOG_INFO("Output saved to [%s], total time: %.2f s",
             output_path.c_str(), result.elapsed_seconds);

    return result;
}

} // namespace stps
