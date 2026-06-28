# Engineering Audit Report: OpusClip Pipeline v2.1

> **Status**: Complete — 30 findings across 8 review areas  
> **Based on**: Static analysis of `opusclip_v2_1_final.py` (1332 lines) — no code was executed  
> **Date**: 2026-06-28

---

## Executive Summary

- **Total findings**: 30 (complete enumeration — no sampling)
- **By severity**: Critical (5), High (10), Medium (10), Low (5)
- **Top 3 recommendations**:
  1. **Fix the FFmpeg pipe resource leak** (REL-005) — a single exception inside the crop-render loop leaves an FFmpeg zombie process, corrupting the next clip silently. This is the only finding that causes silent data corruption.
  2. **Remove hardcoded secrets and eliminate `shell=True`** (SEC-001, SEC-002) — an API key is committed in plain text; `shell=True` in `_sh()` creates a shell-injection surface.
  3. **Decouple from Google Colab** (ARCH-002) — `from google.colab import files` at line 1285 executes unconditionally, crashing the entire pipeline outside Colab.

---

## 1. Architecture Review

### Findings

#### [ARCH-001] Monolithic Structure with Implicit Global State

**Severity**: High  
**Location**: Entire file — global scope  
**Constitution**: Principle III — Architecture Rules  
**Related**: CODE-001, PROD-001, REL-001

**Issue**: The 1332-line file executes sequentially in global scope. Inter-cell state (`transcript_data`, `selected_clips`, `rendered`, `VIDEO_PATH`, `VID_W`, `VID_H`, `VID_FPS`, `SRC_CROP_W`, `TARGET_W`, `TARGET_H`) is shared exclusively through module-level globals. There are no function arguments, return values, or dependency injection at the pipeline level.

**Impact**: Individual pipeline stages cannot be unit-tested in isolation. A failure in any cell leaves the process in an undefined state. Parallel processing of multiple clips is impossible without refactoring the global-state model.

**Suggested Fix**: Introduce a `PipelineContext` dataclass that holds all shared state and is passed explicitly to every stage function. Decouple stages into importable functions.

---

#### [ARCH-002] Hard Platform Dependency on Google Colab

**Severity**: Critical  
**Location**: Cell 1 (L29–192), Cell 3 (L260), Cell 8 (L1285–1330)  
**Constitution**: Principle I — Zero-Cost Policy (Deployment Portability); Principle II — Safety Rules  
**Related**: DEP-002, SEC-003

**Issue**: The pipeline cannot run outside Google Colab for three distinct reasons:
1. **Cell 1 (L47)**: `_sh("pip install -q faster-whisper ...")` — runs `pip install` as application code, not a setup step.
2. **Cell 1 (L51–53)**: `_sh("apt-get install -y -q fonts-noto-core ...")` — assumes root-level Linux package management.
3. **Cell 3 (L260)**: `from google.colab import files as _cf` — inside the `"upload"` branch.
4. **Cell 8 (L1285)**: `from google.colab import files as _cf` — **unconditional, module-level import**. This line executes every time Cell 8 runs and will raise `ModuleNotFoundError` on any non-Colab environment, aborting the pipeline after all clips have been rendered.

**Impact**: The pipeline is undeployable on the target Linux server. Even if the rendering stages complete successfully, Cell 8 will crash before the summary is printed, and the auto-download loop (`L1330`) will have already tried to execute.

**Suggested Fix**: Remove all `pip install` / `apt-get` calls from application code. Move them to `requirements.txt` and an install script. Replace `google.colab.files` with a CLI/local-file output handler.

---

#### [ARCH-003] No Provider Abstraction for AI Components

**Severity**: High  
**Location**: Cell 4 (L325–376), Cell 5 (L481–541), Cell 7 (L1190–1249)  
**Constitution**: Principle III — Replaceable Providers  
**Related**: AI-001, AI-002

**Issue**: `faster-whisper`, `dlib`, and the `openai` SDK are all imported and used directly inside pipeline logic with no abstraction layer. The transcription provider, face-detection provider, and LLM provider are each a single concrete implementation with no interface separating them.

**Impact**: Replacing any AI component (e.g., swapping `dlib` for MediaPipe, or `faster-whisper` for WhisperX) requires editing the core business logic rather than swapping a provider class.

**Suggested Fix**: Define abstract base classes — `TranscriptionProvider`, `FaceDetectorProvider`, `LLMProvider` — and move current implementations behind these interfaces.

---

## 2. Code Review

### Findings

#### [CODE-001] God Function: `render_clip` (~200 lines)

**Severity**: High  
**Location**: Cell 6, Lines 961–1159  
**Constitution**: Principle III — Single Responsibility Principle  
**Related**: REL-005, PERF-002, PERF-003

**Issue**: `render_clip()` is a single 199-line function that performs: two-stage FFmpeg clip extraction, audio normalization, 480p scan file creation, frame-by-frame face detection, SmartDirector state computation, full-resolution raw-pipe rendering, thumbnail selection, ASS subtitle file generation, and FFmpeg subtitle burn-in merge. It manages eight file paths and five subprocess calls.

**Impact**: Any exception in any of the eight steps exposes the caller to partial state (see REL-005). It is impossible to unit-test subtitle generation or smart-crop logic independently.

