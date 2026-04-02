#pragma once

/// @file Registry.h
/// @brief Win32 Registry access abstraction layer.
/// 
/// All operations use Unicode (W) variants exclusively.
/// Uses RAII RegKeyGuard for handle management.

#include "Win32Wrappers.h"
#include <string>
#include <vector>
#include <variant>
#include <cstdint>

namespace CleanSphere::Platform {

/// Registry value data types
enum class RegValueType : uint32_t {
    String      = REG_SZ,
    ExpandString = REG_EXPAND_SZ,
    MultiString = REG_MULTI_SZ,
    DWord       = REG_DWORD,
    QWord       = REG_QWORD,
    Binary      = REG_BINARY,
    None        = REG_NONE
};

/// Represents a single registry value
struct RegValue {
    std::wstring    name;
    RegValueType    type = RegValueType::None;
    std::variant<
        std::wstring,           // REG_SZ, REG_EXPAND_SZ
        uint32_t,               // REG_DWORD
        uint64_t,               // REG_QWORD
        std::vector<uint8_t>,   // REG_BINARY
        std::vector<std::wstring> // REG_MULTI_SZ
    > data;
};

/// Access mode for registry operations
enum class RegAccess : uint32_t {
    Read    = KEY_READ,
    Write   = KEY_WRITE,
    All     = KEY_ALL_ACCESS,
    Read64  = KEY_READ | KEY_WOW64_64KEY,
    Read32  = KEY_READ | KEY_WOW64_32KEY,
    Write64 = KEY_WRITE | KEY_WOW64_64KEY
};

/// Registry operations wrapper. Always uses Unicode (W) variants.
/// Uses RegDeleteKeyExW (not RegDeleteKeyW) for 64-bit compatibility.
class CS_API Registry {
public:
    /// Opens a registry key for reading.
    /// @param rootKey     HKLM, HKCU, HKCR, etc.
    /// @param subKeyPath  Path under the root key
    /// @param access      Access mode (default: Read with 64-bit view)
    /// @return RAII registry key guard, or error message
    [[nodiscard]] static Win32Result<RegKeyGuard> OpenKey(
        HKEY rootKey,
        const std::wstring& subKeyPath,
        RegAccess access = RegAccess::Read64
    );

    /// Reads a string value from a registry key.
    [[nodiscard]] static Win32Result<std::wstring> ReadString(
        HKEY key, const std::wstring& valueName
    );

    /// Reads a DWORD value from a registry key.
    [[nodiscard]] static Win32Result<uint32_t> ReadDWord(
        HKEY key, const std::wstring& valueName
    );

    /// Enumerates all subkey names under a key.
    [[nodiscard]] static Win32Result<std::vector<std::wstring>> EnumSubKeys(
        HKEY key
    );

    /// Enumerates all values in a registry key.
    [[nodiscard]] static Win32Result<std::vector<RegValue>> EnumValues(
        HKEY key
    );

    /// Exports a key and all its subkeys to a .reg backup file.
    /// @param rootKey    Root key (HKLM, HKCU, etc.)
    /// @param subKeyPath Path to export
    /// @param outputPath Full path to the .reg file to write
    [[nodiscard]] static Win32Result<bool> ExportToRegFile(
        HKEY rootKey,
        const std::wstring& subKeyPath,
        const std::wstring& outputPath
    );

    /// Deletes a registry key using RegDeleteKeyExW (64-bit safe).
    /// @param rootKey    Root key
    /// @param subKeyPath Key to delete
    /// @param wow64View  KEY_WOW64_64KEY or KEY_WOW64_32KEY (default: 64-bit)
    [[nodiscard]] static Win32Result<bool> DeleteKeyEx(
        HKEY rootKey,
        const std::wstring& subKeyPath,
        REGSAM wow64View = KEY_WOW64_64KEY
    );

    /// Deletes a single value from a registry key.
    [[nodiscard]] static Win32Result<bool> DeleteValue(
        HKEY key,
        const std::wstring& valueName
    );

    /// Checks if a subkey path exists.
    [[nodiscard]] static bool KeyExists(
        HKEY rootKey,
        const std::wstring& subKeyPath
    ) noexcept;
};

} // namespace CleanSphere::Platform
