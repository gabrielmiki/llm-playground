"""Shared TrackingIterable for testing lazy evaluation in streaming generators."""

from __future__ import annotations

import pytest


@pytest.fixture
def tracking_iterable():
    """Create a TrackingIterable factory for testing lazy evaluation."""

    class _TrackingIterable:
        def __init__(self, items: list):
            self.items = items
            self.call_count = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self.call_count >= len(self.items):
                raise StopIteration
            item = self.items[self.call_count]
            self.call_count += 1
            return item

    return _TrackingIterable
