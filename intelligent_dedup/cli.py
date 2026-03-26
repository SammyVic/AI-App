#!/usr/bin/env python
"""
=============================================================================
cli.py — Headless CLI Entry Point
=============================================================================
Zero Qt dependency. Uses only app.engine, app.models, app.agents.

Usage:
  python cli.py scan --dir "C:/Data" [--method sha256] [--fuzzy] [--semantic]
  python cli.py stats
  python cli.py agent --session <id>
=============================================================================
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


@click.group()
def cli():
    """Intelligent Dedup — Enterprise CLI"""


# ---------------------------------------------------------------------------
# scan command
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--dir", "folder", required=True, help="Directory to scan")
@click.option("--method", default="sha256",
              type=click.Choice(["md5", "sha256", "simple"]), show_default=True)
@click.option("--fuzzy", is_flag=True, default=False, help="Enable fuzzy name matching")
@click.option("--semantic", is_flag=True, default=False, help="Enable ML semantic matching")
@click.option("--min-size", default=1, show_default=True, help="Minimum file size (KB)")
@click.option("--output", default=None, help="Write JSON report to this path")
@click.option("--extensions", default="", help="Comma-separated extension list (.jpg,.png)")
def scan(folder, method, fuzzy, semantic, min_size, output, extensions):
    """Scan FOLDER for duplicate files."""
    if not Path(folder).is_dir():
        console.print(f"[red]ERROR:[/] '{folder}' is not a valid directory.")
        sys.exit(1)

    from app.engine.scanner import ScanConfig
    from app.engine.deduplicator import Deduplicator

    # Parse extensions
    if extensions:
        exts = {e.strip() for e in extensions.split(",") if e.strip()}
    else:
        # Default: common file types
        exts = {
            ".jpg", ".jpeg", ".png", ".gif", ".bmp",
            ".pdf", ".doc", ".docx", ".txt", ".csv",
            ".mp4", ".avi", ".mkv", ".zip", ".rar",
        }

    config = ScanConfig(
        start_dir=folder,
        allowed_extensions=exts,
        min_size_bytes=min_size * 1024,
    )

    console.rule("[bold blue]Intelligent Dedup — Scan Starting")
    console.print(f"  📂 Folder  : {folder}")
    console.print(f"  🔬 Method  : {method}")
    console.print(f"  📏 Min size: {min_size} KB")
    console.print(f"  🧠 Semantic: {semantic} | Fuzzy: {fuzzy}")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning…", total=None)

        def _on_progress(pass_num, done, total, dupes, eta):
            progress.update(task,
                description=f"Pass {pass_num}/3 | Dupes: {dupes:,} | ETA: {eta or '—'}",
                completed=done,
                total=total or 1,
            )

        dedup = Deduplicator(
            config=config,
            algorithm=method,
            use_semantic=semantic,
            use_fuzzy=fuzzy,
            on_progress=_on_progress,
        )
        result = dedup.run()

    # Summary table
    table = Table(title="Scan Results", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Files Scanned", f"{result.files_scanned:,}")
    table.add_row("Duplicate Groups", f"{result.duplicate_groups:,}")
    table.add_row("Duplicate Files", f"{result.duplicate_files:,}")
    table.add_row("Recoverable Space", f"{result.space_recoverable_bytes / (1024**3):.2f} GB")
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    table.add_row("Passes", str(result.passes_completed))
    console.print(table)

    # Persist to DB
    try:
        from app.models.database import init_db
        from app.models.repository import ScanRepository
        SessionLocal = init_db()
        with SessionLocal() as sess:
            repo = ScanRepository(sess)
            db_sess = repo.create_session(folder_path=folder, comparison_method=method,
                                           used_semantic=semantic, used_fuzzy=fuzzy)
            for grp in result.groups:
                repo.create_group(
                    session_id=db_sess.id,
                    group_key=grp.group_key,
                    match_type=grp.match_type,
                    file_paths=grp.file_paths,
                    space_recoverable_bytes=grp.space_recoverable_bytes,
                )
            repo.complete_session(
                db_sess.id,
                files_scanned=result.files_scanned,
                duplicate_groups=result.duplicate_groups,
                duplicate_files=result.duplicate_files,
                space_recoverable_bytes=result.space_recoverable_bytes,
            )
        console.print(f"[green]✅ Session saved to database (id={db_sess.id})[/]")
    except Exception as exc:
        console.print(f"[yellow]⚠ Database write failed: {exc}[/]")

    # Export JSON report
    if output:
        report = {
            "folder": folder,
            "method": method,
            "files_scanned": result.files_scanned,
            "duplicate_groups": result.duplicate_groups,
            "duplicate_files": result.duplicate_files,
            "space_recoverable_bytes": result.space_recoverable_bytes,
            "duration_seconds": round(result.duration_seconds, 2),
            "groups": [
                {
                    "key": g.group_key,
                    "type": g.match_type,
                    "files": g.file_paths,
                    "recoverable_bytes": g.space_recoverable_bytes,
                }
                for g in result.groups
            ],
        }
        Path(output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[green]📄 Report saved:[/] {output}")


# ---------------------------------------------------------------------------
# stats command
# ---------------------------------------------------------------------------

@cli.command()
def stats():
    """Show lifetime statistics from the database."""
    try:
        from app.models.database import init_db
        from app.models.repository import ScanRepository
        SessionLocal = init_db()
        with SessionLocal() as sess:
            repo = ScanRepository(sess)
            s = repo.get_lifetime_stats()
    except Exception as exc:
        console.print(f"[red]Database error:[/] {exc}")
        sys.exit(1)

    table = Table(title="📊 Lifetime Statistics", header_style="bold magenta")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    for k, v in s.items():
        label = k.replace("_", " ").title()
        if "bytes" in k:
            display = f"{v / (1024**3):.2f} GB"
        elif isinstance(v, int):
            display = f"{v:,}"
        else:
            display = str(v)
        table.add_row(label, display)
    console.print(table)


# ---------------------------------------------------------------------------
# agent command
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--session", "session_id", type=int, required=True, help="Scan session ID")
@click.option("--output", default=None, help="Save reasoning log JSON to path")
def agent(session_id, output):
    """Run AI retention agent on a saved scan session."""
    try:
        from app.models.database import init_db
        from app.models.repository import ScanRepository
        from app.agents.reasoning_engine import ReasoningEngine
        from app.engine.deduplicator import DuplicateGroup

        SessionLocal = init_db()
        with SessionLocal() as sess:
            repo = ScanRepository(sess)
            db_groups = repo.get_groups_for_session(session_id)
            if not db_groups:
                console.print(f"[red]No groups found for session {session_id}[/]")
                sys.exit(1)

        groups = [
            DuplicateGroup(
                group_key=g.group_key,
                match_type=g.match_type,
                file_paths=g.file_paths,
                space_recoverable_bytes=g.space_recoverable_bytes,
            )
            for g in db_groups
        ]

        engine = ReasoningEngine()
        with console.status("Running retention agent…"):
            decisions = engine.process(groups)

        for key, d in list(decisions.items())[:20]:
            conf_colour = "green" if d.confidence >= 0.8 else "yellow" if d.confidence >= 0.5 else "red"
            console.print(
                f"[bold]{key}[/] → Keep: [cyan]{d.recommended_keep}[/]  "
                f"Confidence: [{conf_colour}]{d.confidence:.0%}[/]"
            )

        if output:
            engine.export_log(output)
            console.print(f"[green]Agent log saved:[/] {output}")

        summary = engine.summary_stats()
        console.print(f"\n[bold]Summary:[/] {summary['processed']} groups processed, "
                      f"avg confidence {summary['avg_confidence']:.0%}, "
                      f"{summary['high_confidence']} high-confidence decisions.")

    except Exception as exc:
        console.print(f"[red]Agent error:[/] {exc}")
        raise


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