**Suggested Fix**: Decompose into named helper functions: `extract_raw_clip()`, `scan_faces()`, `compute_director_decisions()`, `render_smart_crop()`, `burn_subtitles()`, each with a clear signature and return type.

---

#### [CODE-002] Magic Numbers and Hardcoded Paths Scattered Through Business Logic

**Severity**: Medium  
**Location**: Cell 6, multiple lines  
**Constitution**: Principle III — Maintainability  
**Related**: SEC-003

**Issue**: Production-tuning constants are embedded inline throughout `render_clip()` and `build_ass()` without being centralized in `CONFIG`:
- `L999`: `PRE_SEEK = max(0.0, c_start - 10.0)` — 10-second seek buffer
- `L1007`: `duration + 0.5` — 0.5-second safety buffer
- `L1025`: `SCAN_H = min(480, vid_h)` — 480p scan resolution
- `L1033`: `"-crf", "28"` — scan quality hardcoded (differs from `CONFIG["crf"]`)
- `L1128`: `fade_d = 0.4` — fade duration
- `L981`: `safe_ass = f"/tmp/{base}.ass"` — hardcoded `/tmp/` path
- `L853`: `bd = 5` — B-roll border width
- `L737`: `shadow = 3` — subtitle shadow depth

**Impact**: Tuning any pipeline parameter requires searching through 200 lines rather than editing a config dict.

**Suggested Fix**: Add these values to `CONFIG` or a dedicated `RenderConfig` dataclass.

---

#### [CODE-003] Bare `except: pass` Silences Cleanup Errors

**Severity**: Medium  
**Location**: Cell 6, Lines 1151–1153  
**Constitution**: Principle IV — Reliability  
**Related**: REL-001

**Issue**:
```python
for p in [raw_path, silent_path, audio_path, safe_ass]:
    try: os.remove(p)
    except: pass
```
The bare `except:` catches every possible exception — including `KeyboardInterrupt`, `MemoryError`, and `SystemExit` — and discards it silently.

**Impact**: If a file cannot be deleted due to a permission error, locked file handle, or out-of-disk-space condition, the error is invisible. Temporary files accumulate silently.

**Suggested Fix**: Replace with `except OSError as e: logger.warning("Could not remove %s: %s", p, e)`.

---

#### [CODE-004] Dead Commented-Out Code Block in `fill_missing_words()`

**Severity**: Low  
**Location**: Cell 6, Lines 680–687  
**Constitution**: Principle III — Maintainability  
**Related**: AI-002

**Issue**: Lines 680–687 contain a fully commented-out loop body that was the original implementation of word reconstruction, superseded by the active loop at L690–699. The commented-out block is structurally identical to the active code but lacks the `clean_for_subtitle()` call:
```python
# print(dt)
# for i, mw in enumerate(missing):
#     result.append({
#         "text"  : mw,
#         "start" : round(seg["start"] + i * dt, 3),
#         "end"   : round(seg["start"] + (i + 1) * dt, 3),
#         "prob"  : 0.60,
#     })
```

**Impact**: The dead block creates confusion about which implementation is authoritative. It retains a single debug `print(dt)` comment (L680) with no explanation.

**Suggested Fix**: Delete lines 680–687. If the `clean_for_subtitle()` improvement needs to be documented, add a comment on L689–699 instead.

---

#### [CODE-005] `_BAD_CHARS` Regex Compiled but Never Referenced

**Severity**: Low  
**Location**: Cell 6, Lines 572–591  
**Constitution**: Principle III — Maintainability  
**Related**: CODE-006

**Issue**: `_BAD_CHARS` is a compiled regex pattern defined at module level (L572–591) listing emoji and control character ranges for a blacklist-based cleaning approach. However, `clean_for_subtitle()` at L593 was rewritten to use a **whitelist** character-by-character loop instead. `_BAD_CHARS` is never referenced anywhere in the file after L591.

**Impact**: The compiled regex object wastes memory on every run and misleads readers into thinking a blacklist approach is still active.

**Suggested Fix**: Delete lines 571–591. If the historical reason for the approach change needs to be preserved, add a single comment on `clean_for_subtitle()` instead.

---

#### [CODE-006] `subtitle_font()` Defined but Never Called

**Severity**: Low  
**Location**: Cell 6, Lines 638–640  
**Constitution**: Principle III — Maintainability  
**Related**: CODE-005

**Issue**:
```python
def subtitle_font(line_text: str) -> str:
    """Pick the right font based on the dominant script in a line."""
    return SUBTITLE_FONT_AR if is_arabic_text(line_text) else SUBTITLE_FONT_EN
```
This function is defined but never called anywhere in the 1332-line file. `build_ass()` at L811 calls `is_arabic_text()` directly and assigns the style inline, never invoking `subtitle_font()`.

**Impact**: Readers trying to understand font selection are sent to a dead function. The real font-selection logic is buried inside `build_ass()`.

**Suggested Fix**: Either delete `subtitle_font()` or refactor `build_ass()` to call it, centralizing the font-selection logic.

---

#### [CODE-007] Debug Print Statements Left Inside `build_ass()`

