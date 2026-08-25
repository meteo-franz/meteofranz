from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import PROVINCES_GEOJSON_URL
from .models import ZoneForecast


WIDTH, HEIGHT = 1200, 1360
BG = "#FFFFFF"
INK = "#17324D"
MUTED = "#5D7488"
TRENTINO = "#81D4A4"
BOLZANO = "#8EC5FF"
ACCENT = "#F3A833"
MAP_SCALE = WIDTH / 620
MAP_TOP = 100


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    choices = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in choices:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _download_geojson() -> dict:
    request = urllib.request.Request(
        PROVINCES_GEOJSON_URL,
        headers={"User-Agent": "MeteoFranz/0.1"},
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)


def _rings(geometry: dict) -> list[list[list[float]]]:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon":
        return [polygon[0] for polygon in geometry["coordinates"]]
    return []


def _province_features() -> list[dict]:
    # Se i confini pubblicati non sono raggiungibili, la generazione si ferma:
    # non viene mai sostituita la cartografia con sagome approssimative.
    payload = _download_geojson()
    chosen = []
    for feature in payload["features"]:
        props = feature["properties"]
        acronym = str(props.get("prov_acr", "")).upper()
        code = int(props.get("prov_istat_code_num") or props.get("prov_istat_code") or 0)
        if acronym in {"TN", "BZ"} or code in {21, 22}:
            chosen.append(feature)
    if len(chosen) != 2:
        raise RuntimeError("Confini delle province di Trento e Bolzano non trovati")
    return chosen


def _projector(features: list[dict]):
    all_points = [
        point
        for feature in features
        for ring in _rings(feature["geometry"])
        for point in ring
    ]
    def mercator_y(latitude: float) -> float:
        radians = math.radians(latitude)
        return math.log(math.tan(math.pi / 4 + radians / 2))

    projected = [(math.radians(point[0]), mercator_y(point[1])) for point in all_points]
    min_lon = min(point[0] for point in projected)
    max_lon = max(point[0] for point in projected)
    min_y = min(point[1] for point in projected)
    max_y = max(point[1] for point in projected)
    # Stesso riquadro proporzionale della mappa approvata (viewBox 620 × 650).
    left = 88 * MAP_SCALE
    top = MAP_TOP + 25 * MAP_SCALE
    right = 532 * MAP_SCALE
    bottom = MAP_TOP + 618 * MAP_SCALE
    scale = min((right - left) / (max_lon - min_lon), (bottom - top) / (max_y - min_y))
    used_w = (max_lon - min_lon) * scale
    used_h = (max_y - min_y) * scale
    offset_x = left + ((right - left) - used_w) / 2
    offset_y = top + ((bottom - top) - used_h) / 2

    def project(lon: float, lat: float) -> tuple[int, int]:
        x = offset_x + (math.radians(lon) - min_lon) * scale
        y = offset_y + (max_y - mercator_y(lat)) * scale
        return round(x), round(y)

    return project


def _weather_group(code: int) -> str:
    if code == 0:
        return "sun"
    if code in {1, 2}:
        return "partly"
    if code == 3:
        return "cloud"
    if code in {45, 48}:
        return "fog"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {95, 96, 99}:
        return "storm"
    return "rain"


def _draw_sun(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int = 10) -> None:
    for angle in range(0, 360, 45):
        radians = math.radians(angle)
        x1 = cx + math.cos(radians) * (radius + 4)
        y1 = cy + math.sin(radians) * (radius + 4)
        x2 = cx + math.cos(radians) * (radius + 9)
        y2 = cy + math.sin(radians) * (radius + 9)
        draw.line((x1, y1, x2, y2), fill="#F0A11A", width=3)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill="#FFD45A")


def _draw_cloud(draw: ImageDraw.ImageDraw, cx: int, cy: int, color: str = "#B9C7D5") -> None:
    draw.ellipse((cx - 18, cy - 3, cx + 19, cy + 15), fill=color)
    draw.ellipse((cx - 14, cy - 13, cx + 5, cy + 10), fill=color)
    draw.ellipse((cx - 2, cy - 17, cx + 18, cy + 11), fill=color)


def _draw_weather_icon(draw: ImageDraw.ImageDraw, x: int, y: int, code: int) -> None:
    group = _weather_group(code)
    if group in {"sun", "partly"}:
        _draw_sun(draw, x - (6 if group == "partly" else 0), y - 3, 10)
    if group in {"partly", "cloud", "rain", "storm", "snow", "fog"}:
        _draw_cloud(draw, x + (6 if group == "partly" else 0), y + 3)
    if group == "rain":
        for dx in (-11, 0, 11):
            draw.line((x + dx, y + 17, x + dx - 3, y + 25), fill="#348BD1", width=3)
    elif group == "storm":
        draw.polygon(
            ((x + 1, y + 14), (x - 7, y + 29), (x + 1, y + 27), (x - 2, y + 39), (x + 13, y + 21), (x + 5, y + 23)),
            fill="#F4B323",
        )
    elif group == "snow":
        for dx in (-10, 4, 16):
            draw.text((x + dx, y + 15), "*", fill="#469BD7", font=_font(19, True), anchor="mm")
    elif group == "fog":
        for dy in (16, 23, 30):
            draw.line((x - 17, y + dy, x + 18, y + dy), fill="#94A7B7", width=3)


