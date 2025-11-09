# 📋 **MEGA-PROMPT per Continuazione Progetto "Trasparenza Comuni"**

## 🎯 **CONTESTO DEL PROGETTO**

Sto sviluppando **"Trasparenza Comuni"**, un monitor civico digitale open source per rendere trasparente la gestione economico-finanziaria dei comuni italiani. Il progetto prevede dashboard interattive, analisi AI e confronti tra territori.

**Repository GitHub**: https://github.com/[TUO_USERNAME]/trasparenza-comuni

## 🖥️ **AMBIENTE DI SVILUPPO ATTUALE**

- **OS**: Windows 11
- **Python**: 3.11 via Miniconda (environment: `trasparenza`)
- **IDE**: VS Code con conda environment configurato
- **Path conda**: `C:\Users\Alberto\.conda\envs\trasparenza\`
- **Directory progetto**: `C:\Alberto\Sito\trasparenza-comuni\`

### File `.vscode/settings.json` configurato:
```json
{
    "python.defaultInterpreterPath": "C:/Users/Alberto/.conda/envs/trasparenza/python.exe",
    "python.terminal.activateEnvironment": true,
    "terminal.integrated.defaultProfile.windows": "Command Prompt"
}
```

## 📁 **STRUTTURA PROGETTO IMPLEMENTATA**

```
trasparenza-comuni/
├── .vscode/
│   └── settings.json          ✅ Configurazione VS Code
├── src/
│   ├── __init__.py           ✅
│   ├── main.py               ✅ FastAPI server funzionante
│   ├── api/
│   │   └── __init__.py       ✅
│   ├── collectors/
│   │   ├── __init__.py       ✅
│   │   ├── bdap_collector.py ❌ Non funziona (API offline)
│   │   └── istat_collector.py ✅ FUNZIONANTE - scarica comuni da ISTAT
│   ├── database/
│   │   ├── __init__.py       ✅
│   │   ├── models.py         ✅ Modelli SQLAlchemy definiti
│   │   └── database.py       ✅ Setup database
│   ├── analysis/
│   │   ├── __init__.py       ✅
│   │   └── visualize.py      ✅ Script visualizzazione
│   └── utils/
│       └── __init__.py       ✅
├── data/
│   ├── raw/
│   │   ├── comuni_test.json  ✅ Dati comuni salvati
│   │   └── bilanci_test.json ✅ Bilanci esempio
│   └── processed/
│       └── confronto_comuni.png ✅ Grafico generato
├── notebooks/              ✅ Cartella creata
├── tests/                 ✅ Cartella creata
├── docs/                  ✅ Cartella creata
├── config/                ✅ Cartella creata
├── .gitignore            ✅ Configurato
├── .env                  ✅ File ambiente locale
├── .env.example          ✅ Template variabili
├── README.md             ✅ Documentazione base
└── requirements.txt      ✅ Dipendenze definite
```

## ✅ **LAVORO COMPLETATO (FASE 0 e parte FASE 1)**

### 1. **Setup Ambiente** ✅
- Repository Git inizializzato e pushato su GitHub
- Conda environment "trasparenza" creato e configurato
- VS Code configurato per usare automaticamente l'environment
- Struttura cartelle completa

### 2. **FastAPI Server** ✅
```python
# src/main.py funzionante
# Server risponde su http://localhost:8000
# Endpoints: / e /health
```

### 3. **Collector ISTAT** ✅
```python
# src/collectors/istat_collector.py
# - Scarica lista comuni da CSV ISTAT
# - Filtra per regione
# - Ha dati di backup se ISTAT offline
# - Genera bilanci di esempio per testing
```

### 4. **Database Models** ✅
```python
# src/database/models.py
# Tabelle definite:
# - Comune (id, codice, nome, provincia, regione, popolazione)
# - Bilancio (id, comune_id, anno, dati JSON)
# - UtenteSegnaazione (feedback cittadini)
```

### 5. **Visualizzazione** ✅
```python
# src/analysis/visualize.py
# - Carica dati da JSON
# - Genera grafici confronto comuni
# - Salva PNG in data/processed/
```

### 6. **Dati di Test** ✅
- `data/raw/comuni_test.json`: Lista 5 comuni Lazio
- `data/raw/bilanci_test.json`: Bilanci esempio Roma, Albano, Marino

## 🚀 **FASI DA COMPLETARE - ROADMAP AGGIORNATA**

### **FASE 1: Completamento Data Collection** (1 settimana)
**Status**: 40% completato

#### TODO:
1. **Trovare API funzionanti per bilanci reali**
   - Testare: https://www.openbilanci.it/api/v1/
   - Provare: MinisteroInterno API
   - Alternative: Scraping sito Comuni

2. **Creare collector unificato**
```python
# src/collectors/unified_collector.py
# - Gestisce multiple fonti dati
# - Cache locale per ridurre chiamate API
# - Gestione errori robusta
```

3. **Test su 20-30 comuni pilota**
   - 10 piccoli (<5k abitanti)
   - 10 medi (5k-50k)
   - 10 grandi (>50k)

---

### **FASE 2: Database e Pipeline** (2 settimane)
**Status**: 20% completato

#### TODO:
1. **Setup PostgreSQL locale**
```bash
# Installare PostgreSQL 15+
# Creare database: trasparenza_comuni
# Configurare .env con DATABASE_URL
```

2. **Completare database.py**
```python
# - Connection pooling
# - Migrations con Alembic
# - CRUD operations
```

3. **ETL Pipeline**
```python
# src/etl/pipeline.py
# - Extract: da API/CSV
# - Transform: normalizzazione dati
# - Load: in PostgreSQL
# - Scheduling con APScheduler
```

4. **Data Quality checks**
```python
# src/utils/validators.py
# - Verifica completezza dati
# - Controllo anomalie
# - Report qualità
```

---

### **FASE 3: API e Dashboard Base** (3 settimane)
**Status**: 5% completato

#### TODO:
1. **Espandere FastAPI**
```python
# Endpoints da creare:
# GET /api/comuni - lista paginata
# GET /api/comuni/{id} - dettaglio
# GET /api/comuni/{id}/bilanci - serie storica
# GET /api/confronta - confronto comuni
# GET /api/statistiche/regione/{nome}
```

2. **Frontend React/Streamlit**
   - Decidere: React (più professionale) o Streamlit (più veloce)?
   - Homepage con mappa Italia
   - Pagina dettaglio comune
   - Grafici interattivi (Chart.js/Plotly)

3. **Caching Redis**
   - Cache query database
   - Cache chiamate API esterne
   - TTL configurabile

---

### **FASE 4: Analisi e AI** (2 settimane)
**Status**: 0% completato

#### TODO:
1. **Anomaly Detection**
```python
# src/analysis/anomalies.py
# - Statistical outliers (z-score)
# - Confronto con comuni simili
# - Trend analysis
```

2. **LLM Integration**
```python
# src/ai/llm_reporter.py
# - Ollama locale (Llama 3/Mistral)
# - Generazione report naturali
# - Q&A sui dati
```

3. **Insights automatici**
   - Report mensili per comune
   - Alert su spese anomale
   - Confronti best practices

---

### **FASE 5: Deploy e Produzione** (2 settimane)
**Status**: 0% completato

#### TODO:
1. **Containerizzazione**
```dockerfile
# Dockerfile per app
# docker-compose.yml per stack completo
```

2. **Deploy su Cloud gratuito**
   - Railway.app / Fly.io per backend
   - Vercel/Netlify per frontend
   - Supabase per PostgreSQL

3. **Monitoring**
   - Sentry per errori
   - Plausible per analytics
   - Uptime monitoring

---

## 🐛 **PROBLEMI NOTI DA RISOLVERE**

1. **BDAP API non funziona** (bdap_collector.py)
   - URL cambiato o serve autenticazione
   - TODO: Investigare documentazione ufficiale MEF

2. **Dati bilanci sono mock**
   - Attualmente usiamo dati esempio
   - TODO: Trovare fonte reale accessibile

3. **Test coverage mancante**
   - TODO: Scrivere unit test con pytest

---

## 💻 **COMANDI UTILI PER SVILUPPO**

```bash
# Attivare ambiente (già configurato in VS Code)
conda activate trasparenza

