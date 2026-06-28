# Tasks: Production-Grade Engineering Audit & Refactoring

**Input**: Design documents from `/specs/001-production-audit-refactor/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/audit-report-schema.md, quickstart.md, audit-report.md

**Tests**: Tests are included as Phase 11 per the user's explicit requirement. Tests verify actual behavior — no fake results.

**Organization**: Tasks are grouped by implementation phase (matching plan.md's 11-phase git workflow). Each phase maps to audit-report.md findings and spec.md user stories. The three spec user stories (US1=Audit, US2=Blueprint, US3=Roadmap) are already complete as planning artifacts. The implementation tasks below execute the roadmap produced by US3.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[USx]**: Which user story this task delivers against
- Include exact file paths in descriptions
- **Definition of Done**: A task is only considered complete when its file changes have been validated statically and all its acceptance criteria are fully met.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository scaffolding, project structure, configuration management, and environment setup. Creates the foundation every subsequent phase depends on.

- [ ] T001 Create `src/opusclip/__init__.py` and `src/opusclip/py.typed` marker for the package root
- [ ] T002 Create `src/opusclip/config.py` — define `PipelineConfig` dataclass centralizing all magic numbers with a strict hierarchy (defaults → config file → `.env` → CLI arguments). Addresses audit CODE-002
- [ ] T003 [P] Create `src/opusclip/exceptions.py` — define exception hierarchy: `OpusClipError` (base), `ConfigurationError`, `TranscriptionError`, `ClipSelectionError`, `FaceDetectionError`, `RenderingError`, `MetadataError`, `InputValidationError`
- [ ] T004 [P] Create `src/opusclip/context.py` — define `PipelineContext` dataclass holding video metadata (path, width, height, fps, duration), transcript data, selected clips, render state, and output directory. Addresses audit ARCH-001
- [ ] T005 [P] Create `.env.example` with all required environment variables (`OPUSCLIP_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `WHISPER_MODEL`, `WHISPER_DEVICE`, `OUTPUT_DIR`, `LOG_LEVEL`)
- [ ] T006 [P] Create `pyproject.toml` with project metadata, Python >=3.10 requirement, console_scripts entry point `opusclip`, and dev dependencies (pytest, mypy, ruff)
- [ ] T007 Update `requirements.txt` to pin exact minimum versions per research.md Decision 6 (`faster-whisper>=1.0.0`, `mediapipe>=0.10.9`, `opencv-python-headless>=4.9.0`, `openai>=1.12.0`, `yt-dlp>=2023.12.30`, `numpy>=1.26.4`, `torch>=2.0.0,<3.0.0`)
- [ ] T008 [P] Create `requirements-dev.txt` with `pytest>=8.0`, `pytest-cov>=4.1`, `mypy>=1.8`, `ruff>=0.3.0`
- [ ] T009 Update `.gitignore` to include `*.ass`, `*.wav`, `opusclip_output/`, `__pycache__/`, `.env`, `*.egg-info/`, `dist/`, `build/`, `temp/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`
- [ ] T009a [P] Create `src/opusclip/__version__.py` to define the package version
- [ ] T009b [P] Create `.github/workflows/ci.yml` to define GitHub Actions CI for linting, type checking, and test execution
- [ ] T009c [P] Create `.pre-commit-config.yaml` to enforce formatting (ruff) and type checking locally
- [ ] T009d [P] Create `.gitattributes` to normalize line endings and `.github/CODEOWNERS` to enforce code review
- [ ] T009e [P] Create `.github/PULL_REQUEST_TEMPLATE.md` and basic `.github/ISSUE_TEMPLATE/` structure
- [ ] T009f [P] Create `.github/dependabot.yml` for automated dependency updates

**Checkpoint**: Project skeleton exists. `pip install -e .` would succeed (no business logic yet). All configuration is externalized. CI, pre-commit, and repository standards are fully configured.

---

## Phase 2: Security Hardening (Priority: P1)

**Purpose**: Address all Critical and High security findings from audit-report.md before any other code changes. Corresponds to plan.md Phase 1 - Security.

**Addresses**: SEC-001, SEC-002, SEC-003, SEC-004, ARCH-002 (partial)

