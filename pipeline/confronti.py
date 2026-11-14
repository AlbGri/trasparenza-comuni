"""Gruppi di comuni simili, valori pro capite, percentili del gruppo e posizione del comune.

Il gruppo e' fascia di abitanti per area (regioni ordinarie in quattro aree, ogni regione
speciale a se'). Sotto i 20 comuni con rendiconto e popolazione si allarga: alle regioni dello
stesso tipo (ordinarie o speciali) nella stessa fascia, poi all'Italia. Le speciali non si
mescolano mai alle ordinarie prima del livello Italia.
"""
import logging

import duckdb
import pandas as pd

from pipeline.fonti import PROCESSED

log = logging.getLogger(__name__)

LIMITI_FASCE = [0, 1_000, 5_000, 20_000, 60_000, 250_000, float("inf")]
NOMI_FASCE = {
    1: "sotto 1.000", 2: "1.000-5.000", 3: "5.000-20.000", 4: "20.000-60.000",
    5: "60.000-250.000", 6: "oltre 250.000",
}
AREE_ORDINARIE = {
    "01": "Nord-ovest", "03": "Nord-ovest", "07": "Nord-ovest",
    "05": "Nord-est", "08": "Nord-est",
    "09": "Centro", "10": "Centro", "11": "Centro", "12": "Centro",
}
SUD = "Sud"
TIPI = {"ordinaria": "regioni ordinarie", "speciale": "regioni speciali"}
ITALIA = "Italia"
LIVELLI = ["area", "tipo di regione", "Italia"]
MINIMO_GRUPPO = 20

# Voci pro capite: impegni della spesa e accertamenti delle entrate (competenza), senza partite
# di giro e anticipazioni. `fonte` dice di quale tabella il comune deve essere presente
# perche' una voce assente valga zero.
VOCI = """
SELECT cf, 'spese' AS fonte, 'spesa_titolo' AS misura, titolo AS codice,
    sum(impegni) AS importo FROM spese WHERE NOT esclusa GROUP BY ALL
UNION ALL
SELECT cf, 'spese', 'spesa_corrente_missione', missione, sum(impegni)
    FROM spese WHERE NOT esclusa AND titolo = '01' GROUP BY ALL
UNION ALL
SELECT cf, 'spese', 'spesa_corrente_programma', missione || programma, sum(impegni)
    FROM spese WHERE NOT esclusa AND titolo = '01' GROUP BY ALL
UNION ALL
SELECT cf, 'entrate', 'entrate_titolo', titolo, sum(accertamenti)
    FROM entrate WHERE NOT esclusa GROUP BY ALL
UNION ALL
SELECT cf, 'entrate', 'entrate_proprie', '01+03', sum(accertamenti)
    FROM entrate WHERE titolo IN ('01', '03') GROUP BY ALL
"""


def residenti_per_ente(enti: pd.DataFrame, popolazione: pd.DataFrame) -> pd.DataFrame:
    """Residenti di ogni ente per anno di bilancio (al 1 gennaio dell'anno dopo).

    Nell'anno in cui si estingue l'ente non c'e' piu' al 1 gennaio successivo: valgono i
    residenti al 1 gennaio dello stesso anno, e `al_1_gennaio` lo dice.
    """
    colonne = ["cf", "anno", "al_1_gennaio", "residenti"]
    base = enti[["cf", "codice_istat"]].merge(popolazione, on="codice_istat")[colonne]
    estinti = enti[enti["stato"] == "estinto"]
    ultimo_anno = estinti[["cf", "codice_istat"]].assign(
        anno=estinti["data_cessazione"].dt.year
    )
    inizio_anno = popolazione.assign(anno=popolazione["anno"] + 1)
    ripiego = ultimo_anno.merge(inizio_anno, on=["codice_istat", "anno"])[colonne]
    return pd.concat([base, ripiego]).drop_duplicates(["cf", "anno"]).reset_index(drop=True)


