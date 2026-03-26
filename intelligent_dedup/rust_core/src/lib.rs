// =============================================================================
// rust_core/src/lib.rs
// =============================================================================
// High-performance file scanner and parallel hasher exposed to Python via PyO3.
//
// Functions:
//   scan_directory(path, extensions, min_size) -> List[Dict]
//   hash_files_parallel(paths, algorithm)      -> Dict[str, str]
//
// Build:
//   maturin develop --release   (for development)
//   maturin build --release     (for distribution wheel)
// =============================================================================

use md5::Md5;
use memmap2::Mmap;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString};
use rayon::prelude::*;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs::{self, File};
use std::path::Path;
use std::time::UNIX_EPOCH;
use walkdir::{DirEntry, WalkDir};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Returns true if any directory component is in the exclusion set.
fn is_excluded(entry: &DirEntry) -> bool {
    const EXCLUSIONS: &[&str] = &[
        "windows",
        "appdata",
        "program files",
        "program files (x86)",
        ".git",
        ".svn",
        "node_modules",
        "system32",
        "$recycle.bin",
        "__pycache__",
        ".venv",
        "venv",
    ];
    entry
        .path()
        .components()
        .any(|c| EXCLUSIONS.contains(&c.as_os_str().to_string_lossy().to_lowercase().as_str()))
}

/// Compute MD5 of a file using memory mapping for large-file efficiency.
fn hash_md5(path: &Path) -> Option<String> {
    let file = File::open(path).ok()?;
    let mmap = unsafe { Mmap::map(&file).ok()? };
    let digest = md5::compute(&*mmap);
    Some(format!("{:x}", digest))
}

/// Compute SHA-256 of a file using memory mapping.
fn hash_sha256(path: &Path) -> Option<String> {
    let file = File::open(path).ok()?;
    let mmap = unsafe { Mmap::map(&file).ok()? };
    let mut hasher = Sha256::new();
    hasher.update(&*mmap);
    Some(format!("{:x}", hasher.finalize()))
}

// ---------------------------------------------------------------------------
// PyO3 exported functions
// ---------------------------------------------------------------------------

/// Recursively scan a directory tree and return file metadata.
///
/// Parameters
/// ----------
/// path       : Root directory path as a string.
/// extensions : List of allowed file extensions (e.g. [".jpg", ".png"]).
/// min_size   : Minimum file size in bytes; files smaller than this are skipped.
///
/// Returns
/// -------
/// List of dicts with keys: path, size, ext, modified_secs, is_symlink.
#[pyfunction]
fn scan_directory(
    py: Python<'_>,
    path: &str,
    extensions: Vec<String>,
    min_size: u64,
) -> PyResult<Py<PyList>> {
    let ext_set: std::collections::HashSet<String> =
        extensions.iter().map(|e| e.to_lowercase()).collect();

    // Collect all candidate entries in parallel via rayon
    let entries: Vec<_> = WalkDir::new(path)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| !is_excluded(e))
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file())
        .collect();

    // Parallel metadata extraction
    let results: Vec<HashMap<String, String>> = entries
        .par_iter()
        .filter_map(|entry| {
            let p = entry.path();
            let ext = p
                .extension()
                .map(|e| format!(".{}", e.to_string_lossy().to_lowercase()))
                .unwrap_or_default();

            if !ext_set.contains(&ext) {
                return None;
            }

            let meta = fs::metadata(p).ok()?;
            let size = meta.len();
            if size < min_size {
                return None;
            }

            let mtime = meta
                .modified()
                .ok()
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_secs_f64())
                .unwrap_or(0.0);

            let is_link = p.is_symlink();

            let mut m = HashMap::new();
            m.insert("path".to_string(), p.to_string_lossy().to_string());
            m.insert("size".to_string(), size.to_string());
            m.insert("ext".to_string(), ext);
            m.insert("modified_secs".to_string(), mtime.to_string());
            m.insert("is_symlink".to_string(), is_link.to_string());
            Some(m)
        })
        .collect();

    // Convert to Python list of dicts
    let py_list = PyList::empty_bound(py);
    for item in results {
        let dict = PyDict::new_bound(py);
        for (k, v) in item {
            dict.set_item(k, v)?;
        }
        py_list.append(dict)?;
    }
    Ok(py_list.into())
}

/// Hash a batch of files in parallel using rayon.
///
/// Parameters
/// ----------
/// paths     : List of absolute file paths.
/// algorithm : "md5" or "sha256".
///
/// Returns
/// -------
/// Dict mapping path -> hex_digest. Failed files are omitted from the result.
#[pyfunction]
fn hash_files_parallel(
    py: Python<'_>,
    paths: Vec<String>,
    algorithm: &str,
) -> PyResult<Py<PyDict>> {
    let use_sha256 = algorithm.to_lowercase() == "sha256";

    let results: Vec<(String, String)> = paths
        .par_iter()
        .filter_map(|path_str| {
            let p = Path::new(path_str);
            let digest = if use_sha256 {
                hash_sha256(p)?
            } else {
                hash_md5(p)?
            };
            Some((path_str.clone(), digest))
        })
        .collect();

    let dict = PyDict::new_bound(py);
    for (path, digest) in results {
        dict.set_item(path, digest)?;
    }
    Ok(dict.into())
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

#[pymodule]
fn rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(scan_directory, m)?)?;
    m.add_function(wrap_pyfunction!(hash_files_parallel, m)?)?;
    Ok(())
}