- [ ] T010 [US3] Create `src/opusclip/security.py` — implement `load_api_key()` that reads `OPUSCLIP_API_KEY` from environment, raises `ConfigurationError` if missing. Addresses SEC-001 (hardcoded API key at L211)
- [ ] T011 [US3] Create `src/opusclip/subprocess_utils.py` — implement `run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess` and `run_ytdlp(args: list[str]) -> subprocess.CompletedProcess` using list-based `subprocess.run()` with no `shell=True`. Addresses SEC-002 (`_sh()` at L39-44)
- [ ] T012 [P] [US3] Create `src/opusclip/temp_manager.py` — implement `TempDir` context manager wrapping `tempfile.mkdtemp(prefix="opusclip_")` with automatic cleanup in `__exit__`. Addresses SEC-003 (hardcoded `/tmp/` at L99, L100, L981)
- [ ] T013 [US3] Create `src/opusclip/input_validator.py` — implement `validate_video_path(path: str) -> Path` (resolves symlinks, checks extension, verifies parent directory) and `validate_youtube_url(url: str) -> str` (parses with `urllib.parse`, validates scheme and netloc). Addresses SEC-004 (no validation at L259-282)

**Checkpoint**: All Critical security findings are remediated. No secrets in source. No `shell=True`. No predictable temp paths. Input is validated.

---

## Phase 3: Dependency Cleanup

**Purpose**: Bundle fonts, remove Colab platform coupling, eliminate runtime downloads. Corresponds to plan.md Phase 2 - Dependency Cleanup.

**Addresses**: DEP-001, DEP-002, ARCH-002, CODE-008

- [ ] T014 [US3] Create `fonts/` directory and bundle all TTF files: `Tajawal-ExtraBold.ttf`, `Tajawal-Bold.ttf`, `Montserrat-ExtraBold.ttf`, `Montserrat-Bold.ttf`, `Amiri-Regular.ttf`, and Noto Sans Arabic subset. Include `fonts/OFL.txt` license file. Addresses DEP-001 (runtime font downloads at L59-126)
- [ ] T015 [US3] Create `src/opusclip/fonts.py` — implement `FontManager` class that resolves font paths from the bundled `fonts/` directory relative to the package root, with a `get_font_path(name: str) -> Path` method. Replaces the runtime download logic and `fc-match` diagnostic block (CODE-008 at L173-191)
- [ ] T016 [US3] Create `src/opusclip/input/__init__.py`, `src/opusclip/input/base.py` — define `InputProvider` abstract base class with `acquire(source: str, output_dir: Path) -> VideoMetadata` method. Create `src/opusclip/input/youtube.py` — implement `YouTubeProvider(InputProvider)` wrapping yt-dlp via `subprocess_utils.run_ytdlp()`. Create `src/opusclip/input/local.py` — implement `LocalFileProvider(InputProvider)` with path validation via `input_validator.validate_video_path()`. Addresses ARCH-002 (Colab `google.colab.files` at L260, L1285)

**Checkpoint**: No runtime font downloads. No Colab imports. All fonts bundled with SIL OFL license. Input providers are abstracted.

---

## Phase 4: Core Architecture

**Purpose**: Scaffold the modular structure with abstract base classes for all AI providers. Corresponds to plan.md Phase 3 - Architecture.

**Addresses**: ARCH-001, ARCH-003

