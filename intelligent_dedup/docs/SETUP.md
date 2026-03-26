# Setup Guide — Intelligent Dedup v2.0

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Required |
| pip | 24+ | `python -m pip install --upgrade pip` |
| Rust toolchain | 1.75+ | **Optional** for native core |

---

## 1. Python Environment

```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install all dependencies
pip install -r requirements.txt
```

---

## 2. Rust Performance Core (Optional but Recommended)

The Rust core provides 3–10× faster scanning and hashing on large directories.
Without it, the app falls back to pure Python automatically.

### Install Rust
```powershell
# Download and run rustup (https://rustup.rs)
winget install Rustlang.Rustup
# Restart PowerShell, then:
rustup default stable
```

### Build the extension
```powershell
# Install maturin (Rust-Python bridge builder)
pip install maturin

# Build and install the extension into the active venv
cd rust_core
maturin develop --release
cd ..
```

Verify the build:
```python
import rust_core
print(rust_core.scan_directory("C:/", [".txt"], 1))
```

---

## 3. ML Models (Optional — Semantic Pass)

Models are auto-downloaded from HuggingFace on first use. To pre-download:

```powershell
# Set custom model directory (optional)
$env:DEDUP_MODELS_DIR = "C:\my_models"

# Pre-download image model (~22 MB)
python -c "from app.ml.embedder import ImageEmbedder; ImageEmbedder()"

# Pre-download text model (~23 MB quantised)
python -c "from app.ml.embedder import TextEmbedder; TextEmbedder()"
```

For **offline environments**, manually place ONNX files in `%USERPROFILE%\.intelligent_dedup\models\`:
- `mobileclip_s0_image.onnx`
- `all-MiniLM-L6-v2_quant.onnx`

---

## 4. Run the Application

### GUI
```powershell
python main.py
```

### CLI
```powershell
# Scan a directory
python cli.py scan --dir "C:\Users\vikas\Documents" --method sha256

# View lifetime stats
python cli.py stats

# Run AI agent on session 1
python cli.py agent --session 1 --output agent_log.json
```

---

## 5. Run Tests

```powershell
python -m pytest tests/ -v --tb=short
```

---

## Database Location

The SQLite database is stored at:
```
%USERPROFILE%\.intelligent_dedup\dedup.db
```

Override with environment variable:
```powershell
$env:DEDUP_DB_PATH = "D:\custom\path\dedup.db"
```
