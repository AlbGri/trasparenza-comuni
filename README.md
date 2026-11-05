# Trasparenza Comuni

Monitor civico digitale per la trasparenza economico-finanziaria dei comuni italiani.

Stato: fase esplorativa, in pausa. Ci sono un collector BDAP/SIOPE e due notebook di prova
sulle fonti; nessuna dashboard.

## Obiettivi

- Rendere trasparente e accessibile la gestione economico-finanziaria dei comuni
- Visualizzare costi, entrate e spese con dashboard user-friendly
- Evidenziare virtuosità, sprechi e anomalie
- Favorire il controllo sociale e la consapevolezza civica

## Installazione

Prerequisiti: Python 3.11+, Miniconda (o Anaconda), Git.

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
├── src/
│   ├── main.py         # FastAPI, endpoint / e /health
│   └── collectors/     # Download dei dati BDAP/SIOPE
├── notebooks/          # Esplorazione delle fonti (BDAP, SIOPE, OpenBilanci, dati.gov.it, ...)
└── data/               # Dati scaricati, non versionati
```

## Licenza

[AGPL-3.0](LICENSE)
