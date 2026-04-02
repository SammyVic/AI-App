#pragma once

/// @file FileSystem.h
/// @brief High-performance Win32 file system operations.
/// 
/// Uses FindFirstFileExW with FIND_FIRST_EX_LARGE_FETCH for bulk
/// NTFS directory enumeration. All functions use Unicode (W) variants
/// exclusively as required by Section 4.1.

#include "Win32Wrappers.h"
#include <string>
#include <vector>
#include <functional>
#include <chrono>
#include <atomic>
#include <cstdint>

namespace CleanSphere::Platform {

/// Metadata for a single file system entry discovered during enumeration
struct FileEntry {
    std::wstring    fullPath;
    uint64_t        sizeBytes       = 0;
    DWORD           attributes      = 0;
    std::chrono::system_clock::time_point lastAccessTime;
    std::chrono::system_clock::time_point lastWriteTime;
    std::chrono::system_clock::time_point creationTime;

    [[nodiscard]] bool IsDirectory() const noexcept {
        return (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
    }

    [[nodiscard]] bool IsSymlink() const noexcept {
        return (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
    }

    [[nodiscard]] bool IsHidden() const noexcept {
        return (attributes & FILE_ATTRIBUTE_HIDDEN) != 0;
    }

    [[nodiscard]] bool IsSystem() const noexcept {
        return (attributes & FILE_ATTRIBUTE_SYSTEM) != 0;
    }

    [[nodiscard]] bool IsReadOnly() const noexcept {
        return (attributes & FILE_ATTRIBUTE_READONLY) != 0;
    }
};

/// Callback for file enumeration. Return false to stop enumeration.
using FileEnumCallback = std::function<bool(const FileEntry& entry)>;

/// Options for directory enumeration
struct EnumOptions {
    bool recursive          = true;   ///< Recurse into subdirectories
    bool followSymlinks     = false;  ///< Follow reparse points (SECURITY: default false per spec)
    bool includeHidden      = true;   ///< Include hidden files
    bool includeSystem      = false;  ///< Include system files
    std::wstring pattern    = L"*";   ///< Filename glob pattern
};

/// High-performance file system utility class.
/// Uses FindFirstFileExW with FIND_FIRST_EX_LARGE_FETCH for
/// maximum NTFS throughput as specified in Section 5.1.
class CS_API FileSystem {
public:
    /// Converts a FILETIME to std::chrono::system_clock::time_point
    [[nodiscard]] static std::chrono::system_clock::time_point
    FileTimeToTimePoint(const FILETIME& ft) noexcept;

    /// Enumerates files and directories under rootPath.
    /// @param rootPath       Directory to enumerate (must exist)
    /// @param options        Enumeration options
    /// @param callback       Called for each discovered entry; return false to abort
    /// @param cancelToken    Set to true to abort enumeration
    /// @return               Number of entries enumerated, or error message
    [[nodiscard]] static Win32Result<uint64_t> EnumerateDirectory(
        const std::wstring& rootPath,
        const EnumOptions& options,
        const FileEnumCallback& callback,
        const std::atomic<bool>& cancelToken
    );

    /// Gets attributes and size for a single file.
    [[nodiscard]] static Win32Result<FileEntry> GetFileInfo(
        const std::wstring& filePath
    );

    /// Checks if a path exists on disk.
    [[nodiscard]] static bool PathExists(const std::wstring& path) noexcept;

    /// Checks if a file is currently locked by another process.
    [[nodiscard]] static bool IsFileLocked(const std::wstring& filePath) noexcept;

    /// Expands environment variables in a path (e.g., %TEMP% → C:\Users\...\Temp)
    [[nodiscard]] static Win32Result<std::wstring> ExpandPath(
        const std::wstring& pathWithEnvVars
    );

    /// Gets the total and free space for a drive.
    /// @param drivePath Root path (e.g., L"C:\\")
    /// @param totalBytes [out] Total drive capacity
    /// @param freeBytes  [out] Available free space
    [[nodiscard]] static bool GetDriveSpace(
        const std::wstring& drivePath,
        uint64_t& totalBytes,
        uint64_t& freeBytes
    ) noexcept;

    /// Gets the file system type for a volume (NTFS, ReFS, FAT32, etc.)
    [[nodiscard]] static Win32Result<std::wstring> GetFileSystemType(
        const std::wstring& drivePath
    );

    /// Lists all local fixed drives.
    [[nodiscard]] static std::vector<std::wstring> GetFixedDrives();

private:
    /// Internal recursive enumeration implementation
    static Win32Result<uint64_t> EnumerateDirectoryImpl(
        const std::wstring& dirPath,
        const EnumOptions& options,
        const FileEnumCallback& callback,
        const std::atomic<bool>& cancelToken,
        uint64_t& count
    );
};

} // namespace CleanSphere::Platform
