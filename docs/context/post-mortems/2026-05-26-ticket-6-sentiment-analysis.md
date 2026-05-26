# Post-Mortem: Ticket 6 — Sentiment Analysis with Pretrained Model

**Date:** May 26, 2026  
**Status:** ✅ COMPLETE  
**Review Status:** APPROVE (after 1 TDD review round + 1 code review round + 1 re-review)

---

## 1. Overview

### Original Ticket
**Title:** Implement financial sentiment analysis using FinBERT

**Original Acceptance Criteria (3 ACs, minimal detail):**
```markdown
- AC-01: Given a FusedRecord from Ticket 4 pipeline, When analyze(record) is called, Then returns aggregate sentiment score between -1 and 1
- AC-02: Given empty FusedRecord, When analyze(record) is called, Then returns neutral score 0.0
- AC-03: Given a FusedRecord with articles, When analyze(record) is called, Then returns per-article breakdown
```

**Original api_spec:**
```
FinBertSentiment(model_name: str, device: str | None)
FinBertSentiment.analyze(record: FusedRecord) -> dict
```

### Refined Acceptance Criteria (11 ACs after TDD review)

```
AC-01:  FinBertSentiment(model_name="ProsusAI/finbert") loads in eval mode with no gradient computation
AC-02:  Single positive article returns SentimentResult where score = P(pos)-P(neg) in [-1,1], confidence in [0,1], len(breakdown)==1
AC-03:  3 mixed-sentiment articles produce confidence-weighted aggregate score, mean confidence, and 3 breakdown entries with title/score/confidence/label
AC-04:  Empty news_articles returns SentimentResult(0.0, 0.0, [])
AC-05:  Offline/load failure raises ModelLoadError with descriptive message
AC-06:  Text exceeding max_length (512) silently truncated without error
AC-07:  Blank/whitespace-only articles skipped in breakdown and aggregation
AC-08:  No GPU → device == "cpu" without error
AC-09:  Market-data-only record (news_articles=[]) returns neutral result
AC-10:  None passed as fused_record raises TypeError with descriptive message
AC-11:  Article missing "title" key processed using only summary (no KeyError)
```

---

## 2. Problems Identified

### TDD Review Round 1 — NEEDS REVISION (12 blocking + 5 moderate issues)

The initial ticket had only 3 vague ACs and failed when checked against the actual application context and data types:

#### Blocking Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| Data flow contradiction | **Blocking** | Ticket listed `dependencies: [Ticket 5]` but FinBERT uses its own `BertTokenizer` (WordPiece, vocab ~30522), NOT the BPE backends from Ticket 5. Input should be `FusedRecord` (Ticket 4), not tokenized output |
| Only 2-3 ACs | **Blocking** | 3 ACs is insufficient for coverage. Missing: load failure, device fallback, blank articles, missing keys, truncation, None input, batch processing |
| No concrete output types | **Blocking** | API spec returned `dict` — no `SentimentResult`, `ArticleSentiment`, or field definitions. Downstream consumers couldn't depend on it |
| Score formula unspecified | **Blocking** | "aggregate sentiment score between -1 and 1" — how is this computed from the model's 3-class softmax output? Single-article vs aggregate? |
| Aggregation formula unspecified | **Blocking** | Multiple articles need combining — simple average? Weighted? What weight? |
| FusedRecord data shape unknown | **Blocking** | Review couldn't validate ACs because `FusedRecord.news_articles` structure wasn't loaded. Each article is a dict with keys: `title`, `summary`, `source`, `published_at`, `url` |
| No model init failure handling | **Blocking** | No AC for what happens when HuggingFace is unreachable or model name is invalid |
| What text is analyzed? | **Blocking** | AC-03 says "with articles" — do we use title? summary? both? How concatenated? |
| Truncation unspecified | **Blocking** | BERT has 512-token limit. What happens to longer articles? Silent truncation? Error? |
| batch_size default unspecified | **Blocking** | For 1000+ articles, inference needs batching. Default? Configurable? |
| Device fallback unspecified | **Blocking** | What if GPU unavailable? Silent CPU fallback? Error? |
| Missing import guard | **Blocking** | `torch` and `transformers` may not be installed. Module should load gracefully without them |

