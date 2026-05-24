from __future__ import annotations

import logging
import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable

from src.preprocess.exceptions import TokenizerError
from src.preprocess.fusion import FusedRecord
from src.preprocess.tokenizer_configs import TokenizerConfig

logger = logging.getLogger(__name__)


class BaseTokenizer(ABC):
    def encode(self, text: str) -> list[int]:
        if not text:
            return []
        return self._encode_impl(text)

    def decode(self, tokens: list[int]) -> str:
        if not tokens:
            return ""
        return self._decode_impl(tokens)

    @abstractmethod
    def _encode_impl(self, text: str) -> list[int]: ...

    @abstractmethod
    def _decode_impl(self, tokens: list[int]) -> str: ...

    @abstractmethod
    def vocab_size(self) -> int: ...

    def train(self, texts: list[str]) -> None:
        pass

    def encode_many(self, texts: Iterable[str]) -> Generator[list[int], None, None]:
        for text in texts:
            yield self.encode(text)


class TikTokenTokenizer(BaseTokenizer):
    def __init__(self) -> None:
        import tiktoken

        self._encoding = tiktoken.get_encoding("cl100k_base")

    def _encode_impl(self, text: str) -> list[int]:
        return self._encoding.encode(text, allowed_special="all")

    def _decode_impl(self, tokens: list[int]) -> str:
        return self._encoding.decode(tokens)

    def vocab_size(self) -> int:
        return self._encoding.n_vocab


class HFTokenizerTokenizer(BaseTokenizer):
    def __init__(
        self,
        vocab_size: int = 8192,
        special_tokens: dict[str, int] | None = None,
    ) -> None:
        from tokenizers import Tokenizer
        from tokenizers.models import BPE

        self._vocab_size = vocab_size
        self._special_tokens = special_tokens or {}

        tokenizer = Tokenizer(BPE(unk_token=None))
        self._tokenizer = tokenizer
        self._trained = False

    def train(self, texts: list[str]) -> None:
        from tokenizers import trainers

        special_tokens_list = list(self._special_tokens.keys())
        trainer = trainers.BpeTrainer(
            vocab_size=self._vocab_size,
            special_tokens=special_tokens_list,
        )
        self._tokenizer.train_from_iterator(texts, trainer=trainer)
        self._trained = True

    def _encode_impl(self, text: str) -> list[int]:
        if not self._trained:
            raise TokenizerError("HFTokenizerTokenizer must be trained before encoding")
        return self._tokenizer.encode(text).ids  # type: ignore[no-any-return]

    def _decode_impl(self, tokens: list[int]) -> str:
        return self._tokenizer.decode(tokens, skip_special_tokens=False)  # type: ignore[no-any-return]

    def vocab_size(self) -> int:
        return self._tokenizer.get_vocab_size()  # type: ignore[no-any-return]


class SentencePieceTokenizer(BaseTokenizer):
    def __init__(
        self,
        vocab_size: int = 8192,
        special_tokens: dict[str, int] | None = None,
    ) -> None:
        import sentencepiece

        self._vocab_size = vocab_size
        self._special_tokens = special_tokens or {}
        self._processor = sentencepiece.SentencePieceProcessor()
        self._trained = False

    def train(self, texts: list[str]) -> None:
        import sentencepiece as spm

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for text in texts:
                f.write(text + "\n")
            input_path = f.name

        prefix = input_path.replace(".txt", "")
        try:
            user_defined_symbols = list(self._special_tokens.keys())
            spm.SentencePieceTrainer.Train(
                input=input_path,
                model_prefix=prefix,
                vocab_size=self._vocab_size,
                user_defined_symbols=user_defined_symbols,
                add_dummy_prefix=False,
                byte_fallback=1,
                hard_vocab_limit=0,
            )
            self._processor.Load(prefix + ".model")
        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)
            model_path = prefix + ".model"
            if os.path.exists(model_path):
                os.unlink(model_path)

        self._trained = True

    def _encode_impl(self, text: str) -> list[int]:
        if not self._trained:
            raise TokenizerError(
                "SentencePieceTokenizer must be trained before encoding"
            )
        result = self._processor.EncodeAsIds(text)
        if isinstance(result, list):
            return result
        return list(result)

    def _decode_impl(self, tokens: list[int]) -> str:
        return self._processor.DecodeIds(tokens)  # type: ignore[no-any-return]

    def vocab_size(self) -> int:
        return self._processor.GetPieceSize()  # type: ignore[no-any-return]


class TokenizerFactory:
    @staticmethod
    def create(
        backend: str,
        vocab_size: int = 8192,
        config: TokenizerConfig | None = None,
        **kwargs: object,
    ) -> BaseTokenizer:
        if config is not None:
            backend = config.backend
            vocab_size = config.vocab_size
            kwargs.setdefault("special_tokens", config.special_tokens)

        if vocab_size <= 0:
            raise TokenizerError(f"vocab_size must be positive, got {vocab_size}")

        special_tokens = kwargs.get("special_tokens")
        if special_tokens is not None and not isinstance(special_tokens, dict):
            raise TokenizerError("special_tokens must be a dict or None")

        if backend == "tiktoken":
            if vocab_size != 8192:
                logger.debug(
                    "vocab_size ignored for tiktoken backend (uses fixed cl100k_base encoding)"
                )
            return TikTokenTokenizer()
        elif backend == "tokenizers":
            return HFTokenizerTokenizer(
                vocab_size=vocab_size,
                special_tokens=special_tokens,
            )
        elif backend == "sentencepiece":
            return SentencePieceTokenizer(
                vocab_size=vocab_size,
                special_tokens=special_tokens,
            )
        else:
            raise TokenizerError(f"Unknown tokenizer backend: {backend}")

    @staticmethod
    def fused_record_to_text(record: FusedRecord) -> str:
        parts: list[str] = []
        for article in record.news_articles:
            title = article.get("title", "")
            summary = article.get("summary", "")
            text = f"{title} {summary}".strip()
            if text:
                parts.append(text)
        return "\n".join(parts)
