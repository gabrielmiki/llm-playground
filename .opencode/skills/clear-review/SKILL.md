---
name: clear-review
description: C.L.E.A.R. checklist framework for AI-generated code review
---

# C.L.E.A.R. Code Review Skill

Structured code review framework optimized for AI-generated code.

## Purpose

Provide a systematic checklist for reviewing code, with special attention to AI-specific failure modes.

## Trigger

When user asks to review code, or before any commit.

## Dimensions

### C — Context
Does implementation match original intent?
- [ ] Check story file / acceptance criteria
- [ ] Verify commit message reflects actual changes
- [ ] Confirm no feature creep (scope expanded beyond ticket)

### L — Logic
Is business logic correct?
- [ ] Trace happy path manually
- [ ] Trace at least one error path
- [ ] For ML: verify loss computation, gradient flow, metric calculation
- [ ] Check edge cases are handled

### E — Efficiency
Are there performance issues?
- [ ] N+1 query patterns in data loading
- [ ] Unnecessary loops or repeated computation
- [ ] For ML: batch processing, GPU memory efficiency
- [ ] Tokenization efficiency for text processing

### A — Architecture
Does code respect project patterns?
- [ ] Layer separation (collect → preprocess → model → generate)
- [ ] No circular imports
- [ ] Dependency injection for external services
- [ ] Immutable data/raw/

### R — Reliability
Are error cases handled?
- [ ] Exceptions caught at appropriate layer
- [ ] Timeouts configured for external calls
- [ ] Retries with backoff for transient failures
- [ ] GPU availability handled gracefully

## AI-Specific Checks

- [ ] **Duplication**: Search for similar code blocks that could be extracted
- [ ] **Shallow tests**: Assertions check values, not just status codes
- [ ] **Missing guards**: Null checks, early returns, type validation
- [ ] **Unused imports**: All imports are actually used
- [ ] **Consistent patterns**: Matches existing codebase conventions

## Output

Generate structured review with:
- Verdict: APPROVE | REQUEST_CHANGES | BLOCK
- Findings per dimension
- Specific file:line citations
- Actionable recommendations

## Workflow

After completing the checklist:
1. Summarize findings by dimension
2. Prioritize blocking issues vs. suggestions
3. Provide specific file:line references
4. Offer actionable recommendations