#### Moderate Issues

| Issue | Severity | Problem |
|-------|----------|---------|
| Blank/skipped articles | **Moderate** | AC-07 (blank articles skipped) was a TDD recommendation that became a full AC |
| Missing title handling | **Moderate** | AC-11 (missing "title" key) was a TDD recommendation that became a full AC |
| Parameter naming consistency | **Moderate** | `model_name` not `model_path` — clarify it's a HuggingFace model ID, not a local path |
| Method naming vs conventions | **Moderate** | `.analyze()` not `.predict()` — consistent with "analysis" project naming |
| More edge cases requested | **Moderate** | TDD reviewer suggested additional edge cases beyond what was incorporated |

### Implementation Issues

During implementation, several issues emerged that weren't caught by the spec review:

| Issue | Severity | Problem | Fix |
|-------|----------|---------|-----|
| `MagicMock.__call__` doesn't work | **Blocking** | Setting `mock_model.__call__ = func` is silently ignored — `__call__` is looked up on the type, not the instance | Use `mock_model.side_effect = func` instead |
| `MockTensor.__getitem__` always row 0 | **Medium** | `self._data[0][index]` returns first row's column regardless of which row is being indexed | Check `len(self._data) == 1` for singletons (iter path), else use `self._data[index]` |
| `MockTensor.argmax` hardcoded to 0 | **Medium** | Always returned `0` regardless of actual values — labels always "positive" | Compute actual argmax via `row.index(max(row))` |
| Mock softmax ignores input logits | **Medium** | Global mock returns `[[0.8, 0.1, 0.1]] * batch_size` for any input — multi-article test can't verify different per-article scores | Override side_effect per-test with per-row probabilities |

### Code Review Round 1 — 6 Issues Found (C.L.E.A.R. Framework)

| Severity | Finding | Location | Fix |
|----------|---------|----------|-----|
| **High** | `test_multi_article_weighted_average` only asserts bounds, never verifies actual aggregation values or per-article labels — would pass if formula changed | `test_sentiment.py:276-315` | Override softmax mock per-test with per-row probabilities; assert exact scores/confidence/labels per article + final aggregation |
| **High** | `test_batch_processing` uses `call_count >= 1` instead of `call_count == 1` — would pass if batching broke | `test_sentiment.py:539` | Changed to `assert call_count == 1` |
| **Medium** | Duplicated `SentimentResult(0.0, 0.0, [])` early return in both empty-article and empty-text paths | `sentiment.py:79-84, 100-105` | Extracted `_NEUTRAL_RESULT` constant |
| **Medium** | `self.config` stored but never consumed (only `self.config.id2label` is used) | `sentiment.py:68` | Removed `self.config`, inlined to `self.id2label = AutoConfig.from_pretrained(...).id2label` |
| **Medium** | `or ""` guard unclear — `.get("title", "")` already returns `""`; the `or ""` only guards against `None` values | `sentiment.py:143` | Added `# handle None value` comment |
| **Medium** | `MockTensor.__getitem__` latent bug — always indexes row 0 even for multi-row tensors | `test_sentiment.py:35-36` | Check `len(self._data) == 1` for iter path; use `self._data[index]` for general case |

---

## 3. Fixes Applied

### A. Complete Ticket Rewrite

**Before (3 ACs, vague API):**
```text
- Dependencies: [Ticket 5] — WRONG
- analyze(record) returns dict — no type
- 3 ACs, no edge cases
```

**After (11 ACs, 11 implementation files):**
- Dependencies: [Ticket 4] — CORRECT (FinBERT tokenizes internally)
- `SentimentResult(sentiment_score, confidence, breakdown)` dataclass
- `ArticleSentiment(article_title, score, confidence, label)` dataclass
- Score formula: `P(positive) - P(negative)` from 3-class softmax
- Aggregation: confidence-weighted average: `Σ(score_i × confidence_i) / Σ(confidence_i)`
- 11 ACs covering all edge cases (empty, blank, missing keys, truncation, None, load failure, CPU fallback)

### B. Fixed Data Flow Dependency

**Before:** `dependencies: [Ticket 5]`

