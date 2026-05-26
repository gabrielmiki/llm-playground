from __future__ import annotations

import logging
from dataclasses import dataclass

from src.model.exceptions import ModelLoadError
from src.preprocess.fusion import FusedRecord

logger = logging.getLogger(__name__)

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

try:
    from transformers import (
        AutoConfig,
        AutoModelForSequenceClassification,
        AutoTokenizer,
    )
except ImportError:
    AutoConfig = None  # type: ignore[assignment]
    AutoModelForSequenceClassification = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]


@dataclass
class ArticleSentiment:
    article_title: str
    score: float
    confidence: float
    label: str


@dataclass
class SentimentResult:
    sentiment_score: float
    confidence: float
    breakdown: list[ArticleSentiment]


def _neutral_result() -> SentimentResult:
    return SentimentResult(
        sentiment_score=0.0,
        confidence=0.0,
        breakdown=[],
    )


class FinBertSentiment:
    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        device: str | None = None,
        max_length: int = 512,
        batch_size: int = 32,
    ) -> None:
        if torch is None:
            raise ModelLoadError(
                "torch is not installed. Install with: uv sync --extra model"
            )
        if AutoConfig is None:
            raise ModelLoadError(
                "transformers is not installed. Install with: uv sync --extra model"
            )

        self.model_name = model_name
        self.device = device or (
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.max_length = max_length
        self.batch_size = batch_size

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name
            )
            self.model.to(self.device)
            self.model.eval()
            self.id2label = AutoConfig.from_pretrained(model_name).id2label
            self._pos_idx = 0
            self._neg_idx = 1
            self._neu_idx = 2
            for idx, label in self.id2label.items():
                lower = label.lower()
                if "positive" in lower:
                    self._pos_idx = idx
                elif "negative" in lower:
                    self._neg_idx = idx
                elif "neutral" in lower:
                    self._neu_idx = idx
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load model from HuggingFace: {exc}"
            ) from exc

    def analyze(self, record: FusedRecord) -> SentimentResult:
        if not isinstance(record, FusedRecord):
            raise TypeError("fused_record must be a FusedRecord")

        if not record.news_articles:
            return _neutral_result()

        texts: list[str] = []
        article_indexes: list[int] = []

        for i, article in enumerate(record.news_articles):
            if not isinstance(article, dict):
                continue
            title = article.get("title", "")
            summary = article.get("summary", "")
            text = f"{title} {summary}".strip()
            if not text:
                continue
            texts.append(text)
            article_indexes.append(i)

        if not texts:
            return _neutral_result()

        breakdown: list[ArticleSentiment] = []
        total_weighted_score = 0.0
        total_confidence = 0.0

        pos_idx = self._pos_idx
        neg_idx = self._neg_idx
        neu_idx = self._neu_idx

        for start in range(0, len(texts), self.batch_size):
            batch_texts = texts[start : start + self.batch_size]
            batch_indexes = article_indexes[start : start + self.batch_size]

            with torch.no_grad():
                encoded = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )

                outputs = self.model(
                    input_ids=encoded["input_ids"].to(self.device),
                    attention_mask=encoded["attention_mask"].to(self.device),
                )
                probabilities = torch.nn.functional.softmax(
                    outputs.logits, dim=-1
                )

            for j, probs in enumerate(probabilities):
                probs_cpu = probs.cpu()
                pos = float(probs_cpu[pos_idx])
                neg = float(probs_cpu[neg_idx])
                neu = float(probs_cpu[neu_idx])

                score = pos - neg
                confidence = max(pos, neg, neu)
                label = self.id2label[int(probs_cpu.argmax())]

                article_dict = record.news_articles[batch_indexes[j]]
                title = article_dict.get("title", "") or ""  # handle None value

                breakdown.append(
                    ArticleSentiment(
                        article_title=title,
                        score=score,
                        confidence=confidence,
                        label=label,
                    )
                )
                total_weighted_score += score * confidence
                total_confidence += confidence

        if total_confidence > 0:
            aggregated_score = total_weighted_score / total_confidence
            aggregated_confidence = total_confidence / len(breakdown)
        else:
            aggregated_score = 0.0
            aggregated_confidence = 0.0

        return SentimentResult(
            sentiment_score=aggregated_score,
            confidence=aggregated_confidence,
            breakdown=breakdown,
        )
