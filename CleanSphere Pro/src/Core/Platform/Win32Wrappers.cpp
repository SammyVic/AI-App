#include "Win32Wrappers.h"

// Win32Wrappers.cpp — Implementation file
// Note: Most Win32Wrappers functionality is header-only (inline/template).
// This file exists to ensure the DLL export symbols are generated.

namespace CleanSphere::Platform {

// Ensure DLL export linkage for non-template classes
// The implementations are in the header but the DLL export attribute
// requires at least one translation unit to instantiate the symbols.

} // namespace CleanSphere::Platform
