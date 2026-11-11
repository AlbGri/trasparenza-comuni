"""Anagrafica degli enti e tabella delle consegne.

Il codice ISTAT si ricava dalla catena codice fiscale (BDAP) -> codice catastale (IndicePA) ->
elenco ISTAT; i casi che la catena non risolve stanno in `eccezioni_enti.csv`.
"""
import logging
from pathlib import Path

import pandas as pd
import requests

from pipeline.fonti import PROCESSED, RAW, URL_ELENCO_ISTAT, URL_INDICEPA
from pipeline.scarico import Registro, richiesta, scarica_file

log = logging.getLogger(__name__)

ECCEZIONI = Path(__file__).with_name("eccezioni_enti.csv")
ELENCO_ISTAT = RAW / "istat" / "Elenco-comuni-italiani.csv"
ENTI_IPA = RAW / "indicepa" / "enti.xlsx"
REGIONI_SPECIALI = {"02", "04", "06", "19", "20"}


def leggi_elenco_istat(percorso: Path) -> pd.DataFrame:
    """Elenco ISTAT dei comuni; colonne per posizione, perche' i nomi contengono a capo."""
    elenco = pd.read_csv(percorso, sep=";", encoding="latin-1", dtype=str)
    elenco = elenco.iloc[:, [0, 4, 6, 10, 11, 19]]
    elenco.columns = ["codice_regione", "codice_istat", "nome", "regione", "provincia", "catastale"]
    return elenco


def costruisci_enti(
    soggetti: pd.DataFrame, ipa: pd.DataFrame, istat: pd.DataFrame, eccezioni: pd.DataFrame
) -> pd.DataFrame:
    """Una riga per ente BDAP, con codice ISTAT, stato e successore.

    Args:
        soggetti: comuni dei rendiconti di tutti gli anni (cf, anno e anagrafica BDAP).
        ipa: IndicePA con le colonne `cf` e `catastale`.
        istat: elenco ISTAT letto da `leggi_elenco_istat`.
        eccezioni: codici ISTAT assegnati a mano (`cf`, `codice_istat`).

    Raises:
        ValueError: se due enti attivi finiscono sullo stesso codice ISTAT o se un'eccezione
            cita un codice fiscale o un codice ISTAT che non esiste.
    """
    # BDAP applica a tutti gli anni l'anagrafica corrente: vale la riga dell'ultimo anno
    enti = soggetti.sort_values("anno").drop_duplicates("cf", keep="last")
    enti = enti.merge(ipa, on="cf", how="left")
    enti = enti.merge(istat[["catastale", "codice_istat"]], on="catastale", how="left")

    sconosciuti = set(eccezioni["cf"]) - set(enti["cf"])
    sconosciuti |= set(eccezioni["codice_istat"]) - set(istat["codice_istat"])
    if sconosciuti:
        raise ValueError(f"eccezioni_enti.csv cita valori inesistenti: {sorted(sconosciuti)}")
    a_mano = enti["cf"].map(eccezioni.set_index("cf")["codice_istat"])
    enti["codice_istat"] = a_mano.fillna(enti["codice_istat"])

    enti["stato"] = enti["data_cessazione"].notna().map({True: "estinto", False: "attivo"})
    attivi = enti[(enti["stato"] == "attivo") & enti["codice_istat"].notna()]
    doppi = attivi[attivi["codice_istat"].duplicated(keep=False)]
    if len(doppi):
        raise ValueError(
            "piu' enti attivi sullo stesso codice ISTAT, da risolvere in eccezioni_enti.csv:\n"
            + doppi[["cf", "denominazione", "codice_istat"]].to_string(index=False)
        )

    # sull'ente estinto BDAP scrive provincia e comune di chi lo ha assorbito
    codice_bdap_istat = enti["codice_provincia"].str.zfill(3) + enti["codice_comune"].str.zfill(3)
    successore = codice_bdap_istat.map(attivi.set_index("codice_istat")["cf"])
    enti["successore"] = successore.where(enti["stato"] == "estinto")

    per_codice = istat.set_index("codice_istat")
    riferimento = enti["codice_istat"].fillna(codice_bdap_istat)
    enti["catastale"] = enti["codice_istat"].map(per_codice["catastale"])
    enti["nome"] = (
        enti["codice_istat"]
        .map(per_codice["nome"])
        .fillna(enti["denominazione"].str.removeprefix("COMUNE DI ").str.title())
    )
    enti["provincia"] = riferimento.map(per_codice["provincia"]).fillna(
        enti["provincia"].str.title()
    )
    regioni = istat.drop_duplicates("codice_regione").set_index("codice_regione")["regione"]
    enti["regione"] = enti["codice_regione"].map(regioni)
    enti["tipo_regione"] = (
        enti["codice_regione"].isin(REGIONI_SPECIALI).map({True: "speciale", False: "ordinaria"})
    )
    colonne = [
        "cf", "codice_bdap", "codice_istat", "catastale", "nome", "provincia", "regione",
        "tipo_regione", "stato", "data_cessazione", "successore",
    ]
    return enti[colonne].sort_values("cf").reset_index(drop=True)


