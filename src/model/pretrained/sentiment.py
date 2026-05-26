from __future__ import annotations

import logging
from dataclasses import dataclass

from src.model.exceptions import ModelLoadError
from src.preprocess.fusion import FusedRecord

logger = logging.getLogger(__name__)

try:
    import torch

    from transformers import (
        AutoConfig,
        AutoModelForSequenceClassification,
        AutoTokenizer,
    )
except ImportError:
    torch = None  # type: ignore[assignment]
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


_NEUTRAL_RESULT = SentimentResult(
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
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load model from HuggingFace: {exc}"
            ) from exc

    def analyze(self, record: FusedRecord) -> SentimentResult:
        if record is None:
            raise TypeError("fused_record must be a FusedRecord")

        if not record.news_articles:
            return _NEUTRAL_RESULT

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
            return _NEUTRAL_RESULT

        breakdown: list[ArticleSentiment] = []
        total_weighted_score = 0.0
        total_confidence = 0.0

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
                pos = float(probs_cpu[0])
                neg = float(probs_cpu[1])
                neu = float(probs_cpu[2])

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
