"""Tests for FusedRecordWriter."""

from __future__ import annotations

import json
import os
import tempfile

from src.collect.market_data import MarketData
from src.preprocess.fusion import FusedRecord
from src.preprocess.output_writer import FusedRecordWriter


class TestFusedRecordWriter:
    """Tests for FusedRecordWriter covering single and batch writes."""

    def test_write_record_creates_json_file(self):
        record = FusedRecord(
            ticker="AAPL",
            date="2024-01-15",
            market_data=None,
            news_articles=[{"title": "Test", "published_at": "2024-01-15T10:00:00+00:00"}],
            warnings=[],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FusedRecordWriter(output_dir=tmpdir)
            file_path = writer.write_record(record)
            assert os.path.exists(file_path)
            assert file_path.endswith("AAPL_2024-01-15.json")
            with open(file_path) as f:
                data = json.load(f)
            assert data["ticker"] == "AAPL"
            assert data["date"] == "2024-01-15"
            assert data["market_data"] is None
            assert data["warnings"] == []
            assert len(data["news_articles"]) == 1
            assert data["news_articles"][0]["title"] == "Test"

    def test_write_record_handles_market_data(self):
        market_data = MarketData(
            open=150.0, high=155.0, low=148.0, close=153.0,
            volume=50000000, adjusted_close=152.5, timestamp="2024-01-15",
        )
        record = FusedRecord(
            ticker="MSFT",
            date="2024-01-15",
            market_data=market_data,
            news_articles=[],
            warnings=[],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FusedRecordWriter(output_dir=tmpdir)
            file_path = writer.write_record(record)
            with open(file_path) as f:
                data = json.load(f)
            assert data["market_data"]["open"] == 150.0
            assert data["market_data"]["high"] == 155.0
            assert data["market_data"]["low"] == 148.0
            assert data["market_data"]["close"] == 153.0
            assert data["market_data"]["volume"] == 50000000
            assert data["market_data"]["adjusted_close"] == 152.5
            assert data["market_data"]["timestamp"] == "2024-01-15"

    def test_write_record_creates_directory(self):
        record = FusedRecord(
            ticker="AAPL",
            date="2024-01-15",
            market_data=None,
            news_articles=[],
            warnings=[],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "nested", "dir")
            writer = FusedRecordWriter(output_dir=nested_dir)
            file_path = writer.write_record(record)
            assert os.path.exists(nested_dir)
            assert os.path.exists(file_path)

    def test_write_many_returns_paths(self):
        records = [
            FusedRecord(ticker="AAPL", date="2024-01-15", market_data=None, news_articles=[], warnings=[]),
            FusedRecord(ticker="MSFT", date="2024-01-15", market_data=None, news_articles=[], warnings=[]),
            FusedRecord(ticker="GOOG", date="2024-01-15", market_data=None, news_articles=[], warnings=[]),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FusedRecordWriter(output_dir=tmpdir)
            paths = writer.write_many(records)
            assert len(paths) == 3
            assert all(os.path.exists(p) for p in paths)
            assert any("AAPL" in p for p in paths)
            assert any("MSFT" in p for p in paths)
            assert any("GOOG" in p for p in paths)
            for path in paths:
                with open(path) as f:
                    data = json.load(f)
                assert "ticker" in data
                assert "date" in data
                assert "market_data" in data
                assert "warnings" in data
                assert "news_articles" in data
