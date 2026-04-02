#pragma once

/// @file ErrorCodes.h
/// @brief CleanSphere Pro error code definitions (Section 10 of spec)

#include <cstdint>
#include <string>
#include <string_view>

namespace CleanSphere::Platform {

/// Error severity levels matching the documented code registry
enum class ErrorSeverity : uint8_t {
    Info     = 0,  // CS-I-xxxx — normal operational events
    Warning  = 1,  // CS-W-xxxx — non-critical issues
    Caution  = 2,  // CS-C-xxxx — user action required
    Error    = 3,  // CS-E-xxxx — operation failed
    Critical = 4   // CS-X-xxxx — unrecoverable failure
};

/// Prefixed error codes as defined in Section 10
namespace ErrorCode {
    // INFO
    constexpr std::wstring_view ScanCompleted         = L"CS-I-0001";
    constexpr std::wstring_view CleanupCompleted      = L"CS-I-0002";
    constexpr std::wstring_view ScheduledCleanupRan   = L"CS-I-0003";

    // WARNING
    constexpr std::wstring_view BrowserRunning        = L"CS-W-1001";
    constexpr std::wstring_view RegistrySkipped       = L"CS-W-1002";
    constexpr std::wstring_view FilesAccessDenied     = L"CS-W-1003";
    constexpr std::wstring_view SecureEraseSSDWarning = L"CS-W-1004";
    constexpr std::wstring_view PluginUnsigned        = L"CS-W-3001";

    // CAUTION
    constexpr std::wstring_view ConfirmDeletion       = L"CS-C-2001";
    constexpr std::wstring_view ConfirmRegistryClean  = L"CS-C-2002";
    constexpr std::wstring_view ConfirmUninstall      = L"CS-C-2003";

    // ERROR
    constexpr std::wstring_view DeleteFailed          = L"CS-E-2001";
    constexpr std::wstring_view RegistryBackupFailed  = L"CS-E-2002";
    constexpr std::wstring_view VSSFailed             = L"CS-E-2003";
    constexpr std::wstring_view SchedulerFailed       = L"CS-E-2004";
    constexpr std::wstring_view PluginLoadFailed      = L"CS-E-2005";
    constexpr std::wstring_view CloudSyncFailed       = L"CS-E-2006";

    // CRITICAL
    constexpr std::wstring_view EngineDllFailed       = L"CS-X-9001";
    constexpr std::wstring_view ServiceCrashed        = L"CS-X-9002";
}

} // namespace CleanSphere::Platform
