cmake_minimum_required(VERSION 3.28)
project(CleanSpherePro VERSION 2.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Windows SDK version
set(CMAKE_SYSTEM_VERSION 10.0.22621.0)

# MSVC specific flags
if(MSVC)
    add_compile_options(
        /W4         # Warning level 4
        /WX         # Warnings as errors
        /utf-8      # UTF-8 source and execution character sets
        /permissive- # Standards conformance mode
        /Zc:__cplusplus  # Report correct C++ standard version
    )

    # AddressSanitizer for Debug builds
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        add_compile_options(/fsanitize=address)
    endif()

    # Static analysis for Release builds
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        add_compile_options(/analyze)
    endif()
endif()

# Unicode is mandatory — never use ANSI variants
add_compile_definitions(
    UNICODE
    _UNICODE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    _CRT_SECURE_NO_WARNINGS
)

# Dependencies
include(FetchContent)

# xxHash for duplicate detection
FetchContent_Declare(
    xxHash
    GIT_REPOSITORY https://github.com/Cyan4973/xxHash.git
    GIT_TAG        v0.8.2
    SOURCE_SUBDIR  cmake_unofficial
)

# spdlog for structured logging
FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG        v1.13.0
)

# nlohmann/json for JSON serialization
FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
)

FetchContent_MakeAvailable(xxHash spdlog nlohmann_json)

# Testing
option(BUILD_TESTING "Build unit tests" ON)
if(BUILD_TESTING)
    enable_testing()
    FetchContent_Declare(
        googletest
        GIT_REPOSITORY https://github.com/google/googletest.git
        GIT_TAG        v1.14.0
    )
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googletest)
    include(GoogleTest)
endif()

# Core Engine library
add_subdirectory(src/Core)
