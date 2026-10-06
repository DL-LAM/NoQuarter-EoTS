cmake_minimum_required(VERSION 3.16)

# [NQ EoTS - macOS]: build one universal binary for Intel and Apple Silicon Macs.
# Override with -DCMAKE_OSX_ARCHITECTURES=arm64 (or x86_64) for a single-arch build.
if(APPLE)
    if(NOT CMAKE_OSX_ARCHITECTURES)
        set(CMAKE_OSX_ARCHITECTURES "x86_64;arm64" CACHE STRING "macOS architectures")
    endif()
    if(NOT CMAKE_OSX_DEPLOYMENT_TARGET)
        set(CMAKE_OSX_DEPLOYMENT_TARGET "10.15" CACHE STRING "Minimum macOS version")
    endif()
endif()

project(NoQuarterWrapper)

# Forward directly to the src/ directory containing the full CMake build system
add_subdirectory(src)
