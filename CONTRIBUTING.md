# Contributing to OpusClip

Thank you for your interest in contributing! This project follows a strict set of engineering and repository standards.

## Code Quality Standards
- **SOLID Principles**: Keep modules small and single-purpose.
- **Type Hints**: All function signatures must be fully type-hinted.
- **Dataclasses**: Use `dataclasses` for all state and configuration objects.
- **Logging**: Use the structured `logging` module. Never use `print()` in production logic.
- **Dependency Injection**: Pass dependencies explicitly (e.g., passing an LLM client interface). No hidden global state.

## Implementation Workflow (The 11 Phases)
All development occurs in isolated phases. You must not jump ahead or mix concerns across phases.
1. Each phase must have its own branch.
2. Remove all temporary or debug code before committing.
3. Ensure clean formatting.
4. Update `PROJECT_PROGRESS.md` after completion.

See `PROJECT_PROGRESS.md` for the current phase status.

## Testing
All code must have unit tests. When modifying the rendering pipeline, ensure visual output quality remains identical (1080x1920, CRF 18-22, accurate karaoke subtitles).
