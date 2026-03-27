# Intelligent Dedup - Change Log

## [v2.1.0] - 2026-03-27
### Added
- Added "View Run Summary" button for quick review of deduplication stats.
- Added live elapsed timer in the status bar during active scans.
- Implemented space recoverable size calculations dynamically updating upon file selection.
- Added Feature list display option in the Help menu.
- Added automatic saving of completed scan results and metadata using SQLAlchemy ORM.
- Implemented auto-loading of the most recent prior session on application launch.
- Added tracking and persistence for user checkbox selections and file deletion states between runs and application restarts.

### Changed
- Improved group-level checkbox toggling in the results table; selecting a group heading selects all children.
- Implemented file category master checkbox syncing for streamlined extension filtering.

### Fixed
- Resolved menu overlap display issues for the "Load Previous Session" action.
- Resolved display artifacting by robustly clearing the UI viewing area upon initiating a fresh directory scan.

## [v2.0.0] - Initial Enterprise Release
### Added
- Semantic ML Matching.
- Custom AI Retention Recommendations dynamically evaluating historical patterns.
- Rust-based file system traversal for lightning speed metrics.
- ACID-compliant database for storing historical scans.
