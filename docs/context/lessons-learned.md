# Lessons Learned

Cross-cutting insights synthesized from 9 ticket post-mortems, the idealized architecture, pipeline design, and iterative development process.

**Scope**: Tickets 1–9 cover the full pipeline — async HTTP infrastructure (T1), market data collection (T2), news collection (T3), data quality & fusion (T4), tokenization (T5), sentiment analysis (T6), trading signal generation (T7), multi-format report generation (T8), and graceful degradation (T9).

---

## 1. Process: The TDD Review Workflow

### 1.1 Multiple Review Rounds Catch Different Depths

Every ticket started with 3 vague acceptance criteria. The number of TDD review rounds needed correlated inversely with initial AC quality:

| Ticket | Initial ACs | Rounds to Green | Total Issues Found |
|--------|-------------|-----------------|-------------------|
| T1 (API Client) | 3 | 3 | 4 |
| T2 (Market Data) | 3 | 2 | 6 |
| T3 (News Data) | 3 | 2 | 12 |
| T4 (Quality & Fusion) | 3 | 3 | 11 blocking + 6 moderate |
| T5 (Tokenization) | 8 | 4 | 12 blocking + 14 moderate |
| T6 (Sentiment) | 3 | 1 | 12 blocking + 5 moderate |
| T7 (Signals) | 3 | 3 | 12 blocking + 9 moderate |
| T8 (Reports) | 3 | 5 | 14 blocking + 23 moderate |
| T9 (Degradation) | 3 | 4 | 5 blocking + 10 moderate |