- [ ] T017 [US2] Create `src/opusclip/transcription/__init__.py` and `src/opusclip/transcription/base.py` — define `TranscriptionProvider` ABC with methods: `transcribe(audio_path: Path, language: str) -> TranscriptResult`, `cleanup() -> None`. Define `TranscriptResult` dataclass with `segments`, `words`, `language`, and `duration` fields
- [ ] T018 [P] [US2] Create `src/opusclip/clip_selection/__init__.py` and `src/opusclip/clip_selection/base.py` — define `ClipSelector` ABC with method: `select_clips(transcript: TranscriptResult, config: PipelineConfig) -> list[ClipCandidate]`. Define `ClipCandidate` dataclass with `start`, `end`, `score`, `title`, and `summary` fields
- [ ] T019 [P] [US2] Create `src/opusclip/face_detection/__init__.py` and `src/opusclip/face_detection/base.py` — define `FaceDetector` ABC with methods: `detect(frame: np.ndarray) -> list[FaceResult]`, `is_speaking(face: FaceResult) -> bool`. Define `FaceResult` dataclass with `bbox`, `landmarks`, `mouth_open_score` fields
- [ ] T020 [P] [US2] Create `src/opusclip/subtitle/__init__.py` and `src/opusclip/subtitle/base.py` — define `SubtitleRenderer` ABC with method: `render(words: list[WordTiming], clip_start: float, clip_end: float, config: PipelineConfig) -> Path`. Define `WordTiming` dataclass
- [ ] T021 [P] [US2] Create `src/opusclip/rendering/__init__.py` and `src/opusclip/rendering/base.py` — define `VideoRenderer` ABC with method: `render_clip(context: PipelineContext, clip: ClipCandidate, subtitle_path: Path) -> RenderedClip`. Define `RenderedClip` dataclass with `path`, `thumbnail_path`, `duration`, `resolution` fields
- [ ] T022 [P] [US2] Create `src/opusclip/metadata/__init__.py` and `src/opusclip/metadata/base.py` — define `MetadataGenerator` ABC with method: `generate(clip: ClipCandidate, transcript_excerpt: str, config: PipelineConfig) -> ClipMetadata`. Define `ClipMetadata` dataclass with `title`, `description`, `hashtags`, `category` fields
- [ ] T023 [US2] Create `src/opusclip/pipeline.py` — implement `Pipeline` class that accepts all providers via constructor injection, orchestrates the full pipeline (input → transcription → clip selection → face detection → rendering → subtitle → metadata → output), and passes `PipelineContext` between stages. Addresses ARCH-001 (global state) and ARCH-003 (no provider abstraction)

**Checkpoint**: Full modular architecture scaffolded. All AI-dependent modules have abstract interfaces. `Pipeline` class accepts injected providers. No business logic implemented yet — only contracts.

---

## Phase 5: AI Provider Implementations

**Purpose**: Implement concrete providers behind the abstract interfaces. Migrate face detection from dlib to MediaPipe. Corresponds to plan.md Phase 4 - AI Providers.

**Addresses**: AI-001, AI-002, PERF-001

- [ ] T024 [US2] Create `src/opusclip/transcription/whisper_provider.py` — implement `WhisperProvider(TranscriptionProvider)` wrapping `faster-whisper` with `large-v3` model. Port transcription logic from Cell 4 (L325-376). Include VRAM cleanup via `torch.cuda.empty_cache()`
- [ ] T025 [US2] Create `src/opusclip/transcription/word_repair.py` — port `fill_missing_words()` from Cell 6 (L648-703) as a standalone function. Remove dead commented-out code block (CODE-004 at L680-687). Remove unused `_BAD_CHARS` regex (CODE-005 at L572-591). Remove unused `subtitle_font()` function (CODE-006 at L638-640)
- [ ] T026 [US2] Create `src/opusclip/clip_selection/llm_selector.py` — implement `LLMClipSelector(ClipSelector)` wrapping `openai` SDK with configurable `base_url` and `model`. Port clip selection logic from Cell 5 (L481-541) including the 3-attempt retry loop
- [ ] T027 [US2] Create `src/opusclip/face_detection/mediapipe_detector.py` — implement `MediaPipeFaceDetector(FaceDetector)` using `mediapipe.tasks.vision.FaceLandmarker` with `output_face_blendshapes=True`. Map `jawOpen` blendshape to `mouth_open_score`. Convert normalized coordinates to pixel coordinates. Addresses AI-001 (100MB model for 2 points) and PERF-001 (CPU-bound dlib HOG)
- [ ] T028 [P] [US2] Create `src/opusclip/face_detection/smart_director.py` — port `SmartDirector` class from Cell 6 (L870-921) as a standalone module. Accept `FaceResult` objects instead of raw dlib rectangles. Recalibrate `speaking_mar` threshold for MediaPipe blendshape scale (0.0-1.0)
- [ ] T029 [US2] Create `src/opusclip/metadata/llm_metadata.py` — implement `LLMMetadataGenerator(MetadataGenerator)` wrapping `openai` SDK. Port `gen_meta()` from Cell 7 (L1217-1249). Add 3-attempt retry logic with exponential backoff. Mark failures explicitly with `{"_error": str(e)}` instead of empty dict. Addresses REL-004

