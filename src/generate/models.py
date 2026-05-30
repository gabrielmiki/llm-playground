from __future__ import annotations

from dataclasses import dataclass

from src.model.pretrained.signals import TradingSignal
from src.preprocess.validator import ValidationWarning


@dataclass
class ReportInput:
    ticker_signals: list[TradingSignal]
    date: str
    warnings: list[ValidationWarning] | None = None


@dataclass
class ReportResult:
    report_id: str
    text: str
    json: str
    html: str
