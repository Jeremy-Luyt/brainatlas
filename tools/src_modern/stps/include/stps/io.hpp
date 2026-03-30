// io.hpp — File I/O for v3draw images and marker files
#pragma once

#include "stps/types.hpp"
#include <string>
#include <vector>

namespace stps { namespace io {

// Load a v3draw format image from disk.
// Returns true on success; fills data, dims.
bool load_v3draw(const std::string& path,
                 std::vector<uint8_t>& data,
                 ImageDims& dims);

// Save image data in v3draw format.
bool save_v3draw(const std::string& path,
                 const uint8_t* data,
                 const ImageDims& dims);

// Read .marker file (V3D format: x,y,z,radius,shape,name,comment,...)
// Lines starting with '#' or 'x'/'X' are skipped.
std::vector<Marker> read_markers(const std::string& path);

// Write markers to a simple CSV text file (x, y, z per line).
bool write_markers_txt(const std::string& path,
                       const std::vector<Marker>& markers);

}} // namespace stps::io
