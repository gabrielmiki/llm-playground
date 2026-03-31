---
name: prd-writer
description: Elicit requirements through Socratic questioning before generating specifications
---

# PRD Writer Skill

Elicit requirements through Socratic questioning before generating any specification content.

## Purpose

Ensure requirements are well-understood before writing any specification. Avoids the common trap of generating specs based on incomplete understanding.

## Trigger

When user asks to create a PRD, spec, or requirements document.

## Behavior

### Phase 1: Questioning (MANDATORY)

You MUST ask at least 8 clarifying questions across these categories BEFORE generating content:

**User Roles & Workflows (breadth-first)**
1. Who are the primary users of this feature?
2. What are the main workflows they'll perform?
3. What decisions do they need to make using this feature?

**Edge Cases & Error Handling (depth)**
4. What should happen when data is malformed or incomplete?
5. What are the failure modes and how should they be surfaced?
6. What are the boundary conditions (size limits, rate limits, etc.)?

**Technical Constraints**
7. Are there external API dependencies we need to handle gracefully?
8. What's the acceptable performance envelope (latency, throughput)?
9. Are there security considerations (data privacy, rate limiting)?

**Alternatives Considered**
10. What existing approaches were considered and rejected?

### Phase 2: Generation

Only after questions are resolved, generate the PRD with these sections:
- Goals & Non-Goals
- User Stories (per role)
- API Contract Sketches (Query/Path/Body labeled)
- Edge Cases & Error States
- Alternatives Considered

## Constraints

- Ask 2-3 questions at a time, not all at once
- Do NOT presuppose architecture in questions
- If user gives incomplete answer, ask follow-up before proceeding
- Never generate speculative content during questioning phase
- Progression: open questions → probing questions → clarification → synthesis
