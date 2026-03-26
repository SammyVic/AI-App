# Architecture Overview — Intelligent Dedup v2.0

## Layer Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                       │
│   app/views/main_window.py    app/views/agent_panel.py      │
│   app/views/dialogs/          app/views/theme_manager.py    │
│                 (PyQt6 — zero business logic)               │
└────────────────────────┬────────────────────────────────────┘
                         │ binds to
┌────────────────────────▼────────────────────────────────────┐
│                    VIEWMODEL LAYER                          │
│   ScanViewModel    DuplicateTableModel    StatsViewModel     │
│   (QObject / QAbstractTableModel — owns signals & state)    │
└────────────────────────┬────────────────────────────────────┘
                         │ calls
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌────────────── ┐ ┌──────────────┐ ┌───────────────────────┐
│ DOMAIN ENGINE │ │  DATA LAYER  │ │    AGENT LAYER        │
│  scanner.py   │ │ database.py  │ │ retention_agent.py    │
│  hasher.py    │ │ repository.py│ │ reasoning_engine.py   │
│  deduplicator │ │ (SQLAlchemy) │ │ (transparent scoring) │
└──────┬────────┘ └──────────────┘ └───────────────────────┘
       │ calls                              │ calls
┌──────▼────────────────────┐  ┌──────────▼──────────────────┐
│  PERFORMANCE CORE (Rust)  │  │  ML PIPELINE (ONNX/NumPy)   │
│  rust_core/src/lib.rs     │  │  embedder.py   vector_index  │
│  scan_directory()         │  │  MobileCLIP + MiniLM-L6      │
│  hash_files_parallel()    │  │  cosine similarity clusters  │
└───────────────────────────┘  └─────────────────────────────┘
```

## Data Flow: Scan Operation

```
User clicks "Scan Now"
  → MainWindow._start_scan()
    → ScanViewModel.start_scan()
      → ScanWorker (QThread) spawned
        → Deduplicator.run()
          ├─ Pass 1: FileScanner → rust_core.scan_directory() or os.walk
          ├─ Pass 2: FileHasher  → rust_core.hash_files_parallel() or ThreadPoolExecutor
          └─ Pass 3: ProcessPoolExecutor → ONNX embedder → VectorIndex clusters
        → finished signal → ScanViewModel → MainWindow
          → DuplicateTableModel.load_result()
          → ReasoningEngine.process() → RetentionAgent per group
          → UI renders results + AI panel
          → ScanRepository writes session to SQLite
```

## Concurrency Model

| Pass | CPU Profile | Executor |
|------|-------------|----------|
| 1 — Traversal | I/O-bound | Rust rayon (OS threads) |
| 2 — Hashing | I/O-bound + GIL-free | ThreadPoolExecutor (hashlib releases GIL) |
| 3 — ML Inference | CPU-bound | ProcessPoolExecutor (full GIL bypass) |

## Database Schema (SQLite, WAL mode)

```sql
ScanSession    → id, folder_path, started_at, completed_at, files_scanned ...
FileMetadata   → id, session_id(FK), full_path, size_bytes, md5_hash, sha256_hash, embedding_vector
DuplicateGroup → id, session_id(FK), group_key, match_type, file_paths_json, agent_recommended_keep
FileAction     → id, file_id(FK), full_path, action, acted_at, freed_bytes, agent_recommended
```

## Key Design Decisions

1. **Rust-first, Python fallback** — rust_core is optional; all entry points check `_HAS_RUST` and fall back gracefully.
2. **Headless engine** — `app/engine/` and `app/agents/` import no Qt code; fully testable via `pytest` and runnable via `cli.py`.
3. **Explicit exceptions** — all bare `except: pass` removed; every catch is `except (PermissionError, OSError) as exc: logger.warning(...)`.
4. **MVVM strict separation** — Views contain only `connect()` calls and layout code; zero `if/else` business logic.
5. **SQLAlchemy WAL** — All writes are transactional with PRAGMA `foreign_keys=ON` and `journal_mode=WAL` for corruption resistance.
