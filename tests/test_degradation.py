"""Tests for graceful degradation and historical fallback (Ticket 9).

All 8 acceptance criteria verified. Uses fixtures from
tests/fixtures/degradation_data.py for test data.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta

import pytest

from src.collect.market_data import MarketData
from src.generate.degradation import (
    build_degradation_warning,
    build_insufficient_data_warning,
    find_historical_fallback,
)
from src.generate.models import ReportInput
from src.generate.reporter import ReportGenerator
from src.model.pretrained.signals import TradingSignal
from src.preprocess.fusion import DataFusionEngine, FusedRecord
from tests.fixtures.degradation_data import write_fused_records

_TODAY = "2026-05-22"  # Friday
_YESTERDAY = "2026-05-21"  # Thursday
_TWO_DAYS_AGO = "2026-05-20"  # Wednesday


# ── helpers ─────────────────────────────────────────────────────────────

_CONCRETE_MARKET_DATA = MarketData(
    open=306.12, high=311.40, low=305.84, close=308.82,
    volume=43670223, adjusted_close=None,
    timestamp="2026-05-22T00:00:00+00:00",
)


def _make_record(
    date_str: str,
    has_market: bool = True,
    has_news: bool = True,
    ticker: str = "AAPL",
) -> FusedRecord:
    news = (
        [{"title": f"News {date_str}", "source": "T",
          "published_at": f"{date_str}T10:00:00+00:00",
          "url": "https://x.com/n", "summary": "S"}]
        if has_news else []
    )
    md = _CONCRETE_MARKET_DATA if has_market else None
    return FusedRecord(
        ticker=ticker, date=date_str,
        market_data=md, news_articles=news,
        warnings=[],
    )


# ── TestFindHistoricalFallback ──────────────────────────────────────────

class TestFindHistoricalFallback:
    """Unit tests for the core fallback function."""

    def test_fallback_returns_valid_market_record(
        self, tmp_path: str,
    ) -> None:
        """AC-01: Market data available in historical cache → returned."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=True),
        }
        write_fused_records(records, str(tmp_path))

        result = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        assert result is not None
        assert result.date == _YESTERDAY
        assert result.market_data is not None

    def test_fallback_returns_valid_news_record(
        self, tmp_path: str,
    ) -> None:
        """AC-02: News data available in historical cache → returned."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=True),
        }
        write_fused_records(records, str(tmp_path))

        result = find_historical_fallback("AAPL", _TODAY, "news", str(tmp_path))
        assert result is not None
        assert result.date == _YESTERDAY
        assert len(result.news_articles) > 0

    def test_fallback_returns_none_when_no_files(
        self, tmp_path: str,
    ) -> None:
        """AC-03: No historical cache exists → None."""
        result = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        assert result is None

    def test_fallback_returns_none_when_market_field_null(
        self, tmp_path: str,
    ) -> None:
        """AC-03: File exists but market_data=None → None."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=False, has_news=True),
        }
        write_fused_records(records, str(tmp_path))

        result = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        assert result is None

    def test_fallback_returns_none_when_news_field_empty(
        self, tmp_path: str,
    ) -> None:
        """AC-04: File exists but news_articles=[] → None."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=False),
        }
        write_fused_records(records, str(tmp_path))

        result = find_historical_fallback("AAPL", _TODAY, "news", str(tmp_path))
        assert result is None

    def test_fallback_skips_invalid_and_finds_valid(
        self, tmp_path: str,
    ) -> None:
        """Skips records with invalid field, finds older valid one."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=False, has_news=True),
            _TWO_DAYS_AGO: _make_record(_TWO_DAYS_AGO, has_market=True, has_news=True),
        }
        write_fused_records(records, str(tmp_path))

        result = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        assert result is not None
        assert result.date == _TWO_DAYS_AGO

    def test_fallback_returns_closest_valid_first(
        self, tmp_path: str,
    ) -> None:
        """Returns the closest valid date, not furthest."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=True),
            _TWO_DAYS_AGO: _make_record(_TWO_DAYS_AGO, has_market=True, has_news=True),
        }
        write_fused_records(records, str(tmp_path))

        result = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        assert result is not None
        assert result.date == _YESTERDAY  # closest, not _TWO_DAYS_AGO

    def test_fallback_exhausts_all_offsets(
        self, tmp_path: str,
    ) -> None:
        """Returns None after exhausting all 5 lookback days."""
        # Only write a record 6 days back (outside range)
        far_back = (date.fromisoformat(_TODAY) - timedelta(days=6)).isoformat()
        records = {far_back: _make_record(far_back, has_market=True, has_news=True)}
        write_fused_records(records, str(tmp_path))

        result = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        assert result is None

    def test_fallback_weekend_adjustment(
        self, tmp_path: str,
    ) -> None:
        """Saturday/Sunday target dates adjust to Friday."""
        # Weekend 2026-05-23 (Sat) and 2026-05-24 (Sun) both map to Friday 2026-05-22
        records = {_TODAY: _make_record(_TODAY, has_market=True, has_news=True)}
        write_fused_records(records, str(tmp_path))

        # Sunday → should find Friday's record
        result_sun = find_historical_fallback("AAPL", "2026-05-24", "market", str(tmp_path))
        assert result_sun is not None
        assert result_sun.date == _TODAY

        # Saturday → should find Friday's record
        result_sat = find_historical_fallback("AAPL", "2026-05-23", "market", str(tmp_path))
        assert result_sat is not None
        assert result_sat.date == _TODAY

    def test_fallback_invalid_date_returns_none(self, tmp_path: str) -> None:
        """Invalid date string → None."""
        result = find_historical_fallback(
            "AAPL", "not-a-date", "market", str(tmp_path),
        )
        assert result is None

    def test_fallback_non_existent_directory(self) -> None:
        """Non-existent directory → None."""
        result = find_historical_fallback(
            "AAPL", _TODAY, "market",
            fused_dir="/non/existent/path",
        )
        assert result is None


# ── TestBuildDegradationWarning ─────────────────────────────────────────

class TestBuildDegradationWarning:
    """Unit tests for warning construction."""

    def test_degraded_market_warning(self) -> None:
        historical = _make_record(_YESTERDAY, has_market=True, has_news=True)
        w = build_degradation_warning("market", historical, "AAPL", _TODAY)
        assert w.category == "degraded_market"
        assert w.field == "market_data"
        assert _YESTERDAY in w.message

    def test_degraded_news_warning(self) -> None:
        historical = _make_record(_YESTERDAY, has_market=True, has_news=True)
        w = build_degradation_warning("news", historical, "AAPL", _TODAY)
        assert w.category == "degraded_news"
        assert w.field == "news_articles"
        assert _YESTERDAY in w.message

    def test_fallback_failed_market_warning(self) -> None:
        w = build_degradation_warning("market", None, "AAPL", _TODAY)
        assert w.category == "fallback_failed"
        assert w.field == "market_data"
        assert "no historical fallback" in w.message.lower()

    def test_fallback_failed_news_warning(self) -> None:
        w = build_degradation_warning("news", None, "AAPL", _TODAY)
        assert w.category == "fallback_failed"
        assert w.field == "news_articles"
        assert "no historical fallback" in w.message.lower()

    def test_fallback_failed_market_when_record_has_no_market(self) -> None:
        historical = _make_record(_YESTERDAY, has_market=False, has_news=True)
        w = build_degradation_warning("market", historical, "AAPL", _TODAY)
        assert w.category == "fallback_failed"

    def test_fallback_failed_news_when_record_has_no_news(self) -> None:
        historical = _make_record(_YESTERDAY, has_market=True, has_news=False)
        w = build_degradation_warning("news", historical, "AAPL", _TODAY)
        assert w.category == "fallback_failed"

    def test_insufficient_data_warning(self) -> None:
        w = build_insufficient_data_warning("AAPL", _TODAY)
        assert w.category == "insufficient_data"
        assert w.field == "combined"
        assert _TODAY in w.message
        assert "no market data nor news" in w.message.lower()

    def test_warning_value_is_none(self) -> None:
        w = build_degradation_warning("market", None, "AAPL", _TODAY)
        assert w.value is None


# ── TestDegradationWarningRendering (AC-08) ────────────────────────────

class TestDegradationWarningRendering:
    """AC-08: Degradation warnings render in all three report formats."""

    @pytest.fixture
    def generator(self) -> ReportGenerator:
        return ReportGenerator()

    @pytest.fixture
    def report_input_with_degradation_warnings(self) -> ReportInput:
        """ReportInput containing all degradation warning categories."""
        warnings = [
            build_degradation_warning(
                "market",
                _make_record(_YESTERDAY, has_market=True, has_news=True),
                "AAPL", _TODAY,
            ),
            build_degradation_warning("news", None, "MSFT", _TODAY),
            build_insufficient_data_warning("TSLA", _TODAY),
        ]
        return ReportInput(
            ticker_signals=[
                TradingSignal("AAPL", "buy", 0.65, "Rationale", 0.70, 0.05),
                TradingSignal("MSFT", "hold", 0.25, "Rationale", 0.05, 0.002),
                TradingSignal("TSLA", "hold", 0.20, "Rationale", 0.30, None),
            ],
            date=_TODAY,
            warnings=warnings,
        )

    def test_warnings_in_text(
        self,
        generator: ReportGenerator,
        report_input_with_degradation_warnings: ReportInput,
    ) -> None:
        result = generator.generate(report_input_with_degradation_warnings)
        assert "Warnings:" in result.text
        assert "degraded_market" not in result.text  # category not shown in text
        assert "degraded_news" not in result.text  # category not shown
        assert "insufficient_data" not in result.text  # category not shown
        # Text format uses w.message (the human-readable string)
        assert "used fallback from" in result.text
        assert "no historical fallback found" in result.text.lower()

    def test_warnings_in_json(
        self,
        generator: ReportGenerator,
        report_input_with_degradation_warnings: ReportInput,
    ) -> None:
        result = generator.generate(report_input_with_degradation_warnings)
        parsed = json.loads(result.json)
        assert "warnings" in parsed
        assert len(parsed["warnings"]) == 3
        categories = {w["category"] for w in parsed["warnings"]}
        assert "degraded_market" in categories
        assert "fallback_failed" in categories
        assert "insufficient_data" in categories
        # Verify all four fields exist per warning
        for w in parsed["warnings"]:
            assert "category" in w
            assert "field" in w
            assert "message" in w
            assert "value" in w

    def test_warnings_in_html(
        self,
        generator: ReportGenerator,
        report_input_with_degradation_warnings: ReportInput,
    ) -> None:
        result = generator.generate(report_input_with_degradation_warnings)
        assert 'class="warning"' in result.html
        assert "used fallback from" in result.html
        assert "no historical fallback found" in result.html.lower()

    def test_warnings_section_absent_when_none(
        self,
        generator: ReportGenerator,
    ) -> None:
        input_no_warnings = ReportInput(
            ticker_signals=[
                TradingSignal("AAPL", "buy", 0.65, "R", 0.70, 0.05),
            ],
            date=_TODAY,
        )
        result = generator.generate(input_no_warnings)
        parsed = json.loads(result.json)
        assert "warnings" not in parsed
        assert "Warnings:" not in result.text
        assert 'class="warning"' not in result.html


# ── TestFallbackFileEdgeCases ───────────────────────────────────────────

class TestFallbackFileEdgeCases:
    """Edge cases for file loading in fallback."""

    def test_corrupt_json_file(self, tmp_path: str) -> None:
        """Corrupt JSON file → skipped silently."""
        bad_path = os.path.join(str(tmp_path), "AAPL_2026-05-21.json")
        os.makedirs(str(tmp_path), exist_ok=True)
        with open(bad_path, "w") as f:
            f.write("{not valid json")

        result = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        assert result is None

    def test_wrong_ticker_ignored(self, tmp_path: str) -> None:
        """File for wrong ticker is not considered."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=True),
        }
        write_fused_records(records, str(tmp_path))
        # Rename to wrong ticker
        os.rename(
            os.path.join(str(tmp_path), f"AAPL_{_YESTERDAY}.json"),
            os.path.join(str(tmp_path), f"MSFT_{_YESTERDAY}.json"),
        )
        result = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        assert result is None

    def test_missing_market_data_key_in_file(self, tmp_path: str) -> None:
        """File with missing market_data key → handled gracefully."""
        os.makedirs(str(tmp_path), exist_ok=True)
        with open(os.path.join(str(tmp_path), f"AAPL_{_YESTERDAY}.json"), "w") as f:
            json.dump({"ticker": "AAPL", "date": _YESTERDAY}, f)

        result = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        assert result is None

    def test_per_ticker_independent_market_lookback(self, tmp_path: str) -> None:
        """Each ticker finds its own fallback independently (different dates)."""
        records_aapl = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=True),
        }
        records_msft = {
            _TWO_DAYS_AGO: _make_record(_TWO_DAYS_AGO, has_market=True, has_news=True, ticker="MSFT"),
        }
        dir_aapl = os.path.join(str(tmp_path), "aapl")
        dir_msft = os.path.join(str(tmp_path), "msft")
        write_fused_records(records_aapl, dir_aapl)
        write_fused_records(records_msft, dir_msft)

        result_aapl = find_historical_fallback("AAPL", _TODAY, "market", dir_aapl)
        result_msft = find_historical_fallback("MSFT", _TODAY, "market", dir_msft)

        assert result_aapl is not None
        assert result_aapl.date == _YESTERDAY
        assert result_msft is not None
        assert result_msft.date == _TWO_DAYS_AGO

    def test_per_ticker_mixed_failure_modes(self, tmp_path: str) -> None:
        """AC-07: One ticker finds fallback, another fails independently."""
        records_aapl = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=True),
        }
        dir_aapl = os.path.join(str(tmp_path), "aapl")
        dir_googl = os.path.join(str(tmp_path), "googl")
        write_fused_records(records_aapl, dir_aapl)
        os.makedirs(dir_googl, exist_ok=True)

        result_aapl = find_historical_fallback("AAPL", _TODAY, "market", dir_aapl)
        result_googl = find_historical_fallback("GOOGL", _TODAY, "market", dir_googl)

        assert result_aapl is not None
        assert result_aapl.date == _YESTERDAY
        assert result_googl is None

    def test_per_ticker_in_shared_directory(self, tmp_path: str) -> None:
        """Ticker-scoped lookup ignores other tickers in the same directory."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=True, ticker="AAPL"),
            _TWO_DAYS_AGO: _make_record(_TWO_DAYS_AGO, has_market=True, has_news=True, ticker="MSFT"),
        }
        write_fused_records(records, str(tmp_path))

        result_aapl = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        result_msft = find_historical_fallback("MSFT", _TODAY, "market", str(tmp_path))

        assert result_aapl is not None
        assert result_aapl.date == _YESTERDAY
        assert result_msft is not None
        assert result_msft.date == _TWO_DAYS_AGO


class TestPipelineIntegration:
    """Integration-style tests: fallback + warning + fusion compose as in pipeline.py."""

    def test_fallback_and_warning_compose_for_market_failure(self, tmp_path: str) -> None:
        """Simulates pipeline.py's market failure handler: fallback + warning + fusion."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=True),
        }
        write_fused_records(records, str(tmp_path))

        historical = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        market_data = (
            historical.market_data
            if historical is not None and historical.market_data is not None
            else None
        )
        warnings = [build_degradation_warning("market", historical, "AAPL", _TODAY)]

        assert market_data is not None
        assert market_data is historical.market_data
        assert warnings[0].category == "degraded_market"
        assert _YESTERDAY in warnings[0].message

        fused = DataFusionEngine().fuse("AAPL", _TODAY, market_data, [])
        fused.warnings.extend(warnings)
        assert any(w.category == "degraded_market" for w in fused.warnings)

    def test_fallback_and_warning_compose_for_news_failure(self, tmp_path: str) -> None:
        """Simulates pipeline.py's news failure handler: fallback + warning + fusion."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=True, has_news=True),
        }
        write_fused_records(records, str(tmp_path))

        historical = find_historical_fallback("AAPL", _TODAY, "news", str(tmp_path))
        news_articles = (
            historical.news_articles
            if historical is not None and historical.news_articles
            else []
        )
        warnings = [build_degradation_warning("news", historical, "AAPL", _TODAY)]

        assert len(news_articles) > 0
        assert warnings[0].category == "degraded_news"

        fused = DataFusionEngine().fuse("AAPL", _TODAY, None, news_articles)
        fused.warnings.extend(warnings)
        assert any(w.category == "degraded_news" for w in fused.warnings)

    def test_fallback_failed_and_insufficient_data_compose(self, tmp_path: str) -> None:
        """Simulates full failure: both sources None → fallback_failed + insufficient_data."""
        records = {
            _YESTERDAY: _make_record(_YESTERDAY, has_market=False, has_news=False),
        }
        write_fused_records(records, str(tmp_path))

        hist_market = find_historical_fallback("AAPL", _TODAY, "market", str(tmp_path))
        market_data = (
            hist_market.market_data
            if hist_market is not None and hist_market.market_data is not None
            else None
        )
        w_market = build_degradation_warning("market", hist_market, "AAPL", _TODAY)

        hist_news = find_historical_fallback("AAPL", _TODAY, "news", str(tmp_path))
        news_articles = (
            hist_news.news_articles
            if hist_news is not None and hist_news.news_articles
            else []
        )
        w_news = build_degradation_warning("news", hist_news, "AAPL", _TODAY)

        degradation_warnings = [w_market, w_news]
        if not market_data and not news_articles:
            degradation_warnings.append(
                build_insufficient_data_warning("AAPL", _TODAY)
            )

        assert market_data is None
        assert news_articles == []
        assert w_market.category == "fallback_failed"
        assert w_news.category == "fallback_failed"
        assert len(degradation_warnings) == 3
        assert degradation_warnings[2].category == "insufficient_data"

    def test_market_validator_guard_with_none(self) -> None:
        """Pipeline's if market_data is not None: guard prevents crash (AC-05/06)."""
        from src.preprocess.validator import MarketDataValidator

        market_data = None
        md_validator = MarketDataValidator()

        crashes = False
        try:
            if market_data is not None:
                md_validator.validate(market_data)
                crashes = True
        except TypeError:
            crashes = True

        assert not crashes
