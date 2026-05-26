"""Tests for FinBERT sentiment analysis.

Note: tests are skipped when `torch` is unavailable (e.g., CPython 3.14 on x86_64).
"""

from __future__ import annotations

import importlib
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock torch for environments where it isn't installable (e.g. CPython 3.14
# on macOS x86_64).  A light MockTensor class provides enough of the array
# interface to exercise the sentiment module's inference logic.
# ---------------------------------------------------------------------------
class MockTensor:
    """Minimal tensor stand-in supporting .cpu(), .to(), indexing, iteration,
    and item().  Used to pass logits and softmaxed probabilities through the
    FinBertSentiment.analyze code path."""

    def __init__(self, data: list[list[float]]) -> None:
        self._data = data
        self.shape = (len(data), len(data[0]) if data else 0)

    def cpu(self) -> MockTensor:
        return self

    def to(self, *args: Any, **kwargs: Any) -> MockTensor:
        return self

    def __getitem__(self, index: int) -> float:
        if len(self._data) == 1:
            return self._data[0][index]
        return self._data[index]

    def __iter__(self):
        return iter(MockTensor([row]) for row in self._data)

    def item(self) -> float:
        return self._data[0][0]

    def expand(self, *sizes: int) -> MockTensor:
        return self

    def argmax(self) -> int:
        row = self._data[0]
        return row.index(max(row))

    def __len__(self) -> int:
        return len(self._data)


_MOCK_TORCH = MagicMock(
    name="torch",
    __spec__=importlib.util.spec_from_loader("torch", loader=None),
)
_MOCK_TORCH.__version__ = "2.6.0"
_MOCK_TORCH.cuda.is_available.return_value = False
_MOCK_TORCH.no_grad.return_value.__enter__ = MagicMock()
_MOCK_TORCH.no_grad.return_value.__exit__ = MagicMock(return_value=None)
_MOCK_TORCH.nn.functional.softmax = MagicMock(
    side_effect=lambda x, dim: MockTensor(
        [[0.8, 0.1, 0.1]] * x.shape[0]
    ),
    __name__="softmax",
)
_MOCK_TORCH.long = MagicMock()
_MOCK_TORCH.float = MagicMock()
_MOCK_TORCH.tensor = lambda data, **kwargs: MockTensor(data)
_MOCK_TORCH.zeros = lambda *size, **kwargs: MockTensor(
    [[0.0] * (size[1] if len(size) > 1 else 1)] * size[0]
)
_MOCK_TORCH.ones = lambda *size, **kwargs: MockTensor(
    [[1.0] * (size[1] if len(size) > 1 else 1)] * size[0]
)
_MOCK_TORCH.randn = lambda *size: MockTensor(
    [[0.5, 0.3, 0.2]] * (size[0] if size else 1)
)
_MOCK_TORCH.log = lambda x: MockTensor([[0.5, 0.3, 0.2]])

# Inject into sys.modules so both the module under test and helpers can
# do `import torch` without failure.
sys.modules["torch"] = _MOCK_TORCH

pytest.importorskip("src.model.pretrained.sentiment")

from src.model.exceptions import ModelLoadError  # noqa: E402
from src.model.pretrained.sentiment import FinBertSentiment, SentimentResult  # noqa: E402


def _mock_finbert(num_labels: int = 3) -> MagicMock:
    """Create a mock FinBERT model with controllable probabilities."""
    mock_model = MagicMock()
    mock_model.to.return_value = mock_model

    mock_config = MagicMock()
    mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
    mock_model.config = mock_config

    def side_effect(input_ids=None, attention_mask=None, **kwargs):
        batch_size = input_ids.shape[0] if input_ids is not None else 1
        logits = _MOCK_TORCH.randn(batch_size, num_labels)
        return MagicMock(logits=logits)

    mock_model.side_effect = side_effect
    return mock_model


def _mock_positive_logits_model() -> MagicMock:
    """Model that always predicts positive (high pos, low neg, low neu)."""
    mock_model = MagicMock()
    mock_model.to.return_value = mock_model

    mock_config = MagicMock()
    mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
    mock_model.config = mock_config

    logits = _MOCK_TORCH.tensor([[5.0, -5.0, 0.0]])

    def side_effect(input_ids=None, attention_mask=None, **kwargs):
        return MagicMock(logits=logits)

    mock_model.side_effect = side_effect
    return mock_model


def _encoded_batch(tensor_shape: tuple[int, ...]) -> dict:
    return {
        "input_ids": _MOCK_TORCH.zeros(*tensor_shape, dtype=_MOCK_TORCH.long),
        "attention_mask": _MOCK_TORCH.ones(*tensor_shape, dtype=_MOCK_TORCH.long),
    }


