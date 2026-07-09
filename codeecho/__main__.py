"""
CLI entry point for codeecho.

Invoked via::

    poetry run python -m codeecho [OPTIONS] PATH

:author: Ron Webb
:since: 1.0.0
"""

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
    "path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
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
def main(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-statements,invalid-name
    path: Path,
    types: str,
    threshold: float,
    output: str,
    output_dir: Path,
    db_dir: Path | None,
    fmt: str,
    min_tokens: int,
    exclude: tuple[str, ...],
) -> None:
    """Scan PATH for duplicate and near-duplicate code.

    Generates JSON and/or HTML reports, then removes the intermediate session data
    from the embedded database.
    """
    _console.print(
        Panel(
            f"[bold cyan]codeecho[/bold cyan] [dim]v{__version__}[/dim]  —  Code Duplicate Scanner",
            border_style="dim",
        )
    )

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

    db_path = Path(get_db_path(str(db_dir) if db_dir else None))
    with SessionDB(db_path=db_path) as session_db:
        session_db.create_session(session_id, str(path.resolve()), config)

        # ── Phase 1: File discovery ─────────────────────────────────────────
        _console.print(f"[dim]Scanning:[/dim] [bold]{path.resolve()}[/bold]")
        _ignore_file = IgnoreFile(Path(CONF_DIR) / ".ignore", base_dir=path.resolve())
        files = scanner.scan(path, exclude_patterns=exclude, ignore_file=_ignore_file)
        total_fragments = 0

        if not files:
            _console.print("[yellow]No supported source files found.[/yellow]")
            return

        # ── Phase 2: Parse → Extract → Hash ────────────────────────────────
        total_fragments = _process_files(files, session_db, session_id, min_tokens)

        # ── Phase 3: Clone detection ────────────────────────────────────────
        _console.print("[dim]Detecting clones…[/dim]")
        cnt1, cnt2, cnt3 = detect(session_db, session_id, detect_types, threshold)

        result = ScanResult(
            session_id=session_id,
            scan_path=str(path.resolve()),
            files_scanned=len(files),
            fragments_extracted=total_fragments,  # type: ignore[possibly-undefined]
            type1_groups=cnt1,
            type2_groups=cnt2,
            type3_groups=cnt3,
        )

        # ── Phase 4: Report generation ──────────────────────────────────────
        written: list[Path] = []
        if fmt in ("json", "both"):
            dest = json_reporter.write(
                session_db, result, output_dir / f"{output}.json"
            )
            written.append(dest)
        if fmt in ("html", "both"):
            dest = html_reporter.write(
                session_db, result, output_dir / f"{output}.html"
            )
            written.append(dest)

        # ── Phase 5: Clean up session ───────────────────────────────────────
        session_db.delete_session(session_id)

    # ── Summary table (printed after DB is closed) ──────────────────────────
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

    :returns: Total number of fragments extracted.
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
