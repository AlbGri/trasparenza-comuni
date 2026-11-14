"""Anagrafica degli enti e tabella delle consegne.

Il codice ISTAT si ricava dalla catena codice fiscale (BDAP) -> codice catastale (IndicePA) ->
elenco ISTAT; i casi che la catena non risolve stanno in `eccezioni_enti.csv`. Gli enti estinti
prendono il codice che avevano, dal file ISTAT delle variazioni amministrative.
"""
import logging
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd
import requests

from pipeline.fonti import (
    PRIMO_ANNO, PROCESSED, RAW, URL_ELENCO_ISTAT, URL_INDICEPA, URL_VARIAZIONI,
)
from pipeline.scarico import Registro, richiesta, scarica_file

log = logging.getLogger(__name__)

ECCEZIONI = Path(__file__).with_name("eccezioni_enti.csv")
ELENCO_ISTAT = RAW / "istat" / "Elenco-comuni-italiani.csv"
ENTI_IPA = RAW / "indicepa" / "enti.xlsx"
VARIAZIONI = RAW / "istat" / "Variazioni-amministrative-e-territoriali-dal-1991.zip"
REGIONI_SPECIALI = {"02", "04", "06", "19", "20"}


def leggi_elenco_istat(percorso: Path) -> pd.DataFrame:
    """Elenco ISTAT dei comuni; colonne per posizione, perche' i nomi contengono a capo."""
    elenco = pd.read_csv(percorso, sep=";", encoding="latin-1", dtype=str)
    elenco = elenco.iloc[:, [0, 4, 6, 10, 11, 19]]
    elenco.columns = ["codice_regione", "codice_istat", "nome", "regione", "provincia", "catastale"]
    return elenco


def leggi_variazioni(zip_variazioni: Path) -> pd.DataFrame:
    """Variazioni amministrative ISTAT dal 1991, una riga per comune coinvolto.

    `tipo` contiene ES (estinzione), CS (costituzione), AP (passaggio di provincia, con nuovo
    codice), anche combinati (AQES); `codice_associato` e' il comune di arrivo o il nuovo codice.
    Colonne lette per posizione, come nell'elenco dei comuni.
    """
    with zipfile.ZipFile(zip_variazioni) as archivio:
        nome = next(n for n in archivio.namelist() if n.endswith(".csv"))
        with archivio.open(nome) as origine:
            dati = pd.read_csv(origine, sep=";", encoding="cp1252", dtype=str)
    variazioni = dati.iloc[:, [1, 4, 5, 8, 12]]
    variazioni.columns = ["tipo", "codice", "nome", "codice_associato", "data"]
    return variazioni.assign(
        tipo=variazioni["tipo"].str.strip(),
        data=pd.to_datetime(variazioni["data"], format="%d/%m/%Y"),
    )


def _chiave_nome(nome: pd.Series) -> pd.Series:
    """Nome senza accenti, apostrofi, spazi e maiuscole: "Cagno'" e "Cagnò" coincidono."""
    return nome.map(
        lambda testo: "".join(
            c for c in unicodedata.normalize("NFKD", testo).upper() if c.isascii() and c.isalnum()
        )
    )


def _codici_storici(enti: pd.DataFrame, variazioni: pd.DataFrame) -> pd.DataFrame:
    """Codice ISTAT e nome che gli enti estinti avevano, dalle estinzioni ISTAT.

    Si aggancia per nome e codice del comune di arrivo; se il comune di arrivo ha cambiato
    codice dopo la fusione, per nome soltanto, purche' il nome sia unico.

    Returns:
        Indice `cf`, colonne `codice_istat` e `nome`, solo per gli estinti agganciati.
    """
    estinzioni = variazioni[
        variazioni["tipo"].str.contains("ES")
        & (variazioni["data"] >= pd.Timestamp(PRIMO_ANNO, 1, 1))
    ].drop_duplicates(["codice", "codice_associato"])
    estinzioni = estinzioni.assign(chiave=_chiave_nome(estinzioni["nome"]))
    cercati = enti[(enti["stato"] == "estinto") & enti["codice_istat"].isna()]
    cercati = cercati.assign(
        chiave=_chiave_nome(cercati["denominazione"].str.removeprefix("COMUNE DI ")),
        codice_associato=cercati["successore"].map(enti.set_index("cf")["codice_istat"]),
    )[["cf", "chiave", "codice_associato"]]
    per_successore = cercati.merge(estinzioni, on=["chiave", "codice_associato"])
    unici = estinzioni.drop_duplicates("chiave", keep=False).drop(columns="codice_associato")
    per_nome = cercati[~cercati["cf"].isin(per_successore["cf"])].merge(unici, on="chiave")
    trovati = pd.concat([per_successore, per_nome]).set_index("cf")
    return trovati[["codice", "nome"]].rename(columns={"codice": "codice_istat"})


