"""Popolazione residente per comune.

Per l'anno di bilancio N valgono i residenti al 1 gennaio N+1, cioe' a fine esercizio. Dal
1 gennaio 2019 c'e' un file POSAS per anno; prima si usa la ricostruzione ISTAT 2002-2019.
"""
import io
import logging
import re
import zipfile
from pathlib import Path

import pandas as pd
import requests

from pipeline.fonti import ANNI, PROCESSED, RAW, URL_POSAS, URL_RICOSTRUZIONE
from pipeline.scarico import Registro, scarica_file

log = logging.getLogger(__name__)

PRIMO_POSAS = 2019
ETA_TOTALE = "999"


def leggi_posas(zip_posas: Path) -> pd.DataFrame:
    """Residenti per comune da un file POSAS: la riga con eta' 999 e' il totale del comune.

    Le colonne cambiano da un anno all'altro, quindi si leggono per posizione: codice del
    comune la prima, eta' la terza, totale di maschi e femmine l'ultima.
    """
    with zipfile.ZipFile(zip_posas) as archivio:
        with archivio.open(archivio.namelist()[0]) as origine:
            dati = pd.read_csv(origine, sep=";", skiprows=1, encoding="utf-8-sig", dtype=str)
    totali = dati[dati.iloc[:, 2] == ETA_TOTALE]
    return pd.DataFrame(
        {"codice_istat": totali.iloc[:, 0].values, "residenti": totali.iloc[:, -1].astype(int)}
    ).reset_index(drop=True)


def leggi_ricostruzione(testo: str, date: set[int]) -> pd.DataFrame:
    """Residenti per comune da un CSV provinciale della ricostruzione 2002-2019.

    Il file ha una sezione per cittadinanza, un blocco per anno e per sesso e una colonna per
    eta': si tiene il blocco "Tutte le cittadinanze" / "Totale" e si sommano le eta'.

    Args:
        testo: contenuto del CSV.
        date: anni del 1 gennaio da estrarre.
    """
    righe = []
    anno, tutte, blocco = None, False, None
    for riga in testo.splitlines():
        if trovato := re.search(r"Anno: (\d{4})", riga):
            anno = int(trovato.group(1))
            tutte = "Tutte le cittadinanze" in riga
        elif riga.startswith("Codice comune;Comune;"):
            blocco = riga.split(";")[2]
        elif riga[:1].isdigit() and tutte and blocco == "Totale" and anno in date:
            campi = riga.split(";")
            righe.append((campi[0], anno, sum(int(valore) for valore in campi[2:])))
    return pd.DataFrame(righe, columns=["codice_istat", "al_1_gennaio", "residenti"])


def aggiorna(registro: Registro, sessione: requests.Session) -> bool:
    """Scarica i file ISTAT e riscrive `popolazione` se qualcosa e' cambiato.

    Returns:
        True se la tabella e' stata riscritta.
    """
    date = [anno + 1 for anno in ANNI]
    date_posas = [data for data in date if data >= PRIMO_POSAS]
    date_ricostruzione = {data for data in date if data < PRIMO_POSAS}
    zip_ricostruzione = RAW / "istat" / "PopolazioneEta-Territorio-Comuni.zip"
    zip_posas = {data: RAW / "istat" / f"POSAS_{data}_it_Comuni.zip" for data in date_posas}

    nuovi = [scarica_file(URL_RICOSTRUZIONE, zip_ricostruzione, registro, sessione)]
    nuovi += [
        scarica_file(URL_POSAS.format(anno=data), percorso, registro, sessione)
        for data, percorso in zip_posas.items()
    ]
    destinazione = PROCESSED / "popolazione.parquet"
    if destinazione.exists() and not any(nuovi):
        return False

    parti = [leggi_posas(percorso).assign(al_1_gennaio=data) for data, percorso in zip_posas.items()]
    with zipfile.ZipFile(zip_ricostruzione) as archivio:
        for nome in archivio.namelist():
            testo = io.TextIOWrapper(archivio.open(nome), encoding="utf-8").read()
            parti.append(leggi_ricostruzione(testo, date_ricostruzione))
    popolazione = pd.concat(parti)
    popolazione["anno"] = popolazione["al_1_gennaio"] - 1
    popolazione = popolazione[["codice_istat", "anno", "al_1_gennaio", "residenti"]]
    if popolazione.duplicated(["codice_istat", "anno"]).any():
        raise ValueError("popolazione: comuni ripetuti nello stesso anno")
    popolazione.sort_values(["anno", "codice_istat"]).to_parquet(destinazione, index=False)
    log.info("popolazione: %d righe, anni di bilancio %d-%d", len(popolazione), ANNI[0], ANNI[-1])
    return True
