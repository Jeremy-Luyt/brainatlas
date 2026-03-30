// api.hpp — High-level STPS API (single-sample warp and batch mode)
#pragma once

#include "stps/types.hpp"
#include <string>

namespace stps {

// Run single-sample STPS warp.
// Returns ResultSummary with output info.
ResultSummary run_single_warp(
    const std::string& subject_image_path,
    const std::string& target_marker_path,
    const std::string& subject_marker_path,
    const std::string& output_path,
    const StpsConfig& config,
    const ImageDims* output_size_override = nullptr);

} // namespace stps
