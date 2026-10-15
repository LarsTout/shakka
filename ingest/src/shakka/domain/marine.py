"""Wave forecast value type (WP-12). Display only: never used in evaluations or alerts. Pure."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MarineHour(BaseModel):
    """Wave forecast for the hour [valid_at, valid_at + 1h), UTC.

    All values are instantaneous at valid_at (Open-Meteo Marine "Instant"). wave_dir_deg is the
    direction the waves come from (0 = north), like wind direction. At least one value is set.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    spot_id: str = Field(min_length=1)
    valid_at: datetime
    wave_height_m: float | None = Field(ge=0, allow_inf_nan=False)  # metres
    wave_period_s: float | None = Field(ge=0, allow_inf_nan=False)  # seconds
    wave_dir_deg: int | None = Field(ge=0, le=359)

    @field_validator("valid_at")
    @classmethod
    def _whole_utc_hour(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("valid_at must be timezone-aware")
        value = value.astimezone(UTC)
        if value.minute or value.second or value.microsecond:
            raise ValueError("valid_at must be a whole hour")
        return value

    @model_validator(mode="after")
    def _has_value(self) -> Self:
        if self.wave_height_m is None and self.wave_period_s is None and self.wave_dir_deg is None:
            raise ValueError("at least one wave value is required")
        return self

    def to_row(self, *, fetched_at: datetime) -> dict[str, Any]:
        """Row for public.marine_hours. Keys exactly: spot_id, valid_at, wave_height_m,
        wave_period_s, wave_dir_deg, fetched_at. fetched_at must be aware (ValueError otherwise)."""
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        return {
            "spot_id": self.spot_id,
            "valid_at": self.valid_at,
            "wave_height_m": self.wave_height_m,
            "wave_period_s": self.wave_period_s,
            "wave_dir_deg": self.wave_dir_deg,
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
            valid_at=valid_at,
            wave_height_m=row["wave_height_m"],
            wave_period_s=row["wave_period_s"],
            wave_dir_deg=row["wave_dir_deg"],
        )
