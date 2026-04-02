#pragma once

/// @file Win32Wrappers.h
/// @brief RAII wrappers for Win32 handles and kernel objects.
/// 
/// All Win32 resource types are wrapped in unique_ptr-style RAII classes
/// to prevent resource leaks. Raw new/delete and malloc/free are prohibited
/// per Section 4.1 coding standards.

#include <Windows.h>
#include <memory>
#include <string>
#include <system_error>
#include <expected>
#include <format>

// DLL export/import macro
#ifdef CLEANSPHERE_CORE_EXPORTS
    #define CS_API __declspec(dllexport)
#else
    #define CS_API __declspec(dllimport)
#endif

namespace CleanSphere::Platform {

/// RAII wrapper for Win32 HANDLE (files, events, threads, etc.)
/// Automatically closes the handle on destruction.
class CS_API HandleGuard {
public:
    HandleGuard() noexcept = default;

    explicit HandleGuard(HANDLE handle) noexcept
        : m_handle(handle) {}

    ~HandleGuard() noexcept {
        Close();
    }

    // Move-only semantics
    HandleGuard(HandleGuard&& other) noexcept
        : m_handle(other.m_handle) {
        other.m_handle = INVALID_HANDLE_VALUE;
    }

    HandleGuard& operator=(HandleGuard&& other) noexcept {
        if (this != &other) {
            Close();
            m_handle = other.m_handle;
            other.m_handle = INVALID_HANDLE_VALUE;
        }
        return *this;
    }

    // Non-copyable
    HandleGuard(const HandleGuard&) = delete;
    HandleGuard& operator=(const HandleGuard&) = delete;

    [[nodiscard]] bool IsValid() const noexcept {
        return m_handle != INVALID_HANDLE_VALUE && m_handle != nullptr;
    }

    [[nodiscard]] HANDLE Get() const noexcept {
        return m_handle;
    }

    HANDLE Release() noexcept {
        HANDLE h = m_handle;
        m_handle = INVALID_HANDLE_VALUE;
        return h;
    }

    void Reset(HANDLE handle = INVALID_HANDLE_VALUE) noexcept {
        Close();
        m_handle = handle;
    }

    explicit operator bool() const noexcept {
        return IsValid();
    }

private:
    void Close() noexcept {
        if (IsValid()) {
            ::CloseHandle(m_handle);
            m_handle = INVALID_HANDLE_VALUE;
        }
    }

    HANDLE m_handle = INVALID_HANDLE_VALUE;
};

/// RAII wrapper for Win32 registry key handles (HKEY)
class CS_API RegKeyGuard {
public:
    RegKeyGuard() noexcept = default;

    explicit RegKeyGuard(HKEY key) noexcept
        : m_key(key) {}

    ~RegKeyGuard() noexcept {
        Close();
    }

    RegKeyGuard(RegKeyGuard&& other) noexcept
        : m_key(other.m_key) {
        other.m_key = nullptr;
    }

    RegKeyGuard& operator=(RegKeyGuard&& other) noexcept {
        if (this != &other) {
            Close();
            m_key = other.m_key;
            other.m_key = nullptr;
        }
        return *this;
    }

    RegKeyGuard(const RegKeyGuard&) = delete;
    RegKeyGuard& operator=(const RegKeyGuard&) = delete;

    [[nodiscard]] bool IsValid() const noexcept {
        return m_key != nullptr;
    }

    [[nodiscard]] HKEY Get() const noexcept {
        return m_key;
    }

    HKEY Release() noexcept {
        HKEY k = m_key;
        m_key = nullptr;
        return k;
    }

    void Reset(HKEY key = nullptr) noexcept {
        Close();
        m_key = key;
    }

    explicit operator bool() const noexcept {
        return IsValid();
    }

private:
    void Close() noexcept {
        if (IsValid()) {
            ::RegCloseKey(m_key);
            m_key = nullptr;
        }
    }

    HKEY m_key = nullptr;
};

/// RAII wrapper for FindFirstFileExW / FindClose
class CS_API FindFileGuard {
public:
    FindFileGuard() noexcept = default;

    explicit FindFileGuard(HANDLE findHandle) noexcept
        : m_handle(findHandle) {}

    ~FindFileGuard() noexcept {
        Close();
    }

    FindFileGuard(FindFileGuard&& other) noexcept
        : m_handle(other.m_handle) {
        other.m_handle = INVALID_HANDLE_VALUE;
    }

    FindFileGuard& operator=(FindFileGuard&& other) noexcept {
        if (this != &other) {
            Close();
            m_handle = other.m_handle;
            other.m_handle = INVALID_HANDLE_VALUE;
        }
        return *this;
    }

    FindFileGuard(const FindFileGuard&) = delete;
    FindFileGuard& operator=(const FindFileGuard&) = delete;

    [[nodiscard]] bool IsValid() const noexcept {
        return m_handle != INVALID_HANDLE_VALUE;
    }

    [[nodiscard]] HANDLE Get() const noexcept {
        return m_handle;
    }

