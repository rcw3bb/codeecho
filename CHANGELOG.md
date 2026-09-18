# Changelog

## 1.2.0 - 2026-09-18

### Added

- `config.ini` (seeded into `CODEECHO_CONFIG_DIR`) with an `[override]` section that lets you rename
  the `.ignore` file via the `ignore-file` key. Falls back to the bundled `.ignore` when the
  configured file is missing.
- `--target-list` flag: treat `PATH` as a single file listing scan targets, one per line (blank
  lines and `#`-prefixed comments are skipped), instead of passing `PATH` arguments directly.
- `--basis` flag: file listing basis target paths, one per line — same format as
  `--target-list`. Absolute file/directory entries are merged into the scan automatically
  and matched exactly; relative entries (e.g. a bare filename) are matched by filename/suffix
  against any file discovered in the scan. The report is filtered to only clone groups
  touching at least one basis file, and groups duplicated purely among basis files are
  flagged (`basis_internal` in JSON, a "Basis-to-Basis" badge in HTML, `is_basis` per member).

## 1.1.0 - 2026-08-15

### Added

- Gosu (`.gs`, `.gsx`) is now parsed with a dedicated [tree-sitter-gosu](https://github.com/rcw3bb/tree-sitter-gosu)
  grammar instead of the Java fallback, enabling accurate fragment extraction using Gosu-native node types
  (`compilation_unit`, `function_declaration`, `constructor_declaration`, `class_declaration`).

## 1.0.1 - 2026-07-10

### Fixed

- Type-3 clone detection no longer flags fragments as clones when one is nested inside the other
  within the same file (e.g. a `function` inside its enclosing `class`).
- Type-3 clone groups now drop outer/container fragments (e.g. a whole-`file` fragment) when a
  more specific nested fragment from the same file is already a member of that group, preventing
  false positives caused by union-find transitivity.

## 1.0.0 - 2026-07-10

### Added

- Initial release of codeecho.
