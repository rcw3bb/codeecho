# Changelog

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
