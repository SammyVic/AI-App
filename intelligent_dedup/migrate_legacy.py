import os
import glob
import json
import logging
import argparse
from datetime import datetime

# Adjust the path to import local app modules
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.database import init_db
from app.models.repository import ScanRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration")

def run_migration(source_dir: str):
    SessionLocal = init_db()
    with SessionLocal() as db_session:
        repo = ScanRepository(db_session)
        
        # Look for the old history format JSONs
        if not os.path.isdir(source_dir):
            if os.path.isdir(os.path.join(source_dir, "scan_history")):
                source_dir = os.path.join(source_dir, "scan_history")

        json_files = glob.glob(os.path.join(source_dir, "run_*.json"))
        if not json_files:
            logger.warning(f"No run_*.json files found in {source_dir}.")
            return

        logger.info(f"Found {len(json_files)} legacy session files. Beginning migration to SQLite...")
        
        for json_path in json_files:
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                folder = data.get("folder", "Unknown_Legacy_Scan")
                duplicates = data.get("duplicates", {})
                
                if not duplicates:
                    logger.info(f"Skipping {os.path.basename(json_path)} (No duplicate groups found)")
                    continue
                
                # Extract the timestamp from the legacy filename e.g. run_20260326_213457.json
                basename = os.path.basename(json_path)
                try:
                    date_str = basename.replace("run_", "").replace(".json", "")
                    dt = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                    started_at = dt.timestamp()
                except ValueError:
                    started_at = os.path.getctime(json_path)

                # Create an active session and override the start time
                sess = repo.create_session(folder_path=folder, comparison_method="legacy_md5")
                sess.started_at = started_at
                
                dup_groups = 0
                dup_files = 0
                files_metadata = {}
                total_recoverable = 0
                
                for key, paths in duplicates.items():
                    if not paths or len(paths) < 2:
                        continue
                        
                    dup_groups += 1
                    dup_files += len(paths)
                    
                    group_size_sum = 0
                    
                    # To satisfy the new database constraints, ensure FileMetadata is created
                    for p in paths:
                        if p not in files_metadata:
                            # Because this is historical, the file might have been deleted already.
                            # We gracefully try to stat it, else fallback to 0 bytes.
                            try:
                                stat = os.stat(p)
                                size = stat.st_size
                                mtime = stat.st_mtime
                            except OSError:
                                size = 0
                                mtime = started_at
                                
                            fm = repo.add_file_metadata(
                                session_id=sess.id,
                                full_path=p,
                                filename=os.path.basename(p),
                                extension=os.path.splitext(p)[1].lower() or "unknown",
                                size_bytes=size,
                                modified_at=mtime
                            )
                            files_metadata[p] = fm
                            group_size_sum += size
                    
                    # Calculate recoverable space (all files except one)
                    # For legacy files deleted, size is 0 so this handles safely.
                    recoverable = 0
                    if group_size_sum > 0:
                        avg_file_size = group_size_sum // len(paths)
                        recoverable = avg_file_size * (len(paths) - 1)
                        total_recoverable += recoverable
                    
                    # Create the duplicate cluster representation
                    repo.create_group(
                        session_id=sess.id,
                        group_key=key,
                        match_type="fuzzy" if "fuzzy" in key else "exact_hash",
                        file_paths=paths,
                        space_recoverable_bytes=recoverable
                    )
                
                # Commit all file metadata rows at once
                db_session.commit()
                
                # Mark session completed
                repo.complete_session(
                    session_id=sess.id,
                    files_scanned=len(files_metadata),  # Best bound estimate
                    duplicate_groups=dup_groups,
                    duplicate_files=dup_files,
                    space_recoverable_bytes=total_recoverable
                )
                logger.info(f"Successfully migrated {basename} -> SQLite Session #{sess.id} ({dup_groups} groups)")
                
            except Exception as e:
                db_session.rollback()
                logger.error(f"Failed to migrate {json_path}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate legacy run_*.json files to the new SQLite database.")
    parser.add_argument("--dir", type=str, required=True, help="Path to the directory containing run_*.json files.")
    args = parser.parse_args()
    run_migration(args.dir)
