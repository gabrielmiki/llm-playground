from __future__ import annotations

import json
import os
from datetime import datetime

from src.collect.market_data import MarketData
from src.generate.config import TICKERS
from src.generate.models import ReportInput, ReportResult
from src.generate.reporter import ReportGenerator
from src.model.pretrained import FinBertSentiment, TradingSignalGenerator
from src.preprocess.fusion import FusedRecord
from src.preprocess.validator import ValidationWarning


def _validate_date(date: str) -> None:
    if not date:
        raise ValueError("date must not be empty")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"date must be in YYYY-MM-DD format, got {date!r}")


def _decode_fused_record(data: dict) -> FusedRecord:
    md_data = data.get("market_data")
    market_data = None
    if md_data is not None:
        md_data["volume"] = int(md_data["volume"])
        market_data = MarketData(**md_data)
    warnings = [ValidationWarning(**w) for w in data.get("warnings", [])]
    return FusedRecord(
        ticker=data["ticker"],
        date=data["date"],
        market_data=market_data,
        news_articles=data.get("news_articles", []),
        warnings=warnings,
    )


def load_fused_record(ticker: str, date: str) -> FusedRecord:
    file_path = os.path.join("data/processed/fused", f"{ticker}_{date}.json")
    with open(file_path) as f:
        data = json.load(f)
    return _decode_fused_record(data)


def run_report_generation(date: str) -> ReportResult:
    _validate_date(date)

    sentiment_engine = FinBertSentiment()
    signal_generator = TradingSignalGenerator()

    all_signals = []
    all_warnings: list[ValidationWarning] = []

    for ticker in TICKERS:
        fused = load_fused_record(ticker, date)
        sentiment_result = sentiment_engine.analyze(fused)
        signal = signal_generator.generate(ticker, sentiment_result, fused.market_data)
        all_signals.append(signal)
        all_warnings.extend(fused.warnings)

    report_input = ReportInput(
        ticker_signals=all_signals,
        date=date,
        warnings=all_warnings,
    )
    generator = ReportGenerator()
    result = generator.generate(report_input)

    os.makedirs("data/processed/reports", exist_ok=True)
    _ext_to_attr = {"txt": "text", "json": "json", "html": "html"}
    for ext in ("txt", "json", "html"):
        path = os.path.join("data/processed/reports", f"{result.report_id}.{ext}")
        content = getattr(result, _ext_to_attr[ext])
        with open(path, "w") as f:
            f.write(content)

    return result
