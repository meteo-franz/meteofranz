from __future__ import annotations

import json
import urllib.parse
import urllib.request

from .config import OPEN_METEO_URL, ZONES
from .models import DailyForecast, ZoneForecast


USER_AGENT = "MeteoFranz/0.1 (+https://github.com/meteo-franz/meteofranz)"


def _get_json(url: str, timeout: int = 30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_zone_forecasts() -> list[ZoneForecast]:
    params = {
        "latitude": ",".join(str(zone.latitude) for zone in ZONES),
        "longitude": ",".join(str(zone.longitude) for zone in ZONES),
        "daily": ",".join(
            (
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "wind_gusts_10m_max",
            )
        ),
        "timezone": "Europe/Rome",
        "forecast_days": "3",
    }
    payload = _get_json(f"{OPEN_METEO_URL}?{urllib.parse.urlencode(params)}")
    if not isinstance(payload, list) or len(payload) != len(ZONES):
        raise RuntimeError("Risposta Open-Meteo inattesa per le 11 zone")

    forecasts: list[ZoneForecast] = []
    for zone, item in zip(ZONES, payload, strict=True):
        daily = item["daily"]
        days: list[DailyForecast] = []
        for index, date in enumerate(daily["time"]):
            days.append(
                DailyForecast(
                    date=date,
                    weather_code=int(daily["weather_code"][index]),
                    temp_min=round(daily["temperature_2m_min"][index]),
                    temp_max=round(daily["temperature_2m_max"][index]),
                    precipitation_probability=round(
                        daily["precipitation_probability_max"][index] or 0
                    ),
                    wind_gust=round(daily["wind_gusts_10m_max"][index] or 0),
                )
            )
        forecasts.append(
            ZoneForecast(
                name=zone.name,
                province=zone.province,
                latitude=zone.latitude,
                longitude=zone.longitude,
                days=days,
            )
        )
    return forecasts


def sample_zone_forecasts(date_iso: str) -> list[ZoneForecast]:
    """Dati deterministici per test grafici: non vengono usati negli invii reali."""
    codes = [2, 2, 61, 3, 2, 80, 1, 2, 80, 1, 2]
    maxima = [27, 28, 24, 26, 25, 23, 28, 27, 24, 26, 25]
    forecasts: list[ZoneForecast] = []
    for index, zone in enumerate(ZONES):
        days = [
            DailyForecast(date_iso, codes[index], maxima[index] - 10, maxima[index], 35, 28),
            DailyForecast(date_iso, 2, maxima[index] - 11, maxima[index] + 1, 20, 24),
            DailyForecast(date_iso, 95 if index % 4 == 0 else 3, maxima[index] - 9, maxima[index], 55, 38),
        ]
        forecasts.append(
            ZoneForecast(zone.name, zone.province, zone.latitude, zone.longitude, days)
        )
    return forecasts


def weather_symbol(code: int) -> str:
    if code == 0:
        return "☀️"
    if code in {1, 2}:
        return "🌤️"
    if code == 3:
        return "☁️"
    if code in {45, 48}:
        return "🌫️"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "🌧️"
    if code in {71, 73, 75, 77, 85, 86}:
        return "🌨️"
    if code in {95, 96, 99}:
        return "⛈️"
    return "🌥️"


def weather_label(code: int) -> str:
    if code == 0:
        return "sereno"
    if code in {1, 2}:
        return "in prevalenza soleggiato"
    if code == 3:
        return "molto nuvoloso"
    if code in {45, 48}:
        return "nebbie o nubi basse"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67}:
        return "piogge"
    if code in {71, 73, 75, 77, 85, 86}:
        return "neve"
    if code in {80, 81, 82}:
        return "rovesci"
    if code in {95, 96, 99}:
        return "temporali"
    return "variabile"
