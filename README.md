# Trasparenza Comuni

Osservatorio civico sui bilanci dei comuni italiani: quanto spende ogni comune, per quali servizi, e come si colloca rispetto ai comuni simili.

Stato: online su https://trasparenza-comuni.albgri.com/ (indirizzo di riserva https://albgri.github.io/trasparenza-comuni/). Il sito copre tutti gli 8.057 comuni, estinti compresi, con i rendiconti dal 2016 al 2025 (il 2025 è provvisorio): una pagina per comune con gli indicatori ufficiali, il confronto con i comuni simili, l'andamento negli anni e il CSV scaricabile; una pagina per gruppo di comuni simili e anno, la ricerca, i comuni senza rendiconto, la pagina del metodo e la sitemap. In preparazione: i pagamenti mensili SIOPE e un'API pubblica con i dati in JSON.

## Obiettivi

- Rendere leggibili entrate, spese e salute finanziaria di ogni comune
- Confrontare ogni comune con i comuni simili per dimensione e territorio
- Mostrare l'andamento negli anni e i dati più recenti disponibili
- Offrire gli stessi dati in forma scaricabile, per chi vuole riusarli

## Fonti

Solo dati pubblici ufficiali, citati in ogni pagina:

- OpenBDAP (Ragioneria Generale dello Stato): rendiconti armonizzati dei comuni e indicatori ufficiali, dal 2016
- SIOPE (Banca d'Italia e Ragioneria Generale dello Stato): incassi e pagamenti mensili (in preparazione)
- ISTAT: elenco dei comuni e popolazione residente
- IndicePA: anagrafica degli enti
- Eurostat: indice dei prezzi al consumo armonizzato (IPCA) dell'Italia, calcolato da ISTAT

## Come funziona

Una pipeline Python scarica i dati dalle fonti, li pulisce e calcola indicatori e confronti; il risultato sono file statici, da cui nascono il sito e i dati scaricabili. Non ci sono server né database in rete.

## Installazione

Prerequisiti: Python 3.11, Miniconda (o Anaconda), Git.

```bash
git clone https://github.com/AlbGri/trasparenza-comuni.git
cd trasparenza-comuni
conda create -n trasparenza python=3.11 -y
conda activate trasparenza
pip install -r requirements.txt
```

## Uso

```bash
python -m pipeline      # scarica le fonti, scrive tabelle (data/processed/), JSON (data/export/) e pagine (data/sito/)
python -m pytest        # prove automatiche
```

Il primo lancio scarica tutti gli anni pubblicati da OpenBDAP e dura circa quindici minuti. I lanci successivi riscaricano e ricalcolano solo ciò che alla fonte è cambiato. Si può lanciare un solo passo (`rendiconti`, `anagrafica`, `popolazione`, `prezzi`, `confronti`, `esportazione`, `sito`) e limitare gli anni dei rendiconti, per esempio `python -m pipeline rendiconti --anni 2024`, o le pagine da generare, per esempio `python -m pipeline sito --comuni 037006,057039`. Il sito si genera solo se i numeri di controllo tornano.

A fine lancio la pipeline confronta i numeri di controllo degli anni chiusi (comuni, impegni, spesa corrente, residenti, mediane) con quelli attesi in `pipeline/controlli_attesi.csv` ed esce con un errore se uno non torna.

Tabelle prodotte, tutte per i soli comuni:

| Tabella | Contenuto | Fonte |
|---|---|---|
| `enti` | codice fiscale, codice ISTAT (quello storico per i comuni estinti), nome, provincia, regione, stato (attivo o estinto), data di nascita e di cessazione, successore | OpenBDAP, IndicePA, ISTAT |
| `consegne` | per ente e anno: consegnato, non consegnato, non esisteva | OpenBDAP, ISTAT |
| `spese` | impegni, pagamenti e previsioni per missione, programma e titolo | OpenBDAP |
| `entrate` | accertamenti e riscossioni per titolo e tipologia | OpenBDAP |
| `risultato` | voci del risultato di amministrazione | OpenBDAP |
| `indicatori_ufficiali` | i 55 indicatori calcolati dal comune e allegati al rendiconto | OpenBDAP |
| `parametri` | parametri di deficitarietà, dal 2019 | OpenBDAP |
| `popolazione` | residenti al 1 gennaio dell'anno successivo a quello di bilancio | ISTAT |
| `gruppi` | gruppo di comuni simili di ogni comune, anno per anno: fascia di abitanti e area | pipeline |
| `dimensione_gruppi` | comuni di ogni gruppo, con quanti hanno e non hanno il rendiconto | pipeline |
| `posizioni` | valori per abitante (spesa, entrate, risultato) e indicatori ufficiali, con posizione nel gruppo e andamento; per un comune senza residenti ISTAT, solo gli importi | pipeline |
| `confronti` | mediana, percentili e variazione mediana di ogni gruppo, voce per voce | pipeline |
| `codici` | descrizione di missioni, programmi, titoli, tipologie, voci e indicatori | OpenBDAP |
| `prezzi` | indice IPCA, media annua | Eurostat |
| `versioni_fonti` | versione e data di ogni file scaricato | pipeline |

I gruppi uniscono comuni della stessa fascia di abitanti (sei fasce) e della stessa area: le regioni ordinarie in quattro aree, ogni regione a statuto speciale a sé. Un gruppo con meno di 20 comuni si allarga alle regioni dello stesso tipo, poi a tutta Italia, e lo dichiara.

In `spese` ed `entrate` la colonna `esclusa` segna partite di giro e anticipazioni di cassa, che non sono spesa né entrata vera. Gli interessi pagati sulle anticipazioni (missione 60, titolo 1) sono spesa e restano, come nel portale OpenBDAP. Gli impegni (competenza) e i pagamenti (cassa) sono misure diverse e non vanno sommati né confrontati fra loro.

## Esportazione

I file per il sito e per chi vuole riusare i dati, in `data/export/`:

| File | Contenuto |
|---|---|
| `comuni/{codice ISTAT}.json` | scheda di un comune: anagrafica, consegne, residenti, gruppo e, per ogni voce, serie 2016-2025 di importo, valore per abitante, posizione, mediana del gruppo e andamento |
| `comuni.json` | indice dei comuni, per la ricerca |
| `gruppi/{fascia}-{ambito}.json` | comuni di ogni gruppo, quanti hanno consegnato, percentili per voce e anno |
| `dizionario.json` | nome, unità, misura, fonte e metodo di ogni voce |
| `meta.json` | data dei dati OpenBDAP per anno, date delle altre fonti, fasce di abitanti, indice dei prezzi |

Un comune estinto prima del 2019 può non avere i residenti ISTAT degli anni in cui esisteva: la sua scheda ha gli importi, senza valori per abitante, gruppo e indicatori ufficiali.

## Struttura

```
trasparenza-comuni/
├── pipeline/           # Scarico delle fonti e tabelle di base, un modulo per passo
├── tests/              # Prove automatiche
├── requirements.txt    # Dipendenze Python
└── data/               # Dati scaricati ed elaborati, non versionati
```

## Licenza

Codice: [AGPL-3.0](LICENSE). Numeri calcolati dal sito: CC BY 4.0, citando Trasparenza comuni e le fonti originali. `sito/statico/plotly-basic-2.35.2.min.js` è Plotly.js, con licenza MIT. I caratteri in `sito/statico/caratteri/` (Alegreya, Atkinson Hyperlegible Next) hanno la licenza SIL Open Font License, nei file `OFL-*.txt` della stessa cartella.
