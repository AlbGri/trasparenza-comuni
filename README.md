# Trasparenza Comuni

Osservatorio civico sui bilanci dei comuni italiani: quanto spende ogni comune, per quali
servizi, e come si colloca rispetto ai comuni simili.

Stato: in costruzione. Le fonti sono state verificate e l'impianto è deciso; la pipeline dei
dati è in sviluppo. Non c'è ancora un sito pubblicato.

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

## Struttura

```
trasparenza-comuni/
├── notebooks/          # Prime esplorazioni delle fonti, superate dalla pipeline in arrivo
├── requirements.txt    # Dipendenze Python
└── data/               # Dati scaricati ed elaborati, non versionati
```

## Licenza

[AGPL-3.0](LICENSE)
