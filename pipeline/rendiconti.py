"""Rendiconti di OpenBDAP: dal CSV dentro lo zip remoto al Parquet per anno, soli comuni."""
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import requests

from pipeline.fonti import PROCESSED, url_rendiconto
from pipeline.scarico import Registro, ZipRemoto

log = logging.getLogger(__name__)

CODIFICA = "cp1252"
TIPO_COMUNE = "ELCOMU"

# Partite di giro e anticipazioni: movimenti che non sono spesa ne' entrata vera. Della missione
# 60 (anticipazioni) la restituzione e' il titolo 5; resta nella spesa il titolo 1, gli
# interessi pagati davvero, come nel portale OpenBDAP.
MISSIONI_ESCLUSE = ("99",)
TITOLI_SPESA_ESCLUSI = ("05", "07")
TITOLI_ENTRATA_ESCLUSI = ("07", "09")


def _in(colonna: str, valori: tuple[str, ...]) -> str:
    return f'"{colonna}" IN ({", ".join(repr(v) for v in valori)})'


@dataclass
class Tabella:
    """Come si ricava una tabella da un CSV del rendiconto.

    Attributes:
        pacchetto: zip di OpenBDAP che contiene il file.
        file: parte finale del nome del CSV dentro lo zip.
        chiavi: nome uniforme -> colonna del CSV (testo).
        importi: nome uniforme -> colonna del CSV (numero decimale).
        calcolate: nome uniforme -> espressione SQL sulle colonne del CSV.
        testi: nome uniforme -> colonna del CSV con la descrizione di un codice.
        dal: primo anno in cui il file esiste.
    """

    pacchetto: str
    file: str
    chiavi: dict[str, str]
    importi: dict[str, str] = field(default_factory=dict)
    calcolate: dict[str, str] = field(default_factory=dict)
    testi: dict[str, str] = field(default_factory=dict)
    dal: int = 2016


TABELLE = {
    "spese": Tabella(
        pacchetto="Schemi di bilancio",
        file="SDB Spese.csv",
        chiavi={
            "missione": "Codice Missione Arconet",
            "programma": "Codice Programma Arconet",
            "titolo": "Codice Titolo Spese Arconet",
        },
        importi={
            "impegni": "Impegni",
            "pagamenti_totali": "Tot. Pag.",
            "previsioni_definitive": "Pre.  Def. in CC",
        },
        calcolate={
            "esclusa": _in("Codice Missione Arconet", MISSIONI_ESCLUSE)
            + " OR "
            + _in("Codice Titolo Spese Arconet", TITOLI_SPESA_ESCLUSI)
        },
        testi={
            "desc_missione": "Desc Missione Arconet",
            "desc_programma": "Desc Programma Arconet",
            "desc_titolo": "Desc Titolo Spese Arconet",
        },
    ),
    "entrate": Tabella(
        pacchetto="Schemi di bilancio",
        file="SDB Entrate.csv",
        chiavi={
            "titolo": "Codice Titolo Entrata Arconet",
            "tipologia": "Cod Tipologia Entrata Arconet",
        },
        importi={"accertamenti": "Accert. in CC", "riscossioni_totali": "Tot. Riscos."},
        calcolate={"esclusa": _in("Codice Titolo Entrata Arconet", TITOLI_ENTRATA_ESCLUSI)},
        testi={
            "desc_titolo": "Desc Titolo Entrata Arconet",
            "desc_tipologia": "Desc Tipologia Entrata Arconet",
        },
    ),
    # `Residui` e `Competenza di Gestione` sono riempite solo per riscossioni, pagamenti e
    # residui, e li' sommano al totale: il valore di ogni voce e' `Totale di Gestione`.
    "risultato": Tabella(
        pacchetto="Schemi di bilancio",
        file="SDB Allegato A Risultato di Amministrazione.csv",
        chiavi={"voce": "Cod Voce Ris Amm Rend"},
        importi={"valore": "Totale di Gestione"},
        testi={"desc_voce": "Desc Voce Ris Amm Rend"},
    ),
    "parametri": Tabella(
        pacchetto="Schemi di bilancio",
        file="SDB Allegato l Parametri Obiettivi per Comuni.csv",
        chiavi={"parametro": "Codice Parametro Deficitario"},
        calcolate={
            "esito": """CASE "Valore Parametro Deficitarietà"
                WHEN 'SI' THEN true WHEN 'NO' THEN false END"""
        },
        testi={"desc_parametro": "Parametro Deficitario"},
        dal=2019,
    ),
    "indicatori_ufficiali": Tabella(
        pacchetto="Piano degli indicatori",
        file="PDI Sintetici Allegato 2-a.csv",
        chiavi={
            "gruppo": "Codice Tipologia Indicatore Sintetico 2)a",
            "indicatore": "Codice Indicatore Sintetico 2)a",
        },
        importi={"valore": "Indicatore Tutte Le Missioni"},
        testi={
            "desc_gruppo": "Descrizione Tipologia Indicatore Sintetico 2)a",
            "desc_indicatore": "Descrizione Indicatore Sintetico 2)a",
            "definizione": "Definizione Indicatore Sintetico 2)a",
        },
    ),
}

