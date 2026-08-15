# Contributing to RA.Aid

Thanks for helping improve RA.Aid! This guide covers setup, the dev loop, and the conventions we follow.

## Requirements

- **Python 3.10+** (the project is developed and tested on **3.12**; see `.python-version`)
- **uv** — the preferred package manager. It installs from `uv.lock`, so
  everyone (and CI) gets the exact same, known-working dependency versions.
  Install it from <https://docs.astral.sh/uv/>.

  > Why `uv`? A plain `pip install -e ".[dev]"` does a *fresh* dependency
  > resolve that ignores `uv.lock`. Some of our dependencies (notably
  > `langgraph` and `fireworks-ai`) have released breaking versions, so a
  > fresh resolve can pull a version that crashes at import time. `uv sync`
  > is deterministic and matches what CI runs.

## Setup

```bash
git clone https://github.com/ai-christianson/RA.Aid.git
cd RA.Aid
make setup-dev        # installs dev deps from uv.lock (falls back to pip if uv is missing)
make setup-hooks      # optional: installs git pre-commit hooks
```

## Configure

Copy the example environment file and add the API key(s) for the provider(s) you use:

```bash
cp .env.example .env
# then edit .env
```

Only the provider you actually call needs a key. See `.env.example` for the
full list (primary providers, the optional `EXPERT_*` sub-agent, and web
research).

## Run the tests

```bash
make test             # pytest with coverage (uses uv run when available)
```

or, targeting a single test:

```bash
uv run python -m pytest tests/path/to/test_file.py::test_name
```

> **Note:** a few file-permission tests (`test_permission_error`,
> `test_write_to_readonly_directory`) are skipped when the test process runs
> as **root**, because root bypasses file permission bits and the
> `PermissionError` under test can never be raised. This is expected in
> containers/CI sandboxes.

## Lint & format

We use [ruff](https://docs.astral.sh/ruff/):

```bash
make check            # ruff check (lint only)
make fix              # sort imports, format, and auto-fix lint issues
```

## Making a change

1. Create a feature branch off `master` (e.g. `fix/agent-retry-backoff`).
2. Make your change and keep commits focused; use imperative commit
   messages (`fix: ...`, `feat: ...`, `test: ...`, `docs: ...`, `ci: ...`).
3. Run `make test` and `make check` — both must pass.
4. Open a pull request against `master` and describe what changed and why.

## Pull request checklist

- [ ] `make test` passes
- [ ] `make check` passes
- [ ] New/changed behaviour is covered by tests
- [ ] If you added or changed dependencies, `uv.lock` is updated (`uv lock`)
- [ ] Docs / `.env.example` updated if user-facing config changed

## Questions?

Full documentation lives at <https://docs.ra-aid.ai>. For anything not
covered here, open an issue or start a discussion.
