from __future__ import annotations

import re
from collections import Counter
from datetime import date

from .models import Edition, QuickCard, SourceNote, WatchItem, ZoneForecast
from .sources import sanitize
from .weather import weather_label, weather_symbol


MONTHS = (
    "",
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)
WEEKDAYS = (
    "lunedì",
    "martedì",
    "mercoledì",
    "giovedì",
    "venerdì",
    "sabato",
    "domenica",
)


def _date_label(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month]} {day.year}"


def _source(sources: list[SourceNote], name: str) -> SourceNote | None:
    return next((source for source in sources if source.name == name), None)


def _signals(text: str) -> set[str]:
    lowered = sanitize(text).lower()
    signals: set[str] = set()
    patterns = {
        "temporali": r"tempor|fulmin",
        "rovesci": r"rovesc",
        "pioggia": r"piogg|precipit",
        "sole": r"soleggi|sereno|sole",
        "nuvole": r"nuvol|coperto",
        "vento": r"venti? (?:fort|sostenut)|raffich|föhn|foehn",
        "neve": r"nev|quota neve",
        "caldo": r"caldo|temperature (?:elevate|alte)|afa",
        "freddo": r"freddo|gel|temperature in calo",
        "mattino": r"mattin|prime ore",
        "pomeriggio": r"pomerig|ore più calde",
        "sera": r"sera|serata",
    }
    for signal, pattern in patterns.items():
        if re.search(pattern, lowered):
            signals.add(signal)
    return signals


def _official_sentence(source: SourceNote | None) -> str:
    if not source or not source.available:
        return "Il bollettino ufficiale non era leggibile al momento dell’elaborazione."
    signals = _signals(f"{source.title} {source.text}")
    timing = ""
    if "mattino" in signals and "pomeriggio" in signals:
        timing = " tra mattino e pomeriggio"
    elif "mattino" in signals:
        timing = " soprattutto al mattino"
    elif "pomeriggio" in signals and "sera" in signals:
        timing = " tra pomeriggio e sera"
    elif "pomeriggio" in signals:
        timing = " soprattutto nel pomeriggio"
    elif "sera" in signals:
        timing = " verso sera"

    if "temporali" in signals:
        core = f"L’indicazione ufficiale richiama possibili rovesci o temporali{timing}."
    elif "pioggia" in signals or "rovesci" in signals:
        core = f"L’indicazione ufficiale segnala precipitazioni o rovesci{timing}."
    elif "sole" in signals and "nuvole" in signals:
        core = "L’indicazione ufficiale descrive una giornata tra schiarite e annuvolamenti."
    elif "sole" in signals:
        core = "L’indicazione ufficiale descrive condizioni in prevalenza soleggiate."
    elif "nuvole" in signals:
        core = "L’indicazione ufficiale descrive condizioni prevalentemente nuvolose."
    else:
        core = "Il bollettino ufficiale non evidenzia un segnale dominante facilmente sintetizzabile."
    if "vento" in signals:
        core += " Da considerare anche vento sostenuto o raffiche."
    return core


def _province_stats(zones: list[ZoneForecast], province: str) -> dict:
    selected = [zone for zone in zones if zone.province == province]
    today = [zone.days[0] for zone in selected]
    codes = Counter(weather_label(day.weather_code) for day in today)
    return {
        "zones": selected,
        "dominant": codes.most_common(1)[0][0],
        "min": min(day.temp_min for day in today),
        "max": max(day.temp_max for day in today),
        "rain": max(day.precipitation_probability for day in today),
        "gust": max(day.wind_gust for day in today),
    }


def _province_summary(
    zones: list[ZoneForecast], province: str, official: SourceNote | None
) -> str:
    stats = _province_stats(zones, province)
    place_max = max(stats["zones"], key=lambda zone: zone.days[0].temp_max)
    place_rain = max(
        stats["zones"], key=lambda zone: zone.days[0].precipitation_probability
    )
    official_part = _official_sentence(official)
    numbers = (
        f"Le indicazioni zonali mostrano un quadro prevalentemente {stats['dominant']}, "
        f"con massime comprese indicativamente tra {min(z.days[0].temp_max for z in stats['zones'])} "
        f"e {stats['max']} °C. Il valore più alto è atteso in zona {place_max.name.title()}; "
        f"la probabilità di precipitazione più elevata riguarda {place_rain.name.title()} "
        f"({place_rain.days[0].precipitation_probability}%)."
    )
    return sanitize(f"{official_part} {numbers}")