**After (FIXED):** `dependencies: [Ticket 4]`

FinBERT uses `BertTokenizer` (WordPiece, vocab ~30522) internally — NOT the BPE tokenizer backends from Ticket 5. The sentiment pipeline consumes `FusedRecord` directly (from the fusion pipeline) and handles its own tokenization.

### C. Added Concrete Output Types

**Before:** `-> dict`

**After (FIXED):**
```python
@dataclass
class ArticleSentiment:
    article_title: str
    score: float           # [-1.0, 1.0], P(pos) - P(neg)
    confidence: float      # [0.0, 1.0], max(P(pos), P(neg), P(neu))
    label: str             # "positive" | "negative" | "neutral"

@dataclass
class SentimentResult:
    sentiment_score: float  # aggregated score, confidence-weighted
    confidence: float       # mean of per-article confidences
    breakdown: list[ArticleSentiment]
```

### D. Added Conditional Imports (Import Guard)

**Before:** Top-level `import torch` — crashes if torch not installed

**After (FIXED):**
```python
try:
    import torch
    from transformers import (
        AutoConfig,
        AutoModelForSequenceClassification,
        AutoTokenizer,
    )
except ImportError:
    torch = None
    AutoConfig = None
    AutoModelForSequenceClassification = None
    AutoTokenizer = None
```

Plus runtime guard in `__init__`:
```python
if torch is None:
    raise ModelLoadError("torch is not installed.")
```

### E. Created Fixture Infrastructure

Created `tests/fixtures/sentiment_data.py` with 6 pytest fixture functions:
- `sample_fused_record_single_article` — 1 positive article
- `sample_fused_record_multi_article` — 3 mixed-sentiment articles
- `sample_fused_record_empty_articles` — empty list
- `sample_fused_record_blank_article` — empty title + whitespace summary
- `sample_fused_record_missing_title` — article without "title" key
- `sample_fused_record_long_text` — text exceeding 512 tokens

Registered in `tests/conftest.py`:
```python
pytest_plugins = [
    ...
    "tests.fixtures.sentiment_data",
]
```

### F. Created Model Module Structure

Created 4 files:
- `src/model/__init__.py` — Package declaration
- `src/model/exceptions.py` — `ModelLoadError` exception
- `src/model/pretrained/__init__.py` — Subpackage declaration
- `src/model/pretrained/sentiment.py` — `FinBertSentiment`, `SentimentResult`, `ArticleSentiment`

### G. Implemented Mock Tensor Infrastructure

Since `torch` has no wheel for CPython 3.14 on macOS x86_64, created a `MockTensor` class in tests:

```python
class MockTensor:
    def __init__(self, data: list[list[float]]): ...
    def cpu(self) -> MockTensor: ...
    def to(self, *args, **kwargs) -> MockTensor: ...
    def __getitem__(self, index: int) -> float: ...
    def __iter__(self): ...
    def item(self) -> float: ...
    def expand(self, *sizes) -> MockTensor: ...
    def argmax(self) -> int: ...
```

Plus `sys.modules["torch"] = _MOCK_TORCH` injection for environments where torch is not installed.

### H. Fixed side_effect vs __call__ (Implementation Discovery)

**Before:**
```python
def mock_forward(input_ids=None, attention_mask=None, **kwargs):
    return MagicMock(logits=logits)

mock_model.forward = mock_forward
mock_model.__call__ = mock_forward  # silently ignored!
```

**After (FIXED):**
```python
mock_model.side_effect = lambda input_ids=None, attention_mask=None, **kwargs: MagicMock(logits=logits)
```

`MagicMock.__call__` is a slot looked up on the type, not the instance. Setting it on the instance is silently ignored. `side_effect` is the correct way to control what happens when a mock is called.

### I. Fixed MockTensor.__getitem__ (Code Review)

**Before:**
```python
def __getitem__(self, index: int) -> float:
    return self._data[0][index]  # Always row 0!
```

**After (FIXED):**
```python
def __getitem__(self, index: int) -> float:
    if len(self._data) == 1:
        return self._data[0][index]
    return self._data[index]
```

The `__iter__` path wraps each row as `MockTensor([row])` (single-row), so `__getitem__` must handle both single-row (from iteration) and multi-row (direct access) tensors.

