from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenizerConfig:
    backend: str
    vocab_size: int = 8192
    special_tokens: dict[str, int] | None = None
