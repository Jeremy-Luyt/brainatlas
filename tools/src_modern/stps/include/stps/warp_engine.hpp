// warp_engine.hpp — Block-by-block image warping orchestrator
// Replaces imgwarp_smallmemory, q_imgblockwarp, q_dfblcokinterp_*
#pragma once

#include "stps/types.hpp"
#include <vector>
#include <cstdint>

namespace stps {

// -----------------------------------------------------------------------
// Main STPS/TPS image warp function.
//
// Orchestration (identical to original imgwarp_smallmemory):
//   1. Compute sub-sampled displacement field (TPS or STPS)
//   2. For each block:
//      a) Interpolate sub-DF → full-resolution DF block
//      b) Warp image block using DF
//   3. Assemble output image
//
// Parameters:
//   img_data     — input image pixel data (uint8)
//   img_dims     — input image dimensions (w,h,d,c)
//   target_pts   — target control points (warp destination)
//   subject_pts  — subject control points (warp source)
//   output_dims  — desired output dimensions (may differ from input)
//   config       — algorithm parameters
//
// Returns: warped image pixel data (uint8), same layout as input.
// -----------------------------------------------------------------------
std::vector<uint8_t> warp_image(
    const uint8_t* img_data,
    const ImageDims& img_dims,
    const std::vector<Point3D>& target_pts,
    const std::vector<Point3D>& subject_pts,
    const ImageDims& output_dims,
    const StpsConfig& config);

// -----------------------------------------------------------------------
// Warp a set of 3D points using the STPS/TPS displacement field.
// Each point is displaced by interpolating the DF at its location.
// -----------------------------------------------------------------------
std::vector<Point3D> warp_points(
    const std::vector<Point3D>& points,
    const std::vector<Point3D>& target_pts,
    const std::vector<Point3D>& subject_pts,
    const ImageDims& vol_dims,
    const StpsConfig& config);

} // namespace stps
