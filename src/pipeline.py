"""End-to-end pipeline: collect -> preprocess -> fuse -> sentiment -> signal.

Usage:
    uv run python -m src.pipeline --ticker AAPL --date 2026-05-22
"""

from __future__ import annotations

import warnings

import argparse
import asyncio
import logging
from datetime import date, datetime

from src.collect.exceptions import (
    MarketDataUnavailableError,
    NewsDataUnavailableError,
)
from src.collect.market_data import MarketDataCollector
from src.collect.news_collector import NewsCollector
from src.model.exceptions import ModelLoadError
from src.preprocess.cleaner import TextCleaner
from src.preprocess.fusion import DataFusionEngine
from src.preprocess.language_filter import LanguageFilter
from src.preprocess.output_writer import FusedRecordWriter
from src.preprocess.validator import MarketDataValidator, NewsValidator

# Suppress torch's user warning about NumPy ABI mismatch. The
# "compiled using NumPy 1.x" message from NumPy's C code bypasses
# Python's warnings system entirely and cannot be silenced here;
# pin numpy<2 in pyproject.toml to eliminate both.
warnings.filterwarnings("ignore", message=".*Failed to initialize NumPy.*")

logger = logging.getLogger("pipeline")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def run_pipeline(ticker: str, target_date: str) -> None:
    logger.info("=" * 60)
    logger.info("PIPELINE START: %s @ %s", ticker, target_date)
    logger.info("=" * 60)

    # Stage 1: Collection
    logger.info("")
    logger.info("--- Stage 1: Data Collection ---")
    parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    try:
        async with MarketDataCollector() as md_collector:
            market_data = await md_collector.fetch(ticker, parsed_date)
        logger.info(
            "Market data: open=%.2f close=%.2f high=%.2f low=%.2f volume=%d",
            market_data.open,
            market_data.close,
            market_data.high,
            market_data.low,
            market_data.volume,
        )
    except MarketDataUnavailableError as e:
        logger.warning("Market data unavailable: %s", e)
        market_data = None

    try:
        async with NewsCollector() as news_collector:
            news_articles = await news_collector.fetch_news(ticker, target_date)
        logger.info("News articles: %d raw articles fetched", len(news_articles))
    except NewsDataUnavailableError as e:
        logger.warning("News data unavailable: %s", e)
        news_articles = []

    # Stage 2: Preprocessing
    logger.info("")
    logger.info("--- Stage 2: Preprocessing ---")

    md_validator = MarketDataValidator()
    md_result = md_validator.validate(market_data)
    if not md_result.is_valid:
        for w in md_result.warnings:
            logger.warning("  Market data warning: %s", w.message)

    news_validator = NewsValidator()
    cleaner = TextCleaner()
    lang_filter = LanguageFilter()

    valid_articles: list[dict] = []
    for i, article in enumerate(news_articles):
        v_result = news_validator.validate(article)
        for w in v_result.warnings:
            logger.debug("  Article %d warning: %s", i, w.message)

        title = article.get("title", "") or ""
        summary = article.get("summary", "") or ""

        cleaned_title = cleaner.clean(title).cleaned_text if title else ""
        cleaned_summary = cleaner.clean(summary).cleaned_text if summary else ""

        article_text = f"{cleaned_title} {cleaned_summary}".strip()
        if article_text:
            lang_result = lang_filter.filter(i, article_text)
            if lang_result.excluded:
                logger.info("  Article %d: excluded (%s)", i, lang_result.reason)
                continue

        article["title"] = cleaned_title
        article["summary"] = cleaned_summary
        valid_articles.append(article)

    logger.info(
        "Valid articles after preprocessing: %d / %d",
        len(valid_articles),
        len(news_articles),
    )

    # Stage 3: Fusion
    logger.info("")
    logger.info("--- Stage 3: Data Fusion ---")
    engine = DataFusionEngine()
    fused = engine.fuse(ticker, target_date, market_data, valid_articles)
    logger.info(
        "Fused record: %d matching articles, %d warnings",
        len(fused.news_articles),
        len(fused.warnings),
    )
    for w in fused.warnings:
        logger.warning("  Fusion warning: %s", w.message)

    # Stage 4: Output
    logger.info("")
    logger.info("--- Stage 4: Write Output ---")
    writer = FusedRecordWriter()
    path = writer.write_record(fused)
    logger.info("Fused record written to: %s", path)

    # Stage 5: Sentiment Analysis
    logger.info("")
    logger.info("--- Stage 5: Sentiment Analysis ---")
    sentiment_result = None
    try:
        from src.model.pretrained.sentiment import FinBertSentiment

        sentiment = FinBertSentiment()
        sentiment_result = sentiment.analyze(fused)
        logger.info("Aggregated sentiment score: %+.4f", sentiment_result.sentiment_score)
        logger.info("Aggregated confidence:      %.4f", sentiment_result.confidence)
        logger.info("")
        logger.info("Per-article breakdown:")
        for article in sentiment_result.breakdown:
            logger.info(
                "  [%8s] %+.4f (confidence: %.2f) %s",
                article.label,
                article.score,
                article.confidence,
                article.article_title[:80],
            )
    except ModelLoadError as e:
        logger.warning("Sentiment analysis skipped: %s", e)
        logger.warning("Install torch: uv sync --extra model")
    except ImportError as e:
        logger.warning("Sentiment analysis skipped: %s", e)
        logger.warning("Install torch: uv sync --extra model")

    # Stage 6: Signal Generation
    logger.info("")
    logger.info("--- Stage 6: Signal Generation ---")
    if sentiment_result is not None:
        from src.model.pretrained.signals import TradingSignalGenerator

        generator = TradingSignalGenerator()
        signal = generator.generate(ticker, sentiment_result, fused.market_data)
        logger.info("Signal: %s", signal.signal)
        logger.info("Confidence: %.4f", signal.confidence)
        logger.info("Rationale: %s", signal.rationale)
    else:
        logger.warning("Signal generation skipped: no sentiment result")

    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)


def _parse_cli_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Expected date format YYYY-MM-DD"
        ) from exc
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full data pipeline: collect -> preprocess -> fuse -> sentiment -> signal"
    )
    parser.add_argument(
        "--ticker",
        default="AAPL",
        help="Stock ticker symbol (default: AAPL)",
    )
    parser.add_argument(
        "--date",
        type=_parse_cli_date,
        default=date.today().isoformat(),
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    _setup_logging()
    asyncio.run(run_pipeline(args.ticker.upper(), args.date))


if __name__ == "__main__":
    main()
