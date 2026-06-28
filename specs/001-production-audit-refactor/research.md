# Research & Technology Decisions

**Feature**: `001-production-audit-refactor`  
**Date**: 2026-06-28

This document captures the exhaustive analysis of the external dependencies used in the monolithic OpusClip v2.1 pipeline and formalizes the migration decisions for the target modular architecture.

All research complies with the project's **Zero-Cost Policy** and prioritizes FOSS alternatives.

> **Note on research-based claims**: Where a claim depends on external knowledge (benchmarks, platform capabilities, third-party documentation) rather than direct static analysis of the source code, it is marked **[Research-based]**. These claims should be verified by the user on the target server before being treated as ground truth.

---

## Executive Summary

The most critical dependency finding is that **dlib** (for face tracking) is CPU-only on all target platforms and should be replaced. **faster-whisper** and **FFmpeg** remain best-in-class FOSS tools for their respective tasks. The most impactful correctness issue is the hardcoded API key (SEC-001 in audit-report.md), which is a source-code finding, not research-based.

---

## Decision 1: Face Detection & Tracking

**Current Status**: The pipeline uses `dlib.get_frontal_face_detector()` (HOG) and a ~99 MB `shape_predictor_68_face_landmarks.dat` model. Both run on the CPU only. The model is downloaded to the working directory at startup (Cell 1, L154–162) and the detector is instantiated at Cell 6, L928–929.

- **Decision**: Replace `dlib` with `MediaPipe FaceMesh`.

- **Rationale**:
  - dlib's HOG detector has no GPU path on any platform (confirmed by dlib source code architecture).
  - Only 2 of 68 landmark points are used (audit-report.md AI-001).
  - MediaPipe FaceMesh uses a lightweight TFLite model (~2 MB vs ~99 MB).
  - **[Research-based]**: On Linux x86-64 with the `mediapipe` pip package (the target deployment environment), MediaPipe FaceMesh runs on **CPU** via TFLite inference — there is no GPU-accelerated path available through the pip package on Linux. GPU delegate support exists only for Android/iOS. Despite being CPU-only, TFLite inference is substantially faster than dlib's HOG algorithm due to the more efficient model architecture: approximately 2–5ms/frame at 480p input vs dlib's 15–30ms/frame (based on published MediaPipe benchmarks on comparable hardware). This is still a meaningful ~5–10× throughput improvement for the face scan stage.
  - MediaPipe's `FaceLandmarkerResult` includes blendshape scores (including `jawOpen` / mouth openness) that replace the manual MAR calculation entirely, provided the `output_face_blendshapes=True` option is enabled.
  - Eliminates the slow `dlib` pip compile step (dlib requires C++ build tools and can take 5–15 minutes to install from source).

- **Alternatives considered**:
  - *OpenCV DNN (YuNet/SFace)*: Already bundled with OpenCV (no extra dependency). Provides 5-point landmarks only — insufficient for mouth-state detection without an additional model.
  - *RetinaFace (InsightFace)*: State-of-the-art accuracy for crowded scenes. Adds heavy `insightface` dependency and is overkill for 1–2 person talking-head videos.

- **Migration complexity**: Medium. The `detect_faces()` function (L931–947) and the `SmartDirector` class (L870–921) need to be updated. MediaPipe returns normalized coordinates (0.0–1.0) vs dlib's pixel coordinates; conversion is straightforward. The MAR threshold (`CONFIG["speaking_mar"] = 0.025`) must be recalibrated against the blendshape score scale (0.0–1.0).

---

## Decision 2: Transcription Engine

**Current Status**: The pipeline uses `faster-whisper` (`large-v3`) with float16 inference on CUDA to generate word-level timestamps (Cell 4, L325–376).

- **Decision**: Keep `faster-whisper`. Evaluate `WhisperX` as a future provider swap.

- **Rationale**:
  - **[Research-based]**: `faster-whisper` remains the best-in-class Python-native CUDA Whisper implementation as of 2026, using CTranslate2 as its backend.
  - The codebase already has a 56-line workaround (`fill_missing_words()`, L648–703) for word-level timestamp alignment gaps. This suggests the current implementation has known limitations with short connecting words in Arabic (audit-report.md AI-002).
  - **[Research-based]**: `WhisperX` uses wav2vec2 forced alignment to generate accurate per-word timestamps without interpolation. This would eliminate `fill_missing_words()` entirely. However, `WhisperX` requires a HuggingFace token for its pyannote diarization component, which increases setup friction. If HuggingFace tokens are acceptable, this is the preferred long-term fix.

- **Alternatives considered**:
  - *whisper.cpp*: Excellent for CPU/Apple Silicon. No native Python API — requires subprocess and produces a different output format. Loss of Python-native CUDA throughput.
  - *insanely-fast-whisper*: Uses HuggingFace Transformers pipeline. **[Research-based]**: Effectively unmaintained as of 2025; superseded by faster-whisper for production use.

---

## Decision 3: Video Processing & Subtitle Rendering

**Current Status**: `FFmpeg` is invoked via `subprocess` in 7 distinct locations per clip. Subtitles are generated as `.ass` files and burned via libass.

- **Decision**: Keep `FFmpeg` and `libass`. Optimize the encoding pipeline.

- **Rationale**:
  - FFmpeg is irreplaceable for raw-pipe frame processing, audio normalization, and ASS subtitle burn-in.
  - ASS (Advanced SubStation Alpha) is the only viable format for karaoke-style per-word highlighting with per-line Arabic/English font switching.
  - The current implementation performs **two full CPU encode passes** per clip (audit-report.md PERF-002). Both use `libx264`.