The pattern across all tickets: **Round 1 catches structural gaps** (missing files, undefined types, wrong dependencies). **Round 2 catches design issues** (logical gaps, missing edge cases, pipeline integration). **Rounds 3+ catch spec-reality mismatches** (version-specific constants, field names that don't exist, contradictions between new ACs and existing code).

**Lesson**: Don't try to fix everything in one pass. Each round needs a different lens. Plan for 3–4 rounds as the norm, not the exception.

### 1.2 Context-Driven Review Is Essential

The tokenization ticket (T5) initially looked reasonable — 8 ACs, clear API spec, three backends. It passed a superficial review. But when the review loaded the actual data types from T4 (`FusedRecord`, `MarketData`, news article format), it discovered that "fused analysis text" was completely undefined. There was no contract between T4's structured output and T5's text-only input.

Similarly, T6 (Sentiment) initially listed `dependencies: [Ticket 5]` — but FinBERT uses `BertTokenizer` internally (WordPiece, vocab ~30522), NOT the BPE tokenizer backends from T5. The correct dependency was T4 (Fusion), which provides `FusedRecord`.

**Lesson**: Every review must load the actual data types of upstream dependencies. Don't review a ticket without reading the `@dataclass` definitions from the tickets it depends on.

### 1.3 Code Review After Implementation Is Mandatory

Even with thorough spec review, code review found real bugs in every ticket:

- T1: Metrics accumulation never resets (unbounded growth)
- T2: `except A, B:` syntax (invalid in Python 3)
- T4: `TrackingIterable` duplicated verbatim, `_extract_date()` crashes on `None`
- T5: Empty-string guards duplicated across 3 backends
- T6: `MagicMock.__call__` silently ignored, `MockTensor.__getitem__` always row 0
- T7: Unused fixtures (8 defined, 0 consumed), docstrings missing
- T8: `getattr(result, "txt")` crashes (field is `text`, not `txt`) — **critical runtime bug**
- T9: `fetch_news` dropped from imports (regression), unused params in warning builder

**Lesson**: Spec review and code review find different categories of bugs. Both are necessary. Never skip the code review pass.

### 1.4 Dependency Analysis Is a Standard Pre-Implementation Step

The most effective pattern emerged in T7–T9: before writing any code, trace every import, function call, and data type reference against the actual codebase. This consistently found 3–4 gaps per ticket that spec-only review missed:

- `clamp()` referenced in signal formula but doesn't exist in codebase (T7)
- Pipeline result scoping — Stage 5 variable inaccessible to Stage 6 (T7)
- `volume: int` deserialized as `float` by `json.load()` (T8)
- `ValidationWarning` has 4 required fields, pseudocode passed 3 (T9)
- `reporter.py` renders `- {message}` not `- {category}: {message}` (T9)

**Lesson**: Add a "dependency analysis" phase between spec approval and implementation. Read the actual files referenced by the spec, verify every type and function exists, and check every psuedocode invocation against real signatures.

---

## 2. Specification: Writing Testable Acceptance Criteria

### 2.1 The 3 → 11 AC Expansion Pattern

Every ticket started with 3 vague ACs. Every ticket needed 8–11 refined ACs. The missing categories were consistent:

1. **Error paths** — What happens when input is `None`? Empty list? Malformed?
2. **Edge cases** — Boundaries, empty states, extreme values
3. **Format specifications** — Concrete output schemas, not "human-readable"
4. **Cross-component contracts** — How does this connect to upstream/downstream data types?

The worst offender was AC-03 across all tickets: the original 3rd AC was always vague ("warnings included", "per-article breakdown", "human-readable rationale", "dashboard-ready HTML"). This pattern held in 9/9 tickets.

**Lesson**: Use a checklist for the 3rd AC. It's almost always underspecified. Common patterns: output format, error behavior, cross-format consistency.

### 2.2 Concrete Values Eliminate Ambiguity

Compare:
- **Vague**: "Given strong positive sentiment and market uptrend, When signal is generated, Then result is buy"
- **Concrete**: "Given `sentiment_score=+0.7`, `sentiment.confidence=0.8`, `market_return=+5%`, When `generate()` is called, Then `signal == "buy"` and `confidence > 0.5`"

The concrete version is verifiable by numerical computation and doesn't depend on subjective interpretation of "strong" or "uptrend." This pattern was applied in T7 after the first review round and eliminated all ambiguity.

**Lesson**: Every AC should be computable by manual calculation from given inputs to expected outputs. If you can't pin down the numbers, the formula isn't specified well enough.

### 2.3 Cross-Format ACs Need Extra Care

T8's AC-10 required cross-format consistency (same data count in text, JSON, and HTML). This took 5 review rounds to get right — more than any single-format AC. The challenges:

- **Preamble counting**: What counts as a "data line" in text format? (Header? Separators? Footer?)
- **Structural differences**: `<tr>` rows in HTML exclude the header row; JSON array length is unambiguous
- **Edge cases**: What if there are warnings? Do extra warning lines count?

**Lesson**: Cross-format ACs cost 3× the review effort of single-format ACs. Budget accordingly, or split into single-format sub-ACs.

---

## 3. Architecture: What Worked and What Didn't

### 3.1 What Worked Well

**Provider fallback chain** (T2, T3): Yahoo Finance → Alpha Vantage → Finnhub for market data; Finnhub → NewsAPI for news. The sequential provider list made behavior predictable and testable. No single point of failure.

**Graceful degradation** (T9): Instead of crashing or silently returning `None`, the pipeline falls back to cached data up to 5 trading days old, with explicit warnings in reports. This was the simplest change that covered the most scenarios — no new dataclass fields, no pipeline restructuring.

**Conditional imports for heavy dependencies** (T6): `torch` and `transformers` are imported lazily with `try/except ImportError`. The pipeline skips sentiment analysis gracefully when they're unavailable. This was critical because `torch` has no wheels for Python 3.14 on macOS x86_64.

**Template method pattern for tokenizer backends** (T5): Moving empty-string/empty-list guards from duplicated per-backend code into `BaseTokenizer.encode()`/`decode()` concrete methods eliminated ×3 duplication. Backends only implement `_encode_impl`/`_decode_impl`.

**ValidationWarning categories instead of new status field** (T9): Existing `FusedRecord.warnings → ReportInput.warnings → ReportGenerator` pipeline was reused with no changes. Four warning categories (`degraded_market`, `degraded_news`, `fallback_failed`, `insufficient_data`) covered all degradation scenarios without touching any existing dataclass.

### 3.2 What Didn't Work (Or Could Be Better)

**The idealized architecture still lives in docs only**. The architecture doc describes GPT-2 fine-tuning, BERT custom tasks, from-scratch transformer implementations, and training utilities — none of which are wired into the pipeline. The tokenizer backends (T5) exist and are tested but are never invoked by `pipeline.py`. The actual project is a financial signal pipeline, not an LLM playground.

**Two diverging trading-day implementations**: `market_data.py` uses holiday-aware adjustment, `news_collector.py` uses weekends-only adjustment. T9 extracted `date_utils.py` but only covers the weekends-only variant. The holiday-aware logic remains private to `market_data.py` and unreusable.

**No shared constant for fused filename pattern**: `FusedRecordWriter` and `find_historical_fallback()` both construct paths like `{ticker}_{date}.json` but there's no shared constant. The two implementations are manually kept in sync.

**`MarketData.volume` type mismatch**: Declared as `int` in the dataclass but `json.load()` returns `float` for all numbers. Requires explicit `int()` coercion during deserialization. This silently breaks `isinstance(data.volume, int)` in validation.

### 3.3 Mock Infrastructure Lessons

**MagicMock.__call__ doesn't work on instances** (T6): Setting `mock_model.__call__ = func` is silently ignored because `__call__` is looked up on the type, not the instance. Use `side_effect` instead.

**MockTensor must handle indexing correctly** (T6): The `__iter__` path wraps each row as `MockTensor([row])` (single-row), while direct access uses multi-row tensors. `__getitem__` must check `len(self._data) == 1` to distinguish the two paths.

**Per-test softmax overrides via try/finally** (T6): Global mock returns `[[0.8, 0.1, 0.1]] * batch_size` for most tests. Multi-article tests override `side_effect` with per-row probabilities inside a `try/finally` block. This pattern allows simpler tests on the fast path and exact verification in the multi-article test.

---

## 4. Language & Tool Gotchas

### 4.1 Python-Specific

| Issue | Ticket | Description |
|-------|--------|-------------|
| `except A, B:` syntax | T2, T3 | Python 2 syntax, crashes in Python 3. Ruff didn't catch it. |
| `asyncio.get_event_loop().time()` deprecated | T1 | Use `time.perf_counter()` instead |
| `float('nan')` bypasses `> 0` checks | T4 | `nan > 0` is `False` but `nan <= 0` is also `False`. Use `math.isnan()`. |
| `json.load()` returns `float` for all numbers | T8 | `volume: int` becomes `volume: float` after JSON roundtrip |
| `datetime.now()` makes test fixtures relative | Pipeline.md | Test dates shift every time tests run. Pin to fixed dates. |
| `__call__` on MagicMock instances | T6 | Silently ignored. Use `side_effect` instead. |

### 4.2 Tokenizer-Specific

| Issue | Description |
|-------|-------------|
| tiktoken `allowed_special` must be set | `encode("<|endoftext|>")` raises `ValueError` without `allowed_special={"<|endoftext|>"}` |
| tiktoken `vocab_size` is 100277, not 100257 | 20 additional special tokens added in tiktoken 0.13.0 |
| sentencepiece has immutable BOS (ID 1) and EOS (ID 2) | User-defined symbols start at ID 3+. Pad/bos need IDs 3/4, not 1/2. |
| Trainable backends need `.train()` before `.encode()` | `tokenizers` BPE and `sentencepiece` unigram require training data |

### 4.3 Process Tooling

| Issue | Description |
|-------|-------------|
| Ruff doesn't catch Python 2 exception syntax | `except A, B:` is syntactically valid in Python 3 parser (it's `except (A, B):` with parentheses that changed) — actually it does raise SyntaxError. The post-mortem reports it was not caught because ruff might not flag it in certain contexts, or the code had some other formatting. |
| Fixture auto-discovery not automatic | Each `tests/fixtures/*.py` file must be registered in `tests/conftest.py` `pytest_plugins`. Missed registration was a recurring issue across T4–T9. |
| No `__repr__` on MockTensor | Test failure output shows `<test_sentiment.MockTensor object at 0x...>` instead of actual values, making debugging harder |

