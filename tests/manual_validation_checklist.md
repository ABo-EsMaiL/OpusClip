# Manual Validation Checklist

These tests require a runtime environment with ffmpeg, ffprobe, and (optionally) a CUDA-capable GPU. They cannot run in CI without these external dependencies.

## Prerequisites

- ffmpeg + ffprobe installed and on `PATH`
- CUDA-capable GPU (for GPU-accelerated tests, optional)
- ~2GB free disk space per test video
- A sample video file (any short mp4, 30–60 seconds recommended)

---

## 1. Single-video pipeline

**Command:**
```bash
python -m opusclip /path/to/sample.mp4 --output /tmp/opusclip_test
```

**Expected:**
- Pipeline runs through all 10 stages without error
- JSON output printed to stdout with clips array
- Output directory contains `clips/`, `metadata/`, `pipeline_summary.json`
- Each clip is a valid 1080×1920 mp4 with burned-in subtitles
- Audio is present in each clip

**Failure signals:**
- Import errors at startup
- ffmpeg/ffprobe not found
- Pipeline crash mid-execution

---

## 2. Batch processing (2+ videos)

**Command:**
```bash
python -m opusclip /path/to/video1.mp4 /path/to/video2.mp4 --output /tmp/opusclip_batch
```

**Expected:**
- Both videos processed sequentially
- JSON array output with 2 entries
- Isolated output subdirectories per video (e.g., `video1_abc123/`, `video2_def456/`)
- Failure in one video does not abort the batch

---

## 3. Resume after interruption

**Procedure:**
1. Start processing: `python -m opusclip sample.mp4 --output /tmp/opusclip_resume`
2. Interrupt with `Ctrl+C` mid-way (e.g., during rendering)
3. Re-run with `--resume`: `python -m opusclip sample.mp4 --output /tmp/opusclip_resume --resume`

**Expected:**
- Second run skips completed steps and resumes from last incomplete step
- Completed clips are not re-generated
- Final output matches a clean (non-resumed) run

---

## 4. YouTube URL input

**Command:**
```bash
python -m opusclip "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --output /tmp/opusclip_yt
```

**Expected:**
- Video is downloaded via yt-dlp
- Pipeline proceeds normally
- Output is identical structure to local file input

**Note:** Requires network access and yt-dlp installed.

---

## 5. Encoder selection

**Command:**
```bash
python -m opusclip sample.mp4 --encoder h264_nvenc --output /tmp/opusclip_nvenc
python -m opusclip sample.mp4 --encoder libx264 --output /tmp/opusclip_x264
```

**Expected:**
- Both runs complete successfully
- NVENC run is measurably faster (if GPU available)
- Output quality is visually comparable (CRF 18–22)
- Fallback warning printed if h264_nvenc is unavailable

---

## 6. Legacy renderer

**Command:**
```bash
python -m opusclip sample.mp4 --renderer legacy --output /tmp/opusclip_legacy
```

**Expected:**
- Pipeline completes
- Two-pass rendering (slower but compatible)
- Output quality matches optimized renderer

---

## 7. Face detection & crop quality

**Procedure:**
Process a video with multiple speakers, then inspect the output clips.

**Checklist:**
- [ ] Crop window follows the active speaker
- [ ] Solo speaker → frame centres on that face
- [ ] Multiple speakers → wider GROUP framing
- [ ] No faces → centred crop (BROLL mode)
- [ ] No jarring jumps between shots (smooth panning)

---

## 8. Arabic subtitle rendering

**Procedure:**
Process an Arabic-language video.

**Checklist:**
- [ ] Arabic text renders correctly (right-to-left)
- [ ] Tajawal font used for Arabic styles
- [ ] Montserrat font used for English text
- [ ] Hook style (cyan) renders title card correctly
- [ ] Karaoke word highlighting works
- [ ] No "tofu" (hollow boxes) in subtitle output

---

## 9. Edge cases

**Test each scenario:**
- [ ] 4-hour long video (test memory usage and ffmpeg stability)
- [ ] Video with no audio track (should fail gracefully at transcription)
- [ ] Very short video (<10s) (should produce 0 clips or handle gracefully)
- [ ] Video with non-standard resolution (should still output 1080×1920)
- [ ] Invalid file path (should print error, exit 1)
- [ ] Invalid YouTube URL (should print error, exit 1)
- [ ] Missing API key (should print configuration error, exit 1)

---

## 10. Performance benchmarks

**Test:** Process the same 5-minute video 3 times, record wall-clock time.

| Run | Encoder | Time | Notes |
|-----|---------|------|-------|
| 1 | libx264 (CPU) | ___s | baseline |
| 2 | h264_nvenc | ___s | GPU accelerated |
| 3 | libx264 (resumed) | ___s | resume from cache |

**Acceptance criteria:**
- Pipeline completes in < real-time for CPU encoding of clips under 2 min
- NVENC is at least 2× faster than libx264 on the same hardware
- Resume is measurably faster than a clean run (skips completed steps)
