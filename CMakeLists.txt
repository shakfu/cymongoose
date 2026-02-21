cmake_minimum_required(VERSION 3.15...3.31)
project(${SKBUILD_PROJECT_NAME} VERSION ${SKBUILD_PROJECT_VERSION} LANGUAGES C)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Vendored Mongoose C library version (thirdparty/mongoose/)
set(MONGOOSE_VERSION "7.19")

find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)

# Cythonize _mongoose.pyx -> _mongoose.c
add_custom_command(
    OUTPUT _mongoose.c
    COMMAND Python::Interpreter -m cython
        -X embedsignature=True
        "${CMAKE_CURRENT_SOURCE_DIR}/src/cymongoose/_mongoose.pyx"
        --output-file _mongoose.c
    DEPENDS
        "${CMAKE_CURRENT_SOURCE_DIR}/src/cymongoose/_mongoose.pyx"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/cymongoose/mongoose.pxd"
    COMMENT "Cythonizing _mongoose.pyx"
)

# Build the extension module
python_add_library(_mongoose MODULE
    _mongoose.c
    "${CMAKE_CURRENT_SOURCE_DIR}/thirdparty/mongoose/mongoose.c"
    WITH_SOABI
)

# Include directories (for mongoose.h)
target_include_directories(_mongoose PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/thirdparty/mongoose"
)

# Preprocessor defines
target_compile_definitions(_mongoose PRIVATE
    MG_TLS=MG_TLS_BUILTIN
    MG_ENABLE_PACKED_FS=0
)

# AddressSanitizer option
option(USE_ASAN "Build with AddressSanitizer" OFF)

# Platform-specific settings
if(MSVC)
    target_compile_options(_mongoose PRIVATE /O2 /W4)
    target_link_libraries(_mongoose PRIVATE ws2_32)
    if(USE_ASAN)
        target_compile_options(_mongoose PRIVATE /fsanitize=address)
    endif()
elseif(APPLE)
    target_compile_options(_mongoose PRIVATE -O3 -std=c99)
    if(USE_ASAN)
        target_compile_options(_mongoose PRIVATE -fsanitize=address -fno-omit-frame-pointer -g)
        target_link_options(_mongoose PRIVATE -fsanitize=address)
    endif()
else()
    # Linux
    target_compile_options(_mongoose PRIVATE -O3 -std=c99)
    target_compile_definitions(_mongoose PRIVATE _GNU_SOURCE=1)
    if(USE_ASAN)
        target_compile_options(_mongoose PRIVATE -fsanitize=address -fno-omit-frame-pointer -g)
        target_link_options(_mongoose PRIVATE -fsanitize=address)
    endif()
endif()

install(TARGETS _mongoose DESTINATION cymongoose)
