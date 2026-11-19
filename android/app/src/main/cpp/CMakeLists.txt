cmake_minimum_required(VERSION 3.22)
project(deli_android C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
include(FetchContent)
FetchContent_Declare(jpeg
    URL https://github.com/libjpeg-turbo/libjpeg-turbo/archive/refs/tags/3.0.4.tar.gz
    URL_HASH SHA256=0270f9496ad6d69e743f1e7b9e3e9398f5b4d606b6a47744df4b73df50f62e38)
FetchContent_GetProperties(jpeg)
if(NOT jpeg_POPULATED)
    FetchContent_Populate(jpeg)
endif()
include(ExternalProject)
set(JPEG_BUILD "${CMAKE_CURRENT_BINARY_DIR}/jpeg-build")
set(JPEG_ARGS -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON
    -DCMAKE_MAKE_PROGRAM=${CMAKE_MAKE_PROGRAM}
    -DENABLE_SHARED=OFF -DENABLE_STATIC=ON -DWITH_TURBOJPEG=OFF -DWITH_SIMD=OFF)
if(ANDROID)
    list(APPEND JPEG_ARGS -DCMAKE_TOOLCHAIN_FILE=${CMAKE_TOOLCHAIN_FILE}
        -DANDROID_ABI=${ANDROID_ABI} -DANDROID_PLATFORM=${ANDROID_PLATFORM}
        -DANDROID_STL=c++_static)
endif()
ExternalProject_Add(jpeg_build SOURCE_DIR "${jpeg_SOURCE_DIR}" BINARY_DIR "${JPEG_BUILD}"
    CMAKE_ARGS ${JPEG_ARGS}
    BUILD_COMMAND ${CMAKE_COMMAND} --build <BINARY_DIR> --target jpeg-static --config Release
    INSTALL_COMMAND "" BUILD_BYPRODUCTS "${JPEG_BUILD}/libjpeg.a")
add_library(jpeg_android STATIC IMPORTED)
set_target_properties(jpeg_android PROPERTIES IMPORTED_LOCATION "${JPEG_BUILD}/libjpeg.a")
get_filename_component(DELI_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../.." ABSOLUTE)
if(ANDROID)
    add_library(deli_android SHARED bridge.c ${DELI_ROOT}/src/page_plan.c ${DELI_ROOT}/src/resample.c)
    add_dependencies(deli_android jpeg_build)
    target_include_directories(deli_android PRIVATE ${DELI_ROOT}/src ${jpeg_SOURCE_DIR} ${JPEG_BUILD})
    target_compile_definitions(deli_android PRIVATE DELI_EMBEDDED _POSIX_C_SOURCE=200809L)
    target_compile_options(deli_android PRIVATE -Wall -Wextra -Werror)
    target_link_libraries(deli_android PRIVATE jpeg_android m)
else()
    add_executable(encoder_host ../../../../tests/encoder_host.c ${DELI_ROOT}/src/page_plan.c)
    add_dependencies(encoder_host jpeg_build)
    target_include_directories(encoder_host PRIVATE ${DELI_ROOT}/src ${jpeg_SOURCE_DIR} ${JPEG_BUILD})
    target_compile_definitions(encoder_host PRIVATE DELI_EMBEDDED _POSIX_C_SOURCE=200809L)
    target_link_libraries(encoder_host PRIVATE jpeg_android)
endif()
