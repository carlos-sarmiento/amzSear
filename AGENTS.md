# Repository Guidelines

## Project Structure & Module Organization

`amzsear/` contains the installable Python package. Core scraping and data models live in
`amzsear/core/`, while the command-line entry point is in `amzsear/cli/cli.py`.
User-facing documentation is under `docs/`, with CLI usage in `docs/cli/README.md` and
MCP usage in `docs/mcp/README.md`. API notes live in `docs/core/`. Build metadata is in
`pyproject.toml`; generated artifacts may appear in `dist/` and should not be hand-edited.

## Build, Test, and Development Commands

Use `uv sync` to create or refresh the local environment from `pyproject.toml` and
`uv.lock`. Run the CLI locally with:

```bash
uv run amzsear "Harry Potter"
uv run amzsear -a B00006IFHD -j
uv run amzsear-mcp --host 127.0.0.1 --port 8765
```

Build distributions with `uv build` or `python -m build` if `build` is installed. Run
`python -m unittest discover -s tests` to execute the current test suite.

## Coding Style & Naming Conventions

This package supports Python 3.10+, so avoid syntax that requires newer versions. Follow the
existing style: four-space indentation, module-level classes for product/search concepts,
and `snake_case` for functions and variables. Existing public classes use names such as
`AmzSear`, `AmzProduct`, and `AmzRating`; keep those API names stable unless a breaking
change is intentional. Prefer explicit exception handling with `FetchError` for network or
scraping failures.

## Testing Guidelines

Add focused tests under `tests/`, using names like `test_cli_json_output.py` or
`test_amzsear_pagination.py`. Avoid live Amazon requests in routine tests; use saved HTML
fixtures or mocked `requests` responses so tests are deterministic.

## Commit & Pull Request Guidelines

Recent commits use short imperative subjects, for example `Fix multi-page search keeping only
last page results` and `Remove legacy code and update to use uv`. Keep commit subjects
specific and under roughly 72 characters when possible. Pull requests should describe the
behavior change, list manual or automated checks run, and include CLI output examples for
changes that affect user-facing commands.

## Agent-Specific Instructions

Before committing Markdown changes, verify formatting with the shared
`markdown-table-aligned` workflow. Keep repository guidance concise and update this file when
new tools, tests, or release steps are added.