# Installare nuove dipendenze
pip install nome-pacchetto
pip freeze > requirements.txt

# Eseguire server FastAPI
cd src
python main.py

# Eseguire collector test
python collectors/istat_collector.py

# Git workflow
git add .
git commit -m "descrizione"
git push

# Creare migrazione database (quando implementato)
alembic revision --autogenerate -m "descrizione"
alembic upgrade head
```

---

## 🎯 **PROSSIMI 3 STEP IMMEDIATI**

1. **PRIORITÀ 1**: Trova API funzionante per bilanci reali
   - Testa OpenBilanci API
   - Esplora portale dati.gov.it
   - Verifica MinisteroInterno

2. **PRIORITÀ 2**: Completa database PostgreSQL
   - Installa PostgreSQL locale
   - Implementa migrations Alembic
   - Crea script popolamento dati

3. **PRIORITÀ 3**: Crea prima dashboard minima
   - Usa Streamlit per prototipo veloce
   - Mostra lista comuni
   - Grafico spese base

---

## 📚 **RISORSE E DOCUMENTAZIONE**

- **API Pubbliche da esplorare**:
  - SIOPE: https://www.siope.it/
  - OpenBilanci: https://www.openbilanci.it/
  - ANAC: https://www.anticorruzione.it/-/open-data
  - Dati.gov.it: https://www.dati.gov.it/

- **Tech Stack**:
  - FastAPI: https://fastapi.tiangolo.com/
  - SQLAlchemy: https://www.sqlalchemy.org/
  - Streamlit: https://streamlit.io/
  - Pandas: https://pandas.pydata.org/

---

## ❓ **DOMANDE CHIAVE DA RISOLVERE**

1. Frontend: **React** (professionale) o **Streamlit** (rapido)?
2. Database: Continuare con **PostgreSQL** o usare **SQLite** per semplicità?
3. Deploy: **Railway**/Fly.io o hosting **VPS economico**?
4. Priorità: Focus su **più comuni** o **più features** per pochi comuni?

---

## 🆘 **HELP NEEDED**

Per continuare efficacemente, ho bisogno di:
1. Decidere le priorità tra le fasi
2. Trovare API pubbliche funzionanti per bilanci
3. Scegliere tecnologie per frontend
4. Definire MVP (Minimum Viable Product)

**Sono Alberto, sto sviluppando questo progetto da solo in Python/FastAPI su Windows con VS Code e Conda. La FASE 0 è completa, ho iniziato la FASE 1 ma le API BDAP non funzionano. Help me continue!**
