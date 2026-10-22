# Global Energy Data 2026 — Energy Data Explorer

App Streamlit per esplorare i dati dell'**Energy Institute, *Statistical Review of World Energy* 2026**
(serie 1965–2025) per paese, continente e aggregato: energia primaria, mix elettrico, emissioni,
curve di sostituzione di Marchetti, percorso verso l'elettrificazione e diagrammi di Sankey
dalla primaria agli usi finali.

Sviluppato da **Matteo De Piccoli** e **cs1bc** — [Ci Sarà un Bel Clima](https://unbelclima.it/).

## Avvio

```bash
pip install -r requirements.txt
streamlit run datas.py
```

Il file `EI-Stats-Review-ALL-data (1).xlsx` deve stare nella stessa cartella di `datas.py`.

## Cosa contiene

**Barra laterale**
- *Tipo di area*: **Stati**, **Continenti e aggregati** (Mondo, continenti EI, OCSE, Non-OCSE, UE) oppure
  **Altre aree**: i gruppi residui dell'EI ("Altri Europa", "Africa orientale"…) e la serie storica URSS.
- *Anno*: dal 1965. I dati elettrici partono dal 1985, le emissioni CO2e dal 1990, la capacità
  solare/eolica dal 2000. Quando un dato manca l'app scrive "n.d.".

**Indicatori**: energia primaria (EJ), generazione elettrica (TWh), emissioni CO2e (Mt), primaria pro capite
(GJ/ab) ed elettricità pro capite (MWh/ab). La popolazione è ricavata dividendo l'energia primaria per il
valore pro capite fornito dall'EI.

**📊 Statistiche & Capacità**: composizione della primaria, generazione elettrica per fonte, capacità
installata solare ed eolica.

**📈 Trend, Marchetti & Ternary**
- Emissioni storiche.
- Curve di sostituzione di Marchetti, `log10(f / (1 − f))` con *f* = quota di mercato, sia per la primaria
  sia per il mix elettrico.
- Diagramma ternario Fossili / Fonti "elettriche" (nucleare, idro, solare, eolico) / Biomasse e altro.

**🔄 Sankeys Termodinamici**
1. *Dalla primaria all'energia utile*: fonti raggruppate → elettricità, combustibili usati direttamente e
   perdite nelle centrali → lavoro utile, calore utile, usi non energetici e perdite a valle.
2. *Dalle fonti ai settori finali*: singole fonti → vettori → trasporti, industria, edifici, usi non
   energetici.

Ogni nodo riporta EJ e quota sulla primaria; i flussi rossi sono perdite.

## Dati e metodo

### Fonte
Energy Institute, *Statistical Review of World Energy* 2026, file completo dei dati
(<https://www.energyinst.org/statistical-review>). Fogli usati:

| Grandezza | Fogli EI |
|---|---|
| Energia primaria per fonte (EJ) | `Oil/Gas/Coal/Nuclear/Hydro/Solar/Wind Consumption - EJ`, `Geo Biomass Other - EJ`, `Biofuels consumption - PJ` |
| Energia primaria totale | `Total Energy Supply (TES) -EJ`, `TES per Capita` |
| Generazione elettrica per fonte (TWh) | `Nuclear/Hydro/Solar/Wind Generation - TWh`, `Geo Biomass Other - TWh`, `Oil/Gas/Coal/Other inputs - Elec generation` |
| Generazione totale | `Electricity Generation - TWh` |
| Emissioni | `CO2e Emissions ` |
| Capacità | `Solar Installed Capacity`, `Wind Installed Capacity` |

Nota: nonostante il nome, i fogli `… inputs - Elec generation` riportano la **generazione** in TWh per
combustibile, non l'input di combustibile.

### Contabilità dell'energia primaria
L'edizione 2026 dell'EI usa il **contenuto energetico fisico**:
- idro, solare ed eolico sono contati **1:1** con l'elettricità prodotta (1 TWh = 0,0036 EJ);
- il nucleare con un **rendimento convenzionale del 33%** (≈ 3 EJ di primaria per EJ elettrico);
- geotermia, biomasse e altro con il rispettivo input termico.

Questa scelta pesa molto su ternario, curve di Marchetti sulla primaria e Sankey. Rispetto al vecchio
metodo per sostituzione, le rinnovabili elettriche risultano più "piccole" e le perdite del nucleare più
grandi.

I biocarburanti sono una voce separata: l'EI li ha tolti dal petrolio. Con loro la somma delle fonti
coincide con il totale EI.

### Modello dei Sankey
I flussi di **energia primaria** e di **elettricità per fonte** sono dati EI. Tutto ciò che sta **a valle**
è un modello semplificato, con ipotesi **uguali per tutti i paesi e tutti gli anni**. Le ipotesi si
possono modificare nell'app dal pannello *⚙️ Ipotesi del modello*.

| Passaggio | Ipotesi predefinita |
|---|---|
| Rendimento centrali a carbone / gas / petrolio | 37% / 45% / 33% |
| Nucleare, biomasse/geo | input = consumo primario EI |
| Idro, solare, eolico, altro | nessuna perdita di conversione (metodo EI) |
| Perdite di rete e autoconsumi elettrici | 8% |
| Perdite di filiera dei combustibili (raffinazione, trasporto, autoconsumi) | 15% |
| Combustibili per usi non energetici (materia prima) | 12% |
| Elettricità: quota per lavoro/servizi, rendimento | 77%, 68% |
| Elettricità: rendimento per calore | 91% (valori > 1 rappresentano pompe di calore) |
| Combustibili: quota per lavoro (motori), rendimento | 48%, 29% |
| Combustibili: rendimento per calore | 64% |
| Ripartizione elettricità (trasporti / industria / edifici) | 2 / 43 / 55 % |
| Ripartizione combustibili, usi energetici (trasporti / industria / edifici) | 45 / 33 / 22 % |

Come si calcola:
- La quota di combustibile fossile mandata alle centrali è *generazione / rendimento*, mai più del consumo
  primario di quella fonte. Il resto è considerato uso diretto.
- Le perdite nelle centrali sono *input − generazione*.

## Limiti
- **Sankey a valle**: le ipotesi sono medie globali indicative. Servono per confronti qualitativi e
  d'ordine di grandezza, non sono dati statistici sugli usi finali.
- **Copertura EI**: la biomassa tradizionale non è coperta dall'EI. Nei paesi dove pesa molto, la primaria
  e la quota "Bio & altro" risultano sottostimate.
- **Gruppi residui**: aggregano paesi diversi e non sono confrontabili con i singoli stati.

## Citazione dei dati
> Energy Institute — *Statistical Review of World Energy* (2026).

Per l'uso dei dati valgono i termini dell'Energy Institute.
