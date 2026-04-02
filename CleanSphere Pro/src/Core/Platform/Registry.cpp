#include "Registry.h"
#include <spdlog/spdlog.h>
#include <fstream>
#include <array>
#include <algorithm>

namespace CleanSphere::Platform {

Win32Result<RegKeyGuard> Registry::OpenKey(
    HKEY rootKey,
    const std::wstring& subKeyPath,
    RegAccess access)
{
    HKEY resultKey = nullptr;
    LSTATUS status = ::RegOpenKeyExW(
        rootKey, subKeyPath.c_str(), 0,
        static_cast<REGSAM>(access), &resultKey
    );

    if (status != ERROR_SUCCESS) {
        ::SetLastError(static_cast<DWORD>(status));
        return std::unexpected(
            std::format(L"Failed to open registry key '{}': error {}",
                        subKeyPath, status)
        );
    }

    return RegKeyGuard(resultKey);
}

Win32Result<std::wstring> Registry::ReadString(
    HKEY key, const std::wstring& valueName)
{
    // Query size first
    DWORD dataSize = 0;
    DWORD dataType = 0;
    LSTATUS status = ::RegQueryValueExW(
        key, valueName.c_str(), nullptr, &dataType, nullptr, &dataSize
    );

    if (status != ERROR_SUCCESS) {
        return std::unexpected(
            std::format(L"Failed to query registry value '{}': error {}",
                        valueName, status)
        );
    }

    if (dataType != REG_SZ && dataType != REG_EXPAND_SZ) {
        return std::unexpected(
            std::format(L"Registry value '{}' is not a string type (type={})",
                        valueName, dataType)
        );
    }

    // Read the value
    std::wstring result(dataSize / sizeof(wchar_t), L'\0');
    status = ::RegQueryValueExW(
        key, valueName.c_str(), nullptr, nullptr,
        reinterpret_cast<LPBYTE>(result.data()), &dataSize
    );

    if (status != ERROR_SUCCESS) {
        return std::unexpected(
            std::format(L"Failed to read registry value '{}': error {}",
                        valueName, status)
        );
    }

    // Remove trailing null characters
    while (!result.empty() && result.back() == L'\0') {
        result.pop_back();
    }

    return result;
}

Win32Result<uint32_t> Registry::ReadDWord(
    HKEY key, const std::wstring& valueName)
{
    DWORD data = 0;
    DWORD dataSize = sizeof(DWORD);
    DWORD dataType = 0;

    LSTATUS status = ::RegQueryValueExW(
        key, valueName.c_str(), nullptr, &dataType,
        reinterpret_cast<LPBYTE>(&data), &dataSize
    );

    if (status != ERROR_SUCCESS) {
        return std::unexpected(
            std::format(L"Failed to read DWORD value '{}': error {}",
                        valueName, status)
        );
    }

    if (dataType != REG_DWORD) {
        return std::unexpected(
            std::format(L"Registry value '{}' is not DWORD (type={})",
                        valueName, dataType)
        );
    }

    return data;
}

Win32Result<std::vector<std::wstring>> Registry::EnumSubKeys(HKEY key) {
    std::vector<std::wstring> subKeys;

    for (DWORD index = 0; ; ++index) {
        std::array<wchar_t, 256> keyName{};
        DWORD keyNameSize = static_cast<DWORD>(keyName.size());

        LSTATUS status = ::RegEnumKeyExW(
            key, index, keyName.data(), &keyNameSize,
            nullptr, nullptr, nullptr, nullptr
        );

        if (status == ERROR_NO_MORE_ITEMS) {
            break;
        }

        if (status != ERROR_SUCCESS) {
            return std::unexpected(
                std::format(L"RegEnumKeyExW failed at index {}: error {}",
                            index, status)
            );
        }

        subKeys.emplace_back(keyName.data(), keyNameSize);
    }

    return subKeys;
}

Win32Result<std::vector<RegValue>> Registry::EnumValues(HKEY key) {
    std::vector<RegValue> values;

    for (DWORD index = 0; ; ++index) {
        std::array<wchar_t, 16384> valueName{};
        DWORD valueNameSize = static_cast<DWORD>(valueName.size());
        DWORD dataType = 0;
        DWORD dataSize = 0;

        // First call to get type and size
        LSTATUS status = ::RegEnumValueW(
            key, index, valueName.data(), &valueNameSize,
            nullptr, &dataType, nullptr, &dataSize
        );

        if (status == ERROR_NO_MORE_ITEMS) {
            break;
        }

        if (status != ERROR_SUCCESS) {
            return std::unexpected(
                std::format(L"RegEnumValueW failed at index {}: error {}",
                            index, status)
            );
        }

        RegValue rv;
        rv.name = std::wstring(valueName.data(), valueNameSize);
        rv.type = static_cast<RegValueType>(dataType);

        // Read the actual data based on type
        if (dataType == REG_SZ || dataType == REG_EXPAND_SZ) {
            std::wstring strData(dataSize / sizeof(wchar_t), L'\0');
            valueNameSize = static_cast<DWORD>(valueName.size());
            status = ::RegEnumValueW(
                key, index, valueName.data(), &valueNameSize,
                nullptr, nullptr,
                reinterpret_cast<LPBYTE>(strData.data()), &dataSize
            );
            if (status == ERROR_SUCCESS) {
                while (!strData.empty() && strData.back() == L'\0') {
                    strData.pop_back();
                }
                rv.data = std::move(strData);
            }
        } else if (dataType == REG_DWORD) {
            uint32_t dwordData = 0;
            valueNameSize = static_cast<DWORD>(valueName.size());
            dataSize = sizeof(uint32_t);
            status = ::RegEnumValueW(
                key, index, valueName.data(), &valueNameSize,
                nullptr, nullptr,
                reinterpret_cast<LPBYTE>(&dwordData), &dataSize
            );
            if (status == ERROR_SUCCESS) {
                rv.data = dwordData;
            }
        } else if (dataType == REG_QWORD) {
            uint64_t qwordData = 0;
            valueNameSize = static_cast<DWORD>(valueName.size());
            dataSize = sizeof(uint64_t);
            status = ::RegEnumValueW(
                key, index, valueName.data(), &valueNameSize,
                nullptr, nullptr,
                reinterpret_cast<LPBYTE>(&qwordData), &dataSize
            );
            if (status == ERROR_SUCCESS) {
                rv.data = qwordData;
            }
        } else {
            // Binary or unknown — store as byte vector
            std::vector<uint8_t> binData(dataSize);
            valueNameSize = static_cast<DWORD>(valueName.size());
            status = ::RegEnumValueW(
                key, index, valueName.data(), &valueNameSize,
                nullptr, nullptr, binData.data(), &dataSize
            );
            if (status == ERROR_SUCCESS) {
                rv.data = std::move(binData);
            }
        }

        values.push_back(std::move(rv));
    }

    return values;
}

Win32Result<bool> Registry::ExportToRegFile(
    HKEY rootKey,
    const std::wstring& subKeyPath,
    const std::wstring& outputPath)
{
    // Use RegSaveKeyExW for backup (requires SE_BACKUP_NAME privilege)
    auto keyResult = OpenKey(rootKey, subKeyPath, RegAccess::Read64);
    if (!keyResult.has_value()) {
        return std::unexpected(keyResult.error());
    }

    // For .reg file export, we use reg.exe command as the most reliable method
    // Determine root key name
    std::wstring rootName;
    if (rootKey == HKEY_LOCAL_MACHINE) rootName = L"HKLM";
    else if (rootKey == HKEY_CURRENT_USER) rootName = L"HKCU";
    else if (rootKey == HKEY_CLASSES_ROOT) rootName = L"HKCR";
    else if (rootKey == HKEY_USERS) rootName = L"HKU";
    else {
        return std::unexpected(L"Unsupported root key for export");
    }

    std::wstring fullKeyPath = rootName + L"\\" + subKeyPath;

    // Build command: reg.exe export "KEY" "FILE" /y
    std::wstring cmd = std::format(
        L"reg.exe export \"{}\" \"{}\" /y", fullKeyPath, outputPath
    );

    STARTUPINFOW si{};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;

    PROCESS_INFORMATION pi{};
    BOOL created = ::CreateProcessW(
        nullptr, cmd.data(), nullptr, nullptr, FALSE,
        CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi
    );

    if (!created) {
        return std::unexpected(GetLastErrorMessage());
    }

    HandleGuard processHandle(pi.hProcess);
    HandleGuard threadHandle(pi.hThread);

    ::WaitForSingleObject(pi.hProcess, 30000); // 30 second timeout

    DWORD exitCode = 0;
    ::GetExitCodeProcess(pi.hProcess, &exitCode);

    if (exitCode != 0) {
        return std::unexpected(
            std::format(L"reg.exe export failed with exit code {}", exitCode)
        );
    }

    spdlog::info(L"Registry backup exported to: {}", outputPath);
    return true;
}

Win32Result<bool> Registry::DeleteKeyEx(
    HKEY rootKey,
    const std::wstring& subKeyPath,
    REGSAM wow64View)
{
    // Use RegDeleteKeyExW for 64-bit registry support (Section 5.3)
    LSTATUS status = ::RegDeleteKeyExW(rootKey, subKeyPath.c_str(), wow64View, 0);

    if (status != ERROR_SUCCESS) {
        return std::unexpected(
            std::format(L"Failed to delete registry key '{}': error {}",
                        subKeyPath, status)
        );
    }

    return true;
}

Win32Result<bool> Registry::DeleteValue(
    HKEY key, const std::wstring& valueName)
{
    LSTATUS status = ::RegDeleteValueW(key, valueName.c_str());
    if (status != ERROR_SUCCESS) {
        return std::unexpected(
            std::format(L"Failed to delete registry value '{}': error {}",
                        valueName, status)
        );
    }
    return true;
}

bool Registry::KeyExists(
    HKEY rootKey, const std::wstring& subKeyPath) noexcept
{
    HKEY resultKey = nullptr;
    LSTATUS status = ::RegOpenKeyExW(
        rootKey, subKeyPath.c_str(), 0,
        KEY_READ | KEY_WOW64_64KEY, &resultKey
    );

    if (status == ERROR_SUCCESS && resultKey) {
        ::RegCloseKey(resultKey);
        return true;
    }
    return false;
}

} // namespace CleanSphere::Platform