**Checkpoint**: All AI providers implemented behind interfaces. dlib replaced with MediaPipe. Dead code removed. Retry logic added to metadata generation.

**Manual Validation Step**: User should run `python -c "import mediapipe"` on the target server to verify MediaPipe installs correctly.

---

## Phase 6: Rendering Pipeline

**Purpose**: Decompose the god function, fix resource leaks, implement subtitle and video rendering. Corresponds to plan.md Phase 5 - Rendering.

**Addresses**: CODE-001, REL-005, PERF-002, PERF-003, CODE-009

- [ ] T030 [US2] Create `src/opusclip/subtitle/text_cleaner.py` — port `clean_for_subtitle()` and `is_arabic_text()` from Cell 6 (L593-635). Do NOT port the unused `_BAD_CHARS` regex or `subtitle_font()` function
- [ ] T031 [US2] Create `src/opusclip/subtitle/ass_builder.py` — port `build_ass()` from Cell 6 (L714-900). Remove debug print statements at L779-780 (CODE-007). Use `FontManager` for font paths instead of hardcoded system paths. Accept `PipelineConfig` for style parameters
- [ ] T032 [US2] Create `src/opusclip/rendering/ffmpeg_renderer.py` — implement `FFmpegRenderer(VideoRenderer)`. Decompose `render_clip()` (L961-1159) into helper methods: `_extract_clip()`, `_scan_faces()`, `_render_smart_crop()`, `_burn_subtitles()`. Addresses CODE-001 (god function)
- [ ] T033 [US2] In `src/opusclip/rendering/ffmpeg_renderer.py` — wrap the FFmpeg raw-pipe `Popen` block in `try/finally` ensuring `ffpipe.stdin.close()` and `ffpipe.wait()` are always called, and `raw_cap.release()` is always invoked. Addresses REL-005 (zombie FFmpeg process) and CODE-003 (bare except)
- [ ] T034 [US2] In `src/opusclip/rendering/ffmpeg_renderer.py` — eliminate the intermediate `scan_path` disk file (PERF-003). Feed 480p frames directly via FFmpeg pipe for face detection instead of writing/reading a temporary mp4. Log a warning when `fi >= len(frame_data)` instead of silently using `frame_data[-1]` (CODE-009)
- [ ] T035 [P] [US2] Create `src/opusclip/rendering/broll.py` — port B-roll/blurred-background generation from Cell 6 (L839-863) as a standalone function. Centralize `bd = 5` border width in `PipelineConfig`
- [ ] T035a [US2] Create `src/opusclip/rendering/validator.py` — implement output validation using `ffprobe` to strictly verify final video resolution, codec, duration, and FPS before marking a clip as successfully rendered

**Checkpoint**: `render_clip()` decomposed into 4 focused functions. Output strictly validated. FFmpeg resource leak fixed. No zombie processes. Scan file eliminated. Debug prints removed.

**Manual Validation Step**: User should render a single test clip on the target server and compare output quality (1080x1920, CRF 18-22, subtitle alignment) with the original notebook output.

---

## Phase 7: Reliability & Logging

**Purpose**: Replace all `print()` with structured logging. Add retry logic, cleanup, and exception recovery. Corresponds to plan.md Phase 6 - Reliability.

**Addresses**: REL-001, REL-002, REL-003, REL-004, CODE-003, CODE-007

