# Implementation Plan: Production-Grade Engineering Audit & Refactoring

**Branch**: `001-production-audit-refactor` | **Date**: 2026-06-28 | **Spec**: [spec.md](file:///d:/AI%20Engineer/OpusClip/specs/001-production-audit-refactor/spec.md)

**Input**: Feature specification from `specs/001-production-audit-refactor/spec.md`

## Summary

Perform a comprehensive, analysis-only engineering audit of the existing OpusClip pipeline—a ~1332-line monolithic Jupyter Notebook (`opusclip_v2_1_final.py`) that automates short-video generation from long-form video. The audit produces three deliverables: (1) a structured finding report across 10 review areas, (2) a modular architecture blueprint with replaceable providers, and (3) a prioritized improvement roadmap. No source code is modified.

## Technical Context

**Language/Version**: Python 3.10+ (Colab runtime, migrating to Linux server)

**Primary Dependencies**: faster-whisper, dlib, OpenCV, FFmpeg, openai SDK, yt-dlp, numpy

**Storage**: Local filesystem (JSON cache files for transcript, clips, metadata; intermediate video files)

**Testing**: N/A for audit phase (manual validation of report completeness)

**Target Platform**: Linux server with mid-range GPU (CUDA-capable), migrating from Google Colab

**Project Type**: Analysis/audit deliverable → future CLI pipeline

**Performance Goals**: Pipeline must process up to 4-hour videos within or below real-time on a single mid-range GPU. Output: 1080×1920 clips, CRF 18–22.

**Constraints**: Zero-budget (all dependencies free/FOSS), offline-capable at runtime, no execution on developer machine, prioritize output quality and reliability over raw speed

**Scale/Scope**: Single monolithic file (~1332 lines, 8 notebook cells), 10+ external dependencies, 6+ pipeline stages

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Zero-Cost Policy | All proposed alternatives and dependencies must be free/FOSS | ✅ PASS — audit is analysis-only; all proposed alternatives will be free |
| II. Safety Rules | No automatic execution, downloads, or modifications | ✅ PASS — audit produces documents only; no code execution or downloads |
| II. Safety Rules | No automatic modifications to project files | ✅ PASS — FR-006 explicitly forbids source modifications |
| III. Engineering & Architecture | Prioritize correctness, maintainability, modularity | ✅ PASS — audit evaluates these qualities; blueprint enforces SRP and replaceable providers |
| III. Engineering & Architecture | Replaceable providers for AI components | ✅ PASS — FR-004 requires provider abstractions with ≥2 free alternatives |
| IV. Performance & Reliability | Optimizations must have measurable reasons | ✅ PASS — FR-011/012 define measurable targets (CRF 18–22, ≤ real-time, quality metrics) |
| IV. Compatibility | Backward compatibility preserved | ✅ PASS — FR-010 requires incremental migration with backward compatibility at each step |
| V. Communication | Explain problem/solution/alternatives before changes | ✅ PASS — audit explicitly documents every finding with rationale and alternatives |

**Gate Result**: ✅ ALL GATES PASS — proceed to Phase 0.

## Phase Gate: Audit → Implementation

> **MANDATORY**: The `/speckit-tasks` command MUST NOT be run until ALL of the following conditions are met:

| Gate | Condition | Verified By |
|------|-----------|-------------|
| G-1 | `specs/001-production-audit-refactor/audit-report.md` is complete (all sections present, finding count correct, no "Sampled" qualifier) | Manual inspection |
| G-2 | User has explicitly approved the audit report | User confirmation in chat |
| G-3 | `research.md` has been reviewed for research-based vs code-verified claims | Manual inspection |
| G-4 | Zero source code files were modified during the audit phase | `git status` or file checksum |
| G-5 | All success criteria SC-001–SC-009 in `spec.md` are satisfied | Checklist review |

If any gate fails, the audit report must be revised before proceeding.

## Implementation Phases (Strict Git Workflow)

> **MANDATORY GIT WORKFLOW**: Every phase MUST be completed in its own branch milestone with clean commits. The agent must pause, review modified files, remove debug code, ensure formatting, and create a meaningful git commit (e.g., "Phase 1 - Security") before continuing to the next phase. `PROJECT_PROGRESS.md` must be updated after every phase.

The implementation will follow these 11 strictly ordered phases:

1. **Phase 1 - Security**: Address critical security findings (API keys, shell injection, `/tmp/` usage).
2. **Phase 2 - Dependency Cleanup**: Bundle fonts, resolve platform coupling, establish clean requirements.
3. **Phase 3 - Architecture**: Scaffold the target modular structure (PipelineContext, decoupled stages).
4. **Phase 4 - AI Providers**: Implement Abstract Base Classes for LLM, Transcription, and Face Detection; migrate to MediaPipe.
5. **Phase 5 - Rendering**: Break apart the god function, fix FFmpeg leaks, eliminate unnecessary disk writes.
6. **Phase 6 - Reliability**: Add structured logging, retry logic, exception recovery, and intermediate file cleanup.
7. **Phase 7 - Performance**: Optimize CPU/GPU bottlenecks, evaluate single-pass subtitle burn-in.
8. **Phase 8 - CLI**: Build a robust CLI orchestrator capable of batch processing multiple videos.
9. **Phase 9 - Testing**: Write unit tests, integration tests, and perform static analysis.
10. **Phase 10 - Documentation**: Finalize docstrings, `README.md`, `CONTRIBUTING.md`, and architecture diagrams.
11. **Phase 11 - Final Notebook**: Create a polished Google Colab notebook demonstrating the production pipeline (only after all other phases are complete).

## Code Quality & Repository Standards

- **Architecture**: SOLID principles, strict separation of config and business logic, dependency injection via interfaces.
- **Data Models**: Use `dataclasses` for all shared state (e.g., `PipelineContext`, `ClipState`).
- **Standardization**: Type hints for all signatures, comprehensive docstrings, structured logging (no `print()`), proper exception hierarchy.
- **Tests**: Unit tests for independent modules, integration tests for the pipeline. No fake test results.

## Project Structure

### Documentation (this feature)

```text
specs/001-production-audit-refactor/
├── plan.md              # This file
├── research.md          # Phase 0: dependency & technology research
├── data-model.md        # Phase 1: entity definitions (Finding, Module, Task)
├── contracts/           # Phase 1: audit report format contracts
│   └── audit-report-schema.md
├── quickstart.md        # Phase 1: validation guide
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
# Current state (monolithic — no changes during audit)
opusclip_v2_1_final.py   # 1332-line notebook export (READ-ONLY during audit)

# Target architecture (defined in blueprint, NOT created during audit)
src/
├── core/                # Pipeline orchestrator, config, caching
│   ├── config.py
│   ├── pipeline.py
│   └── cache.py
├── input/               # Video input & download module
│   ├── base.py          # Abstract input provider
│   ├── youtube.py       # yt-dlp provider
│   └── local.py         # Local file provider
├── transcription/       # Speech-to-text module
│   ├── base.py          # Abstract transcription provider
│   ├── whisper.py       # faster-whisper provider
│   └── word_repair.py   # Word timestamp repair
├── clip_selection/      # AI-powered clip identification
│   ├── base.py          # Abstract LLM provider
│   ├── openai_compat.py # OpenAI-compatible API provider
│   └── selector.py      # Clip scoring & validation
├── face_detection/      # Face detection & tracking
│   ├── base.py          # Abstract face detector provider
│   ├── dlib_detector.py # dlib HOG + landmark provider
│   └── smart_director.py # Camera direction logic
├── subtitle/            # Subtitle generation & rendering
│   ├── base.py          # Abstract subtitle renderer
│   ├── ass_builder.py   # ASS format builder
│   ├── text_cleaner.py  # Unicode cleaning
│   └── fonts.py         # Font management
├── rendering/           # Video rendering & composition
│   ├── base.py          # Abstract video renderer
│   ├── ffmpeg.py        # FFmpeg rendering provider
│   └── broll.py         # B-roll background generation
├── metadata/            # Social media metadata generation
│   ├── base.py          # Abstract metadata provider
│   └── llm_meta.py      # LLM-based metadata generator
└── output/              # Output & delivery
    ├── base.py          # Abstract output handler
    ├── local.py         # Local filesystem output
    └── summary.py       # Pipeline summary reporter

tests/
├── unit/
├── integration/
└── contract/
```

**Structure Decision**: The audit phase produces only documentation artifacts (reports, blueprints, roadmap). The target modular structure above is the blueprint output—it is documented but NOT created during the audit phase. Code restructuring happens in subsequent implementation tasks.

> **Note**: The target module structure defined above is a planning blueprint, not a commitment. Final module boundaries will be determined during implementation based on audit findings. Specific files (e.g., `broll.py`, `summary.py`) may be merged or split as the refactoring proceeds.

## Complexity Tracking

> No constitution violations detected. No complexity justifications needed.