# Descrizioni dei codici: campo -> (tabella, espressione del codice, colonna della descrizione).
# Programmi e tipologie si ripetono sotto missioni e titoli diversi: il codice li unisce.
CODICI = {
    "missione": ("spese", "missione", "desc_missione"),
    "programma": ("spese", "missione || programma", "desc_programma"),
    "titolo_spesa": ("spese", "titolo", "desc_titolo"),
    "titolo_entrata": ("entrate", "titolo", "desc_titolo"),
    "tipologia_entrata": ("entrate", "titolo || tipologia", "desc_tipologia"),
    "voce_risultato": ("risultato", "voce", "desc_voce"),
    "parametro": ("parametri", "parametro", "desc_parametro"),
    "gruppo_indicatori": ("indicatori_ufficiali", "gruppo", "desc_gruppo"),
    "indicatore": (
        "indicatori_ufficiali", "gruppo || '.' || indicatore", "desc_indicatore", "definizione"
    ),
}

# Anagrafica dell'ente come la scrive BDAP, ricavata dal file delle spese.
COLONNE_SOGGETTO = {
    "codice_bdap": "Codice BDAP",
    "denominazione": "Denominazione Soggetto",
    "data_cessazione": "Data Cessazione Soggetto",
    "codice_regione": "Codice Regione",
    "regione": "Descrizione Regione",
    "codice_provincia": "Codice Provincia",
    "provincia": "Descrizione Provincia",
    "codice_comune": "Codice Comune",
    "comune": "Descrizione Comune",
}


def _leggi(csv: Path) -> str:
    """Lettura DuckDB di un CSV OpenBDAP gia' in UTF-8, tutto come testo.

    Il punto e virgola a fine riga crea una colonna vuota in coda, che resta fuori perche' le
    colonne si scelgono per nome.
    """
    return (
        f"read_csv('{csv.as_posix()}', delim=';', quote='\"', escape='\"', header=true, "
        "all_varchar=true)"
    )


def _scrivi(con: duckdb.DuckDBPyConnection, query: str, destinazione: Path) -> None:
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    parziale = destinazione.with_name(destinazione.name + ".part")
    con.execute(f"COPY ({query}) TO '{parziale.as_posix()}' (FORMAT parquet)")
    parziale.replace(destinazione)


def converti(csv: Path, tabella: Tabella, destinazione: Path) -> None:
    """Scrive in Parquet le righe dei comuni di un CSV, con colonne uniformi.

    Raises:
        ValueError: se mancano colonne attese, se un comune non ha codice fiscale o se la
            chiave della tabella non e' unica.
    """
    con = duckdb.connect()
    origine = _leggi(csv)
    presenti = set(con.sql(f"SELECT * FROM {origine} LIMIT 0").columns)
    attese = {"Esercizio Finanziario", "Codice Tipologia Soggetto", "CF Soggetto"}
    attese |= set(tabella.chiavi.values()) | set(tabella.importi.values())
    attese |= set(tabella.testi.values())
    if attese - presenti:
        raise ValueError(f"{csv.name}: colonne mancanti {sorted(attese - presenti)}")

    colonne = ['"CF Soggetto" AS cf', 'CAST("Esercizio Finanziario" AS SMALLINT) AS anno']
    colonne += [f'"{origine_}" AS {nome}' for nome, origine_ in tabella.chiavi.items()]
    colonne += [
        f'CAST("{origine_}" AS DECIMAL(18,2)) AS {nome}'
        for nome, origine_ in tabella.importi.items()
    ]
    colonne += [f"{espressione} AS {nome}" for nome, espressione in tabella.calcolate.items()]
    # le definizioni degli indicatori sono riempite di spazi fino a lunghezza fissa
    colonne += [
        f"""regexp_replace(trim("{origine_}"), '\\s+', ' ', 'g') AS {nome}"""
        for nome, origine_ in tabella.testi.items()
    ]
    chiave = ", ".join(["cf", "anno", *tabella.chiavi])
    con.execute(
        f"""CREATE TABLE righe AS SELECT {", ".join(colonne)} FROM {origine}
        WHERE "Codice Tipologia Soggetto" = '{TIPO_COMUNE}' ORDER BY {chiave}"""
    )
    senza_cf = con.execute("SELECT count(*) FROM righe WHERE cf IS NULL").fetchone()[0]
    if senza_cf:
        raise ValueError(f"{csv.name}: {senza_cf} righe di comuni senza codice fiscale")
    doppie = con.execute(
        f"SELECT count(*) FROM (SELECT 1 FROM righe GROUP BY {chiave} HAVING count(*) > 1)"
    ).fetchone()[0]
    if doppie:
        raise ValueError(f"{csv.name}: {doppie} chiavi ripetute ({chiave})")
    _scrivi(con, "SELECT * FROM righe", destinazione)


