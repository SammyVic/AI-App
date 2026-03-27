# Intelligent Dedup - Features List

1. **Intelligent Deduplication**: Find duplicate files using SHA-256, MD5, or Simple (Name+Size) algorithms.
2. **AI Retention Recommendations**: Use advanced ML and semantic matching to intelligently recommend which files to keep.
3. **Advanced Filtering**: Filter scans by specific file extensions and categories, minimum file sizes, and matching heuristics.
4. **Fuzzy Name Matching**: Detect duplicates even when filenames vary slightly through intelligent name comparisons.
5. **Interactive Results Table**: Review grouped duplicate results with preview capabilities, actionable checkboxes, and instant space recovery estimates.
6. **Detailed Run Summaries**: Access comprehensive scan metrics and recovery potential after each operation.
7. **Safe Delete Mechanism**: Remove duplicate files permanently or send them to the Recycle Bin safely.
8. **Export Capabilities**: Export scan results directly to CSV or export AI agent logic tracking to JSON.
9. **Lifetime Statistics Tracker**: Track cumulative space saved, files scanned, and overall deduplication metrics over time.
10. **Historical Sessions & Persistence**: Automatically load the most recent session on startup, persist checkbox/deletion states continuously across app restarts, and reload previous scan runs through the internal ACID-compliant SQLite datastore.
11. **Actionable UI Layout**: High-performance multi-pane interface supporting customizable light, dark, and grey themes.
