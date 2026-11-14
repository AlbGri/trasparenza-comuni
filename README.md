# Trasparenza Comuni

Osservatorio civico sui bilanci dei comuni italiani: quanto spende ogni comune, per quali
servizi, e come si colloca rispetto ai comuni simili.

Stato: in costruzione. La pipeline produce le tabelle di base (anagrafica dei comuni, rendiconti
2016-2025, popolazione) e i confronti fra comuni simili (pro capite, mediane, posizioni);
indicatori ufficiali, esportazione e sito sono i prossimi passi. Non c'è ancora un sito
pubblicato.

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

Il primo lancio scarica tutti gli anni pubblicati da OpenBDAP e dura circa sei minuti. I lanci
successivi riscaricano e ricalcolano solo ciò che alla fonte è cambiato. Si può lanciare un solo
passo (`rendiconti`, `anagrafica`, `popolazione`, `confronti`) e limitare gli anni dei
rendiconti, per esempio `python -m pipeline rendiconti --anni 2024`.

A fine lancio la pipeline confronta i numeri di controllo degli anni chiusi (comuni, impegni,
spesa corrente, residenti, mediane) con quelli attesi in `pipeline/controlli_attesi.csv` ed esce
con un errore se uno non torna.

Tabelle prodotte, tutte per i soli comuni:

| Tabella | Contenuto | Fonte |
|---|---|---|
| `enti` | codice fiscale, codice ISTAT (quello storico per i comuni estinti), nome, provincia, regione, stato (attivo o estinto), data di nascita e di cessazione, successore | OpenBDAP, IndicePA, ISTAT |
| `consegne` | per ente e anno: consegnato, non consegnato, non esisteva | OpenBDAP, ISTAT |
| `spese` | impegni, pagamenti e previsioni per missione, programma e titolo | OpenBDAP |
| `entrate` | accertamenti e riscossioni per titolo e tipologia | OpenBDAP |
| `risultato` | voci del risultato di amministrazione | OpenBDAP |
| `indicatori_ufficiali` | i 55 indicatori certificati dal comune | OpenBDAP |
| `parametri` | parametri di deficitarietà, dal 2019 | OpenBDAP |
| `popolazione` | residenti al 1 gennaio dell'anno successivo a quello di bilancio | ISTAT |
| `gruppi` | gruppo di comuni simili di ogni comune, anno per anno: fascia di abitanti e area | pipeline |
| `dimensione_gruppi` | comuni di ogni gruppo, con quanti hanno e non hanno il rendiconto | pipeline |
| `procapite` | spesa ed entrate pro capite per titolo, missione e programma, con la posizione nel gruppo | pipeline |
| `confronti` | mediana e percentili di ogni gruppo, voce per voce | pipeline |
| `versioni_fonti` | versione e data di ogni file scaricato | pipeline |

I gruppi uniscono comuni della stessa fascia di abitanti (sei fasce) e della stessa area: le
regioni ordinarie in quattro aree, ogni regione a statuto speciale a sé. Un gruppo con meno di
20 comuni si allarga alle regioni dello stesso tipo, poi a tutta Italia, e lo dichiara.

In `spese` ed `entrate` la colonna `esclusa` segna partite di giro e anticipazioni di cassa, che
non sono spesa né entrata vera. Gli impegni (competenza) e i pagamenti (cassa) sono misure
diverse e non vanno sommati né confrontati fra loro.

## Struttura

```
trasparenza-comuni/
├── pipeline/           # Scarico delle fonti e tabelle di base, un modulo per passo
├── tests/              # Prove automatiche
├── requirements.txt    # Dipendenze Python
└── data/               # Dati scaricati ed elaborati, non versionati
```

## Licenza

[AGPL-3.0](LICENSE)
