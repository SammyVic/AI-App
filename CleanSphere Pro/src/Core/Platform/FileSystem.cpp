#include "FileSystem.h"
#include <spdlog/spdlog.h>
#include <algorithm>
#include <array>

namespace CleanSphere::Platform {

std::chrono::system_clock::time_point
FileSystem::FileTimeToTimePoint(const FILETIME& ft) noexcept {
    // FILETIME is 100-nanosecond intervals since 1601-01-01.
    // Convert to system_clock epoch (1970-01-01).
    constexpr int64_t EPOCH_OFFSET = 116444736000000000LL; // 100ns intervals
    ULARGE_INTEGER uli;
    uli.LowPart = ft.dwLowDateTime;
    uli.HighPart = ft.dwHighDateTime;
    int64_t ticks = static_cast<int64_t>(uli.QuadPart) - EPOCH_OFFSET;
    auto duration = std::chrono::duration<int64_t, std::ratio<1, 10000000>>(ticks);
    return std::chrono::system_clock::time_point(
        std::chrono::duration_cast<std::chrono::system_clock::duration>(duration)
    );
}

Win32Result<uint64_t> FileSystem::EnumerateDirectory(
    const std::wstring& rootPath,
    const EnumOptions& options,
    const FileEnumCallback& callback,
    const std::atomic<bool>& cancelToken)
{
    if (rootPath.empty()) {
        return std::unexpected(L"Root path cannot be empty");
    }

    uint64_t count = 0;
    return EnumerateDirectoryImpl(rootPath, options, callback, cancelToken, count);
}

Win32Result<uint64_t> FileSystem::EnumerateDirectoryImpl(
    const std::wstring& dirPath,
    const EnumOptions& options,
    const FileEnumCallback& callback,
    const std::atomic<bool>& cancelToken,
    uint64_t& count)
{
    if (cancelToken.load(std::memory_order_relaxed)) {
        return count; // Cancelled — return what we have
    }

    // Build search path: dir\pattern
    std::wstring searchPath = dirPath;
    if (searchPath.back() != L'\\') {
        searchPath += L'\\';
    }
    searchPath += options.pattern;

    WIN32_FIND_DATAW findData{};

    // Use FindFirstFileExW with FIND_FIRST_EX_LARGE_FETCH for
    // NTFS throughput optimization (Section 5.1)
    FindFileGuard findHandle(::FindFirstFileExW(
        searchPath.c_str(),
        FindExInfoBasic,       // Skip short names — faster
        &findData,
        FindExSearchNameMatch,
        nullptr,
        FIND_FIRST_EX_LARGE_FETCH  // Bulk fetch for NTFS performance
    ));

    if (!findHandle.IsValid()) {
        DWORD err = ::GetLastError();
        if (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND) {
            return count; // Empty directory or doesn't exist — not an error
        }
        if (err == ERROR_ACCESS_DENIED) {
            spdlog::warn(L"Access denied: {}", dirPath);
            return count; // Skip inaccessible directories
        }
        return std::unexpected(GetLastErrorMessage());
    }

    // Subdirectories to recurse into (collected to avoid interleaving)
    std::vector<std::wstring> subdirs;

    do {
        if (cancelToken.load(std::memory_order_relaxed)) {
            return count;
        }

        // Skip . and .. entries
        if (findData.cFileName[0] == L'.' &&
            (findData.cFileName[1] == L'\0' ||
             (findData.cFileName[1] == L'.' && findData.cFileName[2] == L'\0'))) {
            continue;
        }

        // Build full path
        std::wstring fullPath = dirPath;
        if (fullPath.back() != L'\\') {
            fullPath += L'\\';
        }
        fullPath += findData.cFileName;

        bool isDirectory = (findData.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        bool isSymlink = (findData.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;

        // SECURITY: Do not follow symlinks outside scope (Section 12.3)
        if (isSymlink && !options.followSymlinks) {
            if (isDirectory) {
                continue; // Skip symlink directories entirely
            }
            // For symlink files, we still report them but don't dereference
        }

        // Apply hidden/system filters
        if (!options.includeHidden && (findData.dwFileAttributes & FILE_ATTRIBUTE_HIDDEN)) {
            continue;
        }
        if (!options.includeSystem && (findData.dwFileAttributes & FILE_ATTRIBUTE_SYSTEM)) {
            continue;
        }

        // Build FileEntry
        FileEntry entry;
        entry.fullPath = std::move(fullPath);
        entry.attributes = findData.dwFileAttributes;

        if (!isDirectory) {
            ULARGE_INTEGER fileSize;
            fileSize.LowPart = findData.nFileSizeLow;
            fileSize.HighPart = findData.nFileSizeHigh;
            entry.sizeBytes = fileSize.QuadPart;
        }

        entry.lastAccessTime = FileTimeToTimePoint(findData.ftLastAccessTime);
        entry.lastWriteTime = FileTimeToTimePoint(findData.ftLastWriteTime);
        entry.creationTime = FileTimeToTimePoint(findData.ftCreationTime);

        // Invoke callback
        bool continueEnum = callback(entry);
        ++count;

        if (!continueEnum) {
            return count; // Callback requested stop
        }

        // Collect subdirectories for recursive traversal
        if (isDirectory && options.recursive && !isSymlink) {
            subdirs.push_back(entry.fullPath);
        }

    } while (::FindNextFileW(findHandle.Get(), &findData));

    // Check for actual errors (vs normal end of directory)
    DWORD lastError = ::GetLastError();
    if (lastError != ERROR_NO_MORE_FILES) {
        spdlog::warn(L"FindNextFileW error in {}: {}", dirPath, lastError);
    }

    // Recurse into subdirectories
    for (const auto& subdir : subdirs) {
        if (cancelToken.load(std::memory_order_relaxed)) {
            return count;
        }

        // Use wildcard pattern for recursive enumeration
        EnumOptions subOptions = options;
        subOptions.pattern = L"*";

        auto result = EnumerateDirectoryImpl(subdir, subOptions, callback, cancelToken, count);
        if (!result.has_value()) {
            // Log but don't fail entire enumeration for one bad subdirectory
            spdlog::warn(L"Skipping inaccessible subdirectory: {}", subdir);
        }
    }

    return count;
}

Win32Result<FileEntry> FileSystem::GetFileInfo(const std::wstring& filePath) {
    WIN32_FILE_ATTRIBUTE_DATA attrData{};
    if (!::GetFileAttributesExW(filePath.c_str(), GetFileExInfoStandard, &attrData)) {
        return std::unexpected(GetLastErrorMessage());
    }

    FileEntry entry;
    entry.fullPath = filePath;
    entry.attributes = attrData.dwFileAttributes;

    ULARGE_INTEGER fileSize;
    fileSize.LowPart = attrData.nFileSizeLow;
    fileSize.HighPart = attrData.nFileSizeHigh;
    entry.sizeBytes = fileSize.QuadPart;

    entry.lastAccessTime = FileTimeToTimePoint(attrData.ftLastAccessTime);
    entry.lastWriteTime = FileTimeToTimePoint(attrData.ftLastWriteTime);
    entry.creationTime = FileTimeToTimePoint(attrData.ftCreationTime);

    return entry;
}

bool FileSystem::PathExists(const std::wstring& path) noexcept {
    DWORD attrs = ::GetFileAttributesW(path.c_str());
    return attrs != INVALID_FILE_ATTRIBUTES;
}

bool FileSystem::IsFileLocked(const std::wstring& filePath) noexcept {
    HandleGuard handle(::CreateFileW(
        filePath.c_str(),
        GENERIC_READ | GENERIC_WRITE,
        0,  // No sharing — exclusive access attempt
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        nullptr
    ));

    if (!handle.IsValid()) {
        DWORD err = ::GetLastError();
        // These error codes indicate the file is locked
        return err == ERROR_SHARING_VIOLATION ||
               err == ERROR_LOCK_VIOLATION ||
               err == ERROR_ACCESS_DENIED;
    }

    return false; // File is not locked
}

Win32Result<std::wstring> FileSystem::ExpandPath(const std::wstring& pathWithEnvVars) {
    // First call to get required buffer size
    DWORD requiredSize = ::ExpandEnvironmentStringsW(pathWithEnvVars.c_str(), nullptr, 0);
    if (requiredSize == 0) {
        return std::unexpected(GetLastErrorMessage());
    }

    std::wstring expanded(requiredSize, L'\0');
    DWORD actualSize = ::ExpandEnvironmentStringsW(
        pathWithEnvVars.c_str(), expanded.data(), requiredSize
    );

    if (actualSize == 0) {
        return std::unexpected(GetLastErrorMessage());
    }

    // Remove trailing null
    expanded.resize(actualSize - 1);
    return expanded;
}

bool FileSystem::GetDriveSpace(
    const std::wstring& drivePath,
    uint64_t& totalBytes,
    uint64_t& freeBytes) noexcept
{
    ULARGE_INTEGER freeBytesAvailable, totalBytesOnDisk, totalFreeBytesOnDisk;

    BOOL result = ::GetDiskFreeSpaceExW(
        drivePath.c_str(),
        &freeBytesAvailable,
        &totalBytesOnDisk,
        &totalFreeBytesOnDisk
    );

    if (!result) {
        return false;
    }

    totalBytes = totalBytesOnDisk.QuadPart;
    freeBytes = freeBytesAvailable.QuadPart;
    return true;
}

Win32Result<std::wstring> FileSystem::GetFileSystemType(const std::wstring& drivePath) {
    std::array<wchar_t, MAX_PATH + 1> fsName{};
    std::array<wchar_t, MAX_PATH + 1> volumeName{};
    DWORD serialNumber = 0;
    DWORD maxComponentLen = 0;
    DWORD fsFlags = 0;

    BOOL result = ::GetVolumeInformationW(
        drivePath.c_str(),
        volumeName.data(), static_cast<DWORD>(volumeName.size()),
        &serialNumber,
        &maxComponentLen,
        &fsFlags,
        fsName.data(), static_cast<DWORD>(fsName.size())
    );

    if (!result) {
        return std::unexpected(GetLastErrorMessage());
    }

    return std::wstring(fsName.data());
}

std::vector<std::wstring> FileSystem::GetFixedDrives() {
    std::vector<std::wstring> drives;

    DWORD driveMask = ::GetLogicalDrives();
    if (driveMask == 0) {
        return drives;
    }

    for (int i = 0; i < 26; ++i) {
        if (driveMask & (1 << i)) {
            wchar_t driveLetter = static_cast<wchar_t>(L'A' + i);
            std::wstring drivePath = std::wstring(1, driveLetter) + L":\\";

            UINT driveType = ::GetDriveTypeW(drivePath.c_str());
            if (driveType == DRIVE_FIXED) {
                drives.push_back(std::move(drivePath));
            }
        }
    }

    return drives;
}

} // namespace CleanSphere::Platform