### J. Fixed MockTensor.argmax (Implementation Discovery)

**Before:**
```python
def argmax(self) -> int:
    return 0  # Always "positive"
```

**After (FIXED):**
```python
def argmax(self) -> int:
    row = self._data[0]
    return row.index(max(row))
```

### K. Fixed Multi-Article Aggregation Test (Code Review)

**Before:** Provided 3 different logit sets but global mock softmax always returned identical `[[0.8, 0.1, 0.1]]` × 3. Test only checked bounds.

**After (FIXED):** Override softmax side_effect per-test:
```python
original = _MOCK_TORCH.nn.functional.softmax.side_effect
per_article_probs = [
    [0.8, 0.1, 0.1],  # article 0 → score=0.7, conf=0.8, positive
    [0.1, 0.8, 0.1],  # article 1 → score=-0.7, conf=0.8, negative
    [0.3, 0.3, 0.4],  # article 2 → score=0.0, conf=0.4, neutral
]
_MOCK_TORCH.nn.functional.softmax.side_effect = (
    lambda x, dim: MockTensor(per_article_probs[:x.shape[0]])
)
try:
    result = sentiment.analyze(...)
    # Assert exact per-article scores, confidences, labels
    # Assert exact aggregated score and confidence
finally:
    _MOCK_TORCH.nn.functional.softmax.side_effect = original
```

### L. Fixed Duplicated Neutral Result (Code Review)

**Before:** `SentimentResult(0.0, 0.0, [])` returned verbatim in two locations

**After (FIXED):**
```python
_NEUTRAL_RESULT = SentimentResult(
    sentiment_score=0.0, confidence=0.0, breakdown=[],
)
# Both early returns use: return _NEUTRAL_RESULT
```

### M. Fixed Dead self.config (Code Review)

**Before:**
```python
self.config = AutoConfig.from_pretrained(model_name)
self.id2label = self.config.id2label
```

**After (FIXED):**
```python
self.id2label = AutoConfig.from_pretrained(model_name).id2label
```

### N. Fixed Tightened Batch Assertion (Code Review)

**Before:** `assert call_count >= 1`

**After (FIXED):** `assert call_count == 1` (with `batch_size=2` and 2 articles, exactly 1 forward call)

---

## 4. Technical Issues Found During Implementation

### Mock Infrastructure Challenges

The mock environment for torch required careful design because:

1. **No torch wheel for CPython 3.14 on macOS x86_64** — Unsupported platform/Python combination means tests must mock `torch` entirely. The `MockTensor` class needed to support: `.cpu()`, `.to()`, indexing, iteration, `.shape`, `.argmax()`, `.expand()`, `.item()`, and `__len__` — enough to exercise the real inference code path

2. **`sys.modules` injection timing** — The mock must be injected BEFORE `pytest.importorskip("src.model.pretrained.sentiment")` because `sentiment.py` does `import torch` at module level. Loading order is critical

3. **Mock softmax must produce valid probabilities** — Production code calls `torch.nn.functional.softmax(x, dim=-1)` then indexes `probs[0]`, `probs[1]`, `probs[2]`. The mock returns `[[0.8, 0.1, 0.1]] * batch_size` — a valid probability distribution that sums to 1.0

### MagicMock.__call__ Gotcha

Setting `mock_model.__call__ = my_function` does NOT work because `__call__` is defined on the class (in `MockMeta`), not the instance. MagicMock resolves `__call__` through `__getattr__` on the type. The correct approach is setting `mock_model.side_effect = my_function`, which MagicMock checks before falling through to `return_value`.

---

## 5. Final Implementation

### Files Created

```
src/model/
├── __init__.py                  # Package declaration (was empty directory)
├── exceptions.py                # ModelLoadError
└── pretrained/
    ├── __init__.py              # Subpackage declaration
    └── sentiment.py             # FinBertSentiment, SentimentResult, ArticleSentiment

tests/
├── test_sentiment.py            # 13 tests (MockTensor, mock torch setup)
└── fixtures/
    └── sentiment_data.py        # 6 FusedRecord fixtures

docs/
└── context/
    ├── financial-analysis-ticket-6.md  # Rewritten ticket (11 ACs, corrected pipeline)
    └── post-mortems/
        └── 2026-05-26-ticket-6-sentiment-analysis.md  # This file
```

