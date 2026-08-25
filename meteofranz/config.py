from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Zone:
    name: str
    province: str
    latitude: float
    longitude: float


# Ordine editoriale vincolante: prima il Trentino, poi la Provincia di Bolzano.
ZONES: tuple[Zone, ...] = (
    Zone("TRENTO", "Trentino", 46.0748, 11.1217),
    Zone("ALTO GARDA", "Trentino", 45.8892, 10.8431),
    Zone("GIUDICARIE", "Trentino", 46.0355, 10.7267),
    Zone("VALSUGANA", "Trentino", 46.0520, 11.4561),
    Zone("VAL DI NON", "Trentino", 46.3657, 11.0351),
    Zone("FIEMME", "Trentino", 46.2914, 11.4598),
    Zone("BOLZANO", "Provincia di Bolzano", 46.4983, 11.3548),
    Zone("MERANO", "Provincia di Bolzano", 46.6713, 11.1594),
    Zone("VAL PUSTERIA", "Provincia di Bolzano", 46.7966, 11.9368),
    Zone("VAL VENOSTA", "Provincia di Bolzano", 46.6288, 10.7721),
    Zone("VAL ISARCO", "Provincia di Bolzano", 46.7164, 11.6575),
)

METEOTRENTINO_URL = (
    "https://www.meteotrentino.it/previsioni/"
    "bollettino-meteorologico-ufficiale-per-il-trentino/"
)
BOLZANO_RSS_URL = (
    "https://static-wetter.provinz.bz.it/forecast-data/website/rss/it_southtyrol.xml"
)
BOLZANO_URL = "https://meteo.provincia.bz.it/it/"
ROSS_PACHER_TELEGRAM_URL = "https://t.me/s/rosspach"
ROSS_PACHER_PUBLIC_URL = "https://t.me/rosspach"
ROSS_PACHER_FACEBOOK_URL = "https://www.facebook.com/share/1K3UVf6oTb/"
ROSS_PACHER_RSS_URL = "https://rss.app/feeds/ZoUYFBZngBg7gg2q.xml"
POLETTI_INSTAGRAM_URL = "https://www.instagram.com/giacomo_poletti81/"
POLETTI_RSS_URL = "https://rss.app/feeds/bMzI1xUXAH6xNnf9.xml"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
PROVINCES_GEOJSON_URL = (
    "https://raw.githubusercontent.com/guglielmo/geojson-italy/main/"
    "geojson/limits_IT_provinces.geojson"
)

OUTPUT_DIR = "output"
MAP_PATH = f"{OUTPUT_DIR}/map.png"
HTML_PATH = f"{OUTPUT_DIR}/newsletter.html"
DATA_PATH = f"{OUTPUT_DIR}/data.json"


def public_map_url(date_token: str) -> str:
    default = (
        "https://raw.githubusercontent.com/meteo-franz/meteofranz/main/"
        f"output/map.png?v={date_token}"
    )
    return os.getenv("MAP_PUBLIC_URL") or default


def public_logo_url() -> str:
    default = (
        "https://raw.githubusercontent.com/meteo-franz/meteofranz/main/"
        "assets/meteofranz-logo.png"
    )
    return os.getenv("LOGO_PUBLIC_URL") or default


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name) or default
    if required and not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {name}")
    return value or ""
