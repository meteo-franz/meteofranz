from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from meteofranz.config import POLETTI_RSS_URL, ROSS_PACHER_RSS_URL
from meteofranz.editorial import build_edition
from meteofranz.email_renderer import render_email
from meteofranz.main import _sample_sources
from meteofranz.map_renderer import _province_features
from meteofranz.models import SourceNote
from meteofranz.sources import fetch_poletti_rss, fetch_ross_pacher
from meteofranz.weather import sample_zone_forecasts


class MeteoFranzTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["METEOFRANZ_OFFLINE"] = "1"
        self.day = date(2026, 8, 25)
        self.zones = sample_zone_forecasts(self.day.isoformat())
        self.edition = build_edition(self.day, self.zones, _sample_sources())

    def test_exact_zone_order(self) -> None:
        self.assertEqual(
            [zone.name for zone in self.zones],
            [
                "TRENTO", "ALTO GARDA", "GIUDICARIE", "VALSUGANA",
                "VAL DI NON", "FIEMME", "BOLZANO", "MERANO",
                "VAL PUSTERIA", "VAL VENOSTA", "VAL ISARCO",
            ],
        )

    def test_trentino_is_always_first_in_email(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "newsletter.html"
            html = render_email(self.edition, "https://example.test/map.png", str(output))
        self.assertLess(
            html.find(">Provincia di Trento</div>"),
            html.find(">Provincia di Bolzano / Sudtirolo</div>"),
        )

    def test_editorial_vocabulary_and_footer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "newsletter.html"
            html = render_email(self.edition, "https://example.test/map.png", str(output))
        forbidden = "alto" + " " + "adige"
        self.assertNotIn(forbidden, html.lower())
        self.assertIn("{{ unsubscribe }}", html)
        self.assertIn("Giudicarie", html)

    def test_poletti_uses_only_the_approved_recent_rss_feed(self) -> None:
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><item>
          <title>Aggiornamento meteo di Giacomo Poletti</title>
          <link>https://www.instagram.com/p/example/</link>
          <description><![CDATA[<p>Domani schiarite al mattino, poi possibili rovesci sulle montagne nel pomeriggio.</p>]]></description>
          <pubDate>Tue, 25 Aug 2026 05:10:00 GMT</pubDate>
        </item></channel></rss>"""
        now = datetime(2026, 8, 25, 7, 25, tzinfo=ZoneInfo("Europe/Rome"))
        with patch("meteofranz.sources._fetch", return_value=xml) as mocked_fetch:
            source = fetch_poletti_rss(now=now)
        mocked_fetch.assert_called_once_with(POLETTI_RSS_URL)
        self.assertTrue(source.available)
        self.assertIn("possibili rovesci", source.text)
        self.assertEqual(source.url, "https://www.instagram.com/p/example/")

    def test_poletti_rejects_stale_posts(self) -> None:
        xml = b"""<rss version="2.0"><channel><item>
          <title>Vecchio aggiornamento meteorologico non piu recente</title>
          <description>Previsione ormai superata e non utilizzabile per l'edizione odierna.</description>
          <pubDate>Sat, 22 Aug 2026 05:10:00 GMT</pubDate>
        </item></channel></rss>"""
        now = datetime(2026, 8, 25, 7, 25, tzinfo=ZoneInfo("Europe/Rome"))
        with patch("meteofranz.sources._fetch", return_value=xml):
            source = fetch_poletti_rss(now=now)
        self.assertFalse(source.available)

    def test_poletti_reads_multiple_recent_instagram_captions(self) -> None:
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
        <item>
          <title>Nuovo post Instagram</title>
          <link>https://www.instagram.com/p/new/</link>
          <media:content url="https://example.test/new.jpg">
            <media:description>Stamattina piogge in esaurimento; nel pomeriggio schiarite diffuse nelle valli.</media:description>
          </media:content>
          <pubDate>Tue, 25 Aug 2026 05:40:00 GMT</pubDate>
        </item>
        <item>
          <title>Post della sera precedente</title>
          <link>https://www.instagram.com/p/previous/</link>
          <description><![CDATA[Domani torna il sole, con temperature in aumento e vento debole in montagna.]]></description>
          <pubDate>Mon, 24 Aug 2026 19:20:00 GMT</pubDate>
        </item>
        </channel></rss>"""
        now = datetime(2026, 8, 25, 7, 25, tzinfo=ZoneInfo("Europe/Rome"))
        with patch("meteofranz.sources._fetch", return_value=xml):
            source = fetch_poletti_rss(now=now)
        self.assertTrue(source.available)
        self.assertIn("piogge in esaurimento", source.text)
        self.assertIn("temperature in aumento", source.text)
        self.assertEqual(source.url, "https://www.instagram.com/p/new/")

    def test_poletti_and_rosspach_have_equal_named_editorial_weight(self) -> None:
        sources = _sample_sources()
        sources[2] = SourceNote(
            "Meteo Rosspach",
            "https://t.me/rosspach/999",
            True,
            "Tue, 25 Aug 2026 05:05:00 GMT",
            "Aggiornamento mattutino",
            "Nuvolosita irregolare e possibili rovesci nel pomeriggio, poi vento da nord.",
        )
        sources[3] = SourceNote(
            "Giacomo Poletti",
            "https://www.instagram.com/p/example/",
            True,
            "Tue, 25 Aug 2026 05:10:00 GMT",
            "Previsione del giorno",
            "Piogge al mattino, poi schiarite ampie e temperature in ripresa nel pomeriggio.",
        )
        edition = build_edition(self.day, self.zones, sources)
        self.assertTrue(any("Il punto di Giacomo Poletti" in item for item in edition.trentino_paragraphs))
        self.assertTrue(any("Il punto di Meteo Rosspach" in item for item in edition.bolzano_paragraphs))
        self.assertIn("Giacomo Poletti", edition.thirty_seconds)
        self.assertIn("Meteo Rosspach", edition.thirty_seconds)

    def test_rosspach_uses_the_approved_recent_rss_feed_first(self) -> None:
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><item>
          <title>Aggiornamento Meteo Rosspach</title>
          <link>https://t.me/rosspach/999</link>
          <description><![CDATA[<p>Fronte in transito con piogge sparse e rinforzo del vento da nord.</p>]]></description>
          <pubDate>Tue, 25 Aug 2026 05:05:00 GMT</pubDate>
        </item></channel></rss>"""
        now = datetime(2026, 8, 25, 7, 25, tzinfo=ZoneInfo("Europe/Rome"))
        with patch("meteofranz.sources._fetch", return_value=xml) as mocked_fetch:
            source = fetch_ross_pacher(now=now)
        mocked_fetch.assert_called_once_with(ROSS_PACHER_RSS_URL)
        self.assertTrue(source.available)
        self.assertEqual(source.name, "Meteo Rosspach")
        self.assertIn("rinforzo del vento", source.text)

    def test_map_never_falls_back_to_invented_outlines(self) -> None:
        with patch(
            "meteofranz.map_renderer._download_geojson",
            side_effect=OSError("dataset non disponibile"),
        ):
            with self.assertRaises(OSError):
                _province_features()


if __name__ == "__main__":
    unittest.main()
