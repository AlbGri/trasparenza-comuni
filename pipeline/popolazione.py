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

from pipeline.anagrafica import VARIAZIONI, leggi_variazioni
from pipeline.fonti import (
    PRIMA_DATA_POSAS, PRIMO_ANNO, PROCESSED, RAW, URL_POSAS, URL_RICOSTRUZIONE, URL_VARIAZIONI,
)
from pipeline.scarico import Registro, anni_pubblicati, scarica_file

log = logging.getLogger(__name__)

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


def applica_cambi_di_codice(popolazione: pd.DataFrame, variazioni: pd.DataFrame) -> pd.DataFrame:
    """Riporta sul codice nuovo i residenti di un comune che ha cambiato provincia e codice.

    Una riga passa al codice nuovo solo dove il codice nuovo non ha gia' un valore e solo se
    compare nei file ISTAT a qualche data: un codice che ISTAT non usa ancora (come quelli delle
    nuove province sarde) non si inventa.
    """
    cambi = variazioni[variazioni["tipo"].str.contains("AP")]
    cambi = cambi[cambi["codice"] != cambi["codice_associato"]]
    nuovo = popolazione["codice_istat"].map(cambi.set_index("codice")["codice_associato"])
    gia_presenti = pd.MultiIndex.from_frame(popolazione[["codice_istat", "anno"]])
    libero = ~pd.MultiIndex.from_arrays([nuovo, popolazione["anno"]]).isin(gia_presenti)
    da_spostare = nuovo.isin(set(popolazione["codice_istat"])) & libero
    popolazione = popolazione.copy()
    popolazione.loc[da_spostare, "codice_istat"] = nuovo[da_spostare]
    return popolazione


def aggiorna(registro: Registro, sessione: requests.Session) -> bool:
    """Scarica i file ISTAT e riscrive `popolazione` se qualcosa e' cambiato.

    Le date vanno dal 1 gennaio dopo il primo anno di bilancio all'ultimo file POSAS pubblicato.

    Returns:
        True se la tabella e' stata riscritta.
    """
    date_posas = anni_pubblicati(
        PRIMA_DATA_POSAS, lambda data: URL_POSAS.format(anno=data), sessione
    )
    date_ricostruzione = set(range(PRIMO_ANNO + 1, PRIMA_DATA_POSAS))
    zip_ricostruzione = RAW / "istat" / "PopolazioneEta-Territorio-Comuni.zip"
    zip_posas = {data: RAW / "istat" / f"POSAS_{data}_it_Comuni.zip" for data in date_posas}

    scarica_file(URL_RICOSTRUZIONE, zip_ricostruzione, registro, sessione)
    scarica_file(URL_VARIAZIONI, VARIAZIONI, registro, sessione)
    for data, percorso in zip_posas.items():
        scarica_file(URL_POSAS.format(anno=data), percorso, registro, sessione)
    destinazione = PROCESSED / "popolazione.parquet"
    # le variazioni possono essere arrivate con il passo dell'anagrafica: conta la data dei file
    ingressi = [zip_ricostruzione, VARIAZIONI, *zip_posas.values()]
    if destinazione.exists() and destinazione.stat().st_mtime > max(
        percorso.stat().st_mtime for percorso in ingressi
    ):
        return False

    parti = [leggi_posas(percorso).assign(al_1_gennaio=data) for data, percorso in zip_posas.items()]
    with zipfile.ZipFile(zip_ricostruzione) as archivio:
        for nome in archivio.namelist():
            testo = io.TextIOWrapper(archivio.open(nome), encoding="utf-8").read()
            parti.append(leggi_ricostruzione(testo, date_ricostruzione))
    popolazione = pd.concat(parti)
    popolazione["anno"] = popolazione["al_1_gennaio"] - 1
    popolazione = popolazione[["codice_istat", "anno", "al_1_gennaio", "residenti"]]
    popolazione = applica_cambi_di_codice(popolazione, leggi_variazioni(VARIAZIONI))
    if popolazione.duplicated(["codice_istat", "anno"]).any():
        raise ValueError("popolazione: comuni ripetuti nello stesso anno")
    popolazione.sort_values(["anno", "codice_istat"]).to_parquet(destinazione, index=False)
    log.info(
        "popolazione: %d righe, anni di bilancio %d-%d",
        len(popolazione), popolazione["anno"].min(), popolazione["anno"].max(),
    )
    return True