---

## 5. Metrics & Effort Distribution

### 5.1 Spec Review vs Implementation Effort

Across all tickets, spec review (TDD rounds + dependency analysis) took roughly as much time as implementation. The ratio shifted over time:

- T1–T3: Heavy implementation, light review (but bugs found downstream)
- T4–T6: Roughly equal review and implementation effort
- T7–T9: Heavier review, lighter implementation (fewer bugs found in code review)

The effort shift was intentional — earlier tickets under-invested in spec review and paid the cost in bugs. Later tickets invested more upfront and had cleaner implementations.

### 5.2 Code Review Efficiency

| Ticket | Tests | CR Findings | Critical/High | Finding Density |
|--------|-------|-------------|---------------|-----------------|
| T1 | 20 | 4 | 1 critical | 20% |
| T2 | 24 | 2 | 2 critical | 8% |
| T3 | 15 | 3 | 0 critical | 20% |
| T4 | 55 | 8 | 1 high | 15% |
| T5 | 36 | 6 | 0 critical | 17% |
| T6 | 13 | 6 | 2 high | 46% |
| T7 | 25 | 3 | 0 critical | 12% |
| T8 | 34 | 3 | 1 critical | 9% |
| T9 | 33 | 8 | 1 high | 24% |

T6 had the highest finding density (46%). This correlates with the highest mock complexity (MockTensor, `sys.modules` injection, `side_effect` patterns). Pure Python tickets (T7, T8 reporter) had lower finding density.

