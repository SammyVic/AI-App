#include "Privilege.h"
#include <spdlog/spdlog.h>
#include <ShlObj.h>
#include <sddl.h>
#include <algorithm>

#pragma comment(lib, "Advapi32.lib")
#pragma comment(lib, "Shell32.lib")

namespace CleanSphere::Platform {

bool Privilege::IsElevated() noexcept {
    HANDLE tokenHandle = nullptr;
    if (!::OpenProcessToken(::GetCurrentProcess(), TOKEN_QUERY, &tokenHandle)) {
        return false;
    }
    HandleGuard token(tokenHandle);

    TOKEN_ELEVATION elevation{};
    DWORD returnSize = 0;
    if (!::GetTokenInformation(token.Get(), TokenElevation, &elevation,
                                sizeof(elevation), &returnSize)) {
        return false;
    }

    return elevation.TokenIsElevated != 0;
}

bool Privilege::EnablePrivilege(const std::wstring& privilegeName) noexcept {
    return AdjustPrivilege(privilegeName, true);
}

bool Privilege::DisablePrivilege(const std::wstring& privilegeName) noexcept {
    return AdjustPrivilege(privilegeName, false);
}

bool Privilege::HasPrivilege(const std::wstring& privilegeName) noexcept {
    HANDLE tokenHandle = nullptr;
    if (!::OpenProcessToken(::GetCurrentProcess(), TOKEN_QUERY, &tokenHandle)) {
        return false;
    }
    HandleGuard token(tokenHandle);

    LUID luid{};
    if (!::LookupPrivilegeValueW(nullptr, privilegeName.c_str(), &luid)) {
        return false;
    }

    PRIVILEGE_SET privSet{};
    privSet.PrivilegeCount = 1;
    privSet.Control = PRIVILEGE_SET_ALL_NECESSARY;
    privSet.Privilege[0].Luid = luid;
    privSet.Privilege[0].Attributes = SE_PRIVILEGE_ENABLED;

    BOOL hasPriv = FALSE;
    if (!::PrivilegeCheck(token.Get(), &privSet, &hasPriv)) {
        return false;
    }

    return hasPriv != FALSE;
}

Win32Result<std::wstring> Privilege::GetCurrentUserSid() {
    HANDLE tokenHandle = nullptr;
    if (!::OpenProcessToken(::GetCurrentProcess(), TOKEN_QUERY, &tokenHandle)) {
        return std::unexpected(GetLastErrorMessage());
    }
    HandleGuard token(tokenHandle);

    // Get required buffer size
    DWORD tokenInfoSize = 0;
    ::GetTokenInformation(token.Get(), TokenUser, nullptr, 0, &tokenInfoSize);

    if (tokenInfoSize == 0) {
        return std::unexpected(L"Failed to get token information size");
    }

    auto tokenInfo = std::make_unique<uint8_t[]>(tokenInfoSize);
    if (!::GetTokenInformation(token.Get(), TokenUser, tokenInfo.get(),
                                tokenInfoSize, &tokenInfoSize)) {
        return std::unexpected(GetLastErrorMessage());
    }

    auto* tokenUser = reinterpret_cast<TOKEN_USER*>(tokenInfo.get());

    LPWSTR sidString = nullptr;
    if (!::ConvertSidToStringSidW(tokenUser->User.Sid, &sidString)) {
        return std::unexpected(GetLastErrorMessage());
    }

    std::wstring result(sidString);
    ::LocalFree(sidString);
    return result;
}

Win32Result<std::wstring> Privilege::GetAppDataPath() {
    PWSTR appDataPath = nullptr;
    HRESULT hr = ::SHGetKnownFolderPath(
        FOLDERID_RoamingAppData, 0, nullptr, &appDataPath
    );

    if (FAILED(hr) || !appDataPath) {
        return std::unexpected(L"Failed to get APPDATA path");
    }

    std::wstring result = std::wstring(appDataPath) + L"\\CleanSpherePro";
    ::CoTaskMemFree(appDataPath);

    // Ensure the directory exists
    ::CreateDirectoryW(result.c_str(), nullptr);

    return result;
}

bool Privilege::IsPathAllowed(
    const std::wstring& path,
    const std::vector<std::wstring>& allowedPrefixes) noexcept
{
    if (path.empty() || allowedPrefixes.empty()) {
        return false;
    }

    // Normalize path to lowercase for case-insensitive comparison
    std::wstring normalizedPath = path;
    std::transform(normalizedPath.begin(), normalizedPath.end(),
                   normalizedPath.begin(), ::towlower);

    for (const auto& prefix : allowedPrefixes) {
        std::wstring normalizedPrefix = prefix;
        std::transform(normalizedPrefix.begin(), normalizedPrefix.end(),
                       normalizedPrefix.begin(), ::towlower);

        if (normalizedPath.starts_with(normalizedPrefix)) {
            return true;
        }
    }

    spdlog::warn(L"Path rejected by whitelist: {}", path);
    return false;
}

bool Privilege::AdjustPrivilege(
    const std::wstring& privilegeName, bool enable) noexcept
{
    HANDLE tokenHandle = nullptr;
    if (!::OpenProcessToken(::GetCurrentProcess(),
                            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                            &tokenHandle)) {
        spdlog::error(L"Failed to open process token for privilege adjustment");
        return false;
    }
    HandleGuard token(tokenHandle);

    LUID luid{};
    if (!::LookupPrivilegeValueW(nullptr, privilegeName.c_str(), &luid)) {
        spdlog::error(L"Failed to lookup privilege: {}", privilegeName);
        return false;
    }

    TOKEN_PRIVILEGES tokenPriv{};
    tokenPriv.PrivilegeCount = 1;
    tokenPriv.Privileges[0].Luid = luid;
    tokenPriv.Privileges[0].Attributes = enable ? SE_PRIVILEGE_ENABLED : 0;

    if (!::AdjustTokenPrivileges(token.Get(), FALSE, &tokenPriv,
                                  sizeof(tokenPriv), nullptr, nullptr)) {
        spdlog::error(L"AdjustTokenPrivileges failed for: {}", privilegeName);
        return false;
    }

    // AdjustTokenPrivileges can succeed but not actually grant the privilege
    if (::GetLastError() == ERROR_NOT_ALL_ASSIGNED) {
        spdlog::warn(L"Privilege not all assigned: {}", privilegeName);
        return false;
    }

    spdlog::info(L"Privilege {} {}", privilegeName, enable ? L"enabled" : L"disabled");
    return true;
}

} // namespace CleanSphere::Platform