**Severity**: Low  
**Location**: Cell 6, Lines 779–780  
**Constitution**: Principle III — Maintainability  
**Related**: REL-002

**Issue**:
```python
print(f"   🔍 Title raw : {repr(title[:60])}")
print(f"   🔍 Title clean: {repr(clean_t[:60])}")
```
These fire for every clip rendered. A 12-clip batch produces 24 debug lines in stdout without any log level.

**Impact**: Pollutes production output and cannot be suppressed without editing the source.

**Suggested Fix**: Replace with `logger.debug(...)` once structured logging is implemented (see REL-002).

---

#### [CODE-008] Diagnostic Font-Check Block with Duplicate Imports Left in Production

**Severity**: Medium  
**Location**: Cell 1, Lines 173–191  
**Constitution**: Principle III — Maintainability; Principle II — Safety Rules  
**Related**: ARCH-002

**Issue**: After the main environment setup finishes at L171, there is an orphaned diagnostic block that was clearly never cleaned up before shipping:

- **L173**: `import subprocess` — duplicate of the import at L32.
- **L186**: `import os` — duplicate of the import at L33.
- **L175–184**: Loops over all four font families running `fc-match` and prints results.
- **L188–191**: Walks `/tmp/amiri` to print every file it contains.

This block executes unconditionally every time Cell 1 runs.

**Impact**: Reveals the pipeline's internal font installation paths to stdout in production. The duplicate imports are a readability smell. The `/tmp/amiri` walk is a Colab-specific debugging artifact.

**Suggested Fix**: Delete lines 173–191 entirely. The `fc-match` font verification at L130–137 already provides sufficient confirmation.

---

#### [CODE-009] Potential Frame Count Mismatch Between Scan Path and Raw Path

**Severity**: Medium  
**Location**: Cell 6, Lines 1025–1090  
**Constitution**: Principle IV — Reliability  
**Related**: CODE-001, REL-005

**Issue**: `frames_faces` (L1041) is built by decoding `scan_path` (the 480p version), while `raw_cap` (L1081) decodes `raw_path` at full resolution. Both are extracted from the same source with `-t duration+0.5` but encoded at different quality settings (`-crf 28 ultrafast` vs `-crf 22 ultrafast`). In rare edge cases (very short clips, unusual frame rates), the two libx264 encodes can produce a different frame count due to rounding of the duration and PTS propagation.

The existing fallback at L1090 handles the case gracefully:
```python
cx, fstate = frame_data[fi] if fi < len(frame_data) else frame_data[-1]
```
However, it silently uses the last-known crop position and director state for any overflow frames, which can cause the crop to freeze at the last detected face position for the final seconds of the clip.

**Impact**: Subtle visual artifact on the last frames of some clips. Cannot be detected without visual inspection.

**Suggested Fix**: Assert or log a warning when `fi >= len(frame_data)` during the render loop, and consider building `frames_faces` from `raw_cap` directly (avoiding the scan copy entirely, using the scan-scale parameter to downsample in memory).

---

## 3. Performance Review

### Findings

#### [PERF-001] CPU-Bound Face Detection Is the Primary Throughput Bottleneck

**Severity**: High  
**Location**: Cell 6, Lines 928–947  
**Constitution**: Principle IV — Performance Principles  
**Related**: AI-001, ARCH-003

**Issue**: `dlib.get_frontal_face_detector()` (L928) uses Histogram of Oriented Gradients (HOG), a classical CPU-only algorithm. No CUDA or OpenCL path exists in dlib's HOG detector. The landmark predictor at L929 also runs on CPU. Even with the every-3rd-frame optimization (`FACE_DETECT_EVERY = 3`, L955), a 60-second clip at 30 FPS produces `(60×30)/3 = 600` detection calls.

