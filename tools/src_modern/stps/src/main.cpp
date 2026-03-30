// main.cpp — STPS command-line entry point
// Modern C++17 CLI using CLI11, replacing getopt.
// Outputs JSON result summary for Python/FastAPI integration.

#include "stps/api.hpp"
#include "stps/types.hpp"
#include "stps/logger.hpp"

#include <CLI/CLI.hpp>
#include <nlohmann/json.hpp>

#include <iostream>
#include <fstream>
#include <filesystem>
#include <string>

namespace fs = std::filesystem;
using json = nlohmann::json;

static json result_to_json(const stps::ResultSummary& r) {
    json j;
    j["success"] = r.success;
    j["error_message"] = r.error_message;
    j["elapsed_seconds"] = r.elapsed_seconds;
    j["output_file"] = r.output_file;
    j["num_control_points"] = r.num_control_points;
    j["input_dims"] = {
        {"w", r.input_dims.w}, {"h", r.input_dims.h},
        {"d", r.input_dims.d}, {"c", r.input_dims.c}
    };
    j["output_dims"] = {
        {"w", r.output_dims.w}, {"h", r.output_dims.h},
        {"d", r.output_dims.d}, {"c", r.output_dims.c}
    };
    j["mean_marker_distance"] = r.mean_marker_distance;
    j["std_marker_distance"] = r.std_marker_distance;
    return j;
}

int main(int argc, char* argv[]) {
    CLI::App app{"STPS - Subsampled Thin-Plate Spline Image & Point Warping Tool"};
    app.set_version_flag("--version", "stps 1.0.0");

    // ── Input parameters ──
    std::string subject_image;
    std::string target_markers;
    std::string subject_markers;
    std::string output_file;
    std::string log_file;
    std::string output_size_str;

    // ── Algorithm parameters ──
    stps::StpsConfig config;
    int block_size = 4;
    int df_method = 1;
    int img_interp = 0;
    double lambda = 0.2;
    bool verbose = false;

    app.add_option("-s,--subject-image", subject_image,
                   "Subject image file (v3draw format)")
        ->required()
        ->check(CLI::ExistingFile);

    app.add_option("-T,--target-markers", target_markers,
                   "Target marker file (.marker or CSV)")
        ->required()
        ->check(CLI::ExistingFile);

    app.add_option("-S,--subject-markers", subject_markers,
                   "Subject marker file (.marker or CSV)")
        ->required()
        ->check(CLI::ExistingFile);

    app.add_option("-o,--output", output_file,
                   "Output warped image file (v3draw)")
        ->required();

    app.add_option("-b,--block-size", block_size,
                   "Block size for STPS warp (default: 4)")
        ->check(CLI::Range(2, 64));

    app.add_option("-d,--df-method", df_method,
                   "DF interpolation: 0=trilinear(TPS), 1=bspline(STPS) (default: 1)")
        ->check(CLI::Range(0, 1));

    app.add_option("-i,--img-interp", img_interp,
                   "Image interpolation: 0=bilinear, 1=nearest-neighbor (default: 0)")
        ->check(CLI::Range(0, 1));

    app.add_option("--lambda", lambda,
                   "STPS regularization parameter (default: 0.2)")
        ->check(CLI::Range(0.0, 100.0));

    app.add_option("-R,--output-size", output_size_str,
                   "Output dimensions override as W,H,D (e.g. 568,320,456)");

    app.add_option("-l,--log", log_file,
                   "Log output to file");

    app.add_flag("-v,--verbose", verbose,
                 "Enable verbose (debug) logging");

    CLI11_PARSE(app, argc, argv);

    // ── Setup logging ──
    auto& logger = stps::Logger::instance();
    if (verbose) logger.set_level(stps::LogLevel::DEBUG);
    if (!log_file.empty()) {
        if (!logger.open_file(log_file)) {
            std::cerr << "WARNING: Cannot open log file: " << log_file << "\n";
        }
    }

    // ── Configure ──
    config.block_size = block_size;
    config.df_method = df_method;
    config.img_interp = img_interp;
    config.lambda = lambda;

    // ── Parse output size override ──
    stps::ImageDims override_dims;
    stps::ImageDims* override_ptr = nullptr;
    if (!output_size_str.empty()) {
        if (std::sscanf(output_size_str.c_str(), "%lld,%lld,%lld",
                        &override_dims.w, &override_dims.h, &override_dims.d) != 3) {
            std::cerr << "ERROR: Invalid --output-size format. Expected W,H,D\n";
            return 1;
        }
        override_dims.c = 1;
        override_ptr = &override_dims;
    }

    // ── Ensure output directory exists ──
    auto output_parent = fs::path(output_file).parent_path();
    if (!output_parent.empty())
        fs::create_directories(output_parent);

    // ── Run ──
    auto result = stps::run_single_warp(
        subject_image, target_markers, subject_markers,
        output_file, config, override_ptr);

    // ── Output JSON summary ──
    json summary = result_to_json(result);

    // Write JSON summary next to output file
    std::string json_path = output_file + ".summary.json";
    {
        std::ofstream jf(json_path);
        if (jf.is_open()) {
            jf << summary.dump(2) << "\n";
            LOG_INFO("Summary written to: %s", json_path.c_str());
        }
    }

    // Also print summary to stdout for Python subprocess capture
    std::cout << summary.dump(2) << std::endl;

    return result.success ? 0 : 1;
}
