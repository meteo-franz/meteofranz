from __future__ import annotations

import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from .config import (
    BOLZANO_RSS_URL,
    BOLZANO_URL,
    METEOTRENTINO_URL,
    POLETTI_INSTAGRAM_URL,
    POLETTI_RSS_URL,
    ROSS_PACHER_PUBLIC_URL,
    ROSS_PACHER_RSS_URL,
    ROSS_PACHER_TELEGRAM_URL,
)
from .models import SourceNote


USER_AGENT = "Mozilla/5.0 (compatible; MeteoFranz/0.1; personal weather newsletter)"
ROME = ZoneInfo("Europe/Rome")


def sanitize(text: str) -> str:
    text = html.unescape(re.sub(r"\s+", " ", text or "")).strip()
    return re.sub(r"\bAlto\s+Adige\b", "Sudtirolo", text, flags=re.IGNORECASE)


def _fetch(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "it-IT,it;q=0.9"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "svg", "nav", "footer"}:
            self._ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "nav", "footer"} and self._ignored:
            self._ignored -= 1
        if not self._ignored and tag in {"p", "h1", "h2", "h3", "h4", "li", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored and data.strip():
            self.parts.append(data.strip())

    def lines(self) -> list[str]:
        text = " ".join(self.parts).replace(" \n ", "\n")
        return [sanitize(line) for line in text.splitlines() if sanitize(line)]


def _visible_lines(raw: bytes) -> list[str]:
    parser = VisibleTextParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return parser.lines()


def fetch_meteotrentino() -> SourceNote:
    try:
        lines = _visible_lines(_fetch(METEOTRENTINO_URL))
        forecast_index = next(
            i for i, line in enumerate(lines) if line.startswith("Previsioni del ")
        )
        update = lines[forecast_index].removeprefix("Previsioni del ")
        candidates = lines[forecast_index + 1 : forecast_index + 30]
        sentences = [
            line
            for line in candidates
            if len(line) > 65
            and not line.startswith("Scarica")
            and "Informazione importante" not in line
        ]
        if not sentences:
            raise ValueError("Testo del bollettino non individuato")
        return SourceNote(
            name="Meteotrentino",
            url=METEOTRENTINO_URL,
            available=True,
            updated_at=update,
            title="Bollettino meteorologico ufficiale",
            text=sanitize(" ".join(sentences[:2])),
        )
    except Exception as exc:
        return SourceNote(
            name="Meteotrentino",
            url=METEOTRENTINO_URL,
            available=False,
            text=f"Fonte non disponibile: {type(exc).__name__}",
        )


def _xml_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return sanitize(" ".join(element.itertext()))


def _strip_markup(text: str) -> str:
    if not text:
        return ""
    parser = VisibleTextParser()
    parser.feed(html.unescape(text))
    visible = sanitize(" ".join(parser.lines()))
    return visible or sanitize(re.sub(r"<[^>]+>", " ", text))


def _child_by_local_name(element: ET.Element, *names: str) -> ET.Element | None:
    wanted = set(names)
    return next(
        (
            child
            for child in element
            if child.tag.rsplit("}", 1)[-1] in wanted
        ),
        None,
    )


def _parse_feed_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ROME)
    return parsed.astimezone(ROME)


def fetch_bolzano_rss() -> SourceNote:
    try:
        root = ET.fromstring(_fetch(BOLZANO_RSS_URL))
        item = root.find("./channel/item")
        if item is None:
            raise ValueError("RSS privo di elementi")
        title = _xml_text(item.find("title"))
        description = _xml_text(item.find("description"))
        published = _xml_text(item.find("pubDate"))
        if not description:
            raise ValueError("RSS privo di descrizione")
        return SourceNote(
            name="Servizio meteorologico Provincia di Bolzano",
            url=BOLZANO_URL,
            available=True,
            updated_at=published,
            title=title,
            text=description,
        )
    except Exception as exc:
        return SourceNote(
            name="Servizio meteorologico Provincia di Bolzano",
            url=BOLZANO_URL,
            available=False,
            text=f"Fonte non disponibile: {type(exc).__name__}",
        )


class TelegramParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[dict[str, str]] = []
        self._in_text = False
        self._depth = 0
        self._current_text: list[str] = []
        self._latest_time = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if tag == "time" and attributes.get("datetime"):
            self._latest_time = attributes["datetime"]
        if "tgme_widget_message_text" in classes:
            self._in_text = True
            self._depth = 1
            self._current_text = []
        elif self._in_text:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._in_text:
            self._depth -= 1
            if self._depth == 0:
                self.messages.append(
                    {"text": sanitize(" ".join(self._current_text)), "time": self._latest_time}
                )
                self._in_text = False

    def handle_data(self, data: str) -> None:
        if self._in_text and data.strip():
            self._current_text.append(data.strip())