    explicit operator bool() const noexcept {
        return IsValid();
    }

private:
    void Close() noexcept {
        if (IsValid()) {
            ::FindClose(m_handle);
            m_handle = INVALID_HANDLE_VALUE;
        }
    }

    HANDLE m_handle = INVALID_HANDLE_VALUE;
};

/// RAII wrapper for COM initialization (CoInitializeEx / CoUninitialize)
class CS_API ComInitGuard {
public:
    explicit ComInitGuard(DWORD coinitFlags = COINIT_MULTITHREADED) noexcept {
        m_hr = ::CoInitializeEx(nullptr, coinitFlags);
    }

    ~ComInitGuard() noexcept {
        if (SUCCEEDED(m_hr)) {
            ::CoUninitialize();
        }
    }

    ComInitGuard(const ComInitGuard&) = delete;
    ComInitGuard& operator=(const ComInitGuard&) = delete;
    ComInitGuard(ComInitGuard&&) = delete;
    ComInitGuard& operator=(ComInitGuard&&) = delete;

    [[nodiscard]] bool Succeeded() const noexcept {
        return SUCCEEDED(m_hr);
    }

    [[nodiscard]] HRESULT GetResult() const noexcept {
        return m_hr;
    }

private:
    HRESULT m_hr = E_FAIL;
};

/// RAII wrapper for memory-mapped files (CreateFileMappingW / MapViewOfFile)
class CS_API FileMappingGuard {
public:
    FileMappingGuard() noexcept = default;

    ~FileMappingGuard() noexcept {
        Unmap();
    }

    FileMappingGuard(FileMappingGuard&& other) noexcept
        : m_mapping(other.m_mapping)
        , m_view(other.m_view)
        , m_size(other.m_size) {
        other.m_mapping = nullptr;
        other.m_view = nullptr;
        other.m_size = 0;
    }

    FileMappingGuard& operator=(FileMappingGuard&& other) noexcept {
        if (this != &other) {
            Unmap();
            m_mapping = other.m_mapping;
            m_view = other.m_view;
            m_size = other.m_size;
            other.m_mapping = nullptr;
            other.m_view = nullptr;
            other.m_size = 0;
        }
        return *this;
    }

    FileMappingGuard(const FileMappingGuard&) = delete;
    FileMappingGuard& operator=(const FileMappingGuard&) = delete;

    /// Maps a file for read-only access.
    /// @param fileHandle Valid file handle opened with GENERIC_READ
    /// @param size Number of bytes to map (0 = entire file)
    /// @return true on success
    [[nodiscard]] bool MapReadOnly(HANDLE fileHandle, uint64_t size = 0) noexcept {
        Unmap();

        LARGE_INTEGER liSize;
        liSize.QuadPart = static_cast<LONGLONG>(size);

        m_mapping = ::CreateFileMappingW(
            fileHandle, nullptr, PAGE_READONLY,
            liSize.HighPart, liSize.LowPart, nullptr
        );
        if (!m_mapping) return false;

        m_view = ::MapViewOfFile(m_mapping, FILE_MAP_READ, 0, 0, static_cast<SIZE_T>(size));
        if (!m_view) {
            ::CloseHandle(m_mapping);
            m_mapping = nullptr;
            return false;
        }

        m_size = size;
        return true;
    }

    [[nodiscard]] const void* Data() const noexcept { return m_view; }
    [[nodiscard]] uint64_t Size() const noexcept { return m_size; }
    [[nodiscard]] bool IsValid() const noexcept { return m_view != nullptr; }

private:
    void Unmap() noexcept {
        if (m_view) {
            ::UnmapViewOfFile(m_view);
            m_view = nullptr;
        }
        if (m_mapping) {
            ::CloseHandle(m_mapping);
            m_mapping = nullptr;
        }
        m_size = 0;
    }

    HANDLE m_mapping = nullptr;
    void*  m_view    = nullptr;
    uint64_t m_size  = 0;
};

/// Result type for Win32 operations. Uses std::expected (C++23) for
/// non-throwing error propagation.
/// @tparam T Success value type
template<typename T>
using Win32Result = std::expected<T, std::wstring>;

/// Captures the last Win32 error as a formatted wstring.
/// @return Formatted error message including the error code
[[nodiscard]] inline std::wstring GetLastErrorMessage() {
    DWORD errorCode = ::GetLastError();
    if (errorCode == 0) {
        return L"Success";
    }

    LPWSTR messageBuffer = nullptr;
    DWORD size = ::FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        nullptr, errorCode, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        reinterpret_cast<LPWSTR>(&messageBuffer), 0, nullptr
    );

    std::wstring message;
    if (size > 0 && messageBuffer) {
        message = std::format(L"Win32 Error {}: {}", errorCode,
                              std::wstring_view(messageBuffer, size));
        // Trim trailing newline
        while (!message.empty() && (message.back() == L'\n' || message.back() == L'\r')) {
            message.pop_back();
        }
    } else {
        message = std::format(L"Win32 Error {}: (unknown)", errorCode);
    }

    if (messageBuffer) {
        ::LocalFree(messageBuffer);
    }
    return message;
}

} // namespace CleanSphere::Platform