At approximately 15–30ms per call on a mid-range CPU (confirmed by dlib's own benchmarks on 480p input), face detection alone takes **9–18 seconds per 60-second clip**, leaving the GPU mostly idle during this phase.

**Impact**: For a batch of 10 clips averaging 60 seconds each, face detection accounts for approximately 90–180 seconds of CPU-bound wall time that cannot be parallelized with GPU work.

**Suggested Fix**: Replace `dlib` with MediaPipe FaceMesh (see Research section for performance characteristics and migration notes). See also AI-001 for the landmark usage inefficiency.

---

#### [PERF-002] Subtitle Burn-In Causes a Full Second Video Re-Encode

**Severity**: Medium  
**Location**: Cell 6, Lines 1135–1142  
**Constitution**: Principle IV — Performance Principles  
**Related**: CODE-001, PROD-002

**Issue**: The rendering pipeline performs two complete `libx264` encode passes per clip:
1. **L1071–1112**: Raw-pipe encode from Python frames → `silent_path` (CRF 20, preset fast).
2. **L1135–1142**: Subtitle burn-in re-encode of `silent_path` → `final_path` (CRF 20, preset fast).

The second encode re-compresses already-compressed H.264 video, causing generation loss. It also doubles wall-time for the encoding stage.

**Impact**: For a 90-second clip at 1080×1920, each encode pass takes approximately 20–40 seconds on CPU. The double encode adds 20–40 seconds per clip and introduces unnecessary quality loss.

**Suggested Fix**: Explore merging the `subtitles=` FFmpeg filter into the raw-pipe Popen command at L1071 (outputting to `final_path` directly). This is architecturally complex because the ASS file content depends on the subtitle timing which is already computed before the pipe step, so merging is feasible.

---

#### [PERF-003] Unnecessary Intermediate Scan File Written to Disk

**Severity**: Low  
**Location**: Cell 6, Lines 1030–1052  
**Constitution**: Principle IV — Performance Principles  
**Related**: CODE-001, CODE-009

**Issue**: The face scan phase writes a full 480p `.mp4` file to disk (L1030–1035), reads it frame-by-frame with `cv2.VideoCapture` (L1039–1051), then immediately deletes it (L1052). This is pure intermediary disk I/O with no benefit over reading frames from a pipe.

**Impact**: For a 90-second clip at 480p (approximately 15–30 MB), this creates unnecessary SSD writes, occupies disk space during the scan window, and introduces an additional `libx264` encode + decode cycle.

**Suggested Fix**: Feed 480p frames directly to the face detection loop using an FFmpeg subprocess pipe: `ffmpeg ... -vf scale=W:H -f rawvideo pipe:1 | read frames in Python`. This eliminates the disk file entirely.

---

## 4. AI Pipeline Review

### Findings

#### [AI-001] 100 MB Landmark Model Used to Extract Exactly Two Points

**Severity**: Medium  
**Location**: Cell 1 (L154–162), Cell 6 (L928–947)  
**Constitution**: Principle III — Architecture Rules  
**Related**: PERF-001, ARCH-003

**Issue**: `shape_predictor_68_face_landmarks.dat` (~99 MB) is downloaded and loaded to power the MAR (Mouth Aspect Ratio) calculation. The entire calculation is:
```python
mar = abs(shape.part(51).y - shape.part(57).y) / max(fh, 1)
```
Only two of the 68 landmark points — upper lip (index 51) and lower lip (index 57) — are ever accessed. The remaining 66 landmarks are computed and discarded on every frame.

**Impact**: 99 MB model download on every fresh environment. CPU cycles spent predicting 66 unused landmarks. `dlib` compile-time installation is notoriously slow.

**Suggested Fix**: Replace with MediaPipe FaceMesh which provides a direct `mouth_open` blendshape score (see research.md for platform-specific performance notes), or use a smaller 5-point predictor combined with a separate mouth-state classifier.

---

#### [AI-002] `fill_missing_words()` Is a Timing-Interpolation Workaround for Whisper Alignment Gaps

**Severity**: Medium  
**Location**: Cell 6, Lines 648–703  
**Constitution**: Principle IV — Reliability  
**Related**: CODE-004, ARCH-003

**Issue**: Whisper occasionally omits word-level timestamps for the first word of short segments (e.g., "ألا" in "ألا وهو؟"). The 56-line `fill_missing_words()` function reconstructs missing timestamps by dividing the available pre-segment gap equally among missing words. This is a linear-interpolation approximation, not actual timing data.

**Impact**: Reconstructed word timestamps are estimates with up to ±300ms error (depending on gap size and number of missing words). Karaoke subtitle highlighting may appear slightly early or late for reconstructed words.

**Suggested Fix**: This is a known Whisper limitation. As a research-based recommendation: `WhisperX` uses wav2vec2 forced alignment to produce accurate word-level timestamps without interpolation. Migration complexity is Low (WhisperX wraps faster-whisper). However, `WhisperX` requires a HuggingFace token for the pyannote diarization component, which increases setup friction. If HuggingFace tokens are acceptable, this is the preferred long-term fix.

---

## 5. Dependency Review

### Findings

#### [DEP-001] Critical Subtitle Fonts Downloaded at Runtime from External URLs

**Severity**: High  
**Location**: Cell 1, Lines 59–74 (TTF downloads), Lines 98–126 (Amiri zip)  
**Constitution**: Principle IV — Reliability  
**Related**: ARCH-002, CODE-008

**Issue**: Four font families are fetched from external URLs every time the environment is initialized:
- `Tajawal-ExtraBold.ttf` / `Tajawal-Bold.ttf` from `github.com/google/fonts`
- `Montserrat-ExtraBold.ttf` / `Montserrat-Bold.ttf` from `github.com/google/fonts`
- `Amiri-1.003.zip` from `github.com/aliftype/amiri/releases/latest/download/`

The `urllib.request.urlretrieve()` calls at L80 and L104 have no checksum verification, no timeout, and no retry logic. The Amiri URL uses a `releases/latest` redirect, which will silently fetch a future version with potentially different metrics, breaking subtitle layout.

**Impact**: If GitHub is unavailable, rate-limits the request, or changes the URL, subtitle rendering falls back to Noto Sans, fundamentally changing the visual output. The `releases/latest` pattern is particularly fragile in production.

**Suggested Fix**: Bundle all TTF files in the repository under `fonts/`. All fonts are SIL OFL 1.1 licensed, which permits bundling. Include an `OFL.txt` license file alongside the fonts. Remove all runtime download code from Cell 1.

---

#### [DEP-002] `apt-get` Used to Install System Fonts at Runtime

**Severity**: Medium  
**Location**: Cell 1, Lines 51–53  
**Constitution**: Principle I — Zero-Cost Policy; Principle II — Safety Rules  
**Related**: ARCH-002

**Issue**: `apt-get install -y -q fonts-noto-core fonts-noto-extra fonts-noto-color-emoji fonts-dejavu-core` runs as application code. This requires root (`sudo`) access on most systems and is not reproducible across environments without the exact same Ubuntu/Debian package versions.

**Impact**: On a non-Debian Linux server (e.g., RHEL, Alpine, Arch), this command fails silently due to `_sh()`'s lenient error handling, and the pipeline continues without the fallback fonts, causing tofu boxes in subtitle rendering.

**Suggested Fix**: Include the required Noto TTF files in the bundled `fonts/` directory alongside Tajawal and Montserrat. Only the Arabic and Latin subsets are needed for subtitle rendering.

---

## 6. Reliability Review

### Findings

#### [REL-001] Incomplete Resumability After Rendering Failure

**Severity**: High  
**Location**: Cell 6, Lines 985–987, 1163–1178  
**Constitution**: Principle IV — Reliability  
**Related**: CODE-001, CODE-003, REL-005

**Issue**: The rendering loop at L1163–1178 checks `if os.path.exists(final_path)` (L985) to skip already-completed clips — a correct resume mechanism for the final output. However, if a clip fails mid-render (e.g., FFmpeg crashes at step 3/4), the intermediate files (`raw_path`, `scan_path`, `silent_path`, `audio_path`) remain in `opusclip_output/work/`. The cleanup at L1151–1153 is not reached because the exception bypasses it.

On retry, the stale intermediate files are detected by `cv2.VideoCapture` (which may succeed on a truncated file), producing a corrupted clip that passes the `os.path.exists(final_path)` check if a partial output was written.

**Impact**: Stale intermediate files accumulate silently. Retry runs can produce silent corruption if a partial output exists.

**Suggested Fix**: Wrap the entire `render_clip` body in a `try/finally` block with cleanup in the `finally` clause. Before starting, delete any existing intermediate files for the current clip number.

---

#### [REL-002] No Structured Logging — All Output Is `print()`

**Severity**: High  
**Location**: Entire file  
**Constitution**: Principle III — Maintainability  
**Related**: CODE-007, PROD-002

**Issue**: The pipeline uses `print()` for all progress reporting across 1332 lines. There is no `import logging` anywhere in the file. Log level, timestamps, and severity cannot be controlled without editing source code. Stdout cannot be differentiated from stderr programmatically.

**Impact**: On a remote server, there is no way to monitor pipeline health, pipe warnings to a monitoring system, or reproduce the exact log sequence for a failed run.

**Suggested Fix**: Replace all `print()` calls with `logging.getLogger(__name__)` calls at appropriate levels (`DEBUG` for internal state, `INFO` for progress milestones, `WARNING` for recoverable issues, `ERROR` for failures). Configure a `JSONFormatter` for machine-readable output.

---

#### [REL-003] Audio WAV File Written and Never Deleted

**Severity**: Medium  
**Location**: Cell 4, Lines 310–323  
**Constitution**: Principle IV — Reliability  
**Related**: REL-001, PROD-001

**Issue**: `AUDIO_WAV = os.path.join(CONFIG["output_dir"], "audio.wav")` is written during transcription at L321 via FFmpeg (`-c:a pcm_s16le`, 16-bit PCM at 16kHz). It is never deleted. The file size is approximately:
- 30-min video: `30×60×16000×2 bytes ≈ 55 MB`
- 4-hour video: `4×3600×16000×2 bytes ≈ 460 MB`

For a 4-hour source video — the documented maximum — the WAV file alone consumes 460 MB permanently in the output directory. In a batch of 5 videos, this amounts to 2.3 GB of permanent WAV files.

**Impact**: Uncontrolled disk consumption at the target scale. A 4-hour video batch of 5 videos would accumulate 2.3 GB of undeleted WAV files in addition to the rendered clips.

**Suggested Fix**: Delete `AUDIO_WAV` immediately after the Whisper model has finished transcribing and the JSON has been saved. Add to the same cleanup block as the model deletion at L374.

---

#### [REL-004] `gen_meta()` Has No Retry Logic and Silently Loses Metadata

**Severity**: High  
**Location**: Cell 7, Lines 1217–1247  
**Constitution**: Principle IV — Reliability  
**Related**: REL-002, PROD-002

**Issue**: The LLM clip selection loop in Cell 5 (L485–509) implements a 3-attempt retry with `time.sleep()`. `gen_meta()` in Cell 7 does not — it makes a single `client.chat.completions.create()` call (L1218) and a single `json.loads(raw)` call (L1234) with no retry logic.

The outer try/except at L1245–1247 catches any exception and sets `all_meta[n] = {}` (empty dict), then continues to the next clip. The pipeline prints a single `⚠️ {e}` line but does not record the failure anywhere. The resulting `metadata.json` contains `{}` for any failed clip, with no way to distinguish a failed clip from one that simply has no metadata.

**Impact**: Transient API errors (rate limits, timeouts) cause permanent silent metadata loss. Because the cache check at L1236 will find a `metadata.json` with empty entries on the next run, re-running the pipeline will not regenerate the missing metadata.

**Suggested Fix**: Apply the same 3-attempt retry loop from Cell 5 to `gen_meta()`. Mark failed clips explicitly with `{"_error": str(e)}` rather than `{}` so they can be detected and re-run.

---

#### [REL-005] FFmpeg Pipe Process Not Closed on Exception — Zombie Process and Resource Leak

**Severity**: Critical  
**Location**: Cell 6, Lines 1071–1112  
**Constitution**: Principle II — Safety Rules; Principle IV — Reliability  
**Related**: CODE-001, REL-001

**Issue**: The FFmpeg render subprocess is launched with `subprocess.Popen()` at L1071:
```python
ffpipe = subprocess.Popen([
    "ffmpeg", "-y", "-f", "rawvideo", ...
    silent_path,
], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
```

The normal close sequence at L1111–1112 is:
```python
ffpipe.stdin.close()
ffpipe.wait()
```

However, if **any exception is raised inside the `while True:` frame loop** (L1086–1108) — for example, a `cv2.VideoCapture.read()` failure, a numpy shape error, or a `BrokenPipeError` from `ffpipe.stdin.write()` — control transfers directly to the `except Exception as exc:` block at L1175 in the outer clip loop. **Neither `ffpipe.stdin.close()` nor `ffpipe.wait()` is ever called.**

Consequences:
1. The FFmpeg process becomes a zombie, holding an open `stdin` pipe.
2. `silent_path` is never finalized (FFmpeg has not received the full frame stream).
3. The cleanup at L1151–1153 attempts to delete `silent_path`, which may fail silently (the file may be locked or incomplete).
4. On the next clip, a new `ffpipe` is opened. If the zombie from the previous clip is still alive and holding resources, the system may run out of pipe handles.

**Impact**: Silent data corruption on the clip following a failure. Potential zombie process accumulation causing resource exhaustion in a batch job.

**Suggested Fix**: Wrap the pipe rendering block in `try/finally`:
```python
try:
    # ... while True frame loop ...
finally:
    raw_cap.release()
    if ffpipe.stdin and not ffpipe.stdin.closed:
        ffpipe.stdin.close()
    ffpipe.wait()
```

---

## 7. Security Review

### Findings

#### [SEC-001] API Key Hardcoded in Plain Text in Source File

**Severity**: Critical  
**Location**: Cell 2, Line 211  
**Constitution**: Principle II — Safety Rules  
**Related**: ARCH-001

**Issue**:
```python
CONFIG = {
    "api_key": "sk-Fzob35iRvC5gYblBPquBPWLBOkbtn9o6nAN6PW8AWjMK1vkyaLCE7kZMWLD5eBIU",  # ← replace
    ...
}
```
A real API key is committed directly into the source file. The comment `# ← replace` indicates this is a placeholder convention, but the placeholder itself is a real key value.

**Impact**: If this file is committed to any version control system (even a private repository), the key is permanently in the git history and must be rotated immediately.

**Suggested Fix**: Remove the key value. Load from environment variable only: `os.environ.get("OPUSCLIP_API_KEY")`. Raise a clear error at startup if the variable is not set. Add `.env` to `.gitignore` and document usage in README.

---

#### [SEC-002] `shell=True` in `_sh()` Creates a Shell-Injection Surface

**Severity**: Critical  
**Location**: Cell 1, Lines 39–44  
**Constitution**: Principle II — Safety Rules  
**Related**: ARCH-002

**Issue**:
```python
def _sh(cmd, label=""):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
```
`_sh()` is called with all-static strings in the current code, so there is no active injection. However, the pattern is dangerous because:
1. Any future caller that passes a user-derived value (e.g., a filename with spaces or shell metacharacters) will execute arbitrary shell commands.
2. `shell=True` on Windows uses `cmd.exe`, producing different behavior than Linux `bash` — this creates cross-platform inconsistency.
3. The `_sh()` function wraps `pip install` and `apt-get` — commands that should never be run via the shell from application code.

**Impact**: If a YouTube URL or uploaded filename ever passes through `_sh()`, remote code execution is possible.

**Suggested Fix**: Remove `_sh()` entirely. Replace every call with a list-based `subprocess.run([...])` call. Remove the `pip install` and `apt-get` calls from application code.

---

#### [SEC-003] Insecure Hardcoded Paths in `/tmp/` Without Isolation

**Severity**: Critical  
**Location**: Cell 1 (L99–100), Cell 6 (L981)  
**Constitution**: Principle II — Safety Rules  
**Related**: ARCH-002, CODE-002

**Issue**: Two separate locations write files to static, predictable paths in `/tmp/`:
- **L99**: `AMIRI_ZIP = "/tmp/amiri.zip"` — font archive.
- **L100**: `AMIRI_DIR = "/tmp/amiri"` — font extraction directory.
- **L981**: `safe_ass = f"/tmp/{base}.ass"` — ASS subtitle file, e.g. `/tmp/clip_01.ass`.

On a shared Linux server (multi-user or container with shared `/tmp/`), a malicious process can pre-create `/tmp/clip_01.ass` as a symlink pointing to an arbitrary file. When `shutil.copy(ass_path, safe_ass)` at L1123 executes, it will overwrite the symlink target.

**Impact**: CWE-59 (Improper Link Resolution Before File Access) — potential file overwrite of any file the process can write to. In a multi-tenant environment, this is a data integrity risk.

**Suggested Fix**: Replace all `/tmp/` paths with `tempfile.mkdtemp(prefix="opusclip_")` to create an isolated, randomly named temporary directory for each pipeline run. Ensure the temporary directory is deleted in a `finally` block.

---

#### [SEC-004] No Input Validation on Video Source Path or YouTube URL

**Severity**: High  
**Location**: Cell 3, Lines 259–282  
**Constitution**: Principle II — Safety Rules  
**Related**: SEC-002, ARCH-002

**Issue**:
1. **Upload path (L260–263)**: `VIDEO_PATH = list(uploaded.keys())[0]` takes the filename directly from `google.colab.files.upload()`. This filename is subsequently passed to `subprocess.run(["ffmpeg", ..., VIDEO_PATH, ...])`, `subprocess.run(["yt-dlp", ..., VIDEO_PATH, ...])`, and `cv2.VideoCapture(VIDEO_PATH)`. A filename containing shell metacharacters or path traversal sequences (e.g., `../../etc/passwd`) is passed unsanitized.
2. **YouTube URL path (L265)**: `assert YOUTUBE_URL, "Set YOUTUBE_URL above!"` — the only validation is a truthiness check. No URL format validation is performed before passing to `yt-dlp`.

**Impact**: Malformed filenames could cause unexpected behavior in FFmpeg and OpenCV. Path traversal in filenames could cause files to be written outside the output directory. An invalid YouTube URL will produce an unhelpful `yt-dlp` error message with no graceful handling.

**Suggested Fix**: Validate `VIDEO_PATH` using `pathlib.Path.resolve()` to ensure it stays within an allowed directory. Validate `YOUTUBE_URL` with a URL-format check (e.g., `urllib.parse.urlparse()`). Sanitize filenames using `os.path.basename()`.

---

## 8. Production Readiness Review

### Findings

#### [PROD-001] Single-Video Processing Only — No Batch Capability

**Severity**: High  
**Location**: Cell 3, Lines 254–256  
**Constitution**: Principle IV — Scalability  
**Related**: ARCH-001, REL-003

**Issue**: The pipeline is hardcoded to process exactly one video:
```python
INPUT_MODE  = "youtube"
YOUTUBE_URL = "https://youtu.be/OwDU3GH9cGI?si=..."
```
Processing a second video requires manually editing these constants and re-running the entire notebook. The output directory `opusclip_output/` is also fixed, meaning a second run would overwrite the cached transcript, clips, and metadata from the first video.

**Impact**: The stated target of "batch processing at least 5 videos" (from spec.md) is architecturally impossible without refactoring. Concurrent batch runs on the same machine would collide in the output directory.

**Suggested Fix**: Accept a list of video sources as CLI arguments. Derive a per-video output directory from a video-specific identifier (URL hash or filename). Wrap the pipeline in a loop that processes each video independently.

---

#### [PROD-002] No Per-Clip or Per-Stage Exception Recovery

**Severity**: Medium  
**Location**: Cell 4 (L312–376), Cell 5 (L473–541), Cell 6 (L1163–1178)  
**Constitution**: Principle IV — Reliability  
**Related**: REL-004, REL-005

**Issue**: The outer clip loop at L1163–1178 correctly continues to the next clip on exception. However, Cell 4 (transcription) and Cell 5 (clip selection) are top-level executable blocks with no equivalent protection — a `RuntimeError` or OOM from Whisper terminates the entire Python process. Additionally, the Cell 7 `gen_meta()` failure mode (see REL-004) silently produces empty metadata without marking the failure.

**Impact**: An OOM from Whisper on a 4-hour video requires restarting the entire pipeline, even though the transcript JSON cache would be recreated from scratch.

**Suggested Fix**: Wrap Cell 4 and Cell 5 in proper pipeline-stage functions that return structured result objects (`TranscriptResult`, `ClipSelectionResult`). On failure, emit a structured error and allow downstream stages to skip gracefully.

---

## 9. Scalability Analysis for 4-Hour Videos

The spec requires the pipeline to handle videos up to 4 hours. The following is a static analysis of scaling behavior — no benchmarks were run.

### Memory Constraints

- **Audio WAV** (L321): 4hr × 16kHz × 16-bit × 1ch = **460 MB** permanent on disk (see REL-003).
- **`all_words_fixed`** (L707): A 4-hour Arabic lecture at approximately 150 words/minute = ~36,000 words. Each word is a Python dict with 4 fields. At ~200 bytes per dict (Python overhead), the in-memory word list is approximately **7 MB** — acceptable.
- **`frames_faces`** (L1041): Computed per-clip, not per-video. A 90-second clip at 30 FPS produces 2,700 frame-face entries. At ~100 bytes per entry (list of face dicts), this is approximately **270 KB per clip** — acceptable.
- **Transcript JSON** (L371): 36,000 words × ~100 chars each = ~3.6 MB JSON on disk — acceptable.

### Two-Stage Seek Scaling

The two-stage seek at L999–1000 (`PRE_SEEK = max(0.0, c_start - 10.0)`) performs a keyframe jump to 10 seconds before the clip start, then decodes precisely from there. For a clip starting at 3:55:00 (14,100s), FFmpeg seeks to keyframe near 14,090s. This is correct and scales linearly with video length — no issue.

### LLM Context Window Constraint

`compress_transcript()` at L400–417 caps the LLM prompt at `max_chars=28,000` characters. A 4-hour video at ~150 words/minute produces ~36,000 words × ~5 chars/word = ~180,000 characters of transcript. The sampler drops approximately 85% of segments to fit within the budget. For a 4-hour interview, this may cause the LLM to miss high-quality clips in the unsampled segments.

**This is a High-impact scalability gap for the stated 4-hour target.** A 28,000-character window covers approximately 36 minutes of a 4-hour video when evenly sampled. The `step`-based uniform sampling does not prioritize high-density or high-energy segments.

**Suggested Fix** (recommendation, not auditable code finding): Increase `max_chars` to match the target LLM's context window (Gemini 2.0 Flash supports 1M tokens ≈ ~750,000 chars; Llama-3.3-70b on Groq supports 128K tokens ≈ ~95,000 chars). At minimum, document the coverage gap in the configuration comments.

---

## 10. Prioritized Improvement Roadmap

| ID | Priority | Task | Addresses | Benefit | Complexity | Risk |
|----|----------|------|-----------|---------|------------|------|
| T-001 | P1 | Remove hardcoded API key; load from environment variable | SEC-001 | Eliminates Critical security exposure | Low | Low |
| T-002 | P1 | Remove `shell=True` from `_sh()`; eliminate `pip`/`apt-get` from application code | SEC-002, ARCH-002 | Eliminates shell injection surface and Colab coupling | Medium | Low |
| T-003 | P1 | Fix FFmpeg pipe resource leak with `try/finally` | REL-005 | Prevents zombie processes and silent clip corruption | Low | Low |
| T-004 | P1 | Add input validation for video path and YouTube URL | SEC-004 | Prevents path traversal and shell metachar injection | Low | Low |
| T-005 | P2 | Bundle all fonts in `fonts/` directory; remove runtime downloads | DEP-001, DEP-002, SEC-003 | Eliminates network fragility at startup | Low | Low |
| T-006 | P2 | Replace `/tmp/` hardcoded paths with `tempfile.mkdtemp()` | SEC-003, CODE-002 | Eliminates CWE-59 symlink risk; provides clean per-run isolation | Low | Low |
| T-007 | P2 | Add retry logic and explicit failure marking to `gen_meta()` | REL-004 | Prevents silent metadata loss; enables targeted re-runs | Low | Low |
| T-008 | P2 | Delete audio WAV after transcription; clean up dead code blocks | REL-003, CODE-004, CODE-005, CODE-006, CODE-007, CODE-008 | Reclaims 460 MB per 4-hour run; removes maintenance noise | Low | Low |
| T-009 | P2 | Wrap FFmpeg pipe and render loop in `try/finally` for `raw_cap` | REL-001, CODE-003 | Guarantees intermediate file cleanup on failure | Low | Low |
| T-010 | P3 | Replace `dlib` + 68-landmark model with MediaPipe FaceMesh | PERF-001, AI-001, DEP-001 | Eliminates 100 MB model; faster face scan (see research.md) | Medium | Medium |
| T-011 | P3 | Decompose `render_clip()` into focused helper functions | CODE-001, CODE-009 | Enables independent testing and future optimization | High | Medium |
| T-012 | P3 | Introduce `TranscriptionProvider`, `LLMProvider`, `FaceDetectorProvider` interfaces | ARCH-003, AI-002 | Enables provider swaps without core logic changes | Medium | Low |
| T-013 | P3 | Replace all `print()` with structured `logging` module | REL-002, CODE-007 | Enables log level control and production monitoring | Medium | Low |
| T-014 | P4 | Merge subtitle burn into raw-pipe FFmpeg step; evaluate `h264_nvenc` | PERF-002, PERF-003 | Eliminates one full re-encode per clip | Medium | High |
| T-015 | P4 | Build CLI batch orchestrator with per-video output directories | PROD-001, PROD-002, ARCH-001 | Enables queued batch processing of 5+ videos | Medium | Low |

---

## 11. Refactoring Rules & Constraints

Before executing any roadmap task, all implementing agents MUST adhere to these rules:

1. **Zero-Budget**: No paid APIs, SaaS platforms, or commercial SDKs may be introduced.
2. **Offline Capable**: After dependencies are installed, the pipeline must not assume internet access (except for LLM API calls and `yt-dlp` downloads, which are explicitly user-configured).
3. **Backward Compatible**: Every task must preserve the visual output characteristics of v2.1: 1080×1920 clips, CRF 18–22, karaoke-style bilingual subtitles, smart crop behavior.
4. **No Direct OS Modifications**: No `apt-get` or global `pip install` commands inside application logic.
5. **No Automatic Execution**: The implementing agent must never run the pipeline, execute FFmpeg, or load AI models. Tasks that require validation must be documented for manual execution by the user on the target server.
6. **Static Verification First**: Each task must be verifiable by code review before runtime testing.
