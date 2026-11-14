"""Numeri di controllo: a fine lancio si confrontano con quelli attesi in `controlli_attesi.csv`.

Il file contiene i numeri degli anni chiusi, verificati a mano sulle fonti. Un numero che non
torna a fonti invariate e' un errore della pipeline. Gli anni senza il numero dei comuni atteso
sono ancora aperti alle consegne: si riportano senza confronto.
"""
import logging
from pathlib import Path

import duckdb
import pandas as pd

from pipeline.fonti import PROCESSED

log = logging.getLogger(__name__)

ATTESI = Path(__file__).with_name("controlli_attesi.csv")
TOLLERANZE = {"comuni": 0, "residenti": 0, "mld": 0.005, "mediana": 1}


def misura(cartella: Path = PROCESSED) -> pd.DataFrame:
    """Numeri di controllo calcolati sulle tabelle prodotte: anno, misura, valore.

    Comuni e totali vengono dal dettaglio delle spese (spesa corrente = titolo 1 intero, netta
    = senza partite di giro e anticipazioni); le mediane sono della spesa corrente pro capite
    di tutta Italia, per fascia di abitanti.
    """
    con = duckdb.connect()
    totali = con.execute(f"""
        SELECT anno, count(DISTINCT cf) AS comuni,
            sum(impegni)::DOUBLE / 1e9 AS impegni_mld,
            sum(impegni) FILTER (titolo = '01')::DOUBLE / 1e9 AS spesa_corrente_mld,
            sum(impegni) FILTER (NOT esclusa)::DOUBLE / 1e9 AS spesa_netta_mld
        FROM read_parquet('{(cartella / "spese" / "*.parquet").as_posix()}') GROUP BY anno
    """).df()
    residenti = con.execute(f"""
        SELECT anno, sum(residenti)::DOUBLE AS residenti
        FROM read_parquet('{(cartella / "popolazione.parquet").as_posix()}') GROUP BY anno
    """).df()
    mediane = con.execute(f"""
        SELECT p.anno, 'mediana_fascia_' || g.fascia AS misura,
            quantile_cont(p.valore, 0.5) AS valore
        FROM read_parquet('{(cartella / "posizioni" / "*.parquet").as_posix()}') p
        JOIN read_parquet('{(cartella / "gruppi.parquet").as_posix()}') g USING (cf, anno)
        WHERE p.misura = 'spesa_titolo' AND p.codice = '01' GROUP BY ALL
    """).df()
    lunghe = [
        tabella.melt(id_vars="anno", var_name="misura", value_name="valore")
        for tabella in (totali, residenti)
    ]
    return pd.concat(lunghe + [mediane], ignore_index=True)


def confronta(misurati: pd.DataFrame, attesi: pd.DataFrame) -> pd.DataFrame:
    """Affianca valori misurati e attesi; `esito` e' vero se la differenza sta nella tolleranza.

    Un numero atteso che non si riesce a misurare conta come non tornato.
    """
    confronto = attesi.merge(misurati, on=["anno", "misura"], how="left")
    tolleranza = confronto["misura"].map(
        lambda nome: next(t for chiave, t in TOLLERANZE.items() if chiave in nome)
    )
    scarto = (confronto["valore"] - confronto["atteso"]).abs()
    # 1e-9: margine per gli errori di virgola mobile, non per i dati
    confronto["esito"] = scarto <= tolleranza + 1e-9
    return confronto


def esegui(cartella: Path = PROCESSED) -> bool:
    """Confronta e scrive nel log l'esito. Returns: True se tutti i numeri attesi tornano."""
    attesi = pd.read_csv(ATTESI, sep=";")
    misurati = misura(cartella)
    confronto = confronta(misurati, attesi)
    for riga in confronto[~confronto["esito"]].itertuples():
        log.warning(
            "controllo non tornato: %d %s atteso %s, misurato %s",
            riga.anno, riga.misura, riga.atteso, riga.valore,
        )
    chiusi = set(attesi.loc[attesi["misura"] == "comuni", "anno"])
    aperti = misurati[~misurati["anno"].isin(chiusi) & misurati["misura"].isin(
        ["comuni", "impegni_mld", "spesa_corrente_mld"]
    )]
    for anno, righe in aperti.groupby("anno"):
        valori = ", ".join(f"{r.misura} {r.valore:.2f}" for r in righe.itertuples())
        log.info("anno %d aperto alle consegne, senza confronto: %s", anno, valori)
    log.info(
        "controlli: %d su %d tornano", confronto["esito"].sum(), len(confronto)
    )
    return bool(confronto["esito"].all())
