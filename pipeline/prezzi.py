"""Indice dei prezzi al consumo (IPCA, media annua) per mostrare gli euro a prezzi costanti."""
import logging

import pandas as pd
import requests

from pipeline.fonti import PROCESSED, PRIMO_ANNO, URL_IPCA
from pipeline.scarico import Registro, richiesta

log = logging.getLogger(__name__)

DESTINAZIONE = PROCESSED / "prezzi.parquet"


def leggi_jsonstat(dati: dict) -> pd.DataFrame:
    """Serie annua dell'indice da una risposta JSON-stat di Eurostat con il solo asse del tempo.

    Returns:
        Colonne anno e indice (2015 = 100), dal primo anno dei rendiconti.
    """
    anni = dati["dimension"]["time"]["category"]["index"]
    serie = pd.DataFrame(
        {"anno": int(anno), "indice": dati["value"][str(posizione)]}
        for anno, posizione in anni.items()
        if str(posizione) in dati["value"]
    )
    return serie[serie["anno"] >= PRIMO_ANNO].sort_values("anno").reset_index(drop=True)


def aggiorna(registro: Registro, sessione: requests.Session) -> bool:
    """Riscrive la serie se Eurostat l'ha aggiornata.

    La risposta pesa un paio di KB: si chiede ogni volta e si confronta la data di
    aggiornamento che riporta.

    Returns:
        True se la tabella e' stata riscritta.
    """
    dati = richiesta(sessione, URL_IPCA).json()
    aggiornato = dati["updated"]
    if DESTINAZIONE.exists() and registro.invariato(URL_IPCA, "", aggiornato):
        return False
    leggi_jsonstat(dati).to_parquet(DESTINAZIONE, index=False)
    registro.registra(URL_IPCA, "", aggiornato)
    return True
