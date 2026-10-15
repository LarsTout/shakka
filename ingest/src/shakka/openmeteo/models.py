"""Mapping of our model keys to Open-Meteo model ids (see blueprint WP-03, A1)."""

from typing import Final

from shakka.domain.forecast import ModelKey

# The order is fixed: it determines the order of `models=` in the request.
OPEN_METEO_MODELS: Final[dict[ModelKey, str]] = {
    ModelKey.KNMI: "knmi_harmonie_arome_netherlands",
    ModelKey.ICON: "dwd_icon_seamless",
    ModelKey.ECMWF: "ecmwf_ifs",
    ModelKey.GFS: "ncep_gfs_seamless",
}
