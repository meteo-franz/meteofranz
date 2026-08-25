# MeteoFranz

Newsletter meteo personale per Trentino e Sudtirolo, preparata automaticamente ogni mattina e inviata tramite Brevo.

## Cosa fa

- legge il bollettino ufficiale di Meteotrentino;
- legge il feed ufficiale del Servizio meteorologico della Provincia di Bolzano;
- controlla il feed RSS degli aggiornamenti pubblici di Meteo Rosspach, con Telegram come riserva;
- controlla il feed RSS dedicato agli aggiornamenti pubblici di Giacomo Poletti;
- utilizza dati zonali Open-Meteo per temperature, probabilità e simboli;
- genera una mappa unica con 11 zone;
- prepara un'email HTML con il Trentino sempre per primo;
- blocca l'invio se entrambe le fonti ufficiali non sono disponibili;
- invia o programma la campagna attraverso Brevo.

Per Giacomo Poletti viene usato esclusivamente il feed XML `https://rss.app/feeds/vK7EEuALtKzCteSr.xml`; per Meteo Rosspach viene usato prima `https://rss.app/feeds/ZoUYFBZngBg7gg2q.xml`, mantenendo il canale Telegram come riserva. Per entrambi vengono lette fino a tre descrizioni con data verificabile pubblicate nelle ultime 48 ore. I due contributi hanno lo stesso peso editoriale e sono attribuiti esplicitamente nei riepiloghi provinciali; i bollettini ufficiali restano prioritari. Facebook resta una fonte di riscontro e non viene interrogato direttamente.

## Le 11 zone

Trento, Alto Garda, Giudicarie, Valsugana, Val di Non, Fiemme, Bolzano, Merano, Val Pusteria, Val Venosta e Val Isarco.

## Configurazione GitHub

### 1. Secret

Nel repository apri **Settings → Secrets and variables → Actions → Secrets → New repository secret**.

| Nome | Valore |
|---|---|
| `BREVO_API_KEY` | La chiave API creata su Brevo |

La chiave non deve mai essere inserita in un file, in una Issue o in una schermata pubblica.

### 2. Variables

Nella stessa pagina apri la scheda **Variables** e crea:

| Nome | Valore iniziale |
|---|---|
| `BREVO_SENDER_EMAIL` | L'indirizzo mittente verificato in Brevo |
| `BREVO_LIST_NAME` | `MeteoFranz – amici` |
| `LIVE_SEND` | `false` |

`LIVE_SEND=false` mantiene attiva la generazione quotidiana ma impedisce l'invio automatico.

## Primo test

1. Apri la scheda **Actions** del repository.
2. Seleziona **MeteoFranz giornaliero**.
3. Premi **Run workflow**.
4. Lascia `preview` e avvia.
5. Controlla `output/newsletter.html`, `output/map.png` e `output/data.json`.
6. Se l'anteprima è corretta, ripeti scegliendo `send_now`.

## Attivazione alle 7:30

Dopo alcuni invii di prova, modifica la variabile `LIVE_SEND` da `false` a `true`. GitHub avvia il lavoro alle 07:20 italiane e Brevo programma l'invio per le 07:30. In caso di ritardo del sistema, la newsletter viene inviata appena pronta.

## Test locale

```bash
python -m pip install -r requirements.txt
METEOFRANZ_OFFLINE=1 python -m meteofranz.main build --sample
python -m unittest discover -s tests -v
```

I valori generati con `--sample` sono esclusivamente dimostrativi e non vengono utilizzati dall'automazione reale.

La cartografia usa i confini provinciali pubblicati dal progetto `geojson-italy`. Se il dataset non è raggiungibile, la generazione viene interrotta: MeteoFranz non sostituisce mai la mappa con sagome approssimative.

## Fonti e metodo

I bollettini redatti dai previsori ufficiali hanno priorità. I dati modellistici servono per dettagliare le singole zone, non per sostituire il giudizio dei meteorologi. I contributi social vengono considerati solo se recenti, pubblici e leggibili direttamente.

Confini amministrativi: ISTAT, distribuiti dal progetto `guglielmo/geojson-italy` con licenza CC BY 4.0.