class TestFinBertSentiment:
    """Tests for FinBertSentiment initialization and analysis."""

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_model_loads_successfully(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = MagicMock()
        mock_auto_model.from_pretrained.return_value = mock_model

        sentiment = FinBertSentiment(model_name="ProsusAI/finbert")

        assert sentiment.model_name == "ProsusAI/finbert"
        assert sentiment.device in ("cpu", "cuda")
        assert sentiment.max_length == 512
        assert sentiment.batch_size == 32
        mock_model.eval.assert_called_once()
        mock_model.to.assert_called_once()

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_model_load_failure_raises_error(
        self,
        mock_auto_config: MagicMock,
        mock_auto_tokenizer: MagicMock,
        mock_auto_model: MagicMock,
    ):
        mock_auto_model.from_pretrained.side_effect = RuntimeError(
            "Connection refused"
        )

        with pytest.raises(
            ModelLoadError, match="Failed to load model from HuggingFace"
        ):
            FinBertSentiment(model_name="ProsusAI/finbert")

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_cpu_fallback_when_no_gpu(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = MagicMock()
        mock_auto_model.from_pretrained.return_value = mock_model

        _MOCK_TORCH.cuda.is_available.return_value = False
        sentiment = FinBertSentiment(model_name="ProsusAI/finbert")

        assert sentiment.device == "cpu"

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_analyze_single_article(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
        sample_fused_record_single_article,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = _mock_positive_logits_model()
        mock_auto_model.from_pretrained.return_value = mock_model

        mock_tok = MagicMock()
        mock_tok.return_value = _encoded_batch((1, 3))
        mock_auto_tokenizer.from_pretrained.return_value = mock_tok

        sentiment = FinBertSentiment(model_name="ProsusAI/finbert", device="cpu")
        result = sentiment.analyze(sample_fused_record_single_article)

        assert isinstance(result, SentimentResult)
        assert -1.0 <= result.sentiment_score <= 1.0
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.breakdown) == 1

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_sentiment_score_formula(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
        sample_fused_record_single_article,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.config = mock_config
        mock_model.eval.return_value = mock_model

        logits = _MOCK_TORCH.tensor([[0.8, 0.1, 0.1]])

        mock_model.side_effect = lambda input_ids=None, attention_mask=None, **kwargs: MagicMock(logits=logits)
        mock_auto_model.from_pretrained.return_value = mock_model

        mock_tok = MagicMock()
        mock_tok.return_value = _encoded_batch((1, 3))
        mock_auto_tokenizer.from_pretrained.return_value = mock_tok

        sentiment = FinBertSentiment(model_name="ProsusAI/finbert", device="cpu")
        result = sentiment.analyze(sample_fused_record_single_article)

        expected_score = 0.8 - 0.1
        assert abs(result.sentiment_score - expected_score) < 0.01
        assert abs(result.confidence - 0.8) < 0.01
        assert result.breakdown[0].label == "positive"

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_multi_article_weighted_average(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
        sample_fused_record_multi_article,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.config = mock_config
        mock_model.eval.return_value = mock_model

        logits = _MOCK_TORCH.tensor([
            [0.8, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.3, 0.3, 0.4],
        ])

        mock_model.side_effect = lambda input_ids=None, attention_mask=None, **kwargs: MagicMock(logits=logits)
        mock_auto_model.from_pretrained.return_value = mock_model

        mock_tok = MagicMock()
        mock_tok.return_value = _encoded_batch((3, 5))
        mock_auto_tokenizer.from_pretrained.return_value = mock_tok

        original_side_effect = _MOCK_TORCH.nn.functional.softmax.side_effect
        per_article_probs = [
            [0.8, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.3, 0.3, 0.4],
        ]
        _MOCK_TORCH.nn.functional.softmax.side_effect = (
            lambda x, dim: MockTensor(per_article_probs[:x.shape[0]])
        )

        try:
            sentiment = FinBertSentiment(model_name="ProsusAI/finbert", device="cpu")
            result = sentiment.analyze(sample_fused_record_multi_article)
        finally:
            _MOCK_TORCH.nn.functional.softmax.side_effect = original_side_effect

        assert len(result.breakdown) == 3
        assert abs(result.breakdown[0].score - 0.7) < 0.01
        assert abs(result.breakdown[0].confidence - 0.8) < 0.01
        assert result.breakdown[0].label == "positive"
        assert abs(result.breakdown[1].score - (-0.7)) < 0.01
        assert abs(result.breakdown[1].confidence - 0.8) < 0.01
        assert result.breakdown[1].label == "negative"
        assert abs(result.breakdown[2].score - 0.0) < 0.01
        assert abs(result.breakdown[2].confidence - 0.4) < 0.01
        assert result.breakdown[2].label == "neutral"
        expected_confidence = (0.8 + 0.8 + 0.4) / 3
        assert abs(result.sentiment_score - 0.0) < 0.01
        assert abs(result.confidence - expected_confidence) < 0.01

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_empty_article_list(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
        sample_fused_record_empty_articles,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.config = mock_config
        mock_auto_model.from_pretrained.return_value = mock_model

        sentiment = FinBertSentiment(model_name="ProsusAI/finbert", device="cpu")
        result = sentiment.analyze(sample_fused_record_empty_articles)

        assert result.sentiment_score == 0.0
        assert result.confidence == 0.0
        assert result.breakdown == []

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_market_data_only_record(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
    ):
        from src.preprocess.fusion import FusedRecord

        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.config = mock_config
        mock_auto_model.from_pretrained.return_value = mock_model

        record = FusedRecord(
            ticker="AAPL",
            date="2024-01-15",
            market_data=None,
            news_articles=[],
        )

        sentiment = FinBertSentiment(model_name="ProsusAI/finbert", device="cpu")
        result = sentiment.analyze(record)

        assert result.sentiment_score == 0.0
        assert result.confidence == 0.0
        assert result.breakdown == []

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_none_input_raises_type_error(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.config = mock_config
        mock_auto_model.from_pretrained.return_value = mock_model

        sentiment = FinBertSentiment(model_name="ProsusAI/finbert", device="cpu")

        with pytest.raises(TypeError, match="fused_record must be a FusedRecord"):
            sentiment.analyze(None)  # type: ignore[arg-type]

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_blank_article_skipped(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
        sample_fused_record_blank_article,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.config = mock_config
        mock_auto_model.from_pretrained.return_value = mock_model

        sentiment = FinBertSentiment(model_name="ProsusAI/finbert", device="cpu")
        result = sentiment.analyze(sample_fused_record_blank_article)

        assert result.sentiment_score == 0.0
        assert result.confidence == 0.0
        assert len(result.breakdown) == 0

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_missing_title_key_uses_summary(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
        sample_fused_record_missing_title,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = _mock_finbert()
        mock_auto_model.from_pretrained.return_value = mock_model

        mock_tok = MagicMock()
        mock_tok.return_value = _encoded_batch((1, 3))
        mock_auto_tokenizer.from_pretrained.return_value = mock_tok

        sentiment = FinBertSentiment(model_name="ProsusAI/finbert", device="cpu")
        result = sentiment.analyze(sample_fused_record_missing_title)

        assert len(result.breakdown) == 1
        assert result.breakdown[0].article_title == ""

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_long_text_truncation(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
        sample_fused_record_long_text,
    ):
        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = _mock_finbert()
        mock_auto_model.from_pretrained.return_value = mock_model

        mock_tok = MagicMock()
        mock_tok.return_value = _encoded_batch((1, 512))
        mock_auto_tokenizer.from_pretrained.return_value = mock_tok

        sentiment = FinBertSentiment(
            model_name="ProsusAI/finbert", device="cpu", max_length=512
        )
        result = sentiment.analyze(sample_fused_record_long_text)

        assert len(result.breakdown) == 1
        assert isinstance(result.sentiment_score, float)

    @patch("src.model.pretrained.sentiment.torch", _MOCK_TORCH)
    @patch("src.model.pretrained.sentiment.AutoTokenizer")
    @patch("src.model.pretrained.sentiment.AutoModelForSequenceClassification")
    @patch("src.model.pretrained.sentiment.AutoConfig")
    def test_batch_processing(
        self,
        mock_auto_config: MagicMock,
        mock_auto_model: MagicMock,
        mock_auto_tokenizer: MagicMock,
    ):
        from src.preprocess.fusion import FusedRecord

        mock_config = MagicMock()
        mock_config.id2label = {0: "positive", 1: "negative", 2: "neutral"}
        mock_auto_config.from_pretrained.return_value = mock_config

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.config = mock_config
        mock_model.eval.return_value = mock_model

        logits = _MOCK_TORCH.tensor([[0.8, 0.1, 0.1], [0.7, 0.2, 0.1]])

        call_count = 0

        def side_effect(input_ids=None, attention_mask=None, **kwargs):
            nonlocal call_count
            call_count += 1
            return MagicMock(logits=logits)

        mock_model.side_effect = side_effect
        mock_auto_model.from_pretrained.return_value = mock_model

        mock_tok = MagicMock()
        mock_tok.return_value = _encoded_batch((2, 5))
        mock_auto_tokenizer.from_pretrained.return_value = mock_tok

        record = FusedRecord(
            ticker="AAPL",
            date="2024-01-15",
            market_data=None,
            news_articles=[
                {"title": "A", "summary": "Good news."},
                {"title": "B", "summary": "Bad news."},
            ],
        )

        sentiment = FinBertSentiment(
            model_name="ProsusAI/finbert", device="cpu", batch_size=2
        )
        result = sentiment.analyze(record)

        assert len(result.breakdown) == 2
        assert call_count == 1
