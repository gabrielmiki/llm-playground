from __future__ import annotations

import pytest


SAMPLE_FUSED_TEXT = (
    "Apple Reports Record Earnings "
    "Apple Inc. announced strong Q4 results with revenue exceeding expectations."
)

SAMPLE_FUSED_TEXT_MULTI = (
    "Apple Reports Record Earnings "
    "Apple Inc. announced strong Q4 results.\n"
    "Markets Rally on Fed Decision "
    "The Federal Reserve maintained interest rates."
)

SAMPLE_SPECIAL_TOKENS = "<|endoftext|>Hello<|endoftext|>"

SAMPLE_EMPTY = ""

SAMPLE_TICKER = "AAPL"
SAMPLE_DATE = "2024-01-15"


@pytest.fixture
def sample_fused_text() -> str:
    return SAMPLE_FUSED_TEXT


@pytest.fixture
def sample_fused_text_multi() -> str:
    return SAMPLE_FUSED_TEXT_MULTI


@pytest.fixture
def sample_special_tokens_text() -> str:
    return SAMPLE_SPECIAL_TOKENS


@pytest.fixture
def sample_empty_text() -> str:
    return SAMPLE_EMPTY
