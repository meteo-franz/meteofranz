from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class DailyForecast:
    date: str
    weather_code: int
    temp_min: int
    temp_max: int
    precipitation_probability: int
    wind_gust: int


@dataclass
class ZoneForecast:
    name: str
    province: str
    latitude: float
    longitude: float
    days: list[DailyForecast]


@dataclass
class SourceNote:
    name: str
    url: str
    available: bool
    updated_at: str = ""
    title: str = ""
    text: str = ""


@dataclass
class QuickCard:
    label: str
    value: str
    text: str


@dataclass
class WatchItem:
    label: str
    text: str


@dataclass
class Edition:
    date_iso: str
    date_label: str
    phrase: str
    deck: str
    confidence: str
    thirty_seconds: str
    quick_cards: list[QuickCard]
    map_trentino_note: str
    map_bolzano_note: str
    trentino_numbers: str
    bolzano_numbers: str
    trentino_paragraphs: list[str]
    bolzano_paragraphs: list[str]
    trentino_summary: str
    bolzano_summary: str
    watch_items: list[WatchItem]
    zones: list[ZoneForecast]
    sources: list[SourceNote]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
