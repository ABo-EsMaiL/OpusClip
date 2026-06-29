# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-30

### Added
- Pre-flight health checks: Pipeline now validates ffmpeg/ffprobe availability, font paths, and optional GPU encoder support at startup
- Graceful Ctrl+C shutdown: SIGINT/SIGTERM caught in CLI; pipeline completes current step and saves cache before exiting; second interrupt forces immediate exit
- Debug diagnostics: Transcript and prompt character counts printed before LLM API call for easier debugging
- Auto-resume: Cache state auto-saved after every step; pipeline resumes from last completed step by default without requiring a `--resume` flag

### Changed
- `--resume` CLI flag replaced with `--fresh`; pipeline now auto-resumes by default
- `_compress_transcript()` removed from `LLMClipSelector` — full transcript always sent to LLM
- `max_llm_chars` removed from `PipelineConfig`
- `target_width`/`target_height` added to `PipelineConfig` to fix `ASSSubtitleRenderer` config attribute error
- Retry error reporting improved with per-attempt debug output and full traceback on exhaustion
- LLM error diagnostics enhanced: prints `status_code`, `request_id`, `body`; saves raw failed response to disk; reports full exception chain on `ClipSelectionError`

### Fixed
- 4 tests referencing `--resume`/`args.resume` now use `--fresh`/`args.fresh`
- Ruff lint errors (unused import, f-string without placeholders)

### Added
- Phase 1: Repository scaffolded with complete project structure and base configuration.
- Phase 2: Security hardening utilities (`security.py`, `subprocess_utils.py`, `temp_manager.py`, `input_validator.py`) to mitigate static and runtime vulnerabilities.
- Phase 3: Dependency cleanup defining the `FontManager` and `InputProvider` abstraction (font asset bundling deferred per zero-download policy, and concrete providers moved to Phase 4).
- Phase 4: Core Architecture established. Created clean ABCs and dataclass contracts for `TranscriptionProvider`, `ClipSelector`, `FaceDetector`, `SubtitleRenderer`, `VideoRenderer`, and `MetadataGenerator`. Implemented pipeline orchestrator structure without business logic.
- Phase 5: AI Provider Implementations. Ported `WhisperProvider`, `LLMClipSelector`, `LLMMetadataGenerator`, and `SmartDirector`. Refactored face detection to use `MediaPipeFaceDetector` (replacing dlib). Included robust retry logic and VRAM cleanup.
- Base exception hierarchy (`OpusClipError`) and pipeline context definitions.
- CI/CD workflows, pre-commit config, and issue templates.
- Implementation 13-phase workflow defined.
- Phase 6: Rendering pipeline completed. `FFmpegOptimizedRenderer` (single-pass) and `FFmpegLegacyRenderer` (two-pass) implemented. `broll.py`, `validator.py`, `text_cleaner.py`, and `ass_builder.py` completed. Resource leaks fixed with `try/finally` guards. Intermediate scan file eliminated in optimized renderer.
- Phase 7: Integration, CLI & End-to-End pipeline. Concrete `Pipeline` class with 10-step orchestration, progress reporting, and structured error handling. `ProviderFactory` with full dependency injection. `cli.py` with argparse, `__main__.py` entry point. `LocalFileProvider` and `YouTubeProvider` concrete input providers. `PipelineResult` and `ClipResult` dataclasses for structured pipeline output. Progress reporting (`[1/10]...`) for each stage. Audio WAV cleanup after transcription. `pipeline_summary.json` generated per run.
- Phase 8: Performance optimization. Subtitle filter merged into single-pass FFmpeg pipe (eliminated one re-encode pass per clip). `h264_nvenc` hardware encoder support with automatic fallback to `libx264`. `check_encoder_available()` with `lru_cache`. `build_encoder_args()` helper for encoder-specific FFmpeg args. `max_llm_chars` truncation warning when coverage < 50%. `PipelineMetrics` dataclass with per-stage timing, clip render durations, and counters. `--encoder` CLI flag.
- Phase 9: CLI & Batch Processing. `Pipeline.run_batch()` with per-source isolated output dirs and error recovery. `CacheManager` for step-level resume support with source verification. `--resume` CLI flag. Multiple input source support (`nargs="+"`). Optional `tqdm` progress for clip rendering. Output dir naming uses stable hash suffix for collision-free uniqueness.
- Phase 10: Comprehensive test suite. 186 tests across 14 test files covering all 11 phases. Every module includes success and failure paths. Negative-path coverage for invalid configs, malformed URLs, missing fonts, cache corruption, batch failures, and edge cases. `manual_validation_checklist.md` documents 10 runtime scenarios requiring ffmpeg/GPU.
- Phase 11: Complete documentation overhaul. README rewritten with accurate CLI examples, GPU setup guide, troubleshooting section, output structure example, and performance tuning table. `docs/configuration.md` with all PipelineConfig fields, env vars, and CLI flag mapping. `docs/architecture.md` with Mermaid data-flow and dependency-injection diagrams. `docs/api.md` with full API surface reference. CONTRIBUTING.md expanded with dev setup, testing workflow, and project tree. Dockerfile + docker-compose.yml for GPU-capable deployment. `examples/custom_provider.py` and `examples/batch_csv.py`. Added docstrings to all 19 previously undocumented public APIs across 12 files.
- Phase 12: Colab demo notebook (`notebooks/opusclip_demo.ipynb`) — 14-cell polished notebook using production `opusclip` package. Sections: install, config, source selection, pipeline execution, results preview, download, troubleshooting.
- Phase 13: Final polish. Removed remaining TODO markers. Default LLM changed to `opencode.ai/zen/v1` + `deepseek-v4-flash-free`. Hardcoded API key removed from notebook. `docs/release-checklist.md` created. `PROJECT_PROGRESS.md` finalized. `git tag v1.0.0`.
