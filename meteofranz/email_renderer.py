from __future__ import annotations

from html import escape
from pathlib import Path

from .config import public_logo_url
from .models import Edition
from .sources import sanitize


INK = "#17324d"
TEXT = "#304b60"
MUTED = "#6e8190"
ORANGE = "#ef9f23"
GREEN = "#44a36f"
BLUE = "#4a91cf"


def _quick_cards(edition: Edition) -> str:
    colors = ("#fff6dc", "#eef8ff", "#effaf3")
    accents = (ORANGE, BLUE, GREEN)
    cells: list[str] = []
    for card, color, accent in zip(edition.quick_cards, colors, accents, strict=True):
        cells.append(
            '<td width="33.33%" valign="top" style="padding:5px">'
            f'<table role="presentation" width="100%" style="background:{color};'
            f'border-top:5px solid {accent};border-radius:13px"><tr><td style="padding:16px 14px">'
            f'<div style="font:700 12px Arial,sans-serif;color:{MUTED};text-transform:uppercase;'
            f'letter-spacing:.6px">{escape(card.label)}</div>'
            f'<div style="font:800 17px/1.25 Arial,sans-serif;color:{INK};margin-top:7px">'
            f'{escape(card.value)}</div>'
            f'<div style="font:13px/1.45 Arial,sans-serif;color:{TEXT};margin-top:7px">'
            f'{escape(card.text)}</div></td></tr></table></td>'
        )
    return "".join(cells)


def _province_notes(edition: Edition) -> str:
    return f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0">
  <tr><td style="padding:12px 0 12px 16px;border-left:5px solid {GREEN}">
    <div style="font:800 15px Arial,sans-serif;color:{INK}">Provincia di Trento</div>
    <div style="font:14px/1.55 Arial,sans-serif;color:{TEXT};margin-top:5px">{escape(edition.map_trentino_note)}</div>
  </td></tr>
  <tr><td style="padding:12px 0 12px 16px;border-left:5px solid {BLUE}">
    <div style="font:800 15px Arial,sans-serif;color:{INK}">Provincia di Bolzano / Sudtirolo</div>
    <div style="font:14px/1.55 Arial,sans-serif;color:{TEXT};margin-top:5px">{escape(edition.map_bolzano_note)}</div>
  </td></tr>
</table>"""


def _province_block(
    *, title: str, numbers: str, paragraphs: list[str], color: str
) -> str:
    body = "".join(
        f'<p style="margin:11px 0 0;font:15px/1.65 Arial,sans-serif;color:{TEXT}">'
        f'{escape(paragraph)}</p>'
        for paragraph in paragraphs
    )
    return f"""
<table role="presentation" width="100%" style="border-top:4px solid {color}"><tr><td style="padding:18px 0 8px">
  <div style="font:800 19px Arial,sans-serif;color:{INK}">{escape(title)}</div>
  <div style="font:700 13px/1.55 Arial,sans-serif;color:{color};margin-top:7px">{escape(numbers)}</div>
  {body}
</td></tr></table>"""


def _watch_items(edition: Edition) -> str:
    rows: list[str] = []
    for item in edition.watch_items:
        rows.append(
            '<tr><td width="92" valign="top" style="padding:13px 14px 13px 0;'
            f'font:800 15px Arial,sans-serif;color:{ORANGE};border-bottom:1px solid #dfe8ee">'
            f'{escape(item.label)}</td><td valign="top" style="padding:13px 0;'
            f'font:15px/1.6 Arial,sans-serif;color:{TEXT};border-bottom:1px solid #dfe8ee">'
            f'{escape(item.text)}</td></tr>'
        )
    return "".join(rows)


def _source_rows(edition: Edition) -> str:
    rows: list[str] = []
    for source in edition.sources:
        status = "consultata" if source.available else "nessun aggiornamento pubblico recente verificabile"
        color = "#337a55" if source.available else "#7f8d98"
        rows.append(
            '<tr><td style="padding:5px 0;font:13px/1.45 Arial,sans-serif;color:#5c7182">'
            f'<a href="{escape(source.url, quote=True)}" style="color:#386e9e;text-decoration:none">'
            f'{escape(sanitize(source.name))}</a> '
            f'<span style="color:{color}">— {status}</span></td></tr>'
        )
    return "".join(rows)


def _section_title(title: str, badge: str = "") -> str:
    badge_html = (
        f'<td align="right" style="font:700 12px Arial,sans-serif;color:{MUTED}">'
        f'<span style="background:#edf3f7;border-radius:999px;padding:7px 10px">{escape(badge)}</span></td>'
        if badge
        else ""
    )
    return (
        '<table role="presentation" width="100%"><tr><td>'
        f'<h2 style="margin:0;font:800 22px Arial,sans-serif;color:{INK}">{escape(title)}</h2>'
        f'</td>{badge_html}</tr></table>'
    )


def render_email(edition: Edition, map_url: str, output_path: str) -> str:
    date_label = escape(edition.date_label)
    logo_url = public_logo_url()
    html = f"""<!doctype html>
