import sys
import os
import warnings
from setuptools import setup, Extension

# Try to import Cython
try:
    from Cython.Build import cythonize
    HAVE_CYTHON = True
except ImportError:
    HAVE_CYTHON = False
    warnings.warn(
        "Cython not found. Installing without optimized extensions. "
        "For better performance, install Cython and rebuild: "
        "pip install Cython && pip install --no-build-isolation -e .",
        UserWarning
    )


def build_extensions():
    """Build Cython extension modules."""
    if not HAVE_CYTHON:
        return []

    # Compiler flags
    extra_compile_args = []
    extra_link_args = []

    # TLS configuration
    # MG_TLS_BUILTIN enables built-in TLS (no external deps)
    use_tls = True  # Enable TLS support
    # NOTE: Mongoose's built-in TLS is event-loop based with no internal locks,
    # so nogil should be safe even with TLS enabled
    use_nogil = True  # Enable nogil for parallel execution

    if use_tls:
        define_macros = [
            ("MG_TLS", "MG_TLS_BUILTIN"),  # Enable built-in TLS support
            ("MG_ENABLE_PACKED_FS", "0"),  # Disable packed filesystem (not needed)
        ]
    else:
        define_macros = [
            ("MG_TLS", "MG_TLS_NONE"),     # Disable TLS
            ("MG_ENABLE_PACKED_FS", "0"),  # Disable packed filesystem (not needed)
        ]

    if sys.platform == "darwin":
        # macOS specific flags
        extra_compile_args.extend(["-O3", "-std=c99"])
    elif sys.platform == "linux":
        # Linux specific flags
        # _GNU_SOURCE enables POSIX extensions needed for clock_gettime, alloca, ip_mreq
        extra_compile_args.extend(["-O3", "-std=c99"])
        define_macros.append(("_GNU_SOURCE", "1"))
    elif sys.platform == "win32":
        # Windows specific flags
        extra_compile_args.extend(["/O2"])

    include_dirs = ["thirdparty/mongoose"]
    libraries = []

    if sys.platform == "win32":
        libraries.append("ws2_32")

    extensions = [
        Extension(
            "cymongoose._mongoose",
            sources=[
                "src/cymongoose/_mongoose.pyx",
                "thirdparty/mongoose/mongoose.c",
            ],
            include_dirs=include_dirs,
            define_macros=define_macros,
            extra_compile_args=extra_compile_args,
            extra_link_args=extra_link_args,
            libraries=libraries,
        ),
    ]

    # Cythonize with compiler directives
    return cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
            "embedsignature": True,
        },
        compile_time_env={
            "USE_NOGIL": use_nogil,
        },
        # Build in parallel if possible
        nthreads=os.cpu_count() or 1,
    )


# Only build extensions if Cython is available
ext_modules = build_extensions()

# Let setuptools handle the rest via pyproject.toml
setup(
    ext_modules=ext_modules,
    package_dir={"": "src"},
)
