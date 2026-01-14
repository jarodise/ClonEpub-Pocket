---
description: How to run ClonEpub commands
---

# ClonEpub Development Workflow

// turbo-all

## Running the App
```bash
uv run clonepub
```

## Running Python Commands
**NEVER use `python3` directly. Always use:**
```bash
uv run python -c "your_code_here"
```

## Installing Dependencies
```bash
uv sync
```

## Testing Changes
```bash
uv run clonepub
```

## Important Notes
- The project uses `uv` for dependency management
- All Python commands MUST be prefixed with `uv run`
- System Python (`python3`) does NOT have project dependencies