def costruisci_consegne(soggetti: pd.DataFrame, enti: pd.DataFrame) -> pd.DataFrame:
    """Una riga per ente e anno: rendiconto presente oppure no."""
    anni = pd.DataFrame({"anno": sorted(soggetti["anno"].unique())})
    consegne = enti[["cf"]].merge(anni, how="cross")
    presenti = soggetti[["cf", "anno"]].assign(presente=True)
    consegne = consegne.merge(presenti, on=["cf", "anno"], how="left")
    consegne["presente"] = consegne["presente"].notna()
    return consegne


def aggiorna(registro: Registro, sessione: requests.Session, forza: bool) -> bool:
    """Scarica elenco ISTAT e IndicePA e riscrive `enti` e `consegne` se qualcosa e' cambiato.

    Args:
        forza: True se i rendiconti a monte sono stati aggiornati in questo lancio.

    Returns:
        True se le tabelle sono state riscritte.
    """
    risorse = richiesta(sessione, URL_INDICEPA).json()["result"]["resources"]
    url_ipa = next(r["url"] for r in risorse if r["url"].endswith(".xlsx"))
    nuovi = [
        scarica_file(url_ipa, ENTI_IPA, registro, sessione),
        scarica_file(URL_ELENCO_ISTAT, ELENCO_ISTAT, registro, sessione),
    ]
    file_enti = PROCESSED / "enti.parquet"
    file_consegne = PROCESSED / "consegne.parquet"
    aggiornato = (
        file_enti.exists()
        and file_consegne.exists()
        and file_enti.stat().st_mtime > ECCEZIONI.stat().st_mtime
    )
    if aggiornato and not forza and not any(nuovi):
        return False

    soggetti = pd.concat(
        pd.read_parquet(f) for f in sorted((PROCESSED / "soggetti").glob("*.parquet"))
    )
    ipa = pd.read_excel(
        ENTI_IPA, dtype=str, usecols=["Codice_fiscale_ente", "Codice_catastale_comune"]
    ).rename(columns={"Codice_fiscale_ente": "cf", "Codice_catastale_comune": "catastale"})
    istat = leggi_elenco_istat(ELENCO_ISTAT)
    eccezioni = pd.read_csv(ECCEZIONI, sep=";", dtype=str)
    enti = costruisci_enti(soggetti, ipa, istat, eccezioni)
    senza_ente = set(istat["codice_istat"]) - set(enti["codice_istat"].dropna())
    if senza_ente:
        log.warning("comuni ISTAT senza ente BDAP in nessun anno: %s", sorted(senza_ente))
    enti.to_parquet(file_enti, index=False)
    costruisci_consegne(soggetti, enti).to_parquet(file_consegne, index=False)
    log.info(
        "enti: %d, di cui %d con codice ISTAT e %d estinti",
        len(enti), enti["codice_istat"].notna().sum(), (enti["stato"] == "estinto").sum(),
    )
    return True
