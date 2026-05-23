from __future__ import annotations

import logging
from dataclasses import dataclass

import nltk
import regex
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize

logger = logging.getLogger(__name__)


@dataclass
class StopwordRemovalResult:
    original_text: str
    cleaned_text: str
    removed_stopwords: list[str]
    stopword_count: int


@dataclass
class SentenceTokenizeResult:
    original_text: str
    sentences: list[str]
    sentence_count: int


class StopwordRemover:
    def remove(self, text: str, language: str = "english") -> StopwordRemovalResult:
        try:
            stop_words = set(stopwords.words(language))
        except LookupError:
            logger.info("Downloading NLTK stopwords corpus")
            nltk.download("stopwords", quiet=True)
            stop_words = set(stopwords.words(language))

        tokens = regex.findall(r"\p{L}+", text)
        removed: list[str] = []
        kept: list[str] = []

        for token in tokens:
            if token.lower() in stop_words:
                removed.append(token.lower())
            else:
                kept.append(token)

        return StopwordRemovalResult(
            original_text=text,
            cleaned_text=" ".join(kept),
            removed_stopwords=removed,
            stopword_count=len(removed),
        )


class SentenceTokenizer:
    MIN_TEXT_LENGTH = 20

    def tokenize(self, text: str) -> SentenceTokenizeResult:
        if len(text.strip()) < self.MIN_TEXT_LENGTH:
            return SentenceTokenizeResult(
                original_text=text,
                sentences=[],
                sentence_count=0,
            )

        try:
            sentences = sent_tokenize(text)
        except LookupError:
            logger.info("Downloading NLTK punkt tokenizer")
            nltk.download("punkt_tab", quiet=True)
            sentences = sent_tokenize(text)

        return SentenceTokenizeResult(
            original_text=text,
            sentences=sentences,
            sentence_count=len(sentences),
        )
