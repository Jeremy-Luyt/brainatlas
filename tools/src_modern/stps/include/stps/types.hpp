// types.hpp — Core data types for STPS
// Replaces V3D Vol3DSimple, DisplaceFieldF3D, Coord3D_JBA, ImageMarker, etc.
#pragma once

#include <cstdint>
#include <vector>
#include <string>
#include <array>
#include <Eigen/Dense>

namespace stps {

// 3D coordinate (replaces Coord3D_JBA)
struct Point3D {
    double x = 0, y = 0, z = 0;
    Point3D() = default;
    Point3D(double x_, double y_, double z_) : x(x_), y(y_), z(z_) {}
};

// 3D displacement field element (replaces DisplaceFieldF3D)
struct Displacement3D {
    float sx = 0, sy = 0, sz = 0;
};

// Marker point read from .marker file (replaces ImageMarker)
struct Marker {
    double x = 0, y = 0, z = 0;
    int radius = 0;
    int shape = 1;
    std::string name;
    std::string comment;
};

// 3D volume (replaces Vol3DSimple<T>)
template <typename T>
class Volume3D {
public:
    Volume3D() = default;
    Volume3D(int64_t s0, int64_t s1, int64_t s2)
        : sz_{s0, s1, s2}, data_(static_cast<size_t>(s0 * s1 * s2)) {}

    bool valid() const { return !data_.empty() && sz_[0] > 0 && sz_[1] > 0 && sz_[2] > 0; }
    int64_t dim(int i) const { return sz_[i]; }
    int64_t total() const { return sz_[0] * sz_[1] * sz_[2]; }

    T& operator()(int64_t x, int64_t y, int64_t z) {
        return data_[static_cast<size_t>(z * sz_[0] * sz_[1] + y * sz_[0] + x)];
    }
    const T& operator()(int64_t x, int64_t y, int64_t z) const {
        return data_[static_cast<size_t>(z * sz_[0] * sz_[1] + y * sz_[0] + x)];
    }

    T* data() { return data_.data(); }
    const T* data() const { return data_.data(); }
    size_t size() const { return data_.size(); }

private:
    std::array<int64_t, 3> sz_{0, 0, 0};
    std::vector<T> data_;
};

// Image dimensions
struct ImageDims {
    int64_t w = 0, h = 0, d = 0, c = 1;
    int64_t total() const { return w * h * d * c; }
};

// STPS algorithm parameters
struct StpsConfig {
    int block_size = 4;         // Block size for block-by-block processing
    int df_method = 1;          // 0=trilinear (TPS), 1=bspline (STPS)
    int img_interp = 0;         // 0=bilinear, 1=nearest-neighbor
    double lambda = 0.2;        // Regularization parameter for STPS
    int downsample = 4;         // Downsample factor for batch mode

    // Marker offsets for batch mode (matching global registration padding)
    double offset_x = 9.0;
    double offset_y = 8.0;
    double offset_z = 7.0;
};

// Result summary (for JSON output)
struct ResultSummary {
    bool success = false;
    std::string error_message;
    double elapsed_seconds = 0;
    std::string output_file;
    int num_control_points = 0;
    ImageDims input_dims;
    ImageDims output_dims;
    double mean_marker_distance = 0;
    double std_marker_distance = 0;
};

// Convenience typedefs
using MatrixXd = Eigen::MatrixXd;
using MatrixXf = Eigen::MatrixXf;
using VectorXd = Eigen::VectorXd;

} // namespace stps