def costruisci_gruppi(
    enti: pd.DataFrame, consegne: pd.DataFrame, residenti: pd.DataFrame
) -> pd.DataFrame:
    """Gruppo di confronto di ogni ente esistente, anno per anno.

    Returns:
        Una riga per ente e anno (esclusi gli anni in cui non esisteva) con fascia, area,
        `livello` e `ambito` del gruppo scelto. Senza popolazione fascia e gruppo restano vuoti.
    """
    gruppi = consegne[consegne["stato"] != "non esisteva"].merge(
        enti[["cf", "codice_regione", "regione", "tipo_regione"]], on="cf"
    )
    gruppi = gruppi.merge(residenti, on=["cf", "anno"], how="left")
    gruppi["fascia"] = pd.cut(
        gruppi["residenti"], LIMITI_FASCE, right=False, labels=list(NOMI_FASCE)
    ).astype("Int8")
    ordinaria = gruppi["tipo_regione"] == "ordinaria"
    gruppi["area"] = gruppi["regione"].where(
        ~ordinaria, gruppi["codice_regione"].map(AREE_ORDINARIE).fillna(SUD)
    )
    candidati = _ambiti_candidati(gruppi)
    utili = (gruppi["stato"] == "consegnato") & gruppi["fascia"].notna()
    gruppi["livello"] = pd.NA
    gruppi["ambito"] = pd.NA
    for livello in reversed(LIVELLI):
        ambito = candidati[livello]
        quanti = (
            gruppi[utili].groupby(["anno", "fascia", ambito[utili]]).size()
            .reindex(pd.MultiIndex.from_arrays([gruppi["anno"], gruppi["fascia"], ambito]))
            .fillna(0)
            .to_numpy()
        )
        basta = gruppi["fascia"].notna() & (quanti >= MINIMO_GRUPPO)
        if livello == ITALIA:
            basta = gruppi["fascia"].notna()
        gruppi.loc[basta, "livello"] = livello
        gruppi.loc[basta, "ambito"] = ambito[basta]
    colonne = [
        "cf", "anno", "stato", "residenti", "al_1_gennaio", "fascia", "area", "livello", "ambito",
    ]
    return gruppi[colonne].sort_values(["anno", "cf"]).reset_index(drop=True)


def _ambiti_candidati(gruppi: pd.DataFrame) -> dict[str, pd.Series]:
    """Ambito di ciascun livello per ogni riga: area, tipo di regione, Italia."""
    ordinaria = gruppi["area"].isin(set(AREE_ORDINARIE.values()) | {SUD})
    return {
        "area": gruppi["area"],
        "tipo di regione": ordinaria.map({True: TIPI["ordinaria"], False: TIPI["speciale"]}),
        "Italia": pd.Series(ITALIA, index=gruppi.index),
    }


def dimensione_gruppi(gruppi: pd.DataFrame) -> pd.DataFrame:
    """Comuni di ogni gruppo usato, con quanti hanno e quanti non hanno il rendiconto.

    Un gruppo allargato conta tutti i comuni del suo ambito, anche quelli che hanno un gruppo
    piu' stretto. I comuni senza popolazione non hanno fascia: sono contati per area, con
    fascia e livello vuoti.
    """
    candidati = _ambiti_candidati(gruppi)
    parti = []
    for livello in LIVELLI:
        membri = gruppi.assign(ambito=candidati[livello], livello=livello)
        usati = gruppi.loc[gruppi["livello"] == livello, ["anno", "fascia", "ambito"]]
        parti.append(membri.merge(usati.drop_duplicates(), on=["anno", "fascia", "ambito"]))
    senza = gruppi[gruppi["fascia"].isna()].assign(ambito=lambda g: g["area"], livello=pd.NA)
    tutti = pd.concat(parti + [senza])
    tutti["consegnati"] = tutti["stato"] == "consegnato"
    dimensioni = tutti.groupby(
        ["anno", "fascia", "livello", "ambito"], dropna=False, observed=True
    ).agg(comuni=("cf", "size"), consegnati=("consegnati", "sum"))
    dimensioni["non_consegnati"] = dimensioni["comuni"] - dimensioni["consegnati"]
    return dimensioni.reset_index()


