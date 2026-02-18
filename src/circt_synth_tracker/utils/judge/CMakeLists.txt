cmake_minimum_required(VERSION 3.20)
project(aig-judge CXX)

# Set default build type to RelWithDebInfo if not specified
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING
        "Choose the type of build: Debug Release RelWithDebInfo MinSizeRel" FORCE)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Add compile options
add_compile_options(-Wall -Wextra)

# Use FetchContent for dependencies
include(FetchContent)

# Fetch mockturtle
FetchContent_Declare(
    mockturtle
    GIT_REPOSITORY https://github.com/lsils/mockturtle.git
    GIT_TAG master
    PATCH_COMMAND git apply --ignore-whitespace ${CMAKE_CURRENT_SOURCE_DIR}/patches/pr683-fix-emap.patch || true
)

FetchContent_GetProperties(mockturtle)
if(NOT mockturtle_POPULATED)
    FetchContent_Populate(mockturtle)
    # mockturtle is header-only, just use the include directory
endif()

set(MOCKTURTLE_INCLUDE_DIR ${mockturtle_SOURCE_DIR}/include)

# Fetch and build fmt library
FetchContent_Declare(
    fmt
    GIT_REPOSITORY https://github.com/fmtlib/fmt.git
    GIT_TAG 10.2.1
)
FetchContent_MakeAvailable(fmt)

# Generate embedded genlib header from multioutput.genlib
set(GENLIB_SOURCE "${mockturtle_SOURCE_DIR}/experiments/cell_libraries/multioutput.genlib")
set(GENLIB_HEADER "${CMAKE_CURRENT_BINARY_DIR}/embedded_genlib.h")

add_custom_command(
    OUTPUT ${GENLIB_HEADER}
    COMMAND ${CMAKE_COMMAND} 
        -DINPUT_FILE=${GENLIB_SOURCE}
        -DOUTPUT_FILE=${GENLIB_HEADER}
        -DVARIABLE_NAME=EMBEDDED_GENLIB
        -P ${CMAKE_CURRENT_SOURCE_DIR}/embed_genlib.cmake
    DEPENDS ${GENLIB_SOURCE} ${CMAKE_CURRENT_SOURCE_DIR}/embed_genlib.cmake
    COMMENT "Generating embedded genlib header"
    VERBATIM
)

# Generate embedded Sky130 genlib header
set(SKY130_GENLIB_SOURCE "${mockturtle_SOURCE_DIR}/experiments/cell_libraries/sky130.genlib")
set(SKY130_GENLIB_HEADER "${CMAKE_CURRENT_BINARY_DIR}/embedded_sky130_genlib.h")

add_custom_command(
    OUTPUT ${SKY130_GENLIB_HEADER}
    COMMAND ${CMAKE_COMMAND} 
        -DINPUT_FILE=${SKY130_GENLIB_SOURCE}
        -DOUTPUT_FILE=${SKY130_GENLIB_HEADER}
        -DVARIABLE_NAME=EMBEDDED_SKY130_GENLIB
        -P ${CMAKE_CURRENT_SOURCE_DIR}/embed_genlib.cmake
    DEPENDS ${SKY130_GENLIB_SOURCE} ${CMAKE_CURRENT_SOURCE_DIR}/embed_genlib.cmake
    COMMENT "Generating embedded Sky130 genlib header"
    VERBATIM
)

# Add custom target to ensure headers are generated
add_custom_target(generate_genlib_headers DEPENDS ${GENLIB_HEADER} ${SKY130_GENLIB_HEADER})

# Add executable
add_executable(aig-judge
    src/main.cpp
    ${GENLIB_HEADER}
    ${SKY130_GENLIB_HEADER}
)

# Ensure the headers are generated before building
add_dependencies(aig-judge generate_genlib_headers)

# Disable Nauty
target_compile_definitions(aig-judge PRIVATE DISABLE_NAUTY)

# Include directories
target_include_directories(aig-judge PRIVATE
    ${MOCKTURTLE_INCLUDE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_BINARY_DIR}  # For generated embedded_genlib.h
    ${mockturtle_SOURCE_DIR}/lib/kitty
    ${mockturtle_SOURCE_DIR}/lib/lorina
    ${mockturtle_SOURCE_DIR}/lib/parallel_hashmap
    ${mockturtle_SOURCE_DIR}/experiments
)

# Link libraries
target_link_libraries(aig-judge PRIVATE fmt::fmt)

# Installation
install(TARGETS aig-judge
    RUNTIME DESTINATION bin
)
