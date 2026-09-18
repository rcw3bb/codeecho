"""
CLI entry point for codeecho.

Invoked via::

    poetry run python -m codeecho [OPTIONS] PATH

:author: Ron Webb
:since: 1.0.0
"""

import json
import logging
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

from . import __version__, CONF_DIR, DEFAULT_IGNORE_PATH
from . import basis as basis_module
from . import extractor, fingerprint, parser as ts_parser, scanner
from .config import Config
from .db import SessionDB, get_db_path
from .detector import detect
from .models import ScanResult
from .reporter import html_reporter, json_reporter

_console = Console()
_config = Config()
_logger = logging.getLogger("codeecho.__main__")

_FORMAT_CHOICES = click.Choice(["json", "html", "both"])


def _parse_types(types_str: str) -> set[int]:
    """Parse ``--types`` value into a set of integers.

    :since: 1.0.0
    """
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


def _read_target_list(list_file: Path) -> list[Path]:
    """Read one target path per line from *list_file*.

    Blank lines and lines starting with ``#`` are skipped.

    :since: 1.2.0
    """
    result: list[Path] = []
    for line in list_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            result.append(Path(stripped))
    return result


def _load_ignore_file(ignore_path: Path, base_dir: Path) -> IgnoreFile | None:
    """Load an :class:`IgnoreFile` from *ignore_path*, logging failures.

    Returns ``None`` on a missing or non-UTF-8 file instead of raising.

    :since: 1.2.0
    """
    try:
        return IgnoreFile(ignore_path, base_dir=base_dir)
    except FileNotFoundError:
        _logger.warning("Ignore file not found at %s", ignore_path)
        return None
    except UnicodeDecodeError as exc:
        _logger.warning("Ignore file at %s is not valid UTF-8: %s", ignore_path, exc)
        return None


def _build_ignore(base_dir: Path) -> IgnoreFile | None:
    """Build a path-ignore matcher anchored at *base_dir*.

    The ignore filename is resolved from ``config.ini``'s ``[override]
    ignore-file`` setting under :data:`CONF_DIR`; when that file is missing,
    the bundled default ``.ignore`` is tried instead.

    :since: 1.2.0
    """
    custom_path = Path(CONF_DIR) / _config.get_ignore_file()
    ignore = _load_ignore_file(custom_path, base_dir)
    if ignore is not None:
        return ignore
    if custom_path == Path(DEFAULT_IGNORE_PATH):
        return None
    return _load_ignore_file(Path(DEFAULT_IGNORE_PATH), base_dir)


def _resolve_target_paths(
    paths: tuple[Path, ...], target_list: bool
) -> tuple[Path, ...]:
    """Validate *paths* and expand ``--target-list`` into concrete target paths.

    :since: 1.2.0
    """
    if not paths:
        raise click.UsageError("At least one PATH is required.")

    if not target_list:
        return paths

    if len(paths) != 1 or not paths[0].is_file():
        raise click.UsageError(
            "--target-list requires PATH to be a single existing file."
        )
    expanded = tuple(_read_target_list(paths[0]))
    if not expanded:
        raise click.UsageError("--target-list file contains no target paths.")
    return expanded


def _read_basis_targets(basis_path: Path | None) -> list[Path]:
    """Read the basis path(s) listed in *basis_path*, if given.

    Absolute entries are resolved (normalising case/symlinks); relative entries
    (e.g. a bare filename) are left as-is so they can be matched by filename/suffix
    against the scanned files instead of being resolved against the current
    working directory.

    :since: 1.2.0
    """
    if basis_path is None:
        return []
    targets = [
        p.resolve() if p.is_absolute() else p for p in _read_target_list(basis_path)
    ]
    if not targets:
        raise click.UsageError("--basis file contains no target paths.")
    return targets