def converti_soggetti(csv: Path, destinazione: Path) -> None:
    """Scrive l'elenco dei comuni presenti in un CSV, con l'anagrafica che BDAP riporta."""
    colonne = ", ".join(f'"{origine}" AS {nome}' for nome, origine in COLONNE_SOGGETTO.items())
    query = f"""SELECT DISTINCT "CF Soggetto" AS cf,
        CAST("Esercizio Finanziario" AS SMALLINT) AS anno, {colonne}
        FROM {_leggi(csv)} WHERE "Codice Tipologia Soggetto" = '{TIPO_COMUNE}' ORDER BY cf"""
    _scrivi(duckdb.connect(), query, destinazione)


def scrivi_codici(cartella: Path = PROCESSED) -> None:
    """Scrive `codici.parquet`: descrizione di ogni codice, presa dall'ultimo anno che lo usa.

    Dentro un anno vale la descrizione piu' frequente. Colonne: campo, codice, descrizione,
    definizione (solo per gli indicatori), anno.
    """
    con = duckdb.connect()
    parti = []
    for campo, (tabella, codice, descrizione, *definizione) in CODICI.items():
        if not any((cartella / tabella).glob("*.parquet")):
            continue
        file = (cartella / tabella / "*.parquet").as_posix()
        testo_definizione = definizione[0] if definizione else "NULL::VARCHAR"
        parti.append(f"""
            SELECT '{campo}' AS campo, {codice} AS codice, {descrizione} AS descrizione,
                {testo_definizione} AS definizione, anno, count(*) AS righe
            FROM read_parquet('{file}') GROUP BY ALL""")
    query = f"""
        SELECT campo, codice, descrizione, definizione, anno
        FROM ({" UNION ALL ".join(parti)})
        QUALIFY row_number() OVER (
            PARTITION BY campo, codice ORDER BY anno DESC, righe DESC, descrizione) = 1
        ORDER BY campo, codice"""
    _scrivi(con, query, cartella / "codici.parquet")


def aggiorna(anni: range, registro: Registro, sessione: requests.Session) -> int:
    """Porta in `data/processed/` i rendiconti degli anni chiesti, saltando cio' che e' invariato.

    Returns:
        Numero di file scaricati e convertiti.
    """
    convertiti = 0
    for anno in anni:
        for pacchetto in sorted({t.pacchetto for t in TABELLE.values()}):
            zip_remoto = ZipRemoto(url_rendiconto(anno, pacchetto), sessione)
            for nome, tabella in TABELLE.items():
                if tabella.pacchetto != pacchetto or anno < tabella.dal:
                    continue
                indirizzo = f"{zip_remoto.url}#{tabella.file}"
                destinazione = PROCESSED / nome / f"{anno}.parquet"
                if destinazione.exists() and registro.invariato(
                    indirizzo, zip_remoto.etag, zip_remoto.data_file
                ):
                    continue
                log.info("%s %d: scarico e converto", nome, anno)
                with tempfile.TemporaryDirectory() as cartella:
                    csv = Path(cartella) / "origine.csv"
                    zip_remoto.estrai_utf8(zip_remoto.membro(tabella.file), csv, CODIFICA)
                    if nome == "spese":
                        converti_soggetti(csv, PROCESSED / "soggetti" / f"{anno}.parquet")
                    converti(csv, tabella, destinazione)
                registro.registra(indirizzo, zip_remoto.etag, zip_remoto.data_file)
                convertiti += 1
    if convertiti or not (PROCESSED / "codici.parquet").exists():
        scrivi_codici()
    return convertiti