def costruisci_enti(
    soggetti: pd.DataFrame,
    ipa: pd.DataFrame,
    istat: pd.DataFrame,
    eccezioni: pd.DataFrame,
    variazioni: pd.DataFrame,
) -> pd.DataFrame:
    """Una riga per ente BDAP, con codice ISTAT, stato, successore e data di nascita.

    Gli estinti hanno il codice ISTAT che avevano: insieme ai codici dei comuni attivi forma
    un identificativo unico per ogni ente.

    Args:
        soggetti: comuni dei rendiconti di tutti gli anni (cf, anno e anagrafica BDAP).
        ipa: IndicePA con le colonne `cf` e `catastale`.
        istat: elenco ISTAT letto da `leggi_elenco_istat`.
        eccezioni: codici ISTAT assegnati a mano (`cf`, `codice_istat`).
        variazioni: variazioni amministrative lette da `leggi_variazioni`.

    Raises:
        ValueError: se due enti finiscono sullo stesso codice ISTAT, se un estinto non trova
            il suo codice storico o se un'eccezione cita un codice fiscale o un codice ISTAT
            che non esiste.
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

    storici = _codici_storici(enti, variazioni)
    enti["codice_istat"] = enti["codice_istat"].fillna(enti["cf"].map(storici["codice_istat"]))
    enti["nome"] = enti["cf"].map(storici["nome"]).fillna(enti["nome"])
    senza_codice = enti[(enti["stato"] == "estinto") & enti["codice_istat"].isna()]
    if len(senza_codice):
        raise ValueError(
            "estinti senza codice ISTAT storico, da risolvere in eccezioni_enti.csv:\n"
            + senza_codice[["cf", "denominazione"]].to_string(index=False)
        )
    doppi = enti[enti["codice_istat"].notna() & enti["codice_istat"].duplicated(keep=False)]
    if len(doppi):
        raise ValueError(
            "piu' enti sullo stesso codice ISTAT:\n"
            + doppi[["cf", "denominazione", "codice_istat"]].to_string(index=False)
        )
    costituzioni = variazioni[variazioni["tipo"].str.contains("CS")].groupby("codice")["data"]
    enti["data_istituzione"] = enti["codice_istat"].map(costituzioni.max())
    enti["data_cessazione"] = pd.to_datetime(enti["data_cessazione"], format="%d/%m/%Y")
    colonne = [
        "cf", "codice_bdap", "codice_istat", "catastale", "nome", "provincia", "codice_regione",
        "regione", "tipo_regione", "stato", "data_istituzione", "data_cessazione", "successore",
    ]
    return enti[colonne].sort_values("cf").reset_index(drop=True)


def costruisci_consegne(soggetti: pd.DataFrame, enti: pd.DataFrame) -> pd.DataFrame:
    """Una riga per ente e anno, con `stato` consegnato, non consegnato o non esisteva.

    "Non esisteva" vale per l'ente che non ha coperto l'intero anno (nato dopo il 1 gennaio o
    estinto prima del 31 dicembre) e non ha consegnato: il rendiconto di quell'anno, se c'e',
    e' del comune che lo ha preceduto o seguito.
    """
    anni = pd.DataFrame({"anno": sorted(soggetti["anno"].unique())})
    consegne = enti[["cf", "data_istituzione", "data_cessazione"]].merge(anni, how="cross")
    presenti = soggetti[["cf", "anno"]].assign(presente=True)
    consegne = consegne.merge(presenti, on=["cf", "anno"], how="left")
    inizio = pd.to_datetime(consegne["anno"].astype(str) + "-01-01")
    fine = pd.to_datetime(consegne["anno"].astype(str) + "-12-31")
    intero = ~(consegne["data_istituzione"] > inizio) & ~(consegne["data_cessazione"] < fine)
    consegne["stato"] = "non consegnato"
    consegne.loc[~intero, "stato"] = "non esisteva"
    consegne.loc[consegne["presente"].notna(), "stato"] = "consegnato"
    return consegne[["cf", "anno", "stato"]]


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
        scarica_file(URL_VARIAZIONI, VARIAZIONI, registro, sessione),
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
    enti = costruisci_enti(soggetti, ipa, istat, eccezioni, leggi_variazioni(VARIAZIONI))
    senza_ente = set(istat["codice_istat"]) - set(enti["codice_istat"].dropna())
    if senza_ente:
        log.warning("comuni ISTAT senza ente BDAP in nessun anno: %s", sorted(senza_ente))
    enti.to_parquet(file_enti, index=False)
    consegne = costruisci_consegne(soggetti, enti)
    consegne.to_parquet(file_consegne, index=False)
    log.info(
        "enti: %d, di cui %d con codice ISTAT e %d estinti",
        len(enti), enti["codice_istat"].notna().sum(), (enti["stato"] == "estinto").sum(),
    )
    log.info("consegne: %s", consegne["stato"].value_counts().to_dict())
    return True
