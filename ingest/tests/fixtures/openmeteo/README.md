# Open-Meteo fixtures

Weather data by Open-Meteo.com (https://open-meteo.com/), licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

The JSON files are unmodified API responses, recorded for tests only.

forecast_2loc_4models.json: recorded on 2026-10-28 from https://api.open-meteo.com/v1/forecast?latitude=52.4700,52.1000&longitude=4.5700,4.2700&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m&models=knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless&wind_speed_unit=kn&timezone=GMT&timeformat=unixtime&forecast_days=8&cell_selection=sea

Wave data in marine_3loc_2models.json: DWD (EWAM) and ECMWF (WAM) via Open-Meteo.

marine_3loc_2models.json: recorded on 2026-10-15 from https://marine-api.open-meteo.com/v1/marine?latitude=52.4700,52.7500,52.0900&longitude=4.5700,5.3000,5.1200&hourly=wave_height,wave_period,wave_direction&models=ewam,ecmwf_wam&timezone=GMT&timeformat=unixtime&forecast_days=7&cell_selection=sea
