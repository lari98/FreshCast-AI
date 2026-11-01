# Contributing

- Small pull requests against `main`; CI must pass.
- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- Run `ruff format . && ruff check . && mypy && pytest` in `packages/forecasting`.
- Business rules stay free of cloud imports; add a test with every rule change.
