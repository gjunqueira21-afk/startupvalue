from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.auth.rate_limit import clear_local_for_tests


@pytest.fixture(autouse=True)
def isolated_rate_limiter() -> Iterator[None]:
    """The in-process limiter is module state; never let one test's signups throttle another."""
    clear_local_for_tests()
    yield
    clear_local_for_tests()
