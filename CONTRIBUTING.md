# Contributing to OpusClip

Thank you for your interest in contributing! This project follows a strict
set of engineering and repository standards.

## Development Setup

```bash
git clone https://github.com/ABo-EsMaiL/OpusClip.git
cd OpusClip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pip install -r requirements.txt
```

### External Dependencies

- **FFmpeg** (with ffprobe) — required at runtime. Install via your package
  manager or download from [ffmpeg.org](https://ffmpeg.org/).
- **yt-dlp** — required for YouTube input. Install via pip (`pip install yt-dlp`).
- **NVIDIA GPU + CUDA** — optional, but recommended for Whisper and NVENC.

## Code Quality Standards

- **SOLID Principles**: Keep modules small and single-purpose.
- **Type Hints**: All function signatures must be fully type-hinted.
- **Dataclasses**: Use `dataclasses` for all state and configuration objects.
- **Print-based progress**: Use `print()` for user-facing progress (`[1/10]`).
  Do not introduce logging frameworks.
- **Dependency Injection**: Pass dependencies explicitly via constructors.
  No hidden global state.
- **Security**: Never hardcode secrets. Use `load_api_key()` from `security.py`.
  Always use list-based `subprocess.run()` — never `shell=True`.

## Linting and Formatting

This project uses **ruff** for linting:

```bash
ruff check src/ tests/
ruff check --fix src/ tests/   # auto-fix where possible
```

Configuration is in `pyproject.toml` (line-length 100, target Python 3.10).

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=opusclip

# Run a specific test file
pytest tests/unit/test_config.py

# Run tests matching a keyword
pytest -k "cache"
```

All tests must pass before committing. Tests are mock-based and require no
GPU, network, FFmpeg, or API keys. See `tests/manual_validation_checklist.md`
for tests that require a full runtime environment.

## Implementation Workflow (13 Phases)

All development occurs in isolated phases. You must not jump ahead or mix
concerns across phases.

1. Each phase has its own branch (`feature/phase-NN`).
2. Branches are created from `main` after the previous phase is merged.
3. Commit messages must follow **Conventional Commits** (`feat:`, `fix:`,
   `refactor:`, `docs:`).
4. Remove all temporary or debug code before committing.
5. Ensure ruff is clean before committing.
6. Update `CHANGELOG.md`, `PROJECT_PROGRESS.md`, and `tasks.md` before
   opening a PR.
7. Never merge automatically. Wait for review.

See `PROJECT_PROGRESS.md` for current phase status and `CHANGELOG.md` for
a summary of all changes.

## Pull Request Process

1. Create a feature branch from `main`.
2. Make your changes with conventional commit messages.
3. Run `ruff check src/ tests/` and `pytest` — both must pass.
4. Open a PR against `main` with a short summary of changes.
5. Wait for review before merging.

## Project Structure

```
OpusClip/
├── src/
│   └── opusclip/          # Package root
│       ├── __init__.py
│       ├── __main__.py    # python -m opusclip entry point
│       ├── cli.py         # CLI argument parser and runner
│       ├── pipeline.py    # Pipeline orchestrator
│       ├── config.py      # PipelineConfig dataclass
│       ├── context.py     # PipelineContext dataclass
│       ├── exceptions.py  # Exception hierarchy
│       ├── security.py    # API key loading
│       ├── provider_factory.py  # Dependency injection
│       ├── metrics.py     # Performance metrics
│       ├── cache.py       # Step-level resume cache
│       ├── fonts.py       # Font management
│       ├── input/         # Video input providers
│       │   ├── base.py
│       │   ├── local.py
│       │   └── youtube.py
│       ├── transcription/ # Speech-to-text
│       │   ├── base.py
│       │   ├── whisper_provider.py
│       │   └── word_repair.py
│       ├── clip_selection/  # AI clip selection
│       │   ├── base.py
│       │   └── llm_selector.py
│       ├── face_detection/  # Face tracking
│       │   ├── base.py
│       │   ├── mediapipe_detector.py
│       │   └── smart_director.py
│       ├── subtitle/        # Subtitle rendering
│       │   ├── base.py
│       │   ├── ass_builder.py
│       │   └── text_cleaner.py
│       ├── rendering/       # Video rendering
│       │   ├── base.py
│       │   ├── ffmpeg_optimized_renderer.py
│       │   ├── ffmpeg_legacy_renderer.py
│       │   ├── validator.py
│       │   └── broll.py
│       └── metadata/        # Metadata generation
│           ├── base.py
│           └── llm_metadata.py
├── tests/
│   ├── unit/               # Unit tests (186 tests)
│   ├── integration/        # Integration tests
│   └── manual_validation_checklist.md
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── configuration.md
└── fonts/                  # Bundled fonts (TTF)
```