def _fetch_ross_pacher_telegram() -> SourceNote:
    try:
        parser = TelegramParser()
        parser.feed(_fetch(ROSS_PACHER_TELEGRAM_URL).decode("utf-8", errors="replace"))
        if not parser.messages:
            raise ValueError("Nessun post pubblico individuato")
        latest = parser.messages[-1]
        timestamp = latest["time"]
        if timestamp:
            post_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(ROME)
            if datetime.now(ROME) - post_time > timedelta(hours=48):
                raise ValueError("Ultimo post più vecchio di 48 ore")
        text = latest["text"]
        if len(text) < 25:
            raise ValueError("Post privo di testo meteorologico verificabile")
        return SourceNote(
            name="Meteo Rosspach",
            url=ROSS_PACHER_PUBLIC_URL,
            available=True,
            updated_at=timestamp,
            title="Ultimo aggiornamento pubblico",
            text=text[:900],
        )
    except Exception as exc:
        return SourceNote(
            name="Meteo Rosspach",
            url=ROSS_PACHER_PUBLIC_URL,
            available=False,
            text=f"Nessun contributo pubblico recente verificabile: {type(exc).__name__}",
        )


def _fetch_recent_social_rss(
    *,
    name: str,
    feed_url: str,
    fallback_url: str,
    now: datetime | None = None,
    max_chars: int = 1200,
) -> SourceNote:
    try:
        root = ET.fromstring(_fetch(feed_url))
        items = root.findall("./channel/item")
        if not items:
            items = [
                element
                for element in root.iter()
                if element.tag.rsplit("}", 1)[-1] in {"item", "entry"}
            ]
        if not items:
            raise ValueError("Feed RSS privo di elementi")

        candidates: list[tuple[datetime, ET.Element, str]] = []
        for item in items:
            date_element = _child_by_local_name(item, "pubDate", "published", "updated")
            published = _xml_text(date_element)
            published_at = _parse_feed_time(published)
            if published_at is not None:
                candidates.append((published_at, item, published))
        if not candidates:
            raise ValueError("Feed RSS privo di date verificabili")

        published_at, item, published = max(candidates, key=lambda candidate: candidate[0])
        current = (now or datetime.now(ROME)).astimezone(ROME)
        if current - published_at > timedelta(hours=48):
            raise ValueError("Ultimo post più vecchio di 48 ore")

        title = _xml_text(_child_by_local_name(item, "title"))
        content_element = _child_by_local_name(item, "description", "encoded", "content", "summary")
        content = _strip_markup(_xml_text(content_element))
        text = content or title
        if len(text) < 25:
            raise ValueError("Post privo di testo meteorologico verificabile")

        link_element = _child_by_local_name(item, "link")
        link = _xml_text(link_element) if link_element is not None else ""
        if link_element is not None and not link:
            link = sanitize(link_element.attrib.get("href", ""))
        if not link.startswith("http"):
            link = fallback_url

        return SourceNote(
            name=name,
            url=link,
            available=True,
            updated_at=published,
            title=title or "Ultimo aggiornamento pubblico",
            text=text[:max_chars],
        )
    except Exception as exc:
        return SourceNote(
            name=name,
            url=fallback_url,
            available=False,
            text=f"Nessun contributo pubblico recente verificabile: {type(exc).__name__}",
        )


def fetch_ross_pacher(now: datetime | None = None) -> SourceNote:
    """Usa il feed RSS concordato; Telegram resta una riserva."""
    source = _fetch_recent_social_rss(
        name="Meteo Rosspach",
        feed_url=ROSS_PACHER_RSS_URL,
        fallback_url=ROSS_PACHER_PUBLIC_URL,
        now=now,
        max_chars=1200,
    )
    if source.available:
        return source
    telegram_source = _fetch_ross_pacher_telegram()
    return telegram_source if telegram_source.available else source


def fetch_poletti_rss(now: datetime | None = None) -> SourceNote:
    """Legge il feed RSS.app concordato e usa soltanto contributi recenti."""
    return _fetch_recent_social_rss(
        name="Giacomo Poletti",
        feed_url=POLETTI_RSS_URL,
        fallback_url=POLETTI_INSTAGRAM_URL,
        now=now,
        max_chars=1200,
    )


def fetch_all_sources() -> list[SourceNote]:
    return [
        fetch_meteotrentino(),
        fetch_bolzano_rss(),
        fetch_ross_pacher(),
        fetch_poletti_rss(),
    ]