def calcola_anno(
    spese: pd.DataFrame | str, entrate: pd.DataFrame | str, gruppi: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pro capite, posizione nel gruppo e percentili dei gruppi per un anno.

    Una voce che il comune non ha vale zero, se il comune e' nella tabella di quella voce.
    La posizione e' la percentuale degli altri comuni del gruppo con un valore piu' basso.

    Args:
        spese, entrate: tabelle dell'anno, o percorso del Parquet.
        gruppi: gruppi dell'anno, da `costruisci_gruppi`.

    Returns:
        (procapite, confronti): una riga per comune e voce; una riga per gruppo usato e voce.
    """
    con = duckdb.connect()
    for nome, tabella in (("spese", spese), ("entrate", entrate)):
        if isinstance(tabella, str):
            con.execute(f"CREATE VIEW {nome} AS SELECT * FROM read_parquet('{tabella}')")
        else:
            con.register(nome, tabella)
    anno = int(gruppi["anno"].iloc[0])
    validi = gruppi[(gruppi["stato"] == "consegnato") & gruppi["fascia"].notna()].copy()
    candidati = _ambiti_candidati(validi)
    validi["ambito_tipo"] = candidati["tipo di regione"]
    validi["fascia"] = validi["fascia"].astype(int)
    con.register("gruppi", validi)
    con.execute(f"""
        CREATE TABLE valori AS
        WITH voci AS ({VOCI}),
        elenco AS (SELECT DISTINCT fonte, misura, codice FROM voci),
        presenti AS (
            SELECT DISTINCT cf, 'spese' AS fonte FROM spese
            UNION SELECT DISTINCT cf, 'entrate' FROM entrate
        )
        SELECT p.cf, e.misura, e.codice, coalesce(v.importo, 0)::DOUBLE AS importo,
            coalesce(v.importo, 0)::DOUBLE / g.residenti AS procapite,
            g.fascia, g.area, g.ambito_tipo, g.livello, g.ambito
        FROM presenti p
        JOIN elenco e USING (fonte)
        JOIN gruppi g ON g.cf = p.cf
        LEFT JOIN voci v ON v.cf = p.cf AND v.misura = e.misura AND v.codice = e.codice
    """)
    procapite = con.execute(f"""
        SELECT cf, {anno}::SMALLINT AS anno, misura, codice, importo, procapite,
            100 * CASE livello
                WHEN 'area' THEN percent_rank() OVER (
                    PARTITION BY misura, codice, fascia, area ORDER BY procapite)
                WHEN 'tipo di regione' THEN percent_rank() OVER (
                    PARTITION BY misura, codice, fascia, ambito_tipo ORDER BY procapite)
                ELSE percent_rank() OVER (PARTITION BY misura, codice, fascia ORDER BY procapite)
            END AS posizione
        FROM valori ORDER BY cf, misura, codice
    """).df()
    confronti = con.execute(f"""
        WITH membri AS (
            SELECT misura, codice, fascia, area AS ambito, procapite FROM valori
            UNION ALL SELECT misura, codice, fascia, ambito_tipo, procapite FROM valori
            UNION ALL SELECT misura, codice, fascia, '{ITALIA}', procapite FROM valori
        ),
        usati AS (SELECT DISTINCT fascia, livello, ambito FROM valori)
        SELECT {anno}::SMALLINT AS anno, misura, codice, fascia::TINYINT AS fascia, livello,
            ambito, count(*) AS comuni,
            quantile_cont(procapite, 0.10) AS p10, quantile_cont(procapite, 0.25) AS p25,
            quantile_cont(procapite, 0.50) AS mediana, quantile_cont(procapite, 0.75) AS p75,
            quantile_cont(procapite, 0.90) AS p90
        FROM membri JOIN usati USING (fascia, ambito)
        GROUP BY ALL ORDER BY misura, codice, fascia, ambito
    """).df()
    return procapite, confronti


def aggiorna() -> bool:
    """Ricalcola gruppi, pro capite e confronti se una tabella a monte e' cambiata.

    Returns:
        True se le tabelle sono state riscritte.
    """
    ingressi = [PROCESSED / n for n in ("enti.parquet", "consegne.parquet", "popolazione.parquet")]
    ingressi += sorted((PROCESSED / "spese").glob("*.parquet"))
    ingressi += sorted((PROCESSED / "entrate").glob("*.parquet"))
    uscite = [PROCESSED / n for n in ("gruppi.parquet", "dimensione_gruppi.parquet")]
    uscite.append(PROCESSED / "confronti.parquet")
    if all(u.exists() for u in uscite) and min(u.stat().st_mtime for u in uscite) > max(
        i.stat().st_mtime for i in ingressi
    ):
        return False

    enti = pd.read_parquet(PROCESSED / "enti.parquet")
    residenti = residenti_per_ente(enti, pd.read_parquet(PROCESSED / "popolazione.parquet"))
    gruppi = costruisci_gruppi(enti, pd.read_parquet(PROCESSED / "consegne.parquet"), residenti)
    senza = gruppi[(gruppi["stato"] == "consegnato") & gruppi["fascia"].isna()]
    if len(senza):
        log.warning(
            "comuni con rendiconto ma senza popolazione, fuori dai confronti: %s",
            senza.groupby("anno").size().to_dict(),
        )
    confronti = []
    for anno, gruppi_anno in gruppi.groupby("anno"):
        spese = PROCESSED / "spese" / f"{anno}.parquet"
        entrate = PROCESSED / "entrate" / f"{anno}.parquet"
        procapite, confronti_anno = calcola_anno(
            spese.as_posix(), entrate.as_posix(), gruppi_anno
        )
        destinazione = PROCESSED / "procapite" / f"{anno}.parquet"
        destinazione.parent.mkdir(exist_ok=True)
        procapite.to_parquet(destinazione, index=False)
        confronti.append(confronti_anno)
        log.info("confronti %d: %d valori pro capite", anno, len(procapite))
    gruppi.to_parquet(PROCESSED / "gruppi.parquet", index=False)
    dimensione_gruppi(gruppi).to_parquet(PROCESSED / "dimensione_gruppi.parquet", index=False)
    pd.concat(confronti).to_parquet(PROCESSED / "confronti.parquet", index=False)
    return True