- [ ] T036 [US3] Create `src/opusclip/logging_config.py` — configure Python `logging` module with `JSONFormatter` for structured output to console AND a `RotatingFileHandler` for persistent file logging. Define log levels per module. Addresses REL-002
- [ ] T037 [US3] In `src/opusclip/pipeline.py` — add audio WAV cleanup: delete `audio.wav` immediately after transcription completes and JSON is saved. Addresses REL-003 (460MB WAV file never deleted)
- [ ] T038 [US3] In `src/opusclip/rendering/ffmpeg_renderer.py` — add `try/finally` cleanup block for all intermediate files (`raw_path`, `silent_path`, `audio_path`, `safe_ass`). Replace bare `except: pass` with `except OSError as e: logger.warning(...)`. Addresses REL-001 and CODE-003
- [ ] T039 [US3] In `src/opusclip/pipeline.py` — wrap transcription and clip-selection stages in pipeline-stage functions with structured error handling. On failure, emit structured log and allow downstream stages to skip gracefully. Addresses PROD-002
- [ ] T039a [US3] Create `src/opusclip/core/cache.py` — implement `CacheManager` to handle JSON cache files with explicit support for invalidation, state recovery, and force-refresh logic
- [ ] T039b [US3] In `src/opusclip/pipeline.py` — implement pre-flight health checks: validate config before startup, verify FFmpeg binary is installed and executable, verify CUDA/GPU availability (if configured), and verify font paths
- [ ] T039c [US3] In `src/opusclip/cli.py` and `src/opusclip/pipeline.py` — implement graceful shutdown on `Ctrl+C` (SIGINT/SIGTERM). Ensure any running FFmpeg processes are cleanly terminated and intermediate states are written to the cache before exiting

**Checkpoint**: All `print()` replaced with structured logging and file logging. Audio WAV cleaned up after use. Intermediate files cleaned on failure. Cache management formalized. Pipeline performs pre-flight checks and recovers gracefully. Ctrl+C shuts down safely.

---

## Phase 8: Performance Optimization

**Purpose**: Optimize encoding pipeline and evaluate hardware acceleration. Corresponds to plan.md Phase 7 - Performance.

**Addresses**: PERF-002, PERF-003

- [ ] T040 [US3] In `src/opusclip/rendering/ffmpeg_renderer.py` — evaluate merging the `subtitles=` filter into the raw-pipe FFmpeg step to eliminate the second full re-encode pass. If merge is feasible, implement single-pass render. If not feasible due to filter_complex constraints, document the technical reason and keep two-pass. Addresses PERF-002
- [ ] T041 [US3] In `src/opusclip/config.py` — add `encoder` field to `PipelineConfig` (default: `libx264`). In `src/opusclip/rendering/ffmpeg_renderer.py` — add `h264_nvenc` path that is used when `encoder=nvenc` and NVIDIA GPU is detected. Fall back to `libx264` if `h264_nvenc` is unavailable. Addresses PERF-002 research recommendation
- [ ] T042 [US3] In `src/opusclip/clip_selection/llm_selector.py` — make `max_chars` configurable via `PipelineConfig` (default: 28000). Add a log warning when the transcript is truncated to less than 50% coverage, documenting the coverage gap for 4-hour videos. Addresses scalability analysis Section 9
- [ ] T042a [US3] Create `src/opusclip/metrics.py` — implement runtime metrics collection (processing time, Real-Time Factor, GPU/Memory usage estimations, API retries, failure counts) and output a performance report at the end of the pipeline

**Checkpoint**: Encoding pipeline optimized. Hardware acceleration supported where available. LLM context window configurable. Runtime metrics collected.

**Manual Validation Step**: User should compare rendering speed (wall-clock time per clip) before and after on the target server. Output quality must be visually identical.

---

## Phase 9: CLI & Batch Processing

**Purpose**: Build CLI application capable of processing multiple videos. Corresponds to plan.md Phase 8 - CLI.

**Addresses**: PROD-001, PROD-002, ARCH-001