def _discover_files(
    resolved: list[Path], exclude: tuple[str, ...]
) -> list[tuple[Path, str]]:
    """Print scan targets and return the discovered ``(file, language)`` pairs.

    :since: 1.2.0
    """
    for target_path in resolved:
        _console.print(f"[dim]Scanning:[/dim] [bold]{target_path}[/bold]")
    try:
        base_dir = Path(os.path.commonpath(resolved))
        if not base_dir.is_dir():
            base_dir = base_dir.parent
    except ValueError:
        base_dir = Path.cwd()
    ignore_file = _build_ignore(base_dir)
    return scanner.scan(
        tuple(resolved), exclude_patterns=exclude, ignore_file=ignore_file
    )


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
@click.option(
    "--target-list",
    "target_list",
    is_flag=True,
    default=False,
    help=(
        "Treat PATH as a single existing file listing target paths (files "
        "and/or directories), one per line, instead of individual PATH "
        "arguments. Blank lines and lines starting with '#' are skipped."
    ),
)
@click.option(
    "--basis",
    "basis_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="FILE",
    help=(
        "File listing basis target paths, one per line, same format as "
        "--target-list. Absolute file/directory entries are added to the scan "
        "automatically and matched exactly; relative entries (e.g. a bare "
        "filename) are matched by filename/suffix against any file discovered "
        "in the scan. The report is filtered to only clone groups that touch "
        "at least one basis file; groups duplicated purely among basis files "
        "are flagged as such."
    ),
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
    target_list: bool,
    basis_path: Path | None,
) -> None:
    """Scan one or more PATH(s) for duplicate and near-duplicate code.

    Each PATH may be a file or a directory.  Generates JSON and/or HTML reports,
    then removes the intermediate session data from the embedded database.

    :since: 1.0.0
    """
    _console.print(
        Panel(
            f"[bold cyan]codeecho[/bold cyan] [dim]v{__version__}[/dim]  —  Code Duplicate Scanner",
            border_style="dim",
        )
    )

    paths = _resolve_target_paths(paths, target_list)
    detect_types = _parse_types(types)
    if output_dir is None:
        output_dir = Path.cwd() / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    basis_targets = _read_basis_targets(basis_path)

    session_id = str(uuid.uuid4())
    config = {
        "types": types,
        "threshold": threshold,
        "min_tokens": min_tokens,
        "exclude": list(exclude),
        "basis": [str(p) for p in basis_targets],
    }
    resolved = [p.resolve() for p in paths]
    for target in basis_targets:
        if target.is_absolute() and target not in resolved:
            resolved.append(target)

    db_path = Path(get_db_path(str(db_dir) if db_dir else None))
    with SessionDB(db_path=db_path) as session_db:
        session_db.create_session(
            session_id, json.dumps([str(p) for p in resolved]), config
        )

        files = _discover_files(resolved, exclude)

        if not files:
            _console.print("[yellow]No supported source files found.[/yellow]")
            session_db.delete_session(session_id)
            return

        basis_files = None
        if basis_targets:
            basis_files = basis_module.resolve_basis_files(files, basis_targets)
            if not basis_files:
                _console.print(
                    "[yellow]Warning: none of the --basis paths matched any scanned files.[/yellow]"
                )

        total_fragments = _process_files(files, session_db, session_id, min_tokens)

        cnt1, cnt2, cnt3 = _detect_clones(
            session_db, session_id, detect_types, threshold
        )

        basis_counts = {1: 0, 2: 0, 3: 0}
        if basis_files is not None:
            groups = session_db.get_clone_groups(session_id)
            groups_with_members = [
                (g, session_db.get_fragments_for_group(g)) for g in groups
            ]
            basis_counts = basis_module.count_basis_groups_by_type(
                groups_with_members, basis_files
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
            basis_paths=[str(p) for p in basis_targets],
            basis_type1_groups=basis_counts[1],
            basis_type2_groups=basis_counts[2],
            basis_type3_groups=basis_counts[3],
        )

        written = _write_reports(
            session_db, result, output_dir, output, fmt, basis_files
        )

        session_db.delete_session(session_id)

    # ── Summary table (printed after DB is closed) ──────────────────────────
    _print_summary(result, written)


def _detect_clones(
    session_db: SessionDB,
    session_id: str,
    detect_types: set[int],
    threshold: float,
) -> tuple[int, int, int]:
    """Run clone detection and return (type1_count, type2_count, type3_count).

    :since: 1.0.0
    """
    _console.print("[dim]Detecting clones…[/dim]")
    return detect(session_db, session_id, detect_types, threshold)


def _write_reports(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    session_db: SessionDB,
    result: ScanResult,
    output_dir: Path,
    output: str,
    fmt: str,
    basis_files: frozenset[str] | None = None,
) -> list[Path]:
    """Write the requested report formats and return a list of written paths.

    :since: 1.0.0
    """
    written: list[Path] = []
    if fmt in ("json", "both"):
        written.append(
            json_reporter.write(
                session_db, result, output_dir / f"{output}.json", basis_files
            )
        )
    if fmt in ("html", "both"):
        written.append(
            html_reporter.write(
                session_db, result, output_dir / f"{output}.html", basis_files
            )
        )
    return written


def _print_summary(result: ScanResult, written: list[Path]) -> None:
    """Print the scan summary table and list of saved report paths.

    :since: 1.0.0
    """
    has_basis = bool(result.basis_paths)

    def _value(count: int, basis_count: int) -> str:
        return f"{count} ({basis_count})" if has_basis else str(count)

    table = Table(title="Scan Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim", min_width=26)
    table.add_column("Value", justify="right", style="bold")
    table.add_row("Files scanned", str(result.files_scanned))
    table.add_row("Fragments extracted", str(result.fragments_extracted))
    table.add_row(
        "[red]Type-1[/red] clone groups (exact)",
        _value(result.type1_groups, result.basis_type1_groups),
    )
    table.add_row(
        "[yellow]Type-2[/yellow] clone groups (structural)",
        _value(result.type2_groups, result.basis_type2_groups),
    )
    table.add_row(
        "[green]Type-3[/green] clone groups (near-duplicate)",
        _value(result.type3_groups, result.basis_type3_groups),
    )
    _console.print(table)
    if has_basis:
        _console.print("[dim]Value in parentheses = basis-touching groups.[/dim]")
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

    :since: 1.0.0
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
