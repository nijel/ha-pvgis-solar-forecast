# Agent Guidelines

## Pre-commit Checks

All agents working on this repository **MUST** run and pass pre-commit checks before completing their work.

### Installation

```bash
pip3 install pre-commit
```

### Running Pre-commit

Before finalizing any work, run:

```bash
pre-commit run --all-files
```

**All checks must pass.** If any check fails:

1. Review the error messages
1. Fix the issues (many hooks auto-fix)
1. Run pre-commit again until all checks pass
1. Commit the fixes

### Pre-commit Hooks

This repository uses the following pre-commit hooks:

- **trailing-whitespace**: Removes trailing whitespace
- **end-of-file-fixer**: Ensures files end with a newline
- **check-merge-conflict**: Detects merge conflict markers
- **check-yaml/json/toml**: Validates file syntax
- **debug-statements**: Detects Python debug statements
- **mixed-line-ending**: Enforces LF line endings
- **pretty-format-json**: Formats JSON files (2-space indent, preserve order)
- **ruff**: Python linting with auto-fix
- **ruff-format**: Python code formatting
- **pretty-format-yaml**: Formats YAML files (2-space indent)
- **pretty-format-toml**: Formats TOML files
- **validate-pyproject**: Validates pyproject.toml
- **mdformat**: Formats Markdown files (with GitHub Flavored Markdown)
- **codespell**: Spell checking

### Important Notes

- Do not commit code that fails pre-commit checks
- Many hooks auto-fix issues - review the changes before committing
- If you add new Python files, ensure they pass ruff linting and formatting
- Test files have relaxed rules (see `pyproject.toml` for per-file-ignores)
