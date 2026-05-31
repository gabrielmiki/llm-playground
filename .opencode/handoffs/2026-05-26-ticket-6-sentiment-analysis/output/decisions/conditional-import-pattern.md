# Decision: Conditional Import Pattern for Optional ML Dependencies

**Date**: 2026-05-26  
**Context**: Ticket 6 — Sentiment Analysis with FinBERT

## Problem

`torch` and `transformers` are heavy ML dependencies required only by the `src/model/` package. They lack wheels for certain platform/ Python combinations (e.g., CPython 3.14 on macOS x86_64). The module must load without them so tests can run and the rest of the project is unaffected.

## Decision

Use `try/except ImportError` at module load time, setting imported names to `None`:

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

Add a runtime guard in `__init__` that raises `ModelLoadError`:

```python
if torch is None:
    raise ModelLoadError("torch is not installed. Install with: uv sync --extra model")
```

## Trade-offs

| Approach | Pro | Con |
|----------|-----|-----|
| Conditional import (chosen) | Module loads anywhere, clean guard, testable | `# type: ignore[assignment]` needed for mypy |
| Lazy import inside __init__ | No mypy ignores needed | Load error surfaces later (on construction, not import), inconsistent with project pattern |
| Optional dependency group | Clear user intent | Doesn't solve runtime import failure |

## Alternatives Rejected

- **Lazy import in `__init__`**: Delays failure to construction time rather than import time, making test setup more complex
- **Forced dependency**: Torch not available on this platform — not an option
- **`pytest.importorskip` only**: Works for tests but doesn't protect production imports

## Impact

- Tests inject `sys.modules["torch"]` mock before importing sentiment module
- CI and developer machines without torch can still lint, type-check, and run all non-model tests
- Platform-compatible environments (Docker with Python 3.12) can install torch and run integration tests