- [ ] T043 [US3] Create `src/opusclip/cli.py` — implement CLI using `argparse` with subcommands: `process` (single video), `batch` (multiple videos from file/arguments). Accept `--output-dir`, `--language`, `--model`, `--encoder`, `--max-clips`, `--log-level`. Derive per-video output subdirectories from URL hash or filename
- [ ] T044 [US3] Create `src/opusclip/__main__.py` — entry point for `python -m opusclip` that delegates to `cli.py`
- [ ] T045 [US3] In `src/opusclip/pipeline.py` — implement batch orchestration: accept `list[str]` of video sources, process each in an isolated `PipelineContext` with independent output directory and error recovery. A failure in one video must not abort the batch
- [ ] T045a [US3] In `src/opusclip/cli.py` and `pipeline.py` — implement `--resume` flag to automatically recover and continue from the last successful stage using `CacheManager` state
- [ ] T045b [US3] Integrate `tqdm` (or similar progress reporting) into the CLI to provide visual feedback for long-running operations (transcription, rendering)
- [ ] T045c [US3] Create `src/opusclip/provider_factory.py` — implement a provider registry/factory to dynamically resolve and instantiate concrete AI providers based on CLI/Config values

**Checkpoint**: `python -m opusclip process "https://youtube.com/..."` works end-to-end with progress reporting and resume capability. Providers dynamically resolved. Batch mode processes multiple videos independently.

**Manual Validation Step**: User should run `python -m opusclip process --help` to verify CLI structure, then process a test video on the target server.

---

## Phase 10: Testing

**Purpose**: Write unit tests and integration tests for all modules. Corresponds to plan.md Phase 9 - Testing.

- [ ] T046 [P] Create `tests/__init__.py` and `tests/conftest.py` with shared fixtures (mock `PipelineConfig`, sample transcript data, sample `FaceResult`)
- [ ] T047 [P] Create `tests/unit/test_config.py` — test `PipelineConfig` construction, `from_env()` loading, default values, and validation of invalid inputs
- [ ] T048 [P] Create `tests/unit/test_input_validator.py` — test path traversal rejection, valid/invalid YouTube URLs, safe filename resolution
- [ ] T049 [P] Create `tests/unit/test_text_cleaner.py` — test Arabic cleaning, emoji removal, whitelist pass-through, edge cases (empty string, only emojis)
- [ ] T050 [P] Create `tests/unit/test_word_repair.py` — test `fill_missing_words()` with known gap scenarios, no-gap scenarios, and edge cases (empty segments)
- [ ] T051 [P] Create `tests/unit/test_ass_builder.py` — test ASS file generation for Arabic-only, English-only, and bilingual clips. Verify correct style selection and karaoke timing
- [ ] T052 [P] Create `tests/unit/test_smart_director.py` — test `SmartDirector` state transitions: no-face → single-face → multi-face → speaking detection
- [ ] T053 [P] Create `tests/unit/test_temp_manager.py` — test `TempDir` creation, cleanup on normal exit, cleanup on exception
- [ ] T054 [P] Create `tests/unit/test_font_manager.py` — test font path resolution for all bundled fonts, missing font error
- [ ] T055 Create `tests/unit/test_exceptions.py` — test exception hierarchy and `OpusClipError` base class
- [ ] T056 Create `tests/integration/test_pipeline_config.py` — test full pipeline construction with all providers injected, verify no import errors
- [ ] T057 Create `tests/integration/test_cli.py` — test CLI argument parsing, `--help` output, invalid argument rejection
- [ ] T058 Create `tests/manual_validation_checklist.md` — document manual tests that require the target server: transcription accuracy, subtitle sync, crop quality, batch processing, 4-hour video handling

**Checkpoint**: All unit tests pass. Integration tests verify module composition. Manual validation checklist documents what requires runtime testing.

**Manual Validation Step**: User should run `pytest tests/ -v --tb=short` on the target server to verify all tests pass.

---

## Phase 11: Documentation

**Purpose**: Finalize all documentation to production quality. Corresponds to plan.md Phase 10 - Documentation.

