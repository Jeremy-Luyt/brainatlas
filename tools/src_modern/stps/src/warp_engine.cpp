// warp_engine.cpp — Block-by-block image warping
// Replaces imgwarp_smallmemory, q_imgblockwarp, q_dfblcokinterp_linear,
// q_dfblcokinterp_bspline, and the GPU interpolation path.
//
// All CPU-only. Faithfully reproduces original block processing logic.

#include "stps/warp_engine.hpp"
#include "stps/tps_solver.hpp"
#include "stps/logger.hpp"
#include <cmath>
#include <algorithm>
#include <chrono>

namespace stps {

// ── Trilinear interpolation of a single value at fractional coordinates ──
static float trilinear_interp_df(const Volume3D<Displacement3D>& vol,
                                  int64_t dim0, int64_t dim1, int64_t dim2,
                                  double x, double y, double z, int comp) {
    int64_t x0 = static_cast<int64_t>(std::floor(x));
    int64_t x1 = static_cast<int64_t>(std::ceil(x));
    int64_t y0 = static_cast<int64_t>(std::floor(y));
    int64_t y1 = static_cast<int64_t>(std::ceil(y));
    int64_t z0 = static_cast<int64_t>(std::floor(z));
    int64_t z1 = static_cast<int64_t>(std::ceil(z));

    x0 = std::clamp(x0, (int64_t)0, dim0 - 1);
    x1 = std::clamp(x1, (int64_t)0, dim0 - 1);
    y0 = std::clamp(y0, (int64_t)0, dim1 - 1);
    y1 = std::clamp(y1, (int64_t)0, dim1 - 1);
    z0 = std::clamp(z0, (int64_t)0, dim2 - 1);
    z1 = std::clamp(z1, (int64_t)0, dim2 - 1);

    double xd = x - std::floor(x);
    double yd = y - std::floor(y);
    double zd = z - std::floor(z);

    auto get = [&](int64_t ix, int64_t iy, int64_t iz) -> float {
        const auto& d = vol(ix, iy, iz);
        return (comp == 0) ? d.sx : (comp == 1) ? d.sy : d.sz;
    };

    double c00 = get(x0, y0, z0) * (1 - xd) + get(x1, y0, z0) * xd;
    double c10 = get(x0, y1, z0) * (1 - xd) + get(x1, y1, z0) * xd;
    double c01 = get(x0, y0, z1) * (1 - xd) + get(x1, y0, z1) * xd;
    double c11 = get(x0, y1, z1) * (1 - xd) + get(x1, y1, z1) * xd;

    double c0 = c00 * (1 - yd) + c10 * yd;
    double c1 = c01 * (1 - yd) + c11 * yd;

    return static_cast<float>(c0 * (1 - zd) + c1 * zd);
}

// ── Trilinear DF block interpolation (replaces q_dfblcokinterp_linear) ──
// Takes a 2×2×2 corner of the sub-DF and interpolates to a full block.
static void interp_df_block_linear(
    const Volume3D<Displacement3D>& subDF,
    int64_t bx, int64_t by, int64_t bz,
    int64_t sub_x, int64_t sub_y, int64_t sub_z,
    Volume3D<Displacement3D>& block)
{
    for (int64_t z = 0; z < bz; z++) {
        double fz = static_cast<double>(z) / bz;
        for (int64_t y = 0; y < by; y++) {
            double fy = static_cast<double>(y) / by;
            for (int64_t x = 0; x < bx; x++) {
                double fx = static_cast<double>(x) / bx;

                // Trilinear from 2×2×2 corners
                for (int c = 0; c < 3; c++) {
                    auto get = [&](int di, int dj, int dk) -> float {
                        const auto& d = subDF(sub_x + di, sub_y + dj, sub_z + dk);
                        return (c == 0) ? d.sx : (c == 1) ? d.sy : d.sz;
                    };

                    double v000 = get(0, 0, 0), v100 = get(1, 0, 0);
                    double v010 = get(0, 1, 0), v110 = get(1, 1, 0);
                    double v001 = get(0, 0, 1), v101 = get(1, 0, 1);
                    double v011 = get(0, 1, 1), v111 = get(1, 1, 1);

                    double c00 = v000 * (1 - fx) + v100 * fx;
                    double c10 = v010 * (1 - fx) + v110 * fx;
                    double c01 = v001 * (1 - fx) + v101 * fx;
                    double c11 = v011 * (1 - fx) + v111 * fx;
                    double c0  = c00  * (1 - fy) + c10 * fy;
                    double c1  = c01  * (1 - fy) + c11 * fy;
                    float val  = static_cast<float>(c0 * (1 - fz) + c1 * fz);

                    if (c == 0) block(x, y, z).sx = val;
                    else if (c == 1) block(x, y, z).sy = val;
                    else block(x, y, z).sz = val;
                }
            }
        }
    }
}

// ── B-spline DF block interpolation (replaces q_dfblcokinterp_bspline) ──
// Uses a 4×4×4 control-point window from the sub-DF.
// Formula: DF_block = BxBxB * vectorized_control_points
static void interp_df_block_bspline(
    const Volume3D<Displacement3D>& subDF,
    const Eigen::MatrixXd& basis,  // (n^3 × 64)
    int64_t block_size,
    int64_t sub_x, int64_t sub_y, int64_t sub_z,
    Volume3D<Displacement3D>& block)
{
    // Vectorize the 4×4×4 control-point window (64 points, 3 components)
    Eigen::MatrixXd ctrl(64, 3);
    int idx = 0;
    for (int dk = 0; dk < 4; dk++) {
        for (int di = 0; di < 4; di++) {
            for (int dj = 0; dj < 4; dj++) {
                const auto& d = subDF(sub_x + di, sub_y + dj, sub_z + dk);
                ctrl(idx, 0) = d.sx;
                ctrl(idx, 1) = d.sy;
                ctrl(idx, 2) = d.sz;
                idx++;
            }
        }
    }

    // Interpolate: result = basis * ctrl  → (n^3 × 3)
    Eigen::MatrixXd result = basis * ctrl;

    // De-vectorize into block
    idx = 0;
    for (int64_t z = 0; z < block_size; z++) {
        for (int64_t x = 0; x < block_size; x++) {
            for (int64_t y = 0; y < block_size; y++) {
                block(x, y, z).sx = static_cast<float>(result(idx, 0));
                block(x, y, z).sy = static_cast<float>(result(idx, 1));
                block(x, y, z).sz = static_cast<float>(result(idx, 2));
                idx++;
            }
        }
    }
}

// ── Warp a single image block using displacement field (q_imgblockwarp) ──
static void warp_image_block(
    const uint8_t* img_data,
    const ImageDims& img_dims,
    const Volume3D<Displacement3D>& df_block,
    int64_t bx, int64_t by, int64_t bz,
    int img_interp,
    int64_t start_x, int64_t start_y, int64_t start_z,
    uint8_t* out_data,
    const ImageDims& out_dims)
{
    for (int64_t z = 0; z < bz; z++) {
        for (int64_t y = 0; y < by; y++) {
            for (int64_t x = 0; x < bx; x++) {
                int64_t wx = start_x + x;
                int64_t wy = start_y + y;
                int64_t wz = start_z + z;

                if (wx >= out_dims.w || wy >= out_dims.h || wz >= out_dims.d)
                    continue;

                double sx = wx + df_block(x, y, z).sx;
                double sy = wy + df_block(x, y, z).sy;
                double sz = wz + df_block(x, y, z).sz;

                // Out of bounds check
                if (sx < 0 || sx > img_dims.w - 1 ||
                    sy < 0 || sy > img_dims.h - 1 ||
                    sz < 0 || sz > img_dims.d - 1) {
                    for (int64_t c = 0; c < out_dims.c; c++) {
                        out_data[c * out_dims.w * out_dims.h * out_dims.d +
                                 wz * out_dims.w * out_dims.h + wy * out_dims.w + wx] = 0;
                    }
                    continue;
                }

                if (img_interp == 1) {
                    // Nearest-neighbor
                    int64_t nx = static_cast<int64_t>(sx + 0.5);
                    int64_t ny = static_cast<int64_t>(sy + 0.5);
                    int64_t nz = static_cast<int64_t>(sz + 0.5);
                    nx = std::clamp(nx, (int64_t)0, img_dims.w - 1);
                    ny = std::clamp(ny, (int64_t)0, img_dims.h - 1);
                    nz = std::clamp(nz, (int64_t)0, img_dims.d - 1);

                    for (int64_t c = 0; c < out_dims.c; c++) {
                        out_data[c * out_dims.w * out_dims.h * out_dims.d +
                                 wz * out_dims.w * out_dims.h + wy * out_dims.w + wx] =
                            img_data[c * img_dims.w * img_dims.h * img_dims.d +
                                     nz * img_dims.w * img_dims.h + ny * img_dims.w + nx];
                    }
                } else {
                    // Bilinear (trilinear) interpolation
                    int64_t x_s = static_cast<int64_t>(std::floor(sx));
                    int64_t x_b = static_cast<int64_t>(std::ceil(sx));
                    int64_t y_s = static_cast<int64_t>(std::floor(sy));
                    int64_t y_b = static_cast<int64_t>(std::ceil(sy));
                    int64_t z_s = static_cast<int64_t>(std::floor(sz));
                    int64_t z_b = static_cast<int64_t>(std::ceil(sz));

                    double l_w = 1.0 - (sx - x_s), r_w = 1.0 - l_w;
                    double t_w = 1.0 - (sy - y_s), b_w = 1.0 - t_w;
                    double u_w = 1.0 - (sz - z_s), d_w = 1.0 - u_w;

                    for (int64_t c = 0; c < out_dims.c; c++) {
                        auto pix = [&](int64_t px, int64_t py, int64_t pz) -> double {
                            return static_cast<double>(
                                img_data[c * img_dims.w * img_dims.h * img_dims.d +
                                         pz * img_dims.w * img_dims.h + py * img_dims.w + px]);
                        };

                        double higher = t_w * (l_w * pix(x_s, y_s, z_s) + r_w * pix(x_b, y_s, z_s)) +
                                        b_w * (l_w * pix(x_s, y_b, z_s) + r_w * pix(x_b, y_b, z_s));
                        double lower  = t_w * (l_w * pix(x_s, y_s, z_b) + r_w * pix(x_b, y_s, z_b)) +
                                        b_w * (l_w * pix(x_s, y_b, z_b) + r_w * pix(x_b, y_b, z_b));
                        double val = u_w * higher + d_w * lower + 0.5;

                        out_data[c * out_dims.w * out_dims.h * out_dims.d +
                                 wz * out_dims.w * out_dims.h + wy * out_dims.w + wx] =
                            static_cast<uint8_t>(std::clamp(val, 0.0, 255.0));
                    }
                }
            }
        }
    }
}

// -----------------------------------------------------------------------
// Main STPS/TPS image warp (replaces imgwarp_smallmemory)
// -----------------------------------------------------------------------
std::vector<uint8_t> warp_image(
    const uint8_t* img_data,
    const ImageDims& img_dims,
    const std::vector<Point3D>& target_pts,
    const std::vector<Point3D>& subject_pts,
    const ImageDims& output_dims,
    const StpsConfig& config)
{
    // Validate
    if (!img_data) { LOG_ERROR("Input image is null"); return {}; }
    if (target_pts.empty() || subject_pts.empty()) { LOG_ERROR("Control points empty"); return {}; }
    if (target_pts.size() != subject_pts.size()) { LOG_ERROR("Control point count mismatch"); return {}; }

    int64_t bx = config.block_size, by = config.block_size, bz = config.block_size;
    if (bx <= 0 || by <= 0 || bz <= 0) { LOG_ERROR("Invalid block size"); return {}; }

    if (config.df_method == 1 && (bx != by || bx != bz)) {
        LOG_ERROR("B-spline DF interpolation requires cubic blocks (bx=by=bz)");
        return {};
    }

    auto t0 = std::chrono::steady_clock::now();

    // Step 1: Compute sub-sampled displacement field
    LOG_INFO("Computing sub-sampled displacement field...");
    Volume3D<Displacement3D> subDF;
    if (config.df_method == 0) {
        subDF = compute_df_tps(target_pts, subject_pts,
                               output_dims.w, output_dims.h, output_dims.d,
                               bx, by, bz);
    } else {
        subDF = compute_df_stps(target_pts, subject_pts,
                                output_dims.w, output_dims.h, output_dims.d,
                                bx, by, bz, config.lambda);
    }

    if (!subDF.valid()) {
        LOG_ERROR("Failed to compute displacement field");
        return {};
    }

    auto t1 = std::chrono::steady_clock::now();
    double df_time = std::chrono::duration<double>(t1 - t0).count();
    LOG_INFO("DF computation: %.2f s, sub-DF size: [%lld, %lld, %lld]",
             df_time, (long long)subDF.dim(0), (long long)subDF.dim(1), (long long)subDF.dim(2));

    // Step 2: Allocate output
    std::vector<uint8_t> out(static_cast<size_t>(output_dims.total()), 0);

    // Step 3: Block-by-block interpolation and warping
    LOG_INFO("Interpolating DF and warping block-by-block...");
    LOG_INFO("  DF interp: %s", config.df_method == 0 ? "trilinear" : "B-spline");
    LOG_INFO("  Img interp: %s", config.img_interp == 0 ? "bilinear" : "nearest-neighbor");

    Volume3D<Displacement3D> df_block(bx, by, bz);

    if (config.df_method == 0) {
        // Trilinear DF interpolation path
        int64_t n_sub_x = subDF.dim(0) - 1;
        int64_t n_sub_y = subDF.dim(1) - 1;
        int64_t n_sub_z = subDF.dim(2) - 1;

        for (int64_t sz = 0; sz < n_sub_z; sz++) {
            for (int64_t sy = 0; sy < n_sub_y; sy++) {
                for (int64_t sx = 0; sx < n_sub_x; sx++) {
                    interp_df_block_linear(subDF, bx, by, bz, sx, sy, sz, df_block);
                    warp_image_block(img_data, img_dims, df_block, bx, by, bz,
                                    config.img_interp,
                                    sx * bx, sy * by, sz * bz,
                                    out.data(), output_dims);
                }
            }
        }
    } else {
        // B-spline DF interpolation path
        Eigen::MatrixXd basis = build_bspline_basis_3d(static_cast<int>(bx));
        if (basis.rows() == 0) {
            LOG_ERROR("Failed to build B-spline basis");
            return {};
        }
        LOG_DEBUG("B-spline basis: [%d x %d]", (int)basis.rows(), (int)basis.cols());

        int64_t n_sub_x = subDF.dim(0) - 1 - 2;
        int64_t n_sub_y = subDF.dim(1) - 1 - 2;
        int64_t n_sub_z = subDF.dim(2) - 1 - 2;

        for (int64_t sz = 0; sz < n_sub_z; sz++) {
            for (int64_t sy = 0; sy < n_sub_y; sy++) {
                for (int64_t sx = 0; sx < n_sub_x; sx++) {
                    interp_df_block_bspline(subDF, basis, bx, sx, sy, sz, df_block);
                    warp_image_block(img_data, img_dims, df_block, bx, by, bz,
                                    config.img_interp,
                                    sx * bx, sy * by, sz * bz,
                                    out.data(), output_dims);
                }
            }
        }
    }

    auto t2 = std::chrono::steady_clock::now();
    double warp_time = std::chrono::duration<double>(t2 - t1).count();
    LOG_INFO("Block warping: %.2f s, total: %.2f s", warp_time, df_time + warp_time);

    return out;
}

// -----------------------------------------------------------------------
// Warp points using the displacement field
// -----------------------------------------------------------------------
std::vector<Point3D> warp_points(
    const std::vector<Point3D>& points,
    const std::vector<Point3D>& target_pts,
    const std::vector<Point3D>& subject_pts,
    const ImageDims& vol_dims,
    const StpsConfig& config)
{
    if (points.empty()) return {};

    int64_t bx = config.block_size, by = config.block_size, bz = config.block_size;

    Volume3D<Displacement3D> subDF;
    if (config.df_method == 0) {
        subDF = compute_df_tps(target_pts, subject_pts,
                               vol_dims.w, vol_dims.h, vol_dims.d, bx, by, bz);
    } else {
        subDF = compute_df_stps(target_pts, subject_pts,
                                vol_dims.w, vol_dims.h, vol_dims.d, bx, by, bz,
                                config.lambda);
    }

    if (!subDF.valid()) {
        LOG_ERROR("Failed to compute DF for point warping");
        return {};
    }

    std::vector<Point3D> warped;
    warped.reserve(points.size());

    for (const auto& pt : points) {
        // Map point to sub-DF coordinates
        double sx, sy, sz;
        if (config.df_method == 0) {
            sx = pt.x / bx;
            sy = pt.y / by;
            sz = pt.z / bz;
        } else {
            sx = pt.x / bx + 1; // +1 for bspline border offset
            sy = pt.y / by + 1;
            sz = pt.z / bz + 1;
        }

        float dx = trilinear_interp_df(subDF, subDF.dim(0), subDF.dim(1), subDF.dim(2), sx, sy, sz, 0);
        float dy = trilinear_interp_df(subDF, subDF.dim(0), subDF.dim(1), subDF.dim(2), sx, sy, sz, 1);
        float dz = trilinear_interp_df(subDF, subDF.dim(0), subDF.dim(1), subDF.dim(2), sx, sy, sz, 2);

        warped.push_back(Point3D(pt.x + dx, pt.y + dy, pt.z + dz));
    }

    return warped;
}

} // namespace stps