LABEL_OFFSETS = {
    "TRENTO": (42, -5),
    "ALTO GARDA": (-56, 15),
    "GIUDICARIE": (-58, 12),
    "VALSUGANA": (86, 25),
    "VAL DI NON": (-55, -2),
    "FIEMME": (60, -4),
    "BOLZANO": (54, 10),
    "MERANO": (0, -28),
    "VAL PUSTERIA": (64, -5),
    "VAL VENOSTA": (-56, -5),
    "VAL ISARCO": (15, -45),
}

MAP_POINTS = {
    "TRENTO": (11.12, 46.07),
    "ALTO GARDA": (10.86, 45.90),
    "GIUDICARIE": (10.72, 46.08),
    "VALSUGANA": (11.45, 46.05),
    "VAL DI NON": (11.00, 46.36),
    "FIEMME": (11.46, 46.29),
    "BOLZANO": (11.35, 46.50),
    "MERANO": (11.16, 46.67),
    "VAL PUSTERIA": (11.94, 46.80),
    "VAL VENOSTA": (10.77, 46.63),
    "VAL ISARCO": (11.58, 46.77),
}


def _rounded_box(draw: ImageDraw.ImageDraw, xy, fill: str, outline: str) -> None:
    draw.rounded_rectangle(xy, radius=24, fill=fill, outline=outline, width=3)


def render_map(zones: list[ZoneForecast], output_path: str) -> None:
    features = _province_features()
    project = _projector(features)
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    # Legenda verticale, con il Trentino sempre per primo.
    legend_font = _font(24, True)
    draw.rounded_rectangle((38, 23, 62, 47), radius=5, fill=TRENTINO, outline=INK, width=2)
    draw.text((76, 22), "Provincia di Trento", font=legend_font, fill=INK)
    draw.rounded_rectangle((38, 61, 62, 85), radius=5, fill=BOLZANO, outline=INK, width=2)
    draw.text((76, 60), "Provincia di Bolzano / Sudtirolo", font=legend_font, fill=INK)

    for feature in features:
        props = feature["properties"]
        acronym = str(props.get("prov_acr", "")).upper()
        code = int(props.get("prov_istat_code_num") or props.get("prov_istat_code") or 0)
        color = TRENTINO if acronym == "TN" or code == 22 else BOLZANO
        for ring in _rings(feature["geometry"]):
            points = [project(point[0], point[1]) for point in ring]
            draw.polygon(points, fill=color, outline=INK, width=4)

    for zone in zones:
        longitude, latitude = MAP_POINTS[zone.name]
        point_x, point_y = project(longitude, latitude)
        offset_x, offset_y = LABEL_OFFSETS[zone.name]
        center_x = point_x + round(offset_x * MAP_SCALE)
        center_y = point_y + round(offset_y * MAP_SCALE)
        box_w = round(112 * MAP_SCALE)
        box_h = round(48 * MAP_SCALE)
        box_x = max(10, min(WIDTH - box_w - 10, center_x - box_w // 2))
        box_y = max(10, min(HEIGHT - box_h - 10, center_y - box_h // 2))
        draw.ellipse((point_x - 6, point_y - 6, point_x + 6, point_y + 6), fill=INK, outline="#FFFFFF", width=3)

        fill = "#F6FCF8" if zone.province == "Trentino" else "#F5F9FE"
        outline = "#79C99A" if zone.province == "Trentino" else "#7BB7ED"
        _rounded_box(draw, (box_x, box_y, box_x + box_w, box_y + box_h), fill, outline)
        draw.text((box_x + 14, box_y + 9), zone.name, font=_font(20, True), fill=INK)
        _draw_weather_icon(draw, box_x + 29, box_y + 49, zone.days[0].weather_code)
        day = zone.days[0]
        draw.text(
            (box_x + 55, box_y + 42),
            f"{day.temp_max} °C  ·  {day.precipitation_probability}%",
            font=_font(21),
            fill=MUTED,
        )

    image.save(output_path, "PNG", optimize=True)


def render_logo(output_path: str) -> None:
    size = 256
    image = Image.new("RGB", (size, size), INK)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=52, fill=INK)
    draw.ellipse((169, 34, 233, 98), fill="#F4BD3E")
    draw.polygon(((38, 194), (102, 102), (143, 154), (175, 117), (226, 194)), fill="#FFFFFF")
    draw.polygon(((38, 194), (102, 102), (124, 134), (98, 126), (68, 169)), fill="#69B7D5")
    draw.line((51, 215, 96, 202, 143, 215, 188, 224, 235, 215), fill="#69B7D5", width=15, joint="curve")
    image.save(output_path, "PNG", optimize=True)
