"""Tests for LanguageFilter."""

from __future__ import annotations
from unittest.mock import MagicMock, patch

from src.preprocess.language_filter import LanguageFilter, LanguageFilterResult


class TestLanguageFilter:
    """Tests for LanguageFilter covering English detection, exclusion, and edge cases."""

    def test_filter_english_text_accepted(self):
        with patch("src.preprocess.language_filter.langdetect.detect_langs") as mock_detect:
            mock_lang = MagicMock()
            mock_lang.lang = "en"
            mock_lang.prob = 0.95
            mock_detect.return_value = [mock_lang]

            filter_ = LanguageFilter()
            result = filter_.filter(0, "This is an English article about finance.")
            assert result.is_english is True
            assert result.excluded is False
            assert result.confidence == 0.95

    def test_filter_portuguese_text_excluded(self):
        with patch("src.preprocess.language_filter.langdetect.detect_langs") as mock_detect:
            mock_lang = MagicMock()
            mock_lang.lang = "pt"
            mock_lang.prob = 0.95
            mock_detect.return_value = [mock_lang]

            filter_ = LanguageFilter()
            result = filter_.filter(1, "Este é um artigo em português sobre finanças.")
            assert result.is_english is False
            assert result.excluded is True
            assert result.reason == "not_english"

    def test_filter_too_short_text_excluded(self):
        filter_ = LanguageFilter()
        result = filter_.filter(2, "Short")
        assert result.excluded is True
        assert result.reason == "too_short"

    def test_filter_empty_text_excluded(self):
        filter_ = LanguageFilter()
        result = filter_.filter(3, "")
        assert result.excluded is True
        assert result.reason == "too_short"

    def test_filter_low_confidence_english_excluded(self):
        with patch("src.preprocess.language_filter.langdetect.detect_langs") as mock_detect:
            mock_lang = MagicMock()
            mock_lang.lang = "en"
            mock_lang.prob = 0.50
            mock_detect.return_value = [mock_lang]

            filter_ = LanguageFilter()
            result = filter_.filter(4, "Some text here that is long enough for detection.")
            assert result.is_english is True
            assert result.excluded is True
            assert result.reason == "low_confidence"

    def test_filter_many_yields_results(self):
        with patch("src.preprocess.language_filter.langdetect.detect_langs") as mock_detect:
            mock_lang = MagicMock()
            mock_lang.lang = "en"
            mock_lang.prob = 0.95
            mock_detect.return_value = [mock_lang]

            filter_ = LanguageFilter()
            items = [(0, "First article about finance."), (1, "Second article about markets.")]
            results = list(filter_.filter_many(items))
            assert len(results) == 2
            assert all(isinstance(r, LanguageFilterResult) for r in results)
            assert all(r.is_english for r in results)

    def test_filter_many_lazy_evaluation(self, tracking_iterable):
        with patch("src.preprocess.language_filter.langdetect.detect_langs") as mock_detect:
            mock_lang = MagicMock()
            mock_lang.lang = "en"
            mock_lang.prob = 0.95
            mock_detect.return_value = [mock_lang]

            filter_ = LanguageFilter()
            TrackingIterable = tracking_iterable
            items = TrackingIterable([(0, "First article."), (1, "Second article.")])
            gen = filter_.filter_many(items)
            assert items.call_count == 0
            next(gen)
            assert items.call_count == 1
            list(gen)
            assert items.call_count == 2
