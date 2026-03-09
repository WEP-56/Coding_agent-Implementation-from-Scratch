# CodingGirl Engineering Standards

## File Size Rule (Mandatory)

- Preferred: **single file < 800 lines**
- Hard limit: **if a file reaches 1000 lines, it MUST be refactored/split immediately**

### Split Guidance

- Split by responsibility/domain, not arbitrary chunks.
- Keep stable external API surface (function names/command names) when splitting.
- Create an orchestrator/index file for module wiring when needed.
- Add/adjust tests or verification commands after split to ensure no behavior regression.

### Review Checklist

- [ ] Any touched file > 800 lines? If yes, justify and plan split.
- [ ] Any file >= 1000 lines? If yes, split in the same work item (blocking requirement).
- [ ] Build/lint/tests pass after split.