def _province_content(
    zones: list[ZoneForecast],
    province: str,
    official: SourceNote | None,
    expert: SourceNote | None,
    expert_name: str,
) -> tuple[str, str, list[str]]:
    stats = _province_stats(zones, province)
    selected = stats["zones"]
    max_place = max(selected, key=lambda zone: zone.days[0].temp_max)
    rain_place = max(selected, key=lambda zone: zone.days[0].precipitation_probability)
    min_maximum = min(zone.days[0].temp_max for zone in selected)
    numbers = " · ".join(
        f"{zone.name.title()} {zone.days[0].temp_max} °C" for zone in selected
    )
    official_part = _official_sentence(official)
    expert_part = _expert_merge_sentence(official, expert, expert_name)
    first = sanitize(
        f"{official_part} {expert_part} Nel complesso, le indicazioni zonali descrivono un quadro "
        f"{stats['dominant']}, con massime fra {min_maximum} e "
        f"{stats['max']} °C. I valori più elevati sono attesi in zona "
        f"{max_place.name.title()}."
    )

    future = [day for zone in selected for day in zone.days[1:3]]
    future_rain = max(day.precipitation_probability for day in future)
    future_gust = max(day.wind_gust for day in future)
    future_storm = any(day.weather_code in {95, 96, 99} for day in future)
    if future_storm:
        trend = "Nelle successive 48 ore aumenta la possibilità di rovesci o temporali."
    elif future_rain >= 55:
        trend = "Nelle successive 48 ore cresce la probabilità di precipitazioni in alcune zone."
    else:
        trend = "Nelle successive 48 ore non emerge al momento un peggioramento diffuso."
    if future_gust >= 45:
        trend += f" Da sorvegliare anche raffiche modellistiche fino a circa {future_gust} km/h."
    trend += (
        f" Oggi la probabilità più alta di precipitazione riguarda "
        f"{rain_place.name.title()} ({rain_place.days[0].precipitation_probability}%)."
    )
    map_note = sanitize(
        f"Prevalenza di condizioni {stats['dominant']}. Massime fra {min_maximum} e "
        f"{stats['max']} °C; probabilità di precipitazione fino al {stats['rain']}%."
    )
    return numbers, map_note, [first, sanitize(trend)]


def _phrase(zones: list[ZoneForecast], sources: list[SourceNote]) -> str:
    official_text = " ".join(
        f"{source.title} {source.text}"
        for source in sources[:2]
        if source.available
    )
    signals = _signals(official_text)
    max_rain = max(zone.days[0].precipitation_probability for zone in zones)
    has_storm = any(zone.days[0].weather_code in {95, 96, 99} for zone in zones)
    if "temporali" in signals or has_storm:
        return "Schiarite possibili, ma resta da seguire il rischio di rovesci e temporali."
    if "pioggia" in signals or max_rain >= 60:
        return "Giornata variabile: ombrello utile nelle zone con precipitazioni più probabili."
    if "sole" in signals and "nuvole" in signals:
        return "Sole e nuvole si alternano, con differenze sensibili tra le valli."
    if "sole" in signals:
        return "Giornata in prevalenza soleggiata, con consuete differenze tra fondovalle e montagna."
    return "Tempo variabile sulle due province, da leggere valle per valle."


def _expert_sentence(sources: list[SourceNote]) -> str:
    experts = [source for source in sources[2:] if source.available]
    if not experts:
        return ""
    expert_names = " e ".join(source.name for source in experts)
    official_signals = _signals(
        " ".join(f"{source.title} {source.text}" for source in sources[:2] if source.available)
    )
    expert_signals = _signals(
        " ".join(f"{source.title} {source.text}" for source in experts)
    )
    priorities = ("temporali", "rovesci", "pioggia", "vento", "neve", "caldo", "sole")
    shared = next((signal for signal in priorities if signal in official_signals & expert_signals), "")
    if shared:
        label = "precipitazioni" if shared == "pioggia" else shared
        return f"I contributi recenti di {expert_names} sono coerenti sul segnale di {label}."
    added = next((signal for signal in priorities if signal in expert_signals), "")
    if added:
        label = "precipitazioni" if added == "pioggia" else added
        return (
            f"Il contributo recente di {expert_names} aggiunge un possibile segnale di {label}, "
            "mantenuto come indicazione secondaria finché non trova conferma ufficiale."
        )
    return ""


