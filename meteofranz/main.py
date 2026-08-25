from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from .brevo import create_campaign, send_now
from .config import DATA_PATH, HTML_PATH, MAP_PATH, OUTPUT_DIR, public_map_url
from .editorial import build_edition
from .email_renderer import render_email
from .map_renderer import render_map
from .models import SourceNote
from .sources import fetch_all_sources
from .weather import fetch_zone_forecasts, sample_zone_forecasts


ROME = ZoneInfo("Europe/Rome")


def _sample_sources() -> list[SourceNote]:
    return [
        SourceNote(
            "Meteotrentino",
            "https://www.meteotrentino.it/",
            True,
            title="Variabile con locali rovesci",
            text="Schiarite al mattino e qualche rovescio in montagna nel pomeriggio.",
        ),
        SourceNote(
            "Servizio meteorologico Provincia di Bolzano",
            "https://meteo.provincia.bz.it/it/",
            True,
            title="Sole e nubi",
            text="Tempo a tratti soleggiato con isolati temporali verso sera.",
        ),
        SourceNote("Meteo Rosspach", "https://t.me/rosspach", False),
        SourceNote("Giacomo Poletti", "https://www.instagram.com/giacomo_poletti81/", False),
    ]


def build(*, sample: bool = False) -> dict:
    now = datetime.now(ROME)
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    zones = sample_zone_forecasts(now.date().isoformat()) if sample else fetch_zone_forecasts()
    sources = _sample_sources() if sample else fetch_all_sources()
    for source in sources:
        if source.available:
            print(
                f"Fonte {source.name}: OK; aggiornamento={source.updated_at or 'non indicato'}; "
                f"caratteri={len(source.text)}"
            )
        else:
            print(f"Fonte {source.name}: NON DISPONIBILE; motivo={source.text}")
    edition = build_edition(now.date(), zones, sources)
    render_map(edition.zones, MAP_PATH)
    map_url = public_map_url(edition.date_iso.replace("-", ""))
    render_email(edition, map_url, HTML_PATH)
    data = edition.to_dict()
    data["map_url"] = map_url
    data["official_sources_available"] = sum(
        source.available for source in sources[:2]
    )
    # Il repository è pubblico solo per rendere caricabile la mappa nelle email.
    # Non pubblichiamo il testo integrale raccolto dalle fonti.
    for source in data["sources"]:
        source.pop("text", None)
    Path(DATA_PATH).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Edizione generata: {HTML_PATH}")
    print(f"Mappa generata: {MAP_PATH}")
    return data


def send(*, immediate: bool = False) -> int:
    html_path = Path(HTML_PATH)
    data_path = Path(DATA_PATH)
    if not html_path.exists() or not data_path.exists():
        raise RuntimeError("Prima esegui il comando build")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if int(data.get("official_sources_available", 0)) == 0:
        raise RuntimeError("Invio bloccato: nessuna fonte ufficiale era disponibile")
    html_content = html_path.read_text(encoding="utf-8")
    subject = f"MeteoFranz · {data['date_label']} · {data['phrase']}"
    now = datetime.now(ROME)
    target = datetime.combine(now.date(), time(7, 30), tzinfo=ROME)
    # Se GitHub parte in ritardo, l'edizione odierna viene inviata appena pronta:
    # non viene mai spostata per errore alla mattina successiva.
    schedule = None if immediate or target <= now else target
    campaign_id = create_campaign(
        html_content=html_content, subject=subject, send_at=schedule
    )
    if schedule is None:
        send_now(campaign_id)
        print(f"Campagna {campaign_id} inviata")
    else:
        print(f"Campagna {campaign_id} programmata per {schedule.isoformat()}")
    return campaign_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generatore della newsletter MeteoFranz")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build", help="Genera mappa, dati ed email")
    build_parser.add_argument("--sample", action="store_true", help="Usa dati dimostrativi")
    send_parser = sub.add_parser("send", help="Crea e invia la campagna Brevo")
    send_parser.add_argument("--now", action="store_true", help="Invia subito anziché alle 7:30")
    all_parser = sub.add_parser("all", help="Genera e poi invia")
    all_parser.add_argument("--now", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "build":
        build(sample=args.sample)
    elif args.command == "send":
        send(immediate=args.now)
    elif args.command == "all":
        build(sample=False)
        send(immediate=args.now)


if __name__ == "__main__":
    main()
