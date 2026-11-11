# Trasparenza Comuni

Osservatorio civico sui bilanci dei comuni italiani: quanto spende ogni comune, per quali
servizi, e come si colloca rispetto ai comuni simili.

Stato: in costruzione. La pipeline produce le tabelle di base (anagrafica dei comuni, rendiconti
2016-2025, popolazione); indicatori, confronti e sito sono i prossimi passi. Non c'è ancora un
sito pubblicato.

## Obiettivi

- Rendere leggibili entrate, spese e salute finanziaria di ogni comune
- Confrontare ogni comune con i comuni simili per dimensione e territorio
- Mostrare l'andamento negli anni e i dati più recenti disponibili
- Offrire gli stessi dati in forma scaricabile, per chi vuole riusarli

## Fonti

Solo dati pubblici ufficiali, citati in ogni pagina:

- OpenBDAP (Ragioneria Generale dello Stato): rendiconti armonizzati dei comuni e indicatori
  ufficiali, dal 2016
- SIOPE (Banca d'Italia e Ragioneria Generale dello Stato): incassi e pagamenti mensili
- ISTAT: elenco dei comuni e popolazione residente
- IndicePA: anagrafica degli enti

## Come funziona

Una pipeline Python scarica i dati dalle fonti, li pulisce e calcola indicatori e confronti; il
risultato sono file statici, da cui nasceranno il sito e i dati scaricabili. Non ci sono server
né database in rete.

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
python -m pipeline      # scarica le fonti e scrive le tabelle Parquet in data/processed/
python -m pytest        # prove automatiche
```

Il primo lancio scarica i dati di dieci anni e dura circa cinque minuti. I lanci successivi
riscaricano solo ciò che alla fonte è cambiato: senza novità finiscono in pochi secondi. Si può
lanciare un solo passo (`rendiconti`, `anagrafica`, `popolazione`) e limitare gli anni dei
rendiconti, per esempio `python -m pipeline rendiconti --anni 2024`.

Tabelle prodotte, tutte per i soli comuni:

| Tabella | Contenuto | Fonte |
|---|---|---|
| `enti` | codice fiscale, codice ISTAT, nome, provincia, regione, stato (attivo o estinto), successore | OpenBDAP, IndicePA, ISTAT |
| `consegne` | rendiconto presente o no, per ente e anno | OpenBDAP |
| `spese` | impegni, pagamenti e previsioni per missione, programma e titolo | OpenBDAP |
| `entrate` | accertamenti e riscossioni per titolo e tipologia | OpenBDAP |
| `risultato` | voci del risultato di amministrazione | OpenBDAP |
| `indicatori_ufficiali` | i 55 indicatori certificati dal comune | OpenBDAP |
| `parametri` | parametri di deficitarietà, dal 2019 | OpenBDAP |
| `popolazione` | residenti al 1 gennaio dell'anno successivo a quello di bilancio | ISTAT |
| `versioni_fonti` | versione e data di ogni file scaricato | pipeline |

In `spese` ed `entrate` la colonna `esclusa` segna partite di giro e anticipazioni di cassa, che
non sono spesa né entrata vera. Gli impegni (competenza) e i pagamenti (cassa) sono misure
diverse e non vanno sommati né confrontati fra loro.

## Struttura

```
trasparenza-comuni/
├── pipeline/           # Scarico delle fonti e tabelle di base, un modulo per passo
├── tests/              # Prove automatiche
├── notebooks/          # Prime esplorazioni delle fonti, superate dalla pipeline
├── requirements.txt    # Dipendenze Python
└── data/               # Dati scaricati ed elaborati, non versionati
```

## Licenza

[AGPL-3.0](LICENSE)
