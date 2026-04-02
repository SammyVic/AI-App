#pragma once

/// @file Privilege.h
/// @brief Windows privilege and token management.
/// 
/// Handles UAC detection, privilege elevation, and token manipulation
/// required for system-space cleanup operations (Section 11.1).

#include "Win32Wrappers.h"
#include <string>
#include <vector>

namespace CleanSphere::Platform {

/// Privilege management for Windows token operations
class CS_API Privilege {
public:
    /// Checks if the current process is running with administrator privileges.
    [[nodiscard]] static bool IsElevated() noexcept;

    /// Enables a specific privilege on the current process token.
    /// @param privilegeName Win32 privilege constant (e.g., SE_PROFILE_SINGLE_PROCESS_NAME)
    /// @return true if the privilege was successfully enabled
    [[nodiscard]] static bool EnablePrivilege(const std::wstring& privilegeName) noexcept;

    /// Disables a specific privilege on the current process token.
    [[nodiscard]] static bool DisablePrivilege(const std::wstring& privilegeName) noexcept;

    /// Checks if the current token has a specific privilege.
    [[nodiscard]] static bool HasPrivilege(const std::wstring& privilegeName) noexcept;

    /// Gets the SID string for the current user.
    [[nodiscard]] static Win32Result<std::wstring> GetCurrentUserSid();

    /// Gets the current user's %APPDATA% path for CleanSphere data.
    [[nodiscard]] static Win32Result<std::wstring> GetAppDataPath();

    /// Validates that a path starts with an allowed prefix.
    /// Used by the elevated helper to restrict deletion scope (Section 11.1).
    [[nodiscard]] static bool IsPathAllowed(
        const std::wstring& path,
        const std::vector<std::wstring>& allowedPrefixes
    ) noexcept;

private:
    /// Internal: adjusts a single privilege on the current token.
    [[nodiscard]] static bool AdjustPrivilege(
        const std::wstring& privilegeName, bool enable
    ) noexcept;
};

} // namespace CleanSphere::Platform
