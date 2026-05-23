from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass, fields
from typing import Any

from src.preprocess.fusion import FusedRecord

logger = logging.getLogger(__name__)


def _fused_record_to_dict(record: FusedRecord) -> dict:
    return {
        "ticker": record.ticker,
        "date": record.date,
        "market_data": _serialize_market_data(record.market_data),
        "news_articles": record.news_articles,
        "warnings": [
            {
                "category": w.category,
                "field": w.field,
                "message": w.message,
                "value": w.value,
            }
            for w in record.warnings
        ],
    }


def _serialize_market_data(md: object | None) -> dict[str, Any] | None:
    if md is None:
        return None
    return {f.name: getattr(md, f.name) for f in fields(md)}  # type: ignore[arg-type]


@dataclass
class FusedRecordWriter:
    output_dir: str = "data/processed/fused"

    def write_record(self, record: FusedRecord) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        file_path = os.path.join(
            self.output_dir, f"{record.ticker}_{record.date}.json"
        )
        data = _fused_record_to_dict(record)
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Written fused record to {file_path}")
        return file_path

    def write_many(self, records: Iterable[FusedRecord]) -> list[str]:
        return [self.write_record(record) for record in records]
