# Production Release Checklist

Use this checklist to verify the repository is ready for public release.

## Code Quality

- [ ] `ruff check src/ tests/` passes cleanly
- [ ] All 186+ unit/integration tests pass: `pytest -x`
- [ ] No `TODO`, `FIXME`, `XXX`, or `HACK` comments remain in `src/`
- [ ] No debug `print()` calls remain (progress `print()` in `pipeline.py` is intentional)
- [ ] All exception paths handle cleanup (temp dirs, file handles, subprocesses)

## Security

- [ ] No API keys, secrets, or tokens hardcoded in any source file
- [ ] All API keys loaded from environment (`OPUSCLIP_API_KEY`)
- [ ] No `shell=True` subprocess calls
- [ ] Input validation on all user-supplied paths and URLs
- [ ] Temporary files use secure `tempfile` APIs

## Documentation

- [ ] `README.md` is up to date with CLI usage, GPU setup, troubleshooting
- [ ] `docs/configuration.md` matches `PipelineConfig` fields exactly
- [ ] `docs/api.md` documents all public APIs and exception hierarchy
- [ ] `docs/architecture.md` Mermaid diagrams reflect current architecture
- [ ] `CHANGELOG.md` has complete version history
- [ ] `CONTRIBUTING.md` describes dev setup and PR process
- [ ] `examples/` scripts work with current API
- [ ] `notebooks/opusclip_demo.ipynb` runs on Google Colab

## Packaging & Distribution

- [ ] `pyproject.toml` has correct metadata (version, author, Python reqs)
- [ ] `pip install -e .` installs successfully
- [ ] `python -m build` produces valid source and wheel distributions
- [ ] Console script entry point `opusclip` works: `opusclip --help`
- [ ] `python -m opusclip --help` works
- [ ] Docker image builds: `docker build -t opusclip .`
- [ ] `docker-compose up` starts correctly with GPU passthrough

## Deployment

- [ ] `Dockerfile` pins base image and dependency versions
- [ ] `docker-compose.yml` exposes all required environment variables
- [ ] GPU acceleration: `h264_nvenc` encoder tested on target hardware
- [ ] CUDA Whisper tested on target GPU
- [ ] Batch processing tested with at least 2 video sources
- [ ] Resume functionality tested after interruption

## Git & Versioning

- [ ] Version tag applied: `git tag v1.0.0`
- [ ] Tag pushed to remote: `git push origin v1.0.0`
- [ ] All commits on `main` are clean and meaningful
- [ ] No `.env` files, secrets, or large binaries committed
