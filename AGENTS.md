## Purpose

`codeecho` is a Python developer tool that scans a codebase to detect and highlight ECHOES of duplicated or near-duplicated code, enabling refactoring toward cleaner, more maintainable designs. Built with Python >=3.14 and managed by Poetry 2.2+. Key runtime dependencies: `logenrich` (structured logging) and `env-dir-bootstrap` (config directory bootstrapping via `CODEECHO_CONFIG_DIR`). Run with `poetry run python -m codeecho`. Format: `poetry run black codeecho`. Lint: `poetry run pylint codeecho`. Tests with coverage: `poetry run pytest --cov=codeecho tests --cov-report html`.

## Tree

- codeecho/ — main package source code
- codeecho/__init__.py — package entry point; bootstraps config dir and logger
- codeecho/__main__.py — Click CLI entry point (--version, --types, --threshold, --output, --format, --min-tokens, --exclude); Rich progress bar and summary table
- codeecho/models.py — Fragment, CloneGroup, ScanResult dataclasses
- codeecho/db.py — SessionDB context manager; SQLite session store (schema, CRUD, cascade delete)
- codeecho/scanner.py — File discovery (walk, extension→language map, .gitignore-like exclusions)
- codeecho/parser.py — Tree-sitter Language/Parser cache; one fresh Parser per parse() call
- codeecho/normalizer.py — Regex-based token extraction + Type-2 normalisation (ID_N / LIT_N placeholders); per-language keyword sets
- codeecho/extractor.py — Fragment extraction via Tree-sitter queries; byte-range-only node access to avoid TS 0.26 corruption
- codeecho/fingerprint.py — SHA-256 raw and normalised hash computation
- codeecho/detector.py — Type-1/2 (hash grouping) + Type-3 (Jaccard similarity + union-find) detection
- codeecho/reporter/ — Reporter sub-package
- codeecho/reporter/__init__.py — package marker
- codeecho/reporter/json_reporter.py — JSON report writer (reads session DB)
- codeecho/reporter/html_reporter.py — Self-contained HTML report via Jinja2 inline template
- codeecho/logging.ini — logging configuration (bundled with the package)
- tests/ — pytest test suite mirroring the codeecho/ structure
- tests/conftest.py — shared fixtures (session_db, session_id)
- tests/test_models.py — Fragment / CloneGroup / ScanResult model tests
- tests/test_db.py — SessionDB CRUD + cascade delete tests
- tests/test_scanner.py — file discovery and exclusion tests
- tests/test_parser.py — tree-sitter grammar loading + parse tests
- tests/test_normalizer.py — token extraction and normalisation tests
- tests/test_extractor.py — fragment extraction tests
- tests/test_fingerprint.py — hash correctness tests
- tests/test_detector.py — Type-1/2/3 detection tests
- tests/reporter/ — reporter test sub-package
- tests/reporter/__init__.py — package marker
- tests/reporter/test_json_reporter.py — JSON report structure tests
- tests/reporter/test_html_reporter.py — HTML report content tests
- htmlcov/ — HTML coverage report output (generated; do not edit)
- pyproject.toml — project metadata, dependencies, and build config (Poetry)
- .pylintrc — pylint configuration (max line length 120, colorized output)
- CHANGELOG.md — version history following Keep a Changelog / SemVer
- README.md — project documentation and usage instructions

## Rules

- Before adding dependencies, check pyproject.toml and use `poetry add <package>` — never edit pyproject.toml manually for dependencies.
- Before making architectural changes, read README.md and CHANGELOG.md.
- Follow SOLID: each module has a single responsibility and depends on abstractions, not concretions.
- Follow DRY: extract shared logic into utilities; never duplicate business logic.
- Prefer composition over inheritance: build behavior by composing small, focused units.
- Use modern Python syntax: type hints, dataclasses, f-strings, `match` statements, and walrus operator where appropriate.
- Max line length is 120 characters (enforced by pylint and black).
- Place all new tests in tests/ mirroring the codeecho/ package structure.
- All new code must achieve pylint 10.00/10 before committing.
- Never modify pyproject.toml `[build-system]`, .pylintrc, or .gitattributes without approval.
- Always use `poetry run <cmd>` — never invoke python, black, pylint, or pytest directly.
- When you create or discover new files, update the Tree above.

## Note-taking

- After each task, log any correction, preference, or pattern learned.
- Write to the matching docs file's "Session learnings" section; if none fits, add to Rules above. One dated line, plain language. e.g. "Team uses dataclasses over namedtuples for value objects (learned 7/5)"
- 3+ related notes → create a new docs/ file, move notes there, update the Tree. Keep this file under 100 lines.