### Files Modified

```
tests/conftest.py                # Added fixtures.sentiment_data to pytest_plugins
```

### Key Architecture

```python
class FinBertSentiment:
    def __init__(self, model_name="ProsusAI/finbert", device=None, max_length=512, batch_size=32):
        # Conditional imports with try/except ImportError
        # Runtime guard: if torch is None → ModelLoadError
        # Load model + tokenizer from HuggingFace
        # model.eval(), model.to(device)

    def analyze(self, record: FusedRecord) -> SentimentResult:
        # None check → TypeError
        # Empty news_articles → _NEUTRAL_RESULT
        # Build texts from article title + summary
        # No valid texts → _NEUTRAL_RESULT
        # Batch inference with torch.no_grad()
        # softmax → P(pos) - P(neg) per article
        # Confidence-weighted aggregation
```

### Training / Inference Details

| Aspect | Detail |
|--------|--------|
| Model | `ProsusAI/finbert` — BERT-base fine-tuned on financial text |
| Tokenizer | `BertTokenizer` (WordPiece, vocab ~30522) |
| Label mapping | `{0: "positive", 1: "negative", 2: "neutral"}` |
| Score formula | `P(positive) - P(negative)` in [-1.0, 1.0] |
| Aggregation | Confidence-weighted: `Σ(score_i × confidence_i) / Σ(confidence_i)` |
| Confidence | `max(P(pos), P(neg), P(neu))` per article |
| Batch processing | Configurable via `batch_size` (default 32) |
| Truncation | Silent at `max_length=512` via tokenizer's `truncation=True` |

---

## 6. Test Coverage

| Category | Tests | Covers ACs | Status |
|----------|-------|------------|--------|
| Model Loads Successfully | 1 | AC-01 | ✅ |
| Load Failure Raises Error | 1 | AC-05 | ✅ |
| CPU Fallback | 1 | AC-08 | ✅ |
| Single Article Analysis | 1 | AC-02 | ✅ |
| Score Formula | 1 | AC-02 (exact formula) | ✅ |
| Multi-Article Weighted Avg | 1 | AC-03 | ✅ |
| Empty Article List | 1 | AC-04 | ✅ |
| Market-Data Only Record | 1 | AC-09 | ✅ |
| None Input | 1 | AC-10 | ✅ |
| Blank Article Skipped | 1 | AC-07 | ✅ |
| Missing Title Key | 1 | AC-11 | ✅ |
| Long Text Truncation | 1 | AC-06 | ✅ |
| Batch Processing | 1 | (batch_size behavior) | ✅ |
| **Total** | **13** | **11 ACs** | ✅ |

### Fixtures (6 total)

- 1 single article (positive financial news)
- 1 multi-article (3 mixed sentiment)
- 1 empty articles
- 1 blank article (empty title + whitespace summary)
- 1 missing title key
- 1 long text (2000+ words, exceeds 512-token BERT limit)

### Test Infrastructure

- `MockTensor` with `.cpu()`, `.to()`, `.shape`, `.argmax()`, `.expand()`, `.item()`, `__getitem__`, `__iter__`, `__len__`
- `_MOCK_TORCH` module-level mock injected into `sys.modules["torch"]`
- Mock model infrastructure: `_mock_finbert()` and `_mock_positive_logits_model()` factory functions
- `_encoded_batch()` helper for tokenizer return values
- Per-test softmax overrides via `side_effect` save/restore

---

## 7. Outstanding Issues

### Non-Blocking

- [ ] LOW: `_MOCK_TORCH.randn` returns fixed values `[[0.5, 0.3, 0.2]]` rather than truly random — fine for deterministic tests, but if a future test depends on diverse random values (e.g., checking that different articles get different scores), it will need a more sophisticated mock
- [ ] LOW: `MockTensor.__repr__` not implemented — test failure output shows `<test_sentiment.MockTensor object at 0x...>` instead of the actual values, making debugging harder
- [ ] LOW: No integration test against real FinBERT model — requires a platform where torch is installable (e.g., Docker with Python 3.12)
- [ ] LOW: `logger` defined but never used in `sentiment.py:9` — accepted as standard module-level logger pattern for future use

