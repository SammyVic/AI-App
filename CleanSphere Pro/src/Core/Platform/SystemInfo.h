#pragma once

/// @file SystemInfo.h
/// @brief System information queries — SSD detection, memory status, OS version.

#include "Win32Wrappers.h"
#include <string>
#include <cstdint>

namespace CleanSphere::Platform {

/// Storage device type (SSD vs HDD) for I/O optimization
enum class StorageType : uint8_t {
    Unknown = 0,
    HDD     = 1,  // Rotational — optimize for seek minimization
    SSD     = 2,  // Solid-state — optimize for sequential & large block I/O
    NVMe    = 3   // NVMe SSD — highest throughput
};

/// Memory pressure information
struct MemoryStatus {
    uint64_t totalPhysicalBytes     = 0;
    uint64_t availablePhysicalBytes = 0;
    uint64_t totalVirtualBytes      = 0;
    uint64_t availableVirtualBytes  = 0;
    uint64_t totalPageFileBytes     = 0;
    uint64_t availablePageFileBytes = 0;
    uint32_t memoryLoadPercent      = 0;  // 0–100
};

/// System information queries
class CS_API SystemInfo {
public:
    /// Detects the storage type for a given drive letter.
    /// Uses IOCTL_STORAGE_QUERY_PROPERTY (StorageDeviceProperty)
    /// to determine SSD vs HDD as specified in Section 5.1.
    [[nodiscard]] static StorageType GetStorageType(wchar_t driveLetter) noexcept;

    /// Gets current memory status using GlobalMemoryStatusEx.
    [[nodiscard]] static MemoryStatus GetMemoryStatus() noexcept;

    /// Gets the number of logical processor cores.
    [[nodiscard]] static uint32_t GetLogicalProcessorCount() noexcept;

    /// Gets the Windows build number (e.g., 22621 for Win11 22H2).
    [[nodiscard]] static uint32_t GetWindowsBuildNumber() noexcept;

    /// Gets the OS version string (e.g., "10.0.22621.3007").
    [[nodiscard]] static std::wstring GetOSVersionString();

    /// Gets the machine name.
    [[nodiscard]] static std::wstring GetComputerName();

    /// Checks if the current system is Windows 11 (build >= 22000).
    [[nodiscard]] static bool IsWindows11() noexcept;
};

} // namespace CleanSphere::Platform
