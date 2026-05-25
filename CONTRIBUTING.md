# Contributing to Horizon6AutoGear

Thank you for your interest in contributing. This document covers the basics of setting up a development environment and submitting changes.

## Development Setup

1. **Requirements**: Python >= 3.8

2. **Clone and install** in editable mode with dev dependencies:

   ```bash
   git clone https://github.com/Burlesque1/Horizon6AutoGear.git
   cd Horizon6AutoGear
   pip install -e ".[dev]"
   ```

   This installs the package plus `pytest`, `pytest-cov`, and `ruff`.

3. **Run the GUI** to verify the installation:

   ```bash
   horizon6-autogear
   ```

## Testing

Run the full test suite:

```bash
pytest
```

Run a single test file:

```bash
pytest tests/test_forza.py
```

Run with coverage:

```bash
pytest --cov
```

## Linting

Check for lint errors:

```bash
ruff check .
```

The CI pipeline runs `ruff check . --select E9,F63,F7,F82` (syntax errors, undefined names, and invalid operations). Make sure at least those rules pass before pushing.

## Submitting Changes

### Pull Request Process

1. **Fork** the repository on GitHub.
2. **Create a branch** from `main` with a descriptive name:
   - `feat/short-description` for new features
   - `fix/short-description` for bug fixes
   - `docs/short-description` for documentation changes
3. **Make your changes** and commit with clear, concise messages.
4. **Ensure CI passes.** The pipeline runs on Windows and checks linting, tests, and packaging.
5. **Open a pull request** against `main` on GitHub.

### Commit Messages

- Use the imperative mood ("add feature" not "added feature").
- Keep the first line under 72 characters.
- Reference relevant issues when applicable (e.g., "Fixes #12").

## Code Style

- **Follow existing patterns.** The codebase uses consistent conventions across modules -- match the surrounding code.
- **Ruff rules** are the baseline. Run `ruff check .` and fix any reported issues.
- **Bilingual UI strings** are defined as `[English, Chinese]` arrays in `config.py`. Keep both languages in sync when adding or modifying UI text.
- **Windows-specific code** (keyboard input via `win32api`) lives in `shifting/keyboard.py`. Guard platform-specific imports with `sys_platform` checks so macOS/Linux can still import the rest of the package.

## Project Structure

```
src/horizon6_autogear/
  core/          # Engine, data packet parser, car info model
  shifting/      # Shift algorithm and keyboard input (Windows)
  config/        # Constants, UI strings, tuning parameters
  utils/         # Socket helpers, plotting, logging
  gui/           # Chart widgets, HUD overlay
  gui.py         # pywebview Web GUI entry point
```

## Reporting Issues

- **Bugs**: Open an issue at https://github.com/Burlesque1/Horizon6AutoGear/issues with steps to reproduce, expected behavior, and actual behavior.
- **Feature requests**: Open an issue with a clear description of the use case and proposed behavior.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