### Resolved During Review

- [x] Data flow dependency wrong (Ticket 5 → Ticket 4) → corrected in spec rewrite
- [x] Only 3 ACs, no edge cases → expanded to 11 ACs
- [x] No concrete output types → `SentimentResult` + `ArticleSentiment` dataclasses
- [x] Score/aggregation formulas unspecified → defined `P(pos) - P(neg)` + confidence-weighted average
- [x] Missing import guard → try/except ImportError + runtime ModelLoadError
- [x] No fixtures or conftest registration → created 6 fixtures, registered in conftest
- [x] MagicMock.__call__ doesn't work → side_effect pattern throughout
- [x] MockTensor.__getitem__ always row 0 → check len(_data) == 1 for singletons
- [x] MockTensor.argmax hardcoded to 0 → compute actual argmax
- [x] Mock softmax ignores input → per-test side_effect override
- [x] Multi-article test too shallow → exact per-article + aggregation assertions
- [x] Batch test uses `>= 1` → tightened to `== 1`
- [x] Duplicated neutral result → `_NEUTRAL_RESULT` constant
- [x] Dead self.config field → inlined to self.id2label
- [x] Redundant `or ""` without comment → documented

---

## 8. Lessons Learned

### What Went Well

1. **TDD review caught data flow contradiction** — The first review round loaded `FusedRecord` from Ticket 4 and immediately spotted that Ticket 6 depends on Ticket 4 (fusion), not Ticket 5 (tokenization). FinBERT uses its own `BertTokenizer`, making the Ticket 5 dependency incorrect. This would have caused integration failures if caught later

2. **Context-driven spec expansion from 3 → 11 ACs** — The TDD reviewer's systematic approach identified all the missing edge cases (empty input, blank articles, missing title keys, None input, load failure, truncation, CPU fallback) that the original 3 ACs missed entirely

3. **Mock infrastructure works without real torch** — The `sys.modules["torch"]` injection + `MockTensor` pattern successfully exercises the exact same inference code path (`torch.no_grad()`, `.to(device)`, `softmax`, `.cpu()`, indexing, `.argmax()`) without having torch installed. This unblocks development on platforms Python 3.14 where torch isn't available yet

4. **One-session implementation** — After the spec rewrite (which took most of the effort), the actual implementation was completed in a single focused session. This confirms the TDD review investment pays off during coding

5. **side_effect pattern discovered and documented** — The `MagicMock.__call__` gotcha is a well-known pytest pitfall. This is now documented in the post-mortem and test code for future reference

6. **Code review caught 6 real issues** — All 6 C.L.E.A.R. framework findings were legitimate problems: 2 test shallowness bugs (multi-article aggregation verification, batch count assertion), 1 latent MockTensor bug (`__getitem__` row indexing), 2 maintainability issues (duplicated code, dead field), and 1 clarity issue (uncommented guard)

7. **Per-test softmax override for multi-article verification** — The try/finally pattern for temporarily overriding the global mock softmax allows the multi-article test to verify exact per-article and aggregated values while keeping simpler tests on the fast path

### What Could Improve

1. **Check MagicMock limitations earlier** — The `__call__` vs `side_effect` issue cost ~20 minutes of debugging. A known-issues doc for MagicMock patterns used in this project (e.g., `TESTS.md`) would save time for future mock-heavy tests

2. **Platform/Python compatibility check** — The CPython 3.14 on macOS x86_64 torch unavailability was discovered only when `uv pip install torch` failed during implementation. The project should document tested Python versions for each platform, or pin to a version with full wheel coverage

3. **MockTensor completeness checklist** — When creating a mock for a complex external library like torch, a checklist of required interface methods would help: `.cpu()`, `.to()`, `.shape`, indexing, iteration, `.argmax()`, `.expand()`, `.item()`, `__len__`, `__repr__`

4. **Softmax mock granularity** — The global `[[0.8, 0.1, 0.1]] * batch_size` mock is sufficient for most tests but required override for the multi-article test. Consider making the softmax mock smarter (e.g., parametric on input) to avoid per-test overrides in the future

