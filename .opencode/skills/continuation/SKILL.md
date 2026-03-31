---
name: continuation
description: Generate session handoff documents for seamless transitions between agent sessions
---

# Continuation Skill

Generate session handoff documents that enable seamless transitions between agent sessions.

## Purpose

Preserve context and progress between sessions so the next session can continue without rework or confusion.

## Trigger

Before ending any session, generate a continuation prompt if work is incomplete.

## Session Folder Structure

Each session creates a folder at `.opencode/handoffs/YYYY-MM-DD-title/`:

```
.opencode/handoffs/
└── 2024-03-25-attention-implementation/
    ├── handoff.md                    # Main handoff document
    ├── input/
    │   └── context/                  # Previous session outputs
    │       └── tdd-review-output.json
    └── output/
        ├── reviews/                 # Agent review outputs
        │   └── code-review-2024-03-25.json
        ├── decisions/               # Architectural decisions
        │   └── decision-attention-mechanism.md
        └── analysis/               # Research/analysis
            └── attention-benchmarking.md
```

## Document Structure (handoff.md)

```markdown
# Session Handoff: [Brief Title]
**Date**: YYYY-MM-DD  
**Session Duration**: ~XX minutes

## Context
[2 sentences: What was the goal? What are we trying to accomplish?]

## Progress
- [x] **Completed**: [What was finished and its outcome]
- [x] **Completed**: [What was finished and its outcome]
- [ ] **Incomplete**: [What wasn't finished and why]

## Current State
- **Last completed action**: [What was the last thing done]
- **Key decisions made**: [List with references to output/decisions/]
- **Key decisions pending**: [What still needs to be decided]
- **Blockers**: [What's preventing progress]

## Code Context
Run: `git diff HEAD~1` to see implementation changes

## Specs Reference
- Architecture: `docs/context/architecture.md`
- Pipeline: `docs/context/pipeline.md`
- [Any other relevant docs]

## Agent Outputs
- Reviews: `output/reviews/[review-name]-[date].json`
- Decisions: `output/decisions/[decision-name].md`
- Analysis: `output/analysis/[analysis-name].md`

## Do Not Redo
- [Approach Z was tried and failed because...]
- [Known issue: A doesn't work with B]

## Next Steps (Prioritized)
1. **[Action]**: [Specific thing to do]
2. **[Action]**: [Specific thing to do]

## Environment
- Working directory: `/Users/gabriel/GItHub/llm-playground`
- Commands to run: `uv sync`
```

## How Agents Get Code Context

For review agents that need to see code:
1. Run `git diff HEAD~1` to see changes from previous session
2. Run `git diff --name-only` for a list of changed files
3. Use `git show HEAD:path/to/file.py` to see file contents

## Storage

Create folder: `.opencode/handoffs/YYYY-MM-DD-title/`
Save handoff.md inside the folder

## Usage

To start a new session from handoff:
1. Read the handoff file from the folder
2. Check specs in `docs/context/`
3. Run `git diff HEAD~1` to see what was implemented
4. Check `output/` for previous review outputs
5. `/clear` context and start fresh

## Context Management

- Compact at 60% context, not 90%
- Fresh session with written handoff > resuming stale context
- Fewer tokens = fewer errors = higher accuracy
