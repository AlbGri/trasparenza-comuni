# 🏛️ Trasparenza Comuni

Monitor civico digitale per la trasparenza economico-finanziaria dei comuni italiani.

## 🎯 Obiettivi

- Rendere trasparente e accessibile la gestione economico-finanziaria dei comuni
- Visualizzare costi, entrate e spese con dashboard user-friendly
- Evidenziare virtuosità, sprechi e anomalie
- Favorire il controllo sociale e la consapevolezza civica

## 🚀 Quick Start

### Prerequisiti
- Python 3.11+
- PostgreSQL 15+
- Git

### Installazione
```bash
# Clona il repository
git clone https://github.com/TUO_USERNAME/trasparenza-comuni.git
cd trasparenza-comuni

# Crea ambiente virtuale
python -m venv venv

# Attiva ambiente (Windows)
venv\Scripts\activate

# Attiva ambiente (Linux/Mac)
source venv/bin/activate

# Installa dipendenze
pip install -r requirements.txt
```

## 📁 Struttura Progetto
```
trasparenza-comuni/
├── src/
│   ├── api/            # FastAPI backend
│   ├── collectors/     # Data collectors per API pubbliche
│   ├── database/       # Modelli e gestione DB
│   ├── analysis/       # Analisi e AI
│   └── utils/          # Utility functions
├── data/
│   ├── raw/           # Dati grezzi scaricati
│   └── processed/     # Dati elaborati
├── notebooks/         # Jupyter notebooks per analisi
├── tests/            # Test suite
├── docs/             # Documentazione
└── config/           # File di configurazione
```

## 🤝 Contributing

Progetto open source - contribuzioni benvenute!

## 📝 Licenza

MIT License - Vedi [LICENSE](LICENSE) per dettagli