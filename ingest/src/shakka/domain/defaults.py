"""Evaluation thresholds as named constants. Pure: no domain imports.

Values are proposals; Lars reviews them in the M1 test week (WP-05 blueprint, A1).
The exception is SIDESHORE_MAX_DEG, which follows from the hard rule (A14).
"""

from datetime import timedelta
from typing import Final
from zoneinfo import ZoneInfo

LOCAL_TZ: Final = ZoneInfo("Europe/Amsterdam")  # local time for seasons

DEFAULT_MIN_KN: Final = 12.0  # lower wind limit without a spot default
DEFAULT_MAX_KN: Final = 30.0  # upper wind limit
MIN_LIMIT_SPAN_KN: Final = 5.0  # minimum gap between min and max in default_limits
WIND_BORDERLINE_KN: Final = 2.0  # margin for wind_borderline

GUSTY_RATIO: Final = 1.6  # gust/wind from which an hour is gusty (marginal)
TOO_GUSTY_RATIO: Final = 1.9  # gust/wind from which an hour is too gusty (no_go)
GUST_MIN_DELTA_KN: Final = 8.0  # gust must also exceed the wind by this much

ONSHORE_MAX_DEG: Final = 22.5  # angle from shore normal for onshore (inclusive)
SIDE_ONSHORE_MAX_DEG: Final = 67.5  # upper bound of side_onshore (inclusive)
# Hard rule (CLAUDE.md): any offshore component is no_go. Not configurable, not a proposal.
SIDESHORE_MAX_DEG: Final = 90.0  # upper bound of sideshore (inclusive)
SIDE_OFFSHORE_MAX_DEG: Final = 157.5  # label bound: above this is offshore (both are no_go)

DAYLIGHT_MARGIN_BEFORE_SUNRISE: Final = timedelta(minutes=15)  # hour may start this early
DAYLIGHT_MARGIN_AFTER_SUNSET: Final = timedelta(minutes=15)  # hour may end this late

CONFIDENCE_HIGH_SPEED_SPREAD_KN: Final = 4.0  # max wind spread for high
CONFIDENCE_LOW_SPEED_SPREAD_KN: Final = 8.0  # wind spread above this is low
CONFIDENCE_HIGH_DIR_SPREAD_DEG: Final = 20.0  # max direction deviation for high
CONFIDENCE_LOW_DIR_SPREAD_DEG: Final = 45.0  # direction deviation above this is low
CONFIDENCE_HIGH_MIN_MODELS: Final = 3  # min models with wind (and direction) for high

DIR_MIN_RESULTANT: Final = 0.1  # below this mean vector length there is no direction
DIR_MEAN_DECIMALS: Final = 6  # rounding of the circular mean, only to remove float noise

TIDE_SAMPLE_OFFSET: Final = timedelta(minutes=30)  # tide is sampled mid-hour
TIDE_NEIGHBOUR_WINDOW: Final = timedelta(hours=9)  # search window for nearest high/low water
TIDE_LOW_BAND: Final = 0.3  # relative position <= this is "around low water"
TIDE_HIGH_BAND: Final = 0.7  # relative position >= this is "around high water"
