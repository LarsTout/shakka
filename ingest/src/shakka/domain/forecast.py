"""Forecast value types shared by the ingest (WP-03) and the evaluation (WP-05). Pure."""

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelKey(StrEnum):
    KNMI = "knmi"
    ICON = "icon"
    ECMWF = "ecmwf"
    GFS = "gfs"


class SpotLocation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    spot_id: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)


class ForecastHour(BaseModel):
    """One model's wind forecast for the hour [valid_at, valid_at + 1h), UTC.

    wind_kn and dir_deg are instantaneous values at valid_at (Open-Meteo "Instant").
    gust_kn is the maximum gust within [valid_at, valid_at + 1h). Open-Meteo labels
    wind_gusts_10m "Preceding hour max", so the parser stores the raw gust of timestamp
    valid_at + 1h here. The last hour of a response therefore has gust_kn = None.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    spot_id: str = Field(min_length=1)
    model: ModelKey
    valid_at: datetime
    wind_kn: float | None = Field(ge=0, allow_inf_nan=False)  # knots
    gust_kn: float | None = Field(ge=0, allow_inf_nan=False)  # knots
    dir_deg: int | None = Field(ge=0, le=359)  # meteorological "from"

    @field_validator("valid_at")
    @classmethod
    def _whole_utc_hour(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("valid_at must be timezone-aware")
        value = value.astimezone(UTC)
        if value.minute or value.second or value.microsecond:
            raise ValueError("valid_at must be a whole hour")
        return value

    def to_row(self, *, fetched_at: datetime) -> dict[str, Any]:
        """Row for public.forecast_hours. Keys exactly: spot_id, model (str value), valid_at,
        wind_kn, gust_kn, dir_deg, fetched_at. fetched_at must be aware (ValueError otherwise)."""
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        return {
            "spot_id": self.spot_id,
            "model": self.model.value,
            "valid_at": self.valid_at,
            "wind_kn": self.wind_kn,
            "gust_kn": self.gust_kn,
            "dir_deg": self.dir_deg,
            "fetched_at": fetched_at,
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Self:
        """Inverse of to_row; valid_at may be a str (datetime.fromisoformat) or a datetime.
        fetched_at and unknown keys are ignored."""
        valid_at = row["valid_at"]
        if isinstance(valid_at, str):
            valid_at = datetime.fromisoformat(valid_at)
        return cls(
            spot_id=row["spot_id"],
            model=ModelKey(row["model"]),
            valid_at=valid_at,
            wind_kn=row["wind_kn"],
            gust_kn=row["gust_kn"],
            dir_deg=row["dir_deg"],
        )
