# Core Engine library (CleanSphereCore.dll)
# Layers 1 (Platform Abstraction) + 2 (Core Engine)

set(CORE_SOURCES
    # Platform Abstraction Layer (Layer 1)
    Platform/Win32Wrappers.cpp
    Platform/FileSystem.cpp
    Platform/Registry.cpp
    Platform/Privilege.cpp
    Platform/SystemInfo.cpp

    # Scan Engine
    Engine/Scan/ScanEngine.cpp
    Engine/Scan/FileEnumerator.cpp
    Engine/Scan/CategoryDetector.cpp
    Engine/Scan/CategoryDefinitions.cpp

    # Deletion Engine
    Engine/Delete/DeletionEngine.cpp
    Engine/Delete/SecureEraseEngine.cpp
    Engine/Delete/RollbackManager.cpp

    # Registry Engine
    Engine/Registry/RegistryScanner.cpp
    Engine/Registry/RegistryCleaner.cpp
    Engine/Registry/RegistryBackup.cpp

    # Duplicate Detection
    Engine/Duplicate/DuplicateDetector.cpp
    Engine/Duplicate/HashEngine.cpp

    # Startup Manager
    Engine/Startup/StartupManager.cpp

    # Browser Cleanup
    Engine/Browser/BrowserProfileLocator.cpp
    Engine/Browser/BrowserCacheCleaner.cpp

    # Disk Analyzer
    Engine/Disk/DiskAnalyzer.cpp

    # Memory Optimizer
    Engine/Memory/MemoryOptimizer.cpp
)

set(CORE_HEADERS
    # Platform Abstraction Layer
    Platform/Win32Wrappers.h
    Platform/FileSystem.h
    Platform/Registry.h
    Platform/Privilege.h
    Platform/SystemInfo.h
    Platform/ErrorCodes.h

    # Scan Engine
    Engine/Scan/ScanResult.h
    Engine/Scan/ScanEngine.h
    Engine/Scan/FileEnumerator.h
    Engine/Scan/CategoryDetector.h
    Engine/Scan/CategoryDefinitions.h

    # Deletion Engine
    Engine/Delete/DeletionEngine.h
    Engine/Delete/SecureEraseEngine.h
    Engine/Delete/RollbackManager.h
    Engine/Delete/DeletionResult.h

    # Registry Engine
    Engine/Registry/RegistryScanner.h
    Engine/Registry/RegistryCleaner.h
    Engine/Registry/RegistryBackup.h
    Engine/Registry/RegistryEntry.h

    # Duplicate Detection
    Engine/Duplicate/DuplicateDetector.h
    Engine/Duplicate/HashEngine.h
    Engine/Duplicate/DuplicateGroup.h

    # Startup Manager
    Engine/Startup/StartupManager.h
    Engine/Startup/StartupEntry.h

    # Browser Cleanup
    Engine/Browser/BrowserProfileLocator.h
    Engine/Browser/BrowserCacheCleaner.h
    Engine/Browser/BrowserProfile.h

    # Disk Analyzer
    Engine/Disk/DiskAnalyzer.h
    Engine/Disk/DiskNode.h

    # Memory Optimizer
    Engine/Memory/MemoryOptimizer.h
    Engine/Memory/MemoryInfo.h
)

add_library(CleanSphereCore SHARED ${CORE_SOURCES} ${CORE_HEADERS})

target_include_directories(CleanSphereCore
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/Platform
)

target_link_libraries(CleanSphereCore
    PRIVATE
        spdlog::spdlog
        nlohmann_json::nlohmann_json
        xxHash::xxhash
        # Windows SDK libraries
        Shlwapi
        Shell32
        Ole32
        OleAut32
        Advapi32
        Bcrypt
        Wbemuuid
        Taskschd
        Comsupp
)

target_compile_definitions(CleanSphereCore
    PRIVATE
        CLEANSPHERE_CORE_EXPORTS
        _SILENCE_CXX17_CODECVT_HEADER_DEPRECATION_WARNING
)

# Export macro for DLL
target_compile_definitions(CleanSphereCore
    PUBLIC
        $<$<BOOL:${BUILD_SHARED_LIBS}>:CLEANSPHERE_CORE_IMPORTS>
)

# Tests
if(BUILD_TESTING)
    add_subdirectory(Engine/Scan/tests)
    add_subdirectory(Engine/Delete/tests)
    add_subdirectory(Engine/Duplicate/tests)
    add_subdirectory(Engine/Registry/tests)
endif()