- [ ] T059 [P] Update `README.md` — add: architecture diagram (Mermaid), full CLI usage examples, environment variable reference table, performance notes, limitations, FAQ, troubleshooting section, repository structure tree
- [ ] T060 [P] Create `docs/architecture.md` and `docs/api.md` — detailed module dependency diagram (Mermaid), provider interface documentation, developer API surface, data flow through the pipeline, extension points
- [ ] T061 [P] Update `CONTRIBUTING.md` — add: development setup instructions, testing workflow, code style guidelines (ruff config), PR template, phase-based workflow explanation
- [ ] T062 [P] Create `docs/configuration.md` — complete reference for all `PipelineConfig` fields, environment variables, and their defaults
- [ ] T063 Review all `src/opusclip/**/*.py` modules for complete docstrings on every public class and function. Add missing docstrings
- [ ] T063a [P] Create `Dockerfile` and `docker-compose.yml` defining a production-ready containerized environment with GPU passthrough support
- [ ] T063b [P] Create `examples/` directory containing practical scripts demonstrating pipeline usage (e.g., `examples/custom_provider.py`, `examples/batch_csv.py`)

**Checkpoint**: README is publication-quality. Architecture, API, and Docker environments documented. Examples provided. All public APIs have docstrings.

---

## Phase 12: Final Notebook

**Purpose**: Create a polished Google Colab demonstration notebook. Corresponds to plan.md Phase 11 - Final Notebook. This phase executes ONLY after all previous phases are complete and reviewed.

- [ ] T064 Create `notebooks/opusclip_demo.ipynb` — polished Colab notebook with sections: Introduction, Dependency Installation (`pip install -r requirements.txt`), Environment Configuration (API key setup), Upload/YouTube Mode, Pipeline Execution, Download Results, Troubleshooting. The notebook must import and use the production `opusclip` package — no duplicated business logic

**Checkpoint**: Notebook runs on Google Colab and produces identical output to the CLI pipeline.

**Manual Validation Step**: User should upload the notebook to Google Colab, install dependencies, and process a test video to verify end-to-end functionality.

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Final review, cleanup, and repository quality assurance.

- [ ] T065 Review every `src/opusclip/**/*.py` file — remove any remaining TODOs, debug prints, dead code, or placeholder logic
- [ ] T066 Run `ruff check src/ tests/` and `mypy src/` — fix all linting and type errors
- [ ] T067 [P] Update `CHANGELOG.md` with complete history of all 11 implementation phases
- [ ] T068 [P] Update `PROJECT_PROGRESS.md` to 100% completion with all commit hashes
- [ ] T069 Verify all 30 audit findings from audit-report.md have been addressed — cross-reference each finding ID against implementation. Document any findings intentionally deferred
- [ ] T070 Run `quickstart.md` validation scenarios 1-6 against the final codebase
- [ ] T070a Run packaging validation (`python -m build`, `twine check`, or `pip install -e .`) to ensure the package builds correctly for distribution
- [ ] T070b Create `docs/release-checklist.md` as the final Production Release Checklist, verifying all QA steps are met
- [ ] T071 Final `git tag v1.0.0` and prepare repository for public release

**Checkpoint**: Repository is production-ready. All audit findings addressed. All tests pass. Documentation and release artifacts complete. Ready for public release.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Security)**: Depends on Phase 1 — security modules use config and exceptions
- **Phase 3 (Dependencies)**: Depends on Phase 2 — font bundling and input providers use security utilities
- **Phase 4 (Architecture)**: Depends on Phase 1 — ABCs use config and context dataclasses
- **Phase 5 (AI Providers)**: Depends on Phase 4 — concrete providers implement ABCs
- **Phase 6 (Rendering)**: Depends on Phase 5 — renderer uses face detector and subtitle builder
- **Phase 7 (Reliability)**: Depends on Phase 6 — logging and cleanup integrate into pipeline and renderer
- **Phase 8 (Performance)**: Depends on Phase 7 — optimizations layer on top of reliable renderer
- **Phase 9 (CLI)**: Depends on Phase 7 — CLI orchestrates the complete pipeline
- **Phase 10 (Testing)**: Depends on Phase 9 — tests cover all implemented modules
- **Phase 11 (Documentation)**: Depends on Phase 10 — docs describe final architecture and API
- **Phase 12 (Notebook)**: Depends on Phase 11 — notebook uses documented production package
- **Phase 13 (Polish)**: Depends on all previous phases

### Parallel Opportunities Within Phases