def _weather_labels(signals: set[str]) -> list[str]:
    labels = {
        "temporali": "temporali",
        "rovesci": "rovesci",
        "pioggia": "precipitazioni",
        "sole": "schiarite",
        "nuvole": "nuvolosità",
        "vento": "vento o raffiche",
        "neve": "neve o quota neve",
        "caldo": "temperature elevate",
        "freddo": "calo termico",
    }
    order = (
        "temporali", "rovesci", "pioggia", "vento", "neve",
        "caldo", "freddo", "sole", "nuvole",
    )
    return [labels[item] for item in order if item in signals]


def _join_labels(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f" e {values[-1]}"


def _caption_timings(text: str) -> str:
    lowered = sanitize(text).lower()
    timings: list[str] = []
    patterns = (
        ("mattino", r"mattin|prime ore|alba"),
        ("pomeriggio", r"pomerig|ore più calde"),
        ("sera", r"sera|serata"),
        ("notte", r"notte|nottata"),
    )
    for label, pattern in patterns:
        if re.search(pattern, lowered):
            timings.append(label)
    return _join_labels(timings)


def _caption_values(text: str) -> list[str]:
    values = re.findall(
        r"\b\d+(?:[.,]\d+)?(?:\s*[-–/]\s*\d+(?:[.,]\d+)?)?\s*"
        r"(?:°C|°|gradi|mm|km/h)\b",
        text,
        flags=re.IGNORECASE,
    )
    unique: list[str] = []
    for value in values:
        normalized = sanitize(value)
        if normalized.casefold() not in {item.casefold() for item in unique}:
            unique.append(normalized)
    return unique[:4]


def _expert_merge_sentence(
    official: SourceNote | None,
    expert: SourceNote | None,
    expert_name: str,
) -> str:
    """Confronta bollettino e caption e restituisce una vera sintesi ponderata."""
    if not expert or not expert.available or not expert.text:
        return ""
    official_signals = (
        _signals(f"{official.title} {official.text}")
        if official and official.available
        else set()
    )
    expert_signals = _signals(f"{expert.title} {expert.text}")
    shared = _weather_labels(official_signals & expert_signals)
    added = _weather_labels(expert_signals - official_signals)
    parts: list[str] = []
    if shared:
        parts.append(f"conferma il segnale di {_join_labels(shared[:3])}")
    if added:
        verb = "aggiunge" if shared else "richiama"
        parts.append(f"{verb} {_join_labels(added[:3])}")
    if not parts:
        parts.append("offre una lettura locale senza introdurre un segnale dominante diverso")
    timing = _caption_timings(expert.text)
    values = _caption_values(expert.text)
    detail = " e ".join(parts)
    if timing:
        timing_prefix = "tra" if " e " in timing or "," in timing else "nel"
        detail += f", con indicazioni concentrate {timing_prefix} {timing}"
    if values:
        detail += f" e valori citati di {_join_labels(values)}"
    return sanitize(
        f"Nella lettura ponderata, {expert_name} {detail}; il contributo esperto "
        "affina il dettaglio locale senza sostituire il bollettino ufficiale."
    )


def _watch_items(zones: list[ZoneForecast], sources: list[SourceNote]) -> list[WatchItem]:
    items: list[WatchItem] = []
    for day_index in (1, 2):
        daily = [(zone, zone.days[day_index]) for zone in zones]
        forecast_day = date.fromisoformat(daily[0][1].date)
        max_rain_zone, max_rain_day = max(
            daily, key=lambda item: item[1].precipitation_probability
        )
        max_gust = max(item[1].wind_gust for item in daily)
        min_temp = min(item[1].temp_min for item in daily)
        max_temp = max(item[1].temp_max for item in daily)
        storm_zones = [
            zone.name.title()
            for zone, item in daily
            if item.weather_code in {95, 96, 99}
        ]
        if storm_zones:
            places = ", ".join(storm_zones[:4])
            text = (
                f"Possibili rovesci o temporali, con segnale modellistico più evidente "
                f"fra {places}. Probabilità massima giornaliera fino al "
                f"{max_rain_day.precipitation_probability}% e temperature fra "
                f"{min_temp} e {max_temp} °C nelle zone considerate."
            )
        elif max_rain_day.precipitation_probability >= 50:
            text = (
                f"Tempo variabile con precipitazioni localmente possibili; la probabilità "
                f"più alta riguarda {max_rain_zone.name.title()} "
                f"({max_rain_day.precipitation_probability}%). Temperature zonali fra "
                f"{min_temp} e {max_temp} °C."
            )
        else:
            text = (
                f"Non emerge un fenomeno diffuso dominante. Probabilità massima di "
                f"precipitazione {max_rain_day.precipitation_probability}% e temperature "
                f"zonali fra {min_temp} e {max_temp} °C."
            )
        if max_gust >= 45:
            text += f" Possibili raffiche fino a circa {max_gust} km/h."
        items.append(
            WatchItem(
                label=WEEKDAYS[forecast_day.weekday()].capitalize(),
                text=sanitize(text),
            )
        )
    return items


def _quick_cards(zones: list[ZoneForecast]) -> list[QuickCard]:
    today = [zone.days[0] for zone in zones]
    dominant = Counter(weather_label(item.weather_code) for item in today).most_common(1)[0][0]
    representative = next(item for item in today if weather_label(item.weather_code) == dominant)
    today_rain = max(item.precipitation_probability for item in today)
    future = [item for zone in zones for item in zone.days[1:3]]
    future_rain = max(item.precipitation_probability for item in future)
    future_storm = any(item.weather_code in {95, 96, 99} for item in future)
    if today_rain >= 65:
        late_value, late_text = "🌧️ Rischio alto", f"Probabilità zonale fino al {today_rain}%."
    elif today_rain >= 35:
        late_value, late_text = "🌦️ Da seguire", f"Probabilità zonale fino al {today_rain}%."
    else:
        late_value, late_text = "🌤️ Rischio basso", f"Probabilità zonale non oltre il {today_rain}%."
    if future_storm:
        future_value = "⛈️ Instabilità"
        future_text = "Possibili rovesci o temporali in una o più zone."
    elif future_rain >= 55:
        future_value = "🌧️ Più variabile"
        future_text = f"Probabilità zonale fino al {future_rain}%."
    else:
        future_value = "🌤️ Senza svolte nette"
        future_text = "Al momento non emerge un peggioramento diffuso."
    return [
        QuickCard("Oggi", f"{weather_symbol(representative.weather_code)} {dominant.capitalize()}", "Differenze locali fra fondovalle e rilievi."),
        QuickCard("Pomeriggio e sera", late_value, late_text),
        QuickCard("Prossime 48 ore", future_value, future_text),
    ]


def build_edition(
    day: date, zones: list[ZoneForecast], sources: list[SourceNote]
) -> Edition:
    trentino = _source(sources, "Meteotrentino")
    bolzano = _source(sources, "Servizio meteorologico Provincia di Bolzano")
    phrase = _phrase(zones, sources)
    trentino_stats = _province_stats(zones, "Trentino")
    bolzano_stats = _province_stats(zones, "Provincia di Bolzano")
    trentino_numbers, trentino_map, trentino_paragraphs = _province_content(
        zones,
        "Trentino",
        trentino,
        _source(sources, "Giacomo Poletti"),
        "Giacomo Poletti",
    )
    bolzano_numbers, bolzano_map, bolzano_paragraphs = _province_content(
        zones,
        "Provincia di Bolzano",
        bolzano,
        _source(sources, "Meteo Rosspach"),
        "Meteo Rosspach",
    )
    thirty_seconds = sanitize(
        f"{phrase} In Trentino massime zonali fino a {trentino_stats['max']} °C "
        f"e probabilità di precipitazione fino al {trentino_stats['rain']}%; "
        f"in Provincia di Bolzano massime fino a {bolzano_stats['max']} °C "
        f"e probabilità fino al {bolzano_stats['rain']}%. {_expert_sentence(sources)}"
    )
    edition = Edition(
        date_iso=day.isoformat(),
        date_label=_date_label(day),
        phrase=sanitize(phrase),
        deck=thirty_seconds,
        confidence=(
            "medio-alta"
            if sum(source.available for source in sources[:2]) == 2
            else "media"
            if sum(source.available for source in sources[:2]) == 1
            else "limitata"
        ),
        thirty_seconds=thirty_seconds,
        quick_cards=_quick_cards(zones),
        map_trentino_note=trentino_map,
        map_bolzano_note=bolzano_map,
        trentino_numbers=trentino_numbers,
        bolzano_numbers=bolzano_numbers,
        trentino_paragraphs=trentino_paragraphs,
        bolzano_paragraphs=bolzano_paragraphs,
        trentino_summary=" ".join(trentino_paragraphs),
        bolzano_summary=" ".join(bolzano_paragraphs),
        watch_items=_watch_items(zones, sources),
        zones=zones,
        sources=sources,
    )
    # Ultima barriera editoriale per termini e spaziature.
    edition.phrase = sanitize(edition.phrase)
    edition.thirty_seconds = sanitize(edition.thirty_seconds)
    edition.trentino_summary = sanitize(edition.trentino_summary)
    edition.bolzano_summary = sanitize(edition.bolzano_summary)
    return edition