### 5.3 Test Count vs AC Count

On average, 3.3 tests per AC across all tickets. The ratio was higher for complex logic (T6: 13 tests / 11 ACs = 1.2 — each AC is well-covered by a specific test) and lower for infrastructure (T1: 20 tests / 4 ACs = 5.0 — many tests cover the AC indirectly).

---

## 6. Recurring Themes

### 6.1 Vague Third AC

Every single ticket had a vague third AC that needed expansion:

| Ticket | Original AC-03 | Refined To |
|--------|---------------|------------|
| T1 | "properly released" | "connection count returns to 0, no TIME_WAIT sockets" |
| T2 | "appropriate error logged" | "MarketDataParseError with message 'Missing required field: close'" |
| T3 | "excluded with warning logged" | "filtered out, WARNING level log entry emitted" |
| T4 | "correlated by date/time" | "matched by date within target_date ± 0 days" |
| T5 | "Given TokenizerFactory.create('sentencepiece'), When encode, Then backend is SentencePieceProcessor" | "isinstance check against concrete subclasses" |
| T6 | "per-article breakdown" | "3 breakdown entries with title/score/confidence/label" |
| T7 | "human-readable rationale" | "template with label, score, confidence, return, combined_score, signal, N/A" |
| T8 | "warnings included in all formats" | "text: '- {message}', JSON: category/field/message/value, HTML: <div class='warning'>" |
| T9 | "'insufficient_data' status set" | "ValidationWarning category 'insufficient_data', pipeline continues" |

**Lesson**: When reviewing a ticket's 3rd AC, assume it's underspecified and demand concrete output values or exact format specs.

### 6.2 Wrong Dependencies

T5, T6, T7, and T8 all had incorrect dependency declarations. The review caught them before implementation each time, but the pattern suggests that dependency chains are hard to get right in the initial ticket authoring. The fix requires reading upstream type definitions.

### 6.3 Fixture Dead Code

T5, T7, and T8 all had fixtures defined but never consumed by tests. The pattern: create fixture file → register in conftest → define fixtures → write tests using inline data → forget to refactor. A "verify every fixture is consumed by at least one test" checklist item would prevent this.

### 6.4 Late-Discovered Pipeline Integration Gaps

T8 (Round 2) and T9 (Round 1) both discovered pipeline integration issues that weren't visible from the ticket alone. T8's single-ticker vs multi-ticker conflict required reading `pipeline.py` to find. T9's silent catch blocks required reading `pipeline.py:71-81` to find.

**Lesson**: Every review should include reading the pipeline entry point (`pipeline.py`) to understand how the new component connects.

---

## 7. Recommendations

### 7.1 Process

1. **Add dependency analysis as a formal phase** between spec approval and implementation. Read every referenced file, verify every function/type exists, check pseudocode against real signatures.
2. **Add a "read pipeline.py" step** to every review. This catches integration gaps that component-level review misses.
3. **Use a checklist for the 3rd AC** — it's almost always underspecified.
4. **Verify every fixture is consumed** by at least one test before merging.

### 7.2 Architecture

1. **Create a shared constant for fused filename pattern** — currently duplicated between `FusedRecordWriter` and `find_historical_fallback()`.
2. **Unify the two trading-day implementations** — `market_data.py` holiday-aware vs `date_utils.py`/`news_collector.py` weekends-only. Extract a shared holiday calendar.
3. **Add `__repr__` to `MockTensor`** — test failures currently show opaque object references instead of actual values.
4. **Document MagicMock patterns** in a testing reference doc — `side_effect` vs `__call__`, `return_value` vs `side_effect`, and the per-test override via `try/finally`.

### 7.3 Infrastructure

1. **Consider a lightweight integration test framework** for `pipeline.py` exception handlers — async context manager monkeypatching would exercise the actual try→except→fallback flow.
2. **Explore fixture auto-discovery** via pytest conftest plugin conventions, eliminating the manual `pytest_plugins` registration step.
3. **Pin Python version in CI** to a version with full torch wheel coverage (3.12 for macOS x86_64), enabling real FinBERT integration tests.