- **Phase 1**: T003, T004, T005, T006, T008 can all run in parallel
- **Phase 2**: T012 can run in parallel with T010/T011
- **Phase 4**: T018, T019, T020, T021, T022 can all run in parallel (independent ABCs)
- **Phase 5**: T028 can run in parallel with T027
- **Phase 6**: T035 can run in parallel with T030-T034
- **Phase 10**: T047-T055 can all run in parallel (independent test files)
- **Phase 11**: T059-T062 can all run in parallel (independent documentation files)

---

## Parallel Example: Phase 4 (Architecture)

```bash
# Launch all ABC definitions in parallel:
Task T017: "TranscriptionProvider ABC in src/opusclip/transcription/base.py"
Task T018: "ClipSelector ABC in src/opusclip/clip_selection/base.py"
Task T019: "FaceDetector ABC in src/opusclip/face_detection/base.py"
Task T020: "SubtitleRenderer ABC in src/opusclip/subtitle/base.py"
Task T021: "VideoRenderer ABC in src/opusclip/rendering/base.py"
Task T022: "MetadataGenerator ABC in src/opusclip/metadata/base.py"

# Then sequentially:
Task T023: "Pipeline orchestrator in src/opusclip/pipeline.py" (depends on all ABCs)
```

---

## Implementation Strategy

### Entry and Exit Conditions

Every phase MUST adhere to the following lifecycle boundaries:
- **Entry Condition**: The previous phase's PR has been merged by the user. A new branch is created from `main`.
- **Exit Condition**: All tasks are complete, `PROJECT_PROGRESS.md` and `CHANGELOG.md` are updated, all tests pass, and a PR is opened for user review.

### Git Branch Workflow (Mandatory)

Each phase creates its own branch (e.g., `feature/phase-01-setup`). **Never commit directly to `main`.**

Commits must follow **Conventional Commits** (e.g., `feat:`, `fix:`, `refactor:`, `docs:`). Every commit message must be meaningful. Do NOT squash commits before opening the PR.

### Phase Completion & Pause Points

After finishing **every phase**, the agent MUST:
1. Update `PROJECT_PROGRESS.md` with completion percentage, commit hash, and summary.
2. Update `CHANGELOG.md` with user-facing changes.
3. Create clean, Conventional Commits.
4. Push the branch to GitHub.
5. Open (or prepare) a Pull Request into `main`. The PR must contain a short summary of changes.
6. **STOP and wait for user approval**. Never merge automatically. Never delete branches automatically.

### MVP Scope

- Phase 1 + Phase 2 + Phase 3 = Minimum viable safe foundation
- Add Phase 4 + Phase 5 + Phase 6 = Full pipeline with modular architecture
- Add Phase 7 + Phase 8 = Production-grade reliability and performance
- Add Phase 9 = CLI application ready for deployment

### Audit Finding Coverage

| Finding | Addressed By Task(s) |
|---------|---------------------|
| ARCH-001 | T004, T023 |
| ARCH-002 | T016 |
| ARCH-003 | T017-T022 |
| CODE-001 | T032 |
| CODE-002 | T002 |
| CODE-003 | T033, T038 |
| CODE-004 | T025 |
| CODE-005 | T025 |
| CODE-006 | T025 |
| CODE-007 | T031 |
| CODE-008 | T015 |
| CODE-009 | T034 |
| PERF-001 | T027 |
| PERF-002 | T040, T041 |
| PERF-003 | T034 |
| AI-001  | T027 |
| AI-002  | T025 |
| DEP-001 | T014 |
| DEP-002 | T014, T015 |
| REL-001 | T038 |
| REL-002 | T036 |
| REL-003 | T037 |
| REL-004 | T029 |
| REL-005 | T033 |
| SEC-001 | T010 |
| SEC-002 | T011 |
| SEC-003 | T012 |
| SEC-004 | T013 |
| PROD-001 | T043, T045 |
| PROD-002 | T039 |

---

## Notes

- [P] tasks = different files, no dependencies — safe to parallelize
- [USx] label maps task to spec.md user story for traceability
- All 30 audit findings are mapped to specific tasks in the coverage table above
- Every phase must be committed before the next begins
- The agent must STOP after each phase and wait for user approval
- No runtime execution, model loading, or benchmarking by the agent
- Manual validation steps document what requires user testing on the target server
