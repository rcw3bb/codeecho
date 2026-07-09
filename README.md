# codeecho 1.0.0

> A developer tool that scans your codebase to detect and highlight **echoes** of duplicated or near-duplicated code, so you can refactor toward cleaner, more maintainable designs.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](CHANGELOG.md)

## Prerequisites

- Python `>=3.14`

## Installation

```powershell
pip install codeecho
```

## Usage

```powershell
python -m codeecho <path> [options]
```

### Clone detection levels

| Type | Detection strategy | Example |
|------|--------------------|---------|
| **Type-1** | Exact copy-paste — identical token sequences | Two functions with the same code copied verbatim |
| **Type-2** | Structural clone — same structure, renamed identifiers / literals | Same logic with different variable names |
| **Type-3** | Near-duplicate — high Jaccard similarity on token sets | Nearly identical functions with a few extra lines |

### Supported languages

| Language | Extensions |
|----------|-----------|
| Python | `.py` |
| JavaScript | `.js`, `.mjs`, `.cjs` |
| TypeScript | `.ts`, `.tsx` |
| Java | `.java` |
| Go | `.go` |
| Gosu | `.gs`, `.gsx` |

### Arguments

| Argument | Description |
|----------|-------------|
| `path` | Root directory to scan. |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--types <types>` | `all` | Clone types to detect: comma-separated (`1`, `2`, `3`) or `all`. |
| `--threshold <float>` | `0.8` | Jaccard similarity threshold for Type-3 detection (`0.0`–`1.0`). |
| `--output <name>` | `codeecho-output` | Base name (without extension) for output file(s). |
| `--output-dir <dir>` | `<cwd>/reports` | Directory where output file(s) will be written. |
| `--db-dir <dir>` | `~/.codeecho` | Directory for the SQLite scratch database (`codeecho.db`). Session records are removed after the report is written. |
| `--format <fmt>` | `both` | Output format: `json`, `html`, or `both`. |
| `--min-tokens <n>` | `10` | Minimum token count for a code fragment to be included. |
| `--exclude <pattern>` | _(none)_ | Glob pattern(s) to exclude from scanning (repeatable). |
| `--version` | | Print the version and exit. |
| `-h, --help` | | Show help and exit. |

### Examples

Scan the current directory and write both JSON and HTML reports:

```powershell
python -m codeecho .
```

Detect only Type-1 and Type-2 clones in a `src/` tree:

```powershell
python -m codeecho src --types 1,2
```

Scan with a custom output name and directory:

```powershell
python -m codeecho . --output my-scan --output-dir audit/reports
```

Lower the Type-3 threshold to catch more near-duplicates:

```powershell
python -m codeecho . --threshold 0.6
```

Exclude test and vendor directories:

```powershell
python -m codeecho . --exclude "*/tests/*" --exclude "*/vendor/*"
```

## Configuration

| Environment variable | Description |
|----------------------|-------------|
| `CODEECHO_CONFIG_DIR` | Directory where `logging.ini` and `.ignore` are seeded on first run. When unset, the bundled copies inside the package are used directly. |

### `.ignore` file

On first run, a `.ignore` file is seeded into `CODEECHO_CONFIG_DIR` (or the package directory when unset). It follows gitignore syntax and is applied during file scanning to exclude paths in addition to any `--exclude` patterns passed on the command line. Edit this file to permanently suppress paths you never want scanned.

## Development

### Prerequisites

- Poetry `2.2+`

### Setup

```powershell
poetry install
```

### Run

```powershell
poetry run python -m codeecho <path> [options]
```

### Architecture

```mermaid
flowchart TD
    CLI["__main__.py\n(Click CLI)"] --> ScannerM["scanner.py\nFile discovery"]
    ScannerM --> Parser["parser.py\nTree-sitter parsing"]
    Parser --> Extractor["extractor.py\nFragment extraction\n(functions · classes · files)"]
    Extractor --> Normalizer["normalizer.py\nRegex tokeniser\nType-2 normalisation"]
    Normalizer --> Fingerprint["fingerprint.py\nSHA-256 hashing"]
    Fingerprint --> DB["db.py\nSQLite session store"]
    DB --> Detector["detector.py\nType-1 / 2 hash grouping\nType-3 Jaccard similarity"]
    Detector --> DB
    DB --> JSON["reporter/json_reporter.py\nJSON report"]
    DB --> HTML["reporter/html_reporter.py\nHTML report"]
    DB -->|delete session| Cleanup["Session cleanup"]
```

### Format and Lint

```powershell
poetry run black codeecho
poetry run pylint codeecho
```

### Run Tests with Coverage

```powershell
poetry run pytest --cov=codeecho tests --cov-report html
```

## [Changelog](CHANGELOG.md)

## License

This project is licensed under the [MIT License](LICENSE).

## Author

Ron Webb
