"""Unit tests for date range expansion logic.

These tests verify the date expansion algorithm used in the map view's
date navigation buttons. The actual implementation is in JavaScript
(in map.py), but we test the algorithm here in Python to ensure the
logic is correct.

The expansion rules are:
- ~1 day (0-2 days) -> expand by 3 days (to ~1 week)
- ~1 week (3-10 days) -> expand by 14 days (to ~1 month)
- ~1 month (11-45 days) -> expand by 150 days (to ~6 months)
- ~6 months (46-200 days) -> expand by 180 days (to ~1 year)
- >200 days -> expand by 365 days
"""

from datetime import date, timedelta

import pytest


def get_expansion_days(interval_days: int) -> int:
    """Calculate expansion amount based on current interval.

    This mirrors the JavaScript implementation in map.py's expandDateRange function.
    """
    if interval_days <= 2:
        return 3  # ~1 day -> ~1 week
    elif interval_days <= 10:
        return 14  # ~1 week -> ~1 month
    elif interval_days <= 45:
        return 150  # ~1 month -> ~6 months
    elif interval_days <= 200:
        return 180  # ~6 months -> ~1 year
    else:
        return 365  # >200 days -> add 1 year


def expand_date_range(
    date_from: date, date_to: date, direction: str
) -> tuple[date, date]:
    """Expand date range in the given direction.

    Args:
        date_from: Start date of the range.
        date_to: End date of the range.
        direction: 'prev' to expand backward, 'next' to expand forward.

    Returns:
        Tuple of (new_from, new_to) dates.
    """
    interval_days = (date_to - date_from).days
    expand_days = get_expansion_days(interval_days)

    if direction == "prev":
        return (date_from - timedelta(days=expand_days), date_to)
    else:
        return (date_from, date_to + timedelta(days=expand_days))


@pytest.mark.ai_generated
class TestGetExpansionDays:
    """Test the expansion day calculation."""

    def test_single_day_range(self) -> None:
        """A single day (0 days interval) should expand by 3 days."""
        assert get_expansion_days(0) == 3

    def test_one_day_range(self) -> None:
        """A 1-day range should expand by 3 days."""
        assert get_expansion_days(1) == 3

    def test_two_day_range(self) -> None:
        """A 2-day range should expand by 3 days."""
        assert get_expansion_days(2) == 3

    def test_three_day_range_is_week_range(self) -> None:
        """A 3-day range should expand by 14 days (week range)."""
        assert get_expansion_days(3) == 14

    def test_week_range(self) -> None:
        """A 7-day range should expand by 14 days."""
        assert get_expansion_days(7) == 14

    def test_ten_day_range(self) -> None:
        """A 10-day range (upper bound of week) should expand by 14 days."""
        assert get_expansion_days(10) == 14

    def test_eleven_day_range_is_month_range(self) -> None:
        """An 11-day range should expand by 150 days (month range)."""
        assert get_expansion_days(11) == 150

    def test_month_range(self) -> None:
        """A 30-day range should expand by 150 days."""
        assert get_expansion_days(30) == 150

    def test_fortyfive_day_range(self) -> None:
        """A 45-day range (upper bound of month) should expand by 150 days."""
        assert get_expansion_days(45) == 150

    def test_fortysix_day_range_is_halfyear_range(self) -> None:
        """A 46-day range should expand by 180 days (half-year range)."""
        assert get_expansion_days(46) == 180

    def test_halfyear_range(self) -> None:
        """A 180-day range should expand by 180 days."""
        assert get_expansion_days(180) == 180

    def test_twohundred_day_range(self) -> None:
        """A 200-day range (upper bound of half-year) should expand by 180 days."""
        assert get_expansion_days(200) == 180

    def test_twohundredone_day_range_is_year_range(self) -> None:
        """A 201-day range should expand by 365 days (year range)."""
        assert get_expansion_days(201) == 365

    def test_year_range(self) -> None:
        """A 365-day range should expand by 365 days."""
        assert get_expansion_days(365) == 365

    def test_multiyear_range(self) -> None:
        """A 1000-day range should expand by 365 days."""
        assert get_expansion_days(1000) == 365


