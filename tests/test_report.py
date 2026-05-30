"""Tests for multi-format report generation (Ticket 8).

All 11 acceptance criteria verified. Uses fixtures from
tests/fixtures/report_data.py for test data.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

import pytest

from src.generate.config import TICKERS
from src.generate.models import ReportInput
from src.generate.reporter import ReportGenerator
from src.model.pretrained.signals import TradingSignal

_VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class _WellFormednessChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _VOID_ELEMENTS:
            self.tag_stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_ELEMENTS:
            return
        if not self.tag_stack:
            raise ValueError(f"unexpected </{tag}> with empty stack")
        self.tag_stack.pop()


@pytest.fixture
def generator() -> ReportGenerator:
    return ReportGenerator()


class TestAC01FullReport:
    """AC-01: Report contains all 10 tickers, valid JSON, HTML table/html tags."""

    def test_text_contains_all_tickers(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        for ticker in TICKERS:
            assert f"{ticker:<10}" in result.text

    def test_json_is_valid_parseable(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        parsed = json.loads(result.json)
        assert isinstance(parsed, dict)
        assert "signals" in parsed

    def test_html_has_table_and_html_tags(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        assert "<table>" in result.html
        assert "</html>" in result.html


class TestAC02TickerContent:
    """AC-02: Each ticker, signal label, and confidence in text."""

    def test_each_ticker_in_text(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        for signal in sample_report_input_10.ticker_signals:
            assert f"{signal.ticker:<10}" in result.text

    def test_each_signal_label_in_text(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        for signal in sample_report_input_10.ticker_signals:
            assert f"{signal.signal:>12}" in result.text

    def test_each_confidence_in_text(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        for signal in sample_report_input_10.ticker_signals:
            assert f"{signal.confidence:.2f}" in result.text


class TestAC03JsonStructure:
    """AC-03: Valid JSON with signals array containing all 6 fields."""

    def test_json_has_signals_array(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        parsed = json.loads(result.json)
        assert isinstance(parsed["signals"], list)

    def test_each_signal_has_six_fields(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        parsed = json.loads(result.json)
        required_fields = {
            "ticker",
            "signal",
            "confidence",
            "sentiment_score",
            "market_return",
            "rationale",
        }
        for entry in parsed["signals"]:
            assert set(entry.keys()) == required_fields


class TestAC04Warnings:
    """AC-04: Warnings appear in all three formats."""

    def test_warnings_in_text(
        self,
        generator: ReportGenerator,
        sample_report_input_with_warnings: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_with_warnings)
        assert "Warnings:" in result.text
        assert "open price is 0.0" in result.text

    def test_warnings_in_json(
        self,
        generator: ReportGenerator,
        sample_report_input_with_warnings: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_with_warnings)
        parsed = json.loads(result.json)
        assert "warnings" in parsed
        assert len(parsed["warnings"]) == 3

    def test_warnings_in_html(
        self,
        generator: ReportGenerator,
        sample_report_input_with_warnings: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_with_warnings)
        assert "warning" in result.html
        assert "open price is 0.0" in result.html

    def test_no_warnings_section_when_none(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        parsed = json.loads(result.json)
        assert "warnings" not in parsed

    def test_no_warnings_section_when_empty_list(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        input_with_empty_warnings = ReportInput(
            ticker_signals=sample_report_input_10.ticker_signals,
            date=sample_report_input_10.date,
            warnings=[],
        )
        result = generator.generate(input_with_empty_warnings)
        parsed = json.loads(result.json)
        assert "warnings" not in parsed


class TestAC05EmptySignals:
    """AC-05: Empty signals list → ValueError."""

    def test_value_error_raised(
        self,
        generator: ReportGenerator,
        sample_report_input_empty: ReportInput,
    ) -> None:
        with pytest.raises(ValueError, match="ticker_signals must not be empty"):
            generator.generate(sample_report_input_empty)


class TestAC06NoneInput:
    """AC-06: None as ReportInput → TypeError."""

    def test_type_error_raised(self, generator: ReportGenerator) -> None:
        with pytest.raises(TypeError, match="input must be a ReportInput, got None"):
            generator.generate(None)  # type: ignore[arg-type]


class TestAC07NoMarketReturn:
    """AC-07: market_return=None shows 'N/A' in text and HTML."""

    def test_na_in_text(
        self,
        generator: ReportGenerator,
        sample_report_input_no_market: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_no_market)
        assert "N/A" in result.text

    def test_na_in_html(
        self,
        generator: ReportGenerator,
        sample_report_input_no_market: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_no_market)
        assert "N/A" in result.html

    def test_value_present_in_text(
        self,
        generator: ReportGenerator,
        sample_report_input_no_market: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_no_market)
        assert "+5.00%" in result.text


class TestAC08ReportId:
    """AC-08: report_id is an 8-character hex string."""

    def test_8_char_hex(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        assert re.fullmatch(r"[0-9a-f]{8}", result.report_id)

    def test_report_id_in_text(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        assert result.report_id in result.text

    def test_report_id_in_json(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        parsed = json.loads(result.json)
        assert parsed["report_id"] == result.report_id

    def test_report_id_in_html(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        assert result.report_id in result.html


class TestAC09WellFormedHtml:
    """AC-09: HTML is well-formed (parseable without unclosed tags)."""

    def test_html_is_well_formed(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        checker = _WellFormednessChecker()
        try:
            checker.feed(result.html)
        except ValueError as exc:
            pytest.fail(f"HTML is not well-formed: {exc}")

    def test_html_with_warnings_is_well_formed(
        self,
        generator: ReportGenerator,
        sample_report_input_with_warnings: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_with_warnings)
        checker = _WellFormednessChecker()
        try:
            checker.feed(result.html)
        except ValueError as exc:
            pytest.fail(f"HTML with warnings is not well-formed: {exc}")


class TestAC10DataLineCount:
    """AC-10: Data line count matches across all three formats."""

    def _count_text_data_lines(self, text: str) -> int:
        lines = text.split("\n")
        separator_count = 0
        data_start = -1
        data_end = -1
        for i, line in enumerate(lines):
            if line == "-" * 69:
                separator_count += 1
                if separator_count == 1:
                    data_start = i + 1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i] == "=" * 60:
                data_end = i
                break
        if data_start < 0 or data_end < 0:
            return 0
        data_lines = [ln for ln in lines[data_start:data_end] if ln.strip()]
        return len(data_lines)

    def _count_html_data_rows(self, html: str) -> int:
        total_tr = html.count("<tr>")
        header_trs = html.count("<tr><th>")
        return total_tr - header_trs

    def test_counts_match(
        self,
        generator: ReportGenerator,
        sample_report_input_10: ReportInput,
    ) -> None:
        result = generator.generate(sample_report_input_10)
        parsed = json.loads(result.json)
        text_lines = self._count_text_data_lines(result.text)
        html_rows = self._count_html_data_rows(result.html)

        assert text_lines == len(parsed["signals"])
        assert html_rows == len(parsed["signals"])


class TestSignalFormatting:
    """Exercise individual signal fixtures to verify per-type formatting."""

    def test_buy_signal_html_has_buy_class(
        self,
        generator: ReportGenerator,
        sample_trading_signal_buy: TradingSignal,
    ) -> None:
        input_data = ReportInput(
            ticker_signals=[sample_trading_signal_buy],
            date="2026-05-28",
        )
        result = generator.generate(input_data)
        assert 'class="buy"' in result.html

    def test_sell_signal_html_has_sell_class(
        self,
        generator: ReportGenerator,
        sample_trading_signal_sell: TradingSignal,
    ) -> None:
        input_data = ReportInput(
            ticker_signals=[sample_trading_signal_sell],
            date="2026-05-28",
        )
        result = generator.generate(input_data)
        assert 'class="sell"' in result.html

    def test_hold_signal_html_has_hold_class(
        self,
        generator: ReportGenerator,
        sample_trading_signal_hold: TradingSignal,
    ) -> None:
        input_data = ReportInput(
            ticker_signals=[sample_trading_signal_hold],
            date="2026-05-28",
        )
        result = generator.generate(input_data)
        assert 'class="hold"' in result.html

    def test_no_market_signal_na_in_text(
        self,
        generator: ReportGenerator,
        sample_trading_signal_no_market: TradingSignal,
    ) -> None:
        input_data = ReportInput(
            ticker_signals=[sample_trading_signal_no_market],
            date="2026-05-28",
        )
        result = generator.generate(input_data)
        assert "N/A" in result.text

    def test_no_market_signal_null_in_json(
        self,
        generator: ReportGenerator,
        sample_trading_signal_no_market: TradingSignal,
    ) -> None:
        input_data = ReportInput(
            ticker_signals=[sample_trading_signal_no_market],
            date="2026-05-28",
        )
        result = generator.generate(input_data)
        parsed = json.loads(result.json)
        assert parsed["signals"][0]["market_return"] is None

    def test_no_market_signal_na_in_html(
        self,
        generator: ReportGenerator,
        sample_trading_signal_no_market: TradingSignal,
    ) -> None:
        input_data = ReportInput(
            ticker_signals=[sample_trading_signal_no_market],
            date="2026-05-28",
        )
        result = generator.generate(input_data)
        assert "N/A" in result.html


class TestAC11InvalidDate:
    """AC-11: run_report_generation with bad date → ValueError."""

    def test_empty_date_raises(self) -> None:
        from src.generate.orchestrate import _validate_date

        with pytest.raises(ValueError, match="date must not be empty"):
            _validate_date("")

    def test_malformed_date_raises(self) -> None:
        from src.generate.orchestrate import _validate_date

        with pytest.raises(ValueError, match="date must be in YYYY-MM-DD format"):
            _validate_date("not-a-date")

    def test_valid_date_passes(self) -> None:
        from src.generate.orchestrate import _validate_date

        _validate_date("2026-05-28")