- **Optimization Roadmap** (recommendations, not auditable code findings):
  1. **[Research-based]**: Switch the final encode from CPU `libx264 -preset fast` to hardware-accelerated `h264_nvenc` on NVIDIA hardware. The GPU is idle during the subtitle burn step. Expected improvement: **5–10× faster final encode** at comparable quality.
  2. Merge the `subtitles=` FFmpeg filter into the raw-pipe step (L1071), writing directly to `final_path`. This eliminates one full re-encode pass per clip. Implementation risk is High (complex filter_complex expression needed).

- **Alternatives considered**:
  - *OpenCV direct text rendering*: Would eliminate an FFmpeg encode pass but requires reimplementing Arabic BiDi text shaping and karaoke highlighting from scratch. Prohibitively complex.
  - *SRT + drawtext filter*: No support for per-word karaoke highlighting or per-line font switching. Not viable.

---

## Decision 4: Typography & Fonts

**Current Status**: Four font families are downloaded from external URLs at runtime (Cell 1, L59–126). All are SIL OFL 1.1 licensed.

- **Decision**: Bundle all TTF font files in the repository under `fonts/`.

- **Rationale**: Runtime downloads create network fragility, use unverified checksums, and rely on a `releases/latest` redirect for Amiri that could silently fetch a future breaking version. SIL OFL 1.1 explicitly permits bundling fonts in software distributions, provided the `OFL.txt` license file is included.

- **Fonts to bundle**:
  - `Tajawal-ExtraBold.ttf`, `Tajawal-Bold.ttf` (Arabic primary)
  - `Montserrat-ExtraBold.ttf`, `Montserrat-Bold.ttf` (English primary)
  - `Amiri-Regular.ttf` (Arabic calligraphic fallback)
  - Noto Sans Arabic subset (system fallback — include TTF from Noto project)
  - `OFL.txt` license file

- **Total bundle size**: Approximately 2–3 MB for all TTF files.

---

## Decision 5: Remaining Dependencies

| Dependency | Current Usage | Decision | Rationale |
|------------|---------------|----------|-----------|
| **OpenCV (cv2)** | Frame I/O, resizing, blurring (L284, L839–863, L1039–1116) | **Keep** | Essential for frame-by-frame processing. No viable Python alternative for video data manipulation. Apache 2.0. |
| **openai SDK** | Client for Groq, Gemini, opencode.ai (L387, L481, L1187, L1190) | **Keep** | The base_url pattern works correctly for all configured providers. Replacing with raw `httpx` saves ~50 MB disk but adds manual retry/error handling. Not worth it for 2–3 API calls per run. Apache 2.0. |
| **yt-dlp** | YouTube video download (L269–279) | **Keep** | **[Research-based]**: Industry standard; the maintained fork of youtube-dl. `pytube` is too fragile against YouTube API changes. Regular updates required. Unlicense (public domain). |
| **numpy** | Array operations on frames (L844, L1107) | **Keep** | Transitive dependency of OpenCV; unavoidable. BSD 3-Clause. |
| **torch** | CUDA memory management for Whisper (L326, L374) | **Keep — but document** | See torch analysis below. |

---

## Decision 6: PyTorch (torch) Dependency Analysis

**Current Usage**: `torch` is imported at Cell 4 (L326) only for `torch.cuda.empty_cache()` and `gc.collect()` after Whisper inference (L374). It is a transitive dependency of `faster-whisper` through CTranslate2's CUDA backend.

- **Maintenance**: **[Research-based]**: PyTorch is actively maintained by Meta AI. Regular releases. Enormous community. Not at risk of abandonment.

- **License**: BSD 3-Clause (core). CUDA extensions are subject to NVIDIA CUDA EULA — this is a runtime-only constraint (using CUDA binaries), not a code licensing constraint for the pipeline source.

- **Resource Usage**: **[Research-based]**: PyTorch with CUDA support is a large installation (~2 GB with CUDA runtime). On a cold environment without a pre-built Docker image, the first install is slow. The pipeline only uses it for VRAM cleanup — `torch.cuda.empty_cache()` — which could be replaced with `ctranslate2.get_cuda_allocator_stats()` if `torch` is not available, but this is a minor optimization.

- **Risk**: Version pinning is critical. `faster-whisper` requires specific versions of CTranslate2, which in turn requires specific CUDA/cuDNN versions. A mismatch causes silent CPU fallback or cryptic import errors. The pipeline does not pin versions anywhere.

- **Decision**: Keep. Document required version constraints in `requirements.txt` (e.g., `faster-whisper>=1.0.0`, `torch>=2.0.0,<3.0.0`).

---

## License Compliance Summary

| Dependency | License | Bundling Permitted? |
|------------|---------|---------------------|
| faster-whisper | MIT | ✅ Yes |
| dlib | Boost Software License 1.0 | ✅ Yes |
| MediaPipe (proposed replacement) | Apache 2.0 | ✅ Yes |
| OpenCV | Apache 2.0 | ✅ Yes |
| FFmpeg | LGPL 2.1 (default) / GPL (with x264) | ✅ Binary distribution; source LGPL |
| openai SDK | Apache 2.0 | ✅ Yes |
| yt-dlp | Unlicense | ✅ Yes (public domain) |
| numpy | BSD 3-Clause | ✅ Yes |
| torch | BSD 3-Clause (core) | ✅ Yes |
| libass | ISC | ✅ Yes |
| All fonts | SIL OFL 1.1 | ✅ Yes (with OFL.txt) |

All dependencies are confirmed FOSS-compatible. No paid or proprietary components are required.