@pytest.mark.ai_generated
class TestExpandDateRange:
    """Test the full expand_date_range function."""

    def test_single_day_expand_prev(self) -> None:
        """Expanding a single day backward should extend start by 3 days."""
        date_from = date(2024, 6, 15)
        date_to = date(2024, 6, 15)
        new_from, new_to = expand_date_range(date_from, date_to, "prev")
        assert new_from == date(2024, 6, 12)
        assert new_to == date(2024, 6, 15)

    def test_single_day_expand_next(self) -> None:
        """Expanding a single day forward should extend end by 3 days."""
        date_from = date(2024, 6, 15)
        date_to = date(2024, 6, 15)
        new_from, new_to = expand_date_range(date_from, date_to, "next")
        assert new_from == date(2024, 6, 15)
        assert new_to == date(2024, 6, 18)

    def test_week_expand_prev(self) -> None:
        """Expanding a week backward should extend start by 14 days."""
        date_from = date(2024, 6, 10)
        date_to = date(2024, 6, 17)
        new_from, new_to = expand_date_range(date_from, date_to, "prev")
        assert new_from == date(2024, 5, 27)
        assert new_to == date(2024, 6, 17)

    def test_week_expand_next(self) -> None:
        """Expanding a week forward should extend end by 14 days."""
        date_from = date(2024, 6, 10)
        date_to = date(2024, 6, 17)
        new_from, new_to = expand_date_range(date_from, date_to, "next")
        assert new_from == date(2024, 6, 10)
        assert new_to == date(2024, 7, 1)

    def test_month_expand_prev(self) -> None:
        """Expanding a month backward should extend start by 150 days."""
        date_from = date(2024, 6, 1)
        date_to = date(2024, 6, 30)
        new_from, new_to = expand_date_range(date_from, date_to, "prev")
        assert new_from == date(2024, 1, 3)  # 150 days before June 1
        assert new_to == date(2024, 6, 30)

    def test_month_expand_next(self) -> None:
        """Expanding a month forward should extend end by 150 days."""
        date_from = date(2024, 6, 1)
        date_to = date(2024, 6, 30)
        new_from, new_to = expand_date_range(date_from, date_to, "next")
        assert new_from == date(2024, 6, 1)
        assert new_to == date(2024, 11, 27)  # 150 days after June 30

    def test_halfyear_expand_prev(self) -> None:
        """Expanding 6 months backward should extend start by 180 days."""
        date_from = date(2024, 1, 1)
        date_to = date(2024, 6, 30)  # 181 days
        new_from, new_to = expand_date_range(date_from, date_to, "prev")
        assert new_from == date(2023, 7, 5)  # 180 days before Jan 1
        assert new_to == date(2024, 6, 30)

    def test_halfyear_expand_next(self) -> None:
        """Expanding 6 months forward should extend end by 180 days."""
        date_from = date(2024, 1, 1)
        date_to = date(2024, 6, 30)  # 181 days
        new_from, new_to = expand_date_range(date_from, date_to, "next")
        assert new_from == date(2024, 1, 1)
        assert new_to == date(2024, 12, 27)  # 180 days after June 30

    def test_year_expand_prev(self) -> None:
        """Expanding a full year backward should extend start by 365 days."""
        date_from = date(2023, 1, 1)
        date_to = date(2024, 1, 1)  # 366 days (leap year)
        new_from, new_to = expand_date_range(date_from, date_to, "prev")
        assert new_from == date(2022, 1, 1)  # 365 days before Jan 1, 2023
        assert new_to == date(2024, 1, 1)

    def test_year_expand_next(self) -> None:
        """Expanding a full year forward should extend end by 365 days."""
        date_from = date(2023, 1, 1)
        date_to = date(2024, 1, 1)  # 366 days (leap year)
        new_from, new_to = expand_date_range(date_from, date_to, "next")
        assert new_from == date(2023, 1, 1)
        assert new_to == date(2024, 12, 31)  # 365 days after Jan 1, 2024


@pytest.mark.ai_generated
class TestExpansionProgression:
    """Test that repeated expansions grow the range progressively."""

    def test_repeated_prev_expansion_grows_range(self) -> None:
        """Repeatedly expanding backward should progressively grow the range."""
        date_from = date(2024, 6, 15)
        date_to = date(2024, 6, 15)

        # First expansion: 0 days -> +3 days = 3 day range
        new_from, new_to = expand_date_range(date_from, date_to, "prev")
        assert (new_to - new_from).days == 3

        # Second expansion: 3 days -> +14 days = 17 day range
        new_from, new_to = expand_date_range(new_from, new_to, "prev")
        assert (new_to - new_from).days == 17

        # Third expansion: 17 days -> +150 days = 167 day range
        new_from, new_to = expand_date_range(new_from, new_to, "prev")
        assert (new_to - new_from).days == 167

        # Fourth expansion: 167 days -> +180 days = 347 day range
        new_from, new_to = expand_date_range(new_from, new_to, "prev")
        assert (new_to - new_from).days == 347

        # Fifth expansion: 347 days -> +365 days = 712 day range (~2 years)
        new_from, new_to = expand_date_range(new_from, new_to, "prev")
        assert (new_to - new_from).days == 712

    def test_repeated_next_expansion_grows_range(self) -> None:
        """Repeatedly expanding forward should progressively grow the range."""
        date_from = date(2024, 6, 15)
        date_to = date(2024, 6, 15)

        # First expansion: 0 days -> +3 days = 3 day range
        new_from, new_to = expand_date_range(date_from, date_to, "next")
        assert (new_to - new_from).days == 3

        # Second expansion: 3 days -> +14 days = 17 day range
        new_from, new_to = expand_date_range(new_from, new_to, "next")
        assert (new_to - new_from).days == 17

        # Third expansion: 17 days -> +150 days = 167 day range
        new_from, new_to = expand_date_range(new_from, new_to, "next")
        assert (new_to - new_from).days == 167

        # Fourth expansion: 167 days -> +180 days = 347 day range
        new_from, new_to = expand_date_range(new_from, new_to, "next")
        assert (new_to - new_from).days == 347

        # Fifth expansion: 347 days -> +365 days = 712 day range (~2 years)
        new_from, new_to = expand_date_range(new_from, new_to, "next")
        assert (new_to - new_from).days == 712
