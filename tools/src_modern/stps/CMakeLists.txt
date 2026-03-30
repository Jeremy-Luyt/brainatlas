cmake_minimum_required(VERSION 3.16)
project(stps VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── Output directories ──────────────────────────────────────────────
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG   ${CMAKE_BINARY_DIR}/bin)

# ── Dependencies (system packages from msys2 ucrt64) ───────────────
find_package(Eigen3 REQUIRED)
find_package(CLI11 REQUIRED)
find_package(nlohmann_json REQUIRED)

# ── STPS library (static) ──────────────────────────────────────────
add_library(stps_lib STATIC
    src/io.cpp
    src/tps_solver.cpp
    src/warp_engine.cpp
    src/api.cpp
)
target_include_directories(stps_lib PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(stps_lib PUBLIC
    Eigen3::Eigen
    nlohmann_json::nlohmann_json
)
# Suppress Eigen deprecation warnings on MSVC
if(MSVC)
    target_compile_options(stps_lib PRIVATE /W3 /wd4996)
else()
    target_compile_options(stps_lib PRIVATE -Wall -Wextra -Wno-unused-parameter)
endif()

# ── STPS executable ────────────────────────────────────────────────
add_executable(stps src/main.cpp)
target_link_libraries(stps PRIVATE
    stps_lib
    CLI11::CLI11
    nlohmann_json::nlohmann_json
)
if(MSVC)
    target_compile_options(stps PRIVATE /W3 /wd4996)
endif()

# Print output path for user convenience
message(STATUS "STPS exe will be at: ${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/stps${CMAKE_EXECUTABLE_SUFFIX}")
