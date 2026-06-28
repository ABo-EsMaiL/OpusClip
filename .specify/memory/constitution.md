<!--
Sync Impact Report:
- Version change: [CONSTITUTION_VERSION] -> 1.0.0
- List of modified principles:
  - [PRINCIPLE_1_NAME] -> I. Zero-Cost Policy
  - [PRINCIPLE_2_NAME] -> II. Safety Rules
  - [PRINCIPLE_3_NAME] -> III. Engineering & Architecture Rules
  - [PRINCIPLE_4_NAME] -> IV. Performance & Reliability
  - [PRINCIPLE_5_NAME] -> V. Communication Rules
- Added sections:
  - Project Mission (Section 2)
  - Governance Rules
- Removed sections:
  - Section 3 (unused template placeholder)
- Templates requiring updates:
  - .specify/templates/plan-template.md (✅ aligned)
  - .specify/templates/spec-template.md (✅ aligned)
  - .specify/templates/tasks-template.md (✅ aligned)
- Follow-up TODOs: None
-->

# OpusClip Constitution

## Core Principles

### I. Zero-Cost Policy
The project budget is exactly **$0**. All implementations must prioritize free and open-source software. Paid APIs, libraries, SaaS platforms, or commercial services must never become mandatory dependencies. Whenever a commercial solution is suggested, an equivalent free alternative must also be proposed.

### II. Safety Rules
- **Never execute the project automatically**: The assistant must NEVER run the application, execute notebooks, launch scripts, render videos, execute FFmpeg commands, start servers, run benchmarks, download AI models, download datasets, install packages, or execute shell commands that modify the system unless the user explicitly asks for that action. The assistant's default behavior is analysis only.
- **Never download anything automatically**: Do not download AI/Whisper/LLM models, font packages, system packages, Docker images, Python packages, Git repositories, or external assets automatically. Clearly explain what should be downloaded and wait for user approval.
- **Never consume local machine resources**: Assume the user's local computer has limited CPU, RAM, GPU, VRAM and storage. Heavy operations must be postponed until the user runs them on the dedicated server. Do not assume local execution is acceptable.
- **Experimental code policy**: If a tiny experiment is necessary, create a temporary folder named `temp/`, place every generated file inside it, never modify project files, never overwrite existing files, and delete temporary artifacts when finished if requested. No experiment may touch the main project structure.
- **No automatic modifications**: Never rewrite large portions of the project without approval. Every significant refactor must first be explained. Large architectural changes require user confirmation.

### III. Engineering & Architecture Rules
- **Engineering Principles**: Always prioritize correctness, maintainability, readability, modularity, performance, scalability, and reliability. Short-term hacks are prohibited.
- **Architecture Rules**: The project should evolve toward modular architecture, reusable components, and replaceable providers (AI providers, transcription engine, subtitle engine, face detection engine). Avoid global state whenever possible. Functions should follow the Single Responsibility Principle.

### IV. Performance & Reliability
- **Performance Principles**: Every optimization must have a measurable reason. Review CPU usage, GPU usage, RAM usage, Disk I/O, FFmpeg efficiency, Whisper performance, Face detection performance, and Subtitle rendering performance. Avoid premature optimization but eliminate obvious bottlenecks.
- **Reliability**: The project should support resume after interruption, logging, validation, retries, caching, and graceful failure.
- **Compatibility**: Maintain backward compatibility whenever practical. Existing features should continue working unless the user explicitly approves breaking changes.

### V. Communication Rules
Before implementing changes, the assistant must:
- Explain the problem.
- Explain why it matters.
- Explain the proposed solution.
- Explain possible alternatives.
- Explain expected impact.
Never hide assumptions. If uncertain, ask instead of guessing.

## Project Mission
Build a production-grade AI-powered automatic short-video generation pipeline from long-form videos while relying entirely on free and open-source technologies whenever possible. The primary goal is long-term maintainability, reliability, performance, and modular architecture rather than quick fixes.

## Governance
- **Amendment Procedure**: Any updates or amendments to this constitution must be proposed by the agent or requested by the user, and ratified by the user before taking effect.
- **Versioning Policy**: Semantic versioning rules apply (Major: backward incompatible changes, Minor: new sections/expanded guidance, Patch: typo/wording fixes).
- **Compliance Review**: All design documents, code changes, and task checklists must be validated against the principles defined in this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-06-28 | **Last Amended**: 2026-06-28
