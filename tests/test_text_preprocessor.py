"""Tests for StopwordRemover and SentenceTokenizer."""

from __future__ import annotations

from src.preprocess.text_preprocessor import SentenceTokenizer, StopwordRemover


class TestStopwordRemover:
    """Tests for StopwordRemover covering stopword removal and edge cases."""

    def test_remove_removes_english_stopwords(self):
        remover = StopwordRemover()
        text = "The quick brown fox jumps over the lazy dog"
        result = remover.remove(text)
        assert "the" in result.removed_stopwords
        assert "over" in result.removed_stopwords
        assert result.stopword_count == 3
        assert "The" not in result.cleaned_text
        assert "quick" in result.cleaned_text

    def test_remove_no_stopwords(self):
        remover = StopwordRemover()
        text = "quick brown fox jumps lazy dog"
        result = remover.remove(text)
        assert result.stopword_count == 0
        assert result.cleaned_text == text

    def test_remove_empty_text(self):
        remover = StopwordRemover()
        result = remover.remove("")
        assert result.stopword_count == 0
        assert result.cleaned_text == ""

    def test_remove_case_insensitive_matching(self):
        remover = StopwordRemover()
        text = "The Quick Brown Fox"
        result = remover.remove(text)
        assert "the" in result.removed_stopwords
        assert "Quick" in result.cleaned_text

    def test_remove_non_english_language(self):
        remover = StopwordRemover()
        text = "Der schnelle braune Fuchs"
        result = remover.remove(text, language="german")
        assert "der" in result.removed_stopwords


class TestSentenceTokenizer:
    """Tests for SentenceTokenizer covering tokenization and edge cases."""

    def test_tokenize_returns_sentences(self):
        tokenizer = SentenceTokenizer()
        text = "Hello world. This is a test."
        result = tokenizer.tokenize(text)
        assert len(result.sentences) == 2
        assert result.sentence_count == 2
        assert "Hello world." in result.sentences
        assert "This is a test." in result.sentences

    def test_tokenize_short_text_returns_empty(self):
        tokenizer = SentenceTokenizer()
        text = "Hi"
        result = tokenizer.tokenize(text)
        assert result.sentence_count == 0
        assert result.sentences == []

    def test_tokenize_empty_text(self):
        tokenizer = SentenceTokenizer()
        result = tokenizer.tokenize("")
        assert result.sentence_count == 0
        assert result.sentences == []

    def test_tokenize_no_sentence_endings(self):
        tokenizer = SentenceTokenizer()
        text = "Hello world no punctuation here"
        result = tokenizer.tokenize(text)
        assert result.sentence_count >= 1
