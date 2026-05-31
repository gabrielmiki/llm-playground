# Decision: Template Method Pattern for Empty Guards

**Date**: 2026-05-26  
**Status**: ✅ Implemented

## Problem

All 3 backends (`TikTokenTokenizer`, `HFTokenizerTokenizer`, `SentencePieceTokenizer`) had identical empty-string and empty-list guard clauses duplicated in their `encode()` and `decode()` methods:

```python
def encode(self, text: str) -> list[int]:
    if not text:
        return []
    ...

def decode(self, tokens: list[int]) -> str:
    if not tokens:
        return ""
    ...
```

## Decision

Move empty guards to `BaseTokenizer.encode()/decode()` as concrete methods, and have backends implement `_encode_impl()/_decode_impl()` as private abstract methods:

```python
class BaseTokenizer(ABC):
    def encode(self, text: str) -> list[int]:
        if not text:
            return []
        return self._encode_impl(text)

    def decode(self, tokens: list[int]) -> str:
        if not tokens:
            return ""
        return self._decode_impl(tokens)
```

## Rationale

- Removes ×3 duplication (DRY)
- Follows established template method pattern in codebase
- Backends only implement the core logic, not infrastructure
- Empty guard policy is centralized — can't be forgotten in a new backend

## Files Changed

- `src/preprocess/tokenizer.py` — BaseTokenizer, all 3 backends
- `tests/test_tokenizer.py` — unchanged (test behavior is identical)
