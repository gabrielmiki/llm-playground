"""Tests for TextCleaner."""

from __future__ import annotations

from src.preprocess.cleaner import CleaningResult, TextCleaner


class TestTextCleaner:
    """Tests for TextCleaner covering encoding fixes, whitespace,
    special characters, garbled detection, and streaming."""

    def test_clean_encoding_fix(self, dirty_text: str):
        cleaner = TextCleaner()
        result = cleaner.clean(dirty_text)
        assert "\u2014" in result.cleaned_text  # em-dash
        assert "'" in result.cleaned_text  # apostrophe after ftfy fix
        assert result.encoding_fixed is True

    def test_clean_whitespace_normalization(self):
        cleaner = TextCleaner()
        text = "Hello   World\n\n\nThis is   a test.\n"
        result = cleaner.clean(text)
        assert result.cleaned_text == "Hello World This is a test."
        assert result.whitespace_fixed is True

    def test_clean_garbled_detection(self, garbled_text: str):
        cleaner = TextCleaner()
        result = cleaner.clean(garbled_text)
        assert result.is_garbled is True

    def test_clean_special_chars_removed(self):
        cleaner = TextCleaner()
        text = "Hello\u200bWorld\u0000Test\u001FEnd"
        result = cleaner.clean(text)
        assert "\u200b" not in result.cleaned_text
        assert "\u0000" not in result.cleaned_text
        assert "\u001f" not in result.cleaned_text
        assert result.special_chars_removed > 0

    def test_clean_clean_text_no_changes(self, clean_text: str):
        cleaner = TextCleaner()
        result = cleaner.clean(clean_text)
        assert result.was_fixed is False
        assert result.cleaned_text == clean_text

    def test_clean_empty_text(self):
        cleaner = TextCleaner()
        result = cleaner.clean("")
        assert result.cleaned_text == ""
        assert result.was_fixed is False
        assert result.is_garbled is False

    def test_clean_text_with_only_whitespace(self):
        cleaner = TextCleaner()
        result = cleaner.clean("   \n\n   ")
        assert result.cleaned_text == ""
        assert result.whitespace_fixed is True

    def test_clean_removes_zero_width_spaces(self):
        cleaner = TextCleaner()
        text = "Hello\u200bWorld\u200bTest"
        result = cleaner.clean(text)
        assert "\u200b" not in result.cleaned_text
        assert result.cleaned_text == "HelloWorldTest"
        assert result.special_chars_removed > 0

    def test_clean_many_yields_results(self):
        cleaner = TextCleaner()
        texts = ["hello", "world", "test"]
        results = list(cleaner.clean_many(texts))
        assert len(results) == 3
        assert all(isinstance(r, CleaningResult) for r in results)
        assert [r.cleaned_text for r in results] == ["hello", "world", "test"]

    def test_clean_many_lazy_evaluation(self, tracking_iterable):
        cleaner = TextCleaner()
        TrackingIterable = tracking_iterable

        texts = TrackingIterable(["a", "b", "c"])
        gen = cleaner.clean_many(texts)
        assert texts.call_count == 0
        next(gen)
        assert texts.call_count == 1
        list(gen)
        assert texts.call_count == 3
