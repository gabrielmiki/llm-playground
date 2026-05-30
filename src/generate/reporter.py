from __future__ import annotations

import html
import json
import uuid
from typing import Any

from src.generate.models import ReportInput, ReportResult


class ReportGenerator:
    def generate(self, input: ReportInput | None) -> ReportResult:
        if input is None:
            raise TypeError("input must be a ReportInput, got None")
        if not input.ticker_signals:
            raise ValueError("ticker_signals must not be empty")

        self._report_id = uuid.uuid4().hex[:8]

        text = self._format_text(input)
        json_str = self._format_json(input)
        html_str = self._format_html(input)

        return ReportResult(
            report_id=self._report_id,
            text=text,
            json=json_str,
            html=html_str,
        )

    def _format_text(self, input: ReportInput) -> str:
        lines: list[str] = []
        lines.append(f"Report: {input.date}")
        lines.append(f"Report ID: {self._report_id}")
        lines.append("=" * 60)
        lines.append("")

        header = (
            f"{'Ticker':<10}"
            f"{'Signal':>12}"
            f"{'Confidence':>12}"
            f"{'Sentiment':>12}"
            f"{'Market Return':>13}"
            f" Rationale"
        )
        lines.append(header)
        lines.append("-" * 69)

        for s in input.ticker_signals:
            ticker = f"{s.ticker:<10}"
            sig = f"{s.signal:>12}"
            conf = f"{s.confidence:>12.2f}"
            sent = f"{s.sentiment_score:>+12.4f}"

            if s.market_return is not None:
                mret = f"{s.market_return:+.2%}"
            else:
                mret = "N/A"
            mret_col = f"{mret:>13}"

            rationale = s.rationale
            if len(rationale) > 60:
                rationale = rationale[:60] + "..."

            lines.append(f"{ticker}{sig}{conf}{sent}{mret_col} {rationale}")

        lines.append("")
        lines.append("=" * 60)

        if input.warnings:
            lines.append("Warnings:")
            for w in input.warnings:
                lines.append(f"- {w.message}")

        return "\n".join(lines) + "\n"

    def _format_json(self, input: ReportInput) -> str:
        signals: list[dict[str, Any]] = [
            {
                "ticker": s.ticker,
                "signal": s.signal,
                "confidence": s.confidence,
                "sentiment_score": s.sentiment_score,
                "market_return": s.market_return,
                "rationale": s.rationale,
            }
            for s in input.ticker_signals
        ]
        result: dict[str, Any] = {
            "report_id": self._report_id,
            "date": input.date,
            "signals": signals,
        }
        if input.warnings:
            result["warnings"] = [
                {
                    "category": w.category,
                    "field": w.field,
                    "message": w.message,
                    "value": w.value,
                }
                for w in input.warnings
            ]
        return json.dumps(result, indent=2)

    def _format_html(self, input: ReportInput) -> str:
        rows_parts: list[str] = []
        for s in input.ticker_signals:
            css_class = s.signal
            mret = f"{s.market_return:+.2%}" if s.market_return is not None else "N/A"
            safe_rationale = html.escape(s.rationale)
            rows_parts.append(
                f"    <tr>"
                f"<td>{html.escape(s.ticker)}</td>"
                f'<td class="{css_class}">{html.escape(s.signal)}</td>'
                f"<td>{s.confidence:.2f}</td>"
                f"<td>{s.sentiment_score:+.4f}</td>"
                f"<td>{mret}</td>"
                f"<td>{safe_rationale}</td>"
                f"</tr>"
            )
        rows_html = "\n".join(rows_parts)

        warnings_html = ""
        if input.warnings:
            warning_items = "\n".join(
                f"    <p>{html.escape(w.message)}</p>" for w in input.warnings
            )
            warnings_html = f'<div class="warning">\n{warning_items}\n  </div>\n'

        return (
            f"<!DOCTYPE html>\n"
            f"<html>\n"
            f"<head><title>Report: {input.date}</title>\n"
            f"<style>\n"
            f"  table {{ border-collapse: collapse; width: 100%; }}\n"
            f"  th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}\n"
            f"  th {{ background: #f5f5f5; }}\n"
            f"  .buy  {{ color: green; font-weight: bold; }}\n"
            f"  .sell {{ color: red; font-weight: bold; }}\n"
            f"  .hold {{ color: #888; }}\n"
            f"  .warning {{ background: #fff3cd; }}\n"
            f"</style>\n"
            f"</head>\n"
            f"<body>\n"
            f"<h1>End-of-Day Report</h1>\n"
            f"<p>Date: {input.date} | Report ID: {self._report_id}</p>\n"
            f"<table>\n"
            f"  <tr><th>Ticker</th><th>Signal</th><th>Confidence</th>"
            f"<th>Sentiment</th><th>Market Return</th><th>Rationale</th></tr>\n"
            f"{rows_html}\n"
            f"</table>\n"
            f"{warnings_html}"
            f"</body>\n"
            f"</html>"
        )
