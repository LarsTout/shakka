"""Daylight check via astral. Pure: the date is always passed to astral, never the clock."""

import functools
from datetime import UTC, date, datetime, timedelta

from astral import Observer
from astral.sun import sunrise, sunset

from shakka.domain.defaults import DAYLIGHT_MARGIN_AFTER_SUNSET, DAYLIGHT_MARGIN_BEFORE_SUNRISE


@functools.lru_cache(maxsize=4096)
def sun_times(lat: float, lon: float, day: date) -> tuple[datetime, datetime]:
    """(sunrise, sunset) on UTC date `day`, tz-aware UTC, via astral with date=day, tzinfo=UTC.
    Propagates astral's ValueError when the sun does not rise or set."""
    observer = Observer(latitude=lat, longitude=lon)
    return (
        sunrise(observer, date=day, tzinfo=UTC),
        sunset(observer, date=day, tzinfo=UTC),
    )


def is_daylight(lat: float, lon: float, valid_at: datetime) -> bool:
    """True if the hour [valid_at, valid_at + 1h) lies within
    [sunrise - DAYLIGHT_MARGIN_BEFORE_SUNRISE, sunset + DAYLIGHT_MARGIN_AFTER_SUNSET]
    of the UTC date of valid_at. ValueError if valid_at is naive."""
    if valid_at.tzinfo is None or valid_at.utcoffset() is None:
        raise ValueError("valid_at must be timezone-aware")
    t = valid_at.astimezone(UTC)
    sr, ss = sun_times(lat, lon, t.date())
    return (
        t >= sr - DAYLIGHT_MARGIN_BEFORE_SUNRISE
        and t + timedelta(hours=1) <= ss + DAYLIGHT_MARGIN_AFTER_SUNSET
    )
