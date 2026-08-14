"""
CLI entry point for codeecho.

Invoked via::

    poetry run python -m codeecho [OPTIONS] PATH
"""

import json
import os
import uuid
from pathlib import Path

import click
from braincraft import IgnoreFile
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.table import Table

from codeecho import __version__, CONF_DIR
from codeecho import extractor, fingerprint, parser as ts_parser, scanner
from codeecho.db import SessionDB, get_db_path
from codeecho.detector import detect
from codeecho.models import ScanResult
from codeecho.reporter import html_reporter, json_reporter

_console = Console()

_FORMAT_CHOICES = click.Choice(["json", "html", "both"])


def _parse_types(types_str: str) -> set[int]:
    """Parse ``--types`` value into a set of integers."""
    if types_str.strip().lower() == "all":
        return {1, 2, 3}
    result: set[int] = set()
    for token in types_str.split(","):
        token = token.strip()
        if token.isdigit() and token in {"1", "2", "3"}:
            result.add(int(token))
    if not result:
        raise click.BadParameter(
            f"Invalid types value: {types_str!r}. Use 'all' or e.g. '1,2,3'."
        )
    return result


@click.command(
    name="codeecho", context_settings={"help_option_names": ["-h", "--help"]}
)
@click.version_option(
    version=__version__, prog_name="codeecho", message="%(prog)s v%(version)s"
)
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "--types",
    default="all",
    show_default=True,
    metavar="TYPES",
    help="Clone types to detect: comma-separated (e.g. '1,2') or 'all'.",
)
@click.option(
    "--threshold",
    default=0.8,
    show_default=True,
    type=click.FloatRange(0.0, 1.0),
    help="Jaccard similarity threshold for Type-3 (near-duplicate) detection.",
)
@click.option(
    "--output",
    default="codeecho-output",
    show_default=True,
    metavar="NAME",
    help="Base name (without extension) for output file(s).",
)
@click.option(
    "--output-dir",
    default=None,
    show_default=False,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory where output file(s) will be written.  [default: <cwd>/reports]",
)
@click.option(
    "--db-dir",
    "db_dir",
    default=None,
    show_default=False,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory for the SQLite scratch database.  [default: ~/.codeecho]",
)
@click.option(
    "--format",
    "fmt",
    default="both",
    show_default=True,
    type=_FORMAT_CHOICES,
    help="Output format.",
)
@click.option(
    "--min-tokens",
    default=10,
    show_default=True,
    type=click.IntRange(1),
    help="Minimum token count for a fragment to be considered.",
)
@click.option(
    "--exclude",
    multiple=True,
    metavar="PATTERN",
    help="Glob pattern(s) to exclude from scanning (repeatable).",
)
def main(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,invalid-name
    paths: tuple[Path, ...],
    types: str,
    threshold: float,
    output: str,
    output_dir: Path | None,
    db_dir: Path | None,
    fmt: str,
    min_tokens: int,
    exclude: tuple[str, ...],
) -> None:
    """Scan one or more PATH(s) for duplicate and near-duplicate code.

    Each PATH may be a file or a directory.  Generates JSON and/or HTML reports,
    then removes the intermediate session data from the embedded database.
    """
    _console.print(
        Panel(
            f"[bold cyan]codeecho[/bold cyan] [dim]v{__version__}[/dim]  —  Code Duplicate Scanner",
            border_style="dim",
        )
    )

    if not paths:
        raise click.UsageError("At least one PATH is required.")

    detect_types = _parse_types(types)
    if output_dir is None:
        output_dir = Path.cwd() / "reports"
    session_id = str(uuid.uuid4())
    config = {
        "types": types,
        "threshold": threshold,
        "min_tokens": min_tokens,
        "exclude": list(exclude),
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    resolved = [p.resolve() for p in paths]

    db_path = Path(get_db_path(str(db_dir) if db_dir else None))
    with SessionDB(db_path=db_path) as session_db:
        session_db.create_session(
            session_id, json.dumps([str(p) for p in resolved]), config
        )

        # ── Phase 1: File discovery ─────────────────────────────────────────
        for p in resolved:
            _console.print(f"[dim]Scanning:[/dim] [bold]{p}[/bold]")
        try:
            base_dir = Path(os.path.commonpath(resolved))
            if not base_dir.is_dir():
                base_dir = base_dir.parent
        except ValueError:
            base_dir = Path.cwd()
        _ignore_file = IgnoreFile(Path(CONF_DIR) / ".ignore", base_dir=base_dir)
        files = scanner.scan(
            tuple(resolved), exclude_patterns=exclude, ignore_file=_ignore_file
        )
        total_fragments = 0

        if not files:
            _console.print("[yellow]No supported source files found.[/yellow]")
            session_db.delete_session(session_id)
            return

        # ── Phase 2: Parse → Extract → Hash ────────────────────────────────
        total_fragments = _process_files(files, session_db, session_id, min_tokens)

        # ── Phase 3: Clone detection ────────────────────────────────────────
        cnt1, cnt2, cnt3 = _detect_clones(
            session_db, session_id, detect_types, threshold
        )

        result = ScanResult(
            session_id=session_id,
            version=__version__,
            scan_path=[str(p) for p in resolved],
            files_scanned=len(files),
            fragments_extracted=total_fragments,
            type1_groups=cnt1,
            type2_groups=cnt2,
            type3_groups=cnt3,
        )

        # ── Phase 4: Report generation ──────────────────────────────────────
        written = _write_reports(session_db, result, output_dir, output, fmt)

        # ── Phase 5: Clean up session ───────────────────────────────────────
        session_db.delete_session(session_id)

    # ── Summary table (printed after DB is closed) ──────────────────────────
    _print_summary(result, written)


def _detect_clones(
    session_db: SessionDB,
    session_id: str,
    detect_types: set[int],
    threshold: float,
) -> tuple[int, int, int]:
    """Run clone detection and return (type1_count, type2_count, type3_count)."""
    _console.print("[dim]Detecting clones…[/dim]")
    return detect(session_db, session_id, detect_types, threshold)


def _write_reports(
    session_db: SessionDB,
    result: ScanResult,
    output_dir: Path,
    output: str,
    fmt: str,
) -> list[Path]:
    """Write the requested report formats and return a list of written paths."""
    written: list[Path] = []
    if fmt in ("json", "both"):
        written.append(
            json_reporter.write(session_db, result, output_dir / f"{output}.json")
        )
    if fmt in ("html", "both"):
        written.append(
            html_reporter.write(session_db, result, output_dir / f"{output}.html")
        )
    return written


def _print_summary(result: ScanResult, written: list[Path]) -> None:
    """Print the scan summary table and list of saved report paths."""
    table = Table(title="Scan Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim", min_width=26)
    table.add_column("Value", justify="right", style="bold")
    table.add_row("Files scanned", str(result.files_scanned))
    table.add_row("Fragments extracted", str(result.fragments_extracted))
    table.add_row("[red]Type-1[/red] clone groups (exact)", str(result.type1_groups))
    table.add_row(
        "[yellow]Type-2[/yellow] clone groups (structural)", str(result.type2_groups)
    )
    table.add_row(
        "[green]Type-3[/green] clone groups (near-duplicate)", str(result.type3_groups)
    )
    _console.print(table)
    _console.print("\n[bold]Reports saved:[/bold]")
    for dest in written:
        _console.print(f"  [cyan]•[/cyan] {dest}")


def _process_files(
    files: list[tuple[Path, str]],
    session_db: SessionDB,
    session_id: str,
    min_tokens: int,
) -> int:
    """Parse, extract, and hash every file; bulk-insert fragments into *session_db*.

    Returns:
        Total number of fragments extracted.
    """
    total = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=_console,
        transient=True,
    ) as progress:
        task = progress.add_task("Processing files…", total=len(files))
        for file_path, language in files:
            try:
                source_bytes = file_path.read_bytes()
                tree = ts_parser.parse(source_bytes, language)
                if tree is not None:
                    frags = extractor.extract_fragments(
                        tree, source_bytes, file_path, language, session_id, min_tokens
                    )
                    fingerprint.hash_all(frags)
                    session_db.insert_many_fragments(frags)
                    total += len(frags)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                _console.print(f"[red]Error processing {file_path.name}: {exc}[/red]")
            finally:
                progress.advance(task)
    return total


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
