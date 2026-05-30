# Code Review Round 1: Ticket 9 — Graceful Degradation

**Reviewer**: code-reviewer agent  
**Framework**: C.L.E.A.R.  
**Date**: May 30, 2026  

## Verdict: REQUEST_CHANGES

## Findings

| # | Type | Severity | Finding | Location | Fix |
|---|------|----------|---------|----------|-----|
| 1 | Logic | Medium | `build_degradation_warning()` accepts `ticker`/`target_date` but never uses them — misleading API | `degradation.py:23-28` | Include ticker/date in fallback_failed messages |
| 2 | Architecture | Medium | Dead `WARNING_FIELDS` constant — never referenced | `fusion.py:11` | Remove it |
| 3 | Architecture | Low | Unnecessary `_get_weekday_adjustment` alias after extracting `date_utils.py` | `news_collector.py:38` | Replace with direct import |
| 4 | Test | Low | Per-ticker test uses separate directories (unrealistic) | `test_degradation.py:382` | Add shared-directory test |
| 5 | Reliability | Low | No integration test for `pipeline.py` exception handlers | `pipeline.py:82-112` | Add `TestPipelineIntegration` |
| 6 | Context | Low | Stale docstring references `news_collector._get_weekday_adjustment()` | `degradation.py:125` | Update to `date_utils.get_weekday_adjustment()` |

## AC Coverage: All 8 PASS
