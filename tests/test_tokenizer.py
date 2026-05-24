"""Tests for the tokenization pipeline."""

from __future__ import annotations

import pytest

from src.preprocess.exceptions import TokenizerError
from src.preprocess.tokenizer import (
    HFTokenizerTokenizer,
    SentencePieceTokenizer,
    TikTokenTokenizer,
    TokenizerFactory,
)

BACKENDS = ["tiktoken", "tokenizers", "sentencepiece"]
TRAINING_CORPUS = ["Hello world. Sample training text for initialization."]


@pytest.fixture(params=BACKENDS)
def tokenizer(request):
    t = TokenizerFactory.create(request.param)
    if request.param != "tiktoken":
        t.train(TRAINING_CORPUS)
    return t


class TestTokenizer:
    def test_encode_returns_integers(self, tokenizer):
        tokens = tokenizer.encode("Hello world")
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert all(isinstance(t, int) for t in tokens)

    def test_ascii_roundtrip(self, tokenizer):
        text = "Hello world"
        tokens = tokenizer.encode(text)
        decoded = tokenizer.decode(tokens)
        if isinstance(tokenizer, TikTokenTokenizer):
            assert decoded == text
        else:
            assert len(decoded) > 0
            assert isinstance(decoded, str)

    @pytest.mark.parametrize("backend", ["tiktoken", "tokenizers", "sentencepiece"])
    def test_vocab_size(self, backend):
        t = TokenizerFactory.create(backend)
        if backend != "tiktoken":
            t.train(TRAINING_CORPUS)
        vs = t.vocab_size()
        assert vs > 0
        if backend == "tiktoken":
            assert vs == 100277
        else:
            assert vs <= 8192

    def test_unknown_backend_error(self):
        with pytest.raises(
            TokenizerError, match="Unknown tokenizer backend: invalid_backend"
        ):
            TokenizerFactory.create("invalid_backend")

    def test_empty_string_encode(self, tokenizer, sample_empty_text):
        assert tokenizer.encode(sample_empty_text) == []

    def test_empty_list_decode(self, tokenizer):
        assert tokenizer.decode([]) == ""

    def test_tiktoken_special_token_roundtrip(self):
        t = TokenizerFactory.create("tiktoken")
        text = "<|endoftext|>"
        tokens = t.encode(text)
        assert len(tokens) == 1
        assert tokens[0] == 100257
        assert t.decode(tokens) == text

    def test_tokenizers_special_tokens_roundtrip(self):
        t = TokenizerFactory.create(
            "tokenizers",
            vocab_size=512,
            special_tokens={"<|pad|>": 0, "<|bos|>": 1},
        )
        t.train(TRAINING_CORPUS)
        pad_tokens = t.encode("<|pad|>")
        bos_tokens = t.encode("<|bos|>")
        assert len(pad_tokens) == 1
        assert len(bos_tokens) == 1
        assert pad_tokens[0] == 0
        assert bos_tokens[0] == 1
        text = "<|pad|><|bos|>"
        tokens = t.encode(text)
        decoded = t.decode(tokens)
        assert "<|pad|>" in decoded
        assert "<|bos|>" in decoded

    def test_sentencepiece_special_tokens_roundtrip(self):
        t = TokenizerFactory.create(
            "sentencepiece",
            vocab_size=512,
            special_tokens={"<|pad|>": 3, "<|bos|>": 4},
        )
        t.train(TRAINING_CORPUS)
        pad_tokens = t.encode("<|pad|>")
        bos_tokens = t.encode("<|bos|>")
        assert len(pad_tokens) == 1
        assert len(bos_tokens) == 1
        assert pad_tokens[0] == 3
        assert bos_tokens[0] == 4
        text = "<|pad|><|bos|>"
        tokens = t.encode(text)
        decoded = t.decode(tokens)
        assert "<|pad|>" in decoded
        assert "<|bos|>" in decoded

    def test_backend_class_tiktoken(self):
        assert isinstance(TokenizerFactory.create("tiktoken"), TikTokenTokenizer)

    def test_backend_class_tokenizers(self):
        assert isinstance(TokenizerFactory.create("tokenizers"), HFTokenizerTokenizer)

    def test_backend_class_sentencepiece(self):
        assert isinstance(
            TokenizerFactory.create("sentencepiece"), SentencePieceTokenizer
        )

    def test_tokenizers_ids_within_vocab(self):
        t = TokenizerFactory.create("tokenizers", vocab_size=512)
        t.train(TRAINING_CORPUS)
        tokens = t.encode("Hello world")
        assert len(tokens) > 0
        assert all(tid < 512 for tid in tokens)

    @pytest.mark.parametrize(
        "backend,bad_size",
        [
            ("tokenizers", -1),
            ("tokenizers", 0),
            ("sentencepiece", -1),
            ("sentencepiece", 0),
        ],
    )
    def test_invalid_vocab_size(self, backend, bad_size):
        with pytest.raises(TokenizerError, match="vocab_size must be positive"):
            TokenizerFactory.create(backend, vocab_size=bad_size)

    def test_fused_record_to_text_with_articles(self):
        from src.preprocess.fusion import FusedRecord

        record = FusedRecord(
            ticker="AAPL",
            date="2024-01-15",
            market_data=None,
            news_articles=[
                {
                    "title": "Apple Reports Record Earnings",
                    "summary": "Apple Inc. announced strong Q4 results.",
                },
                {
                    "title": "Markets Rally on Fed Decision",
                    "summary": "The Federal Reserve maintained interest rates.",
                },
            ],
        )
        text = TokenizerFactory.fused_record_to_text(record)
        assert "Apple Reports Record Earnings" in text
        assert "Markets Rally on Fed Decision" in text
        assert "\n" in text

    def test_fused_record_to_text_empty_articles(self):
        from src.preprocess.fusion import FusedRecord

        record = FusedRecord(
            ticker="AAPL",
            date="2024-01-15",
            market_data=None,
            news_articles=[],
        )
        assert TokenizerFactory.fused_record_to_text(record) == ""

    def test_fused_record_to_text_skips_empty_parts(self):
        from src.preprocess.fusion import FusedRecord

        record = FusedRecord(
            ticker="AAPL",
            date="2024-01-15",
            market_data=None,
            news_articles=[
                {"title": "", "summary": ""},
                {"title": "Real News", "summary": "Content here."},
            ],
        )
        text = TokenizerFactory.fused_record_to_text(record)
        assert "Real News" in text
        assert text.count("\n") == 0

    def test_encode_many_lazy_evaluation(self, tokenizer, tracking_iterable):
        TrackingIterable = tracking_iterable
        texts = TrackingIterable(["Hello", "world", "test"])
        gen = tokenizer.encode_many(texts)
        assert texts.call_count == 0
        next(gen)
        assert texts.call_count == 1
        list(gen)
        assert texts.call_count == 3

    def test_encode_many_results(self, tokenizer):
        texts = ["Hello", "world", "test"]
        results = list(tokenizer.encode_many(texts))
        assert len(results) == 3
        for tokens in results:
            assert isinstance(tokens, list)
            assert len(tokens) > 0