5. **Integration test planning** — With torch unavailable on the dev machine, integration tests against the real FinBERT model require a Docker container or CI runner. This should be documented and scheduled rather than left as a vague follow-up

6. **Consistent use of _MOCK_TORCH across tests** — Some tests use `_mock_finbert()` or `_mock_positive_logits_model()` while others construct mocks inline. This inconsistency makes it harder to refactor mock behavior globally (e.g., when adding support for a new mocking scenario)

### Key Metrics

| Metric | Value |
|--------|-------|
| Original ACs | 3 |
| Refined ACs | 11 |
| TDD review rounds | 1 |
| Code review rounds | 1 (fixes) + 1 (re-review) |
| Files created | 8 |
| Files modified | 1 |
| Total tests | 13 |
| Implementation time | Single session (~2-3h coding) |
| Spec + review effort | ~1h (TDD + code review + fixes) |
| Issues found by TDD review | 12 blocking + 5 moderate |
| Issues found by code review | 6 (2 high, 4 medium) |
| Issues found during implementation | 3 (MockTensor.__getitem__, argmax, __call__) |

---

## 9. Acceptance Criteria Verification

| AC | Verification Method | Status |
|----|---------------------|--------|
| AC-01 | `test_model_loads_successfully` — eval mode, no_grad, device assignment | ✅ |
| AC-02 | `test_analyze_single_article` + `test_sentiment_score_formula` — exact score = 0.8-0.1, conf = 0.8, len=1 | ✅ |
| AC-03 | `test_multi_article_weighted_average` — 3 articles, exact per-article scores/confidence/labels, confidence-weighted aggregate | ✅ |
| AC-04 | `test_empty_article_list` — returns (0.0, 0.0, []) | ✅ |
| AC-05 | `test_model_load_failure_raises_error` — ModelLoadError with "Failed to load model" | ✅ |
| AC-06 | `test_long_text_truncation` — 2000-word text processed without error via single breakdown entry | ✅ |
| AC-07 | `test_blank_article_skipped` — empty title + whitespace summary yields neutral result with 0 breakdown | ✅ |
| AC-08 | `test_cpu_fallback_when_no_gpu` — device == "cpu" when cuda unavailable | ✅ |
| AC-09 | `test_market_data_only_record` — market_data without news returns (0.0, 0.0, []) | ✅ |
| AC-10 | `test_none_input_raises_type_error` — TypeError with "fused_record must be a FusedRecord" | ✅ |
| AC-11 | `test_missing_title_key_uses_summary` — article without "title" key processes using summary only | ✅ |

---

## 10. Timeline

| Date | Activity |
|------|----------|
| May 26, 2026 | Original ticket loaded (3 ACs, wrong dependency, missing types) |
| May 26, 2026 | TDD review round 1 (NEEDS REVISION — 12 blocking + 5 moderate issues) |
| May 26, 2026 | Fixed: data flow dependency corrected to Ticket 4, 11 ACs defined, dataclasses added, score/aggregation formulas specified, import guard added |
| May 26, 2026 | Implementation: `src/model/` structure, `sentiment.py`, test file, fixtures, conftest |
| May 26, 2026 | Implementation discovery: `MagicMock.__call__` doesn't work → `side_effect`, MockTensor.argmax hardcoded |
| May 26, 2026 | **Code review round 1**: 6 issues (test shallowness, latent MockTensor bug, duplicated code, dead field, weak assertion, unclear guard) |
| May 26, 2026 | **Fixed**: per-test softmax override with exact assertions, MockTensor.__getitem__/argmax, _NEUTRAL_RESULT, tightened assertion, dead field, comment |
| May 26, 2026 | **Re-review**: APPROVE — all issues resolved |
| May 26, 2026 | Post-mortem created |

---

## 11. Next Steps

1. Mark Ticket 6 as ✅ COMPLETE in tickets index document
2. Document MagicMock patterns (side_effect vs __call__) in project testing guidelines
3. Consider Docker integration test for real FinBERT model (requires torch-compatible environment)
4. Proceed to downstream generation ticket that consumes SentimentResult
