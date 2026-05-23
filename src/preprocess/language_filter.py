from __future__ import annotations

import logging
from collections.abc import Generator, Iterable
from dataclasses import dataclass

import langdetect
from langdetect.lang_detect_exception import LangDetectException

logger = logging.getLogger(__name__)


@dataclass
class LanguageFilterResult:
    article_index: int
    detected_languages: list[tuple[str, float]]
    is_english: bool
    confidence: float
    excluded: bool
    reason: str | None


class LanguageFilter:
    MIN_TEXT_LENGTH = 10
    ENGLISH_CONFIDENCE_THRESHOLD = 0.90

    def filter(self, article_index: int, text: str) -> LanguageFilterResult:
        cleaned = text.strip()
        if not cleaned:
            logger.warning(f"Article {article_index}: empty text after cleaning")
            return LanguageFilterResult(
                article_index=article_index,
                detected_languages=[],
                is_english=False,
                confidence=0.0,
                excluded=True,
                reason="too_short",
            )

        if len(cleaned) < self.MIN_TEXT_LENGTH:
            logger.warning(
                f"Article {article_index}: text too short ({len(cleaned)} chars)"
            )
            return LanguageFilterResult(
                article_index=article_index,
                detected_languages=[],
                is_english=False,
                confidence=0.0,
                excluded=True,
                reason="too_short",
            )

        try:
            langs = langdetect.detect_langs(cleaned)
        except LangDetectException as exc:
            logger.warning(f"Article {article_index}: language detection failed: {exc}")
            return LanguageFilterResult(
                article_index=article_index,
                detected_languages=[],
                is_english=False,
                confidence=0.0,
                excluded=True,
                reason="too_short",
            )

        detected = [(lang.lang, lang.prob) for lang in langs]
        primary_lang = langs[0].lang
        confidence = langs[0].prob
        is_english = primary_lang == "en"

        if is_english and confidence >= self.ENGLISH_CONFIDENCE_THRESHOLD:
            return LanguageFilterResult(
                article_index=article_index,
                detected_languages=detected,
                is_english=True,
                confidence=confidence,
                excluded=False,
                reason=None,
            )

        if not is_english:
            reason = "not_english"
        else:
            reason = "low_confidence"

        logger.info(
            f"Article {article_index}: excluded ({reason}), "
            f"lang={primary_lang}, confidence={confidence:.3f}"
        )
        return LanguageFilterResult(
            article_index=article_index,
            detected_languages=detected,
            is_english=is_english,
            confidence=confidence,
            excluded=True,
            reason=reason,
        )

    def filter_many(
        self, items: Iterable[tuple[int, str]]
    ) -> Generator[LanguageFilterResult, None, None]:
        for article_index, text in items:
            yield self.filter(article_index, text)