<html lang="it">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#edf3f7;padding:0">
<div style="display:none;max-height:0;overflow:hidden;color:transparent">{escape(edition.thirty_seconds)}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#edf3f7">
<tr><td align="center" style="padding:22px 10px">
<table role="presentation" width="680" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:680px;background:#ffffff;border-radius:20px;overflow:hidden">
  <tr><td style="padding:25px 32px;background:{INK};border-bottom:6px solid {GREEN}">
    <table role="presentation" width="100%"><tr>
      <td width="70"><img src="{escape(logo_url, quote=True)}" width="58" height="58" alt="Logo MeteoFranz" style="display:block;border:0;border-radius:13px"></td>
      <td><div style="font:800 30px Arial,sans-serif;color:#fff">Meteo<span style="color:#ffd45a">Franz</span></div>
      <div style="font:13px Arial,sans-serif;color:#bed0df;margin-top:5px">Trentino · Sudtirolo</div></td>
      <td align="right" valign="middle" style="font:13px/1.4 Arial,sans-serif;color:#bed0df">{date_label}<br>edizione delle 7:30</td>
    </tr></table>
  </td></tr>

  <tr><td style="padding:31px 32px 26px">
    <h1 style="margin:0;font:800 29px/1.22 Arial,sans-serif;color:{INK}">{escape(edition.phrase)}</h1>
    <p style="margin:10px 0 0;font:16px/1.6 Arial,sans-serif;color:{TEXT}">{escape(edition.deck)}</p>
  </td></tr>

  <tr><td style="padding:24px 27px;border-top:1px solid #dfe8ee">
    {_section_title("Il tempo in 30 secondi", f"affidabilità {edition.confidence}")}
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:13px"><tr>{_quick_cards(edition)}</tr></table>
  </td></tr>

  <tr><td style="padding:25px 20px 15px;border-top:1px solid #dfe8ee">
    <div style="padding:0 12px">{_section_title("Mappa prevista per oggi", "07:30–24:00")}
    <div style="font:13px Arial,sans-serif;color:{MUTED};margin-top:5px">Undici zone · temperatura massima e probabilità di precipitazione</div></div>
    <img src="{escape(map_url, quote=True)}" width="640" alt="Mappa MeteoFranz delle province di Trento e Bolzano con undici zone" style="display:block;width:100%;max-width:640px;height:auto;border:0;margin-top:14px">
    <div style="padding:8px 12px 0">{_province_notes(edition)}</div>
  </td></tr>

  <tr><td style="padding:26px 32px 18px;border-top:1px solid #dfe8ee">
    {_section_title("Previsione condensata e ponderata", "fonti ufficiali + esperti")}
    <div style="margin-top:12px">{_province_block(title="Provincia di Trento", numbers=edition.trentino_numbers, paragraphs=edition.trentino_paragraphs, color=GREEN)}</div>
    <div style="margin-top:12px">{_province_block(title="Provincia di Bolzano / Sudtirolo", numbers=edition.bolzano_numbers, paragraphs=edition.bolzano_paragraphs, color=BLUE)}</div>
  </td></tr>

  <tr><td style="padding:26px 32px 25px;border-top:1px solid #dfe8ee">
    {_section_title("Fenomeni da sorvegliare nelle prossime 48 ore", "aggiornare con i prossimi bollettini")}
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px">{_watch_items(edition)}</table>
  </td></tr>

  <tr><td style="padding:24px 32px;background:#f3f7fa;border-top:5px solid {ORANGE}">
    <div style="font:800 14px Arial,sans-serif;color:{INK};margin-bottom:7px">Fonti consultate</div>
    <table role="presentation" width="100%">{_source_rows(edition)}</table>
    <p style="margin:14px 0 0;font:12px/1.55 Arial,sans-serif;color:{MUTED}">MeteoFranz è una sintesi editoriale informativa e automatizzata. I bollettini redatti dai previsori ufficiali hanno priorità sui dati modellistici e sui contributi social. Per allerte e decisioni sensibili fanno fede i servizi provinciali e la Protezione civile.</p>
    <p style="margin:12px 0 0;font:12px/1.55 Arial,sans-serif;color:{MUTED}">Ricevi questa email perché hai accettato di partecipare alla prova di MeteoFranz. <a href="{{{{ unsubscribe }}}}" style="color:#386e9e">Disiscriviti</a>.</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""
    Path(output_path).write_text(html, encoding="utf-8")
    return html
