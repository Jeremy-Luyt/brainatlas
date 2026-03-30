// io.cpp — v3draw I/O and marker file parsing
// Replaces stackutil.cpp loadImage/saveImage + basic_surf_objs.cpp readMarker_file
//
// v3draw format:
//   4 bytes: magic "raw_image_stack_by_hpeng"  (actually: "raw_image_stack_by_hpeng\0" = 24 bytes)
//   Actually the format is simpler for recent V3D:
//     - Format key: first 24 bytes = "raw_image_stack_by_hpeng"
//     - 1 byte: endianness ('L' or 'B')
//     - 2 bytes: data type size (1=uint8, 2=uint16, 4=float32)
//     - 4*4=16 bytes: dimensions as uint32 (w, h, d, c)   [if type size in header says so]
//   Followed by raw pixel data.
//
// For simplicity and correctness, we implement the format exactly as V3D does it.

#include "stps/io.hpp"
#include "stps/logger.hpp"
#include <fstream>
#include <sstream>
#include <cstring>
#include <algorithm>
#include <filesystem>

namespace fs = std::filesystem;

namespace stps { namespace io {

// ── v3draw format constants ──
static const char V3DRAW_MAGIC[] = "raw_image_stack_by_hpeng";
static constexpr size_t MAGIC_LEN = 24;

bool load_v3draw(const std::string& path,
                 std::vector<uint8_t>& data,
                 ImageDims& dims) {
    std::ifstream fin(path, std::ios::binary);
    if (!fin.is_open()) {
        LOG_ERROR("Cannot open file: %s", path.c_str());
        return false;
    }

    // Read magic
    char magic[MAGIC_LEN + 1] = {};
    fin.read(magic, MAGIC_LEN);
    if (std::strncmp(magic, V3DRAW_MAGIC, MAGIC_LEN) != 0) {
        LOG_ERROR("Not a valid v3draw file (bad magic): %s", path.c_str());
        return false;
    }

    // Endianness byte
    char endian;
    fin.read(&endian, 1);
    // We assume little-endian ('L') throughout — Windows is LE.

    // Data type size (bytes per voxel)
    uint16_t dtype_size = 0;
    fin.read(reinterpret_cast<char*>(&dtype_size), 2);

    // Dimensions
    if (dtype_size <= 2) {
        // Standard 32-bit dimension header
        uint32_t sz[4];
        fin.read(reinterpret_cast<char*>(sz), 4 * sizeof(uint32_t));
        dims.w = sz[0]; dims.h = sz[1]; dims.d = sz[2]; dims.c = sz[3];
    } else {
        // 64-bit dimension header (raw5d or v3draw with large dims)
        uint32_t sz[4];
        fin.read(reinterpret_cast<char*>(sz), 4 * sizeof(uint32_t));
        dims.w = sz[0]; dims.h = sz[1]; dims.d = sz[2]; dims.c = sz[3];
    }

    if (dims.w <= 0 || dims.h <= 0 || dims.d <= 0 || dims.c <= 0) {
        LOG_ERROR("Invalid dimensions in v3draw: %lld x %lld x %lld x %lld",
                  (long long)dims.w, (long long)dims.h, (long long)dims.d, (long long)dims.c);
        return false;
    }

    int64_t total = dims.total();
    int64_t total_bytes = total * dtype_size;
    LOG_INFO("Loading v3draw: %lldx%lldx%lldx%lld, dtype_size=%u, total_bytes=%lld",
             (long long)dims.w, (long long)dims.h, (long long)dims.d,
             (long long)dims.c, (unsigned)dtype_size, (long long)total_bytes);

    // Read raw data
    if (dtype_size == 1) {
        data.resize(static_cast<size_t>(total));
        fin.read(reinterpret_cast<char*>(data.data()), total);
    } else if (dtype_size == 2) {
        // Convert uint16 to uint8 (scale by >> 8) — same as original stackutil behavior
        std::vector<uint16_t> buf16(static_cast<size_t>(total));
        fin.read(reinterpret_cast<char*>(buf16.data()), total * 2);
        data.resize(static_cast<size_t>(total));
        for (size_t i = 0; i < data.size(); i++)
            data[i] = static_cast<uint8_t>(buf16[i] >> 8);
    } else {
        LOG_ERROR("Unsupported v3draw dtype_size: %u", (unsigned)dtype_size);
        return false;
    }

    if (!fin.good() && !fin.eof()) {
        LOG_WARN("Read may be incomplete for: %s", path.c_str());
    }
    return true;
}

bool save_v3draw(const std::string& path,
                 const uint8_t* data,
                 const ImageDims& dims) {
    // Ensure parent directory exists
    auto parent = fs::path(path).parent_path();
    if (!parent.empty())
        fs::create_directories(parent);

    std::ofstream fout(path, std::ios::binary);
    if (!fout.is_open()) {
        LOG_ERROR("Cannot create output file: %s", path.c_str());
        return false;
    }

    // Magic
    fout.write(V3DRAW_MAGIC, MAGIC_LEN);

    // Endianness
    char endian = 'L';
    fout.write(&endian, 1);

    // Data type size (uint8)
    uint16_t dtype_size = 1;
    fout.write(reinterpret_cast<const char*>(&dtype_size), 2);

    // Dimensions
    uint32_t sz[4] = {
        static_cast<uint32_t>(dims.w),
        static_cast<uint32_t>(dims.h),
        static_cast<uint32_t>(dims.d),
        static_cast<uint32_t>(dims.c)
    };
    fout.write(reinterpret_cast<const char*>(sz), 4 * sizeof(uint32_t));

    // Pixel data
    int64_t total = dims.total();
    fout.write(reinterpret_cast<const char*>(data), total);
    fout.close();

    LOG_INFO("Saved v3draw: %s (%lldx%lldx%lldx%lld)",
             path.c_str(), (long long)dims.w, (long long)dims.h,
             (long long)dims.d, (long long)dims.c);
    return true;
}

std::vector<Marker> read_markers(const std::string& path) {
    std::vector<Marker> markers;
    std::ifstream fin(path);
    if (!fin.is_open()) {
        LOG_ERROR("Cannot open marker file: %s", path.c_str());
        return markers;
    }

    std::string line;
    while (std::getline(fin, line)) {
        // Trim leading spaces
        size_t start = line.find_first_not_of(" \t\r\n");
        if (start == std::string::npos) continue;
        line = line.substr(start);

        // Skip comments and header lines
        if (line.empty() || line[0] == '#' || line[0] == 'x' || line[0] == 'X')
            continue;

        // Parse CSV: x, y, z [, radius, shape, name, comment, ...]
        std::istringstream iss(line);
        std::string token;
        std::vector<std::string> fields;
        while (std::getline(iss, token, ',')) {
            // Trim whitespace
            size_t s = token.find_first_not_of(" \t");
            size_t e = token.find_last_not_of(" \t\r\n");
            if (s != std::string::npos && e != std::string::npos)
                fields.push_back(token.substr(s, e - s + 1));
            else
                fields.push_back("");
        }

        if (fields.size() < 3) continue;

        Marker m;
        m.x = std::stod(fields[0]);
        m.y = std::stod(fields[1]);
        m.z = std::stod(fields[2]);
        if (fields.size() >= 4) m.radius = std::stoi(fields[3]);
        if (fields.size() >= 5) m.shape = std::stoi(fields[4]);
        if (fields.size() >= 6) m.name = fields[5];
        if (fields.size() >= 7) m.comment = fields[6];

        markers.push_back(m);
    }

    LOG_INFO("Read %zu markers from %s", markers.size(), path.c_str());
    return markers;
}

bool write_markers_txt(const std::string& path,
                       const std::vector<Marker>& markers) {
    auto parent = fs::path(path).parent_path();
    if (!parent.empty())
        fs::create_directories(parent);

    std::ofstream fout(path);
    if (!fout.is_open()) {
        LOG_ERROR("Cannot create marker file: %s", path.c_str());
        return false;
    }

    fout << "##x,y,z,radius,shape,name,comment\n";
    for (const auto& m : markers) {
        fout << m.x << ", " << m.y << ", " << m.z
             << ", " << m.radius << ", " << m.shape
             << ", " << m.name << ", " << m.comment << "\n";
    }
    return true;
}

}} // namespace stps::io
