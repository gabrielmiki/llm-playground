# LLM Playground Process Flow

## Overview
This document describes how to use the agents, skills, and folder structure together for effective AI-assisted development.

## Session Folder Structure

Each session creates a folder at `.claude/handoffs/YYYY-MM-DD-title/`:

```
.claude/handoffs/
└── 2024-03-25-attention-implementation/
    ├── handoff.md                    # Main handoff document
    ├── input/
    │   └── context/                  # Previous session outputs (review results, decisions)
    │       └── tdd-review-output.json
    └── output/
        ├── reviews/                 # Agent review outputs for this session
        │   └── code-review-2024-03-25.json
        ├── decisions/               # Architectural decisions made this session
        │   └── decision-attention-mechanism.md
        └── analysis/               # Research/analysis done this session
            └── attention-benchmarking.md
```

## Complete Workflow

### Phase 1: Session Start

1. **Check for handoff folder** in `.claude/handoffs/`
2. **Read handoff.md** if exists (previous session context)
3. **Check specs** in `docs/context/`:
   - `@docs/context/architecture.md` — model architecture
   - `@docs/context/pipeline.md` — data pipeline
4. **Get code context**: Run `git diff HEAD~1` to see recent changes
5. **Load relevant skill** if needed: `/skill prd-writer`, `/skill continuation`, etc.

### Phase 2: Requirement Definition (optional)

**Trigger**: User asks to define requirements for new feature.

1. Load @.claude/skills/prd-writer
2. Elicit requirements via Socratic questioning
3. Generate PRD
4. Save to relevant location (e.g., `docs/requirements/`)

### Phase 3: Planning (optional)

**Trigger**: User asks to generate tickets from PRD.

1. Load @.claude/skills/ticket-generator
2. Convert PRD to structured tickets
3. Order by dependency:
   - collect/ (data sources first)
   - preprocess/ (cleaning, tokenization)
   - model/ (architecture)
   - generate/ (text generation)
   - tests/ (last)

### Phase 4: Per-Ticket Implementation Loop

For each ticket, follow this sequence:

```
┌─────────────────────────────────────────────────────────────┐
│  TDD Review (before coding)                                 │
│  Invoke: @.claude/agents/tdd-reviewer                       │
│  Input: Ticket acceptance criteria                           │
│  Output: Validation report → output/reviews/tdd-review-[date].json │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Implementation (main session)                               │
│  - Write code following patterns in docs/context/           │
│  - Run git diff HEAD~1 to see changes                      │
│  - Store implementation files                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Pre-commit Check (if errors exist)                         │
│  Invoke: @.claude/agents/pre-commit-checker                │
│  Input: Quality tool output (ruff, mypy, pytest)            │
│  Output: Structured error explanation → output/reviews/     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Security Diagnosis (if new dependencies)                   │
│  Invoke: @.claude/agents/security-diagnosis               │
│  Input: git diff HEAD~1, pyproject.toml                    │
│  Output: Package verification → output/reviews/              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Code Review (before commit)                                │
│  Invoke: @.claude/agents/code-reviewer                     │
│  Input: git diff HEAD~1, specs in docs/context/            │
│  Output: C.L.E.A.R. analysis → output/reviews/              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Commit                                                      │
│  - Stage changes                                            │
│  - Write detailed commit message                              │
│  - Run quality checks (uv run ruff check .)                  │
└─────────────────────────────────────────────────────────────┘
```

### Phase 5: Session End

1. Load @.claude/skills/continuation
2. Create session folder: `.claude/handoffs/YYYY-MM-DD-title/`
3. Save handoff.md with:
   - Progress (completed/incomplete)
   - Current state
   - Key decisions made
   - Do not redo list
   - Next steps
4. Store agent outputs to:
   - `output/reviews/` — all review JSONs
   - `output/decisions/` — architectural decisions
   - `output/analysis/` — research/analysis

### Phase 6: Architecture Decisions

**Trigger**: Major technical decision needed.

1. Invoke @.claude/agents/architecture-reviewer
2. Input: Plan + git diff + specs
3. Output: Review with ADR recommendation
4. If decision made, save to `output/decisions/decision-[name].md`

## Agent Invocation Reference

| Agent | When | How to Invoke | Input |
|-------|------|---------------|-------|
| tdd-reviewer | Before coding | @.claude/agents/tdd-reviewer | Acceptance criteria |
| code-reviewer | Before commit | @.claude/agents/code-reviewer | git diff output |
| pre-commit-checker | After lint/tests | @.claude/agents/pre-commit-checker | Quality tool JSON |
| security-diagnosis | After adding deps | @.claude/agents/security-diagnosis | git diff, pyproject.toml |
| architecture-reviewer | Major decisions | @.claude/agents/architecture-reviewer | Plan + specs |

## Skill Reference

| Skill | Purpose | Load Command |
|-------|---------|-------------|
| prd-writer | Socratic requirements elicitation | /skill prd-writer |
| ticket-generator | PRD → structured tickets | /skill ticket-generator |
| continuation | Session handoff generation | /skill continuation |
| clear-review | C.L.E.A.R. checklist | /skill clear-review |

## How Agents Get Code Context

All review agents use `git diff` to get code context:

```bash
git diff HEAD~1              # Full diff of changes
git diff --name-only        # List of changed files
git show HEAD:path/file.py  # File at specific commit
```

Agents are instructed to run these commands at the start of their execution.

## Specs Always in docs/context/

- `@docs/context/architecture.md` — Model architecture patterns
- `@docs/context/pipeline.md` — Data pipeline documentation
- Any feature-specific specs stored in relevant docs/ subdirectory

## Handoff Folder Contents

```
.claude/handoffs/[session-name]/
├── handoff.md                    # REQUIRED: Main handoff document
├── input/
│   └── context/                  # Previous session outputs
│       └── [previous-review-outputs].json
└── output/
    ├── reviews/                 # Agent outputs this session
    │   ├── code-review-YYYY-MM-DD.json
    │   ├── tdd-review-YYYY-MM-DD.json
    │   └── security-diagnosis-YYYY-MM-DD.json
    ├── decisions/               # Architectural decisions
    │   └── decision-[name].md
    └── analysis/               # Research/analysis
        └── [analysis-name].md
```

## Context Management Rules

1. **Compact at 60%**, not 90%
2. **Fresh session > stale context**: Use handoffs to reset
3. **Git diff for code**: Agents always use `git diff` for code context
4. **Specs in docs/context/**: Reference, don't copy
5. **Outputs persist**: Agent outputs saved to folder for future reference
