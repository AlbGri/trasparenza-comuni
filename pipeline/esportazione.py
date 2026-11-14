"""Esportazione in `data/export/`: un JSON per comune, indice, gruppi, dizionario e metadati.

Sono le basi del sito e dell'API statica. Le serie sono a colonne: ogni lista e' allineata
con `anni`, e un anno senza dato vale null.
"""
import json
import logging
import re
import shutil
import unicodedata
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path

import duckdb
import pandas as pd

from pipeline.confronti import LIVELLI, MISURE_CON_ANDAMENTO, NOMI_FASCE, _ambiti_candidati
from pipeline.fonti import EXPORT, PROCESSED, URL_IPCA

log = logging.getLogger(__name__)

INDICATORI_CSV = Path(__file__).with_name("indicatori.csv")
PROGRAMMI = ("0301", "0903", "1005", "1201")
INDICATORI = (
    "01.01", "03.01", "04.01", "04.04", "05.01", "07.04", "09.05", "10.04", "13.01", "13.02",
    "13.03",
)
VOCI_ESPORTATE = f"""
    misura IN ('spesa_titolo', 'spesa_corrente_missione', 'entrate_titolo', 'entrate_proprie',
        'risultato_disponibile')
    OR (misura = 'spesa_corrente_programma' AND codice IN {PROGRAMMI})
    OR (misura = 'indicatore' AND codice IN {INDICATORI})
"""
FONTE_SPESE = "OpenBDAP, Rendiconto, Schemi di bilancio, Spese.csv"
FONTE_ENTRATE = "OpenBDAP, Rendiconto, Schemi di bilancio, Entrate.csv"
FONTE_RISULTATO = (
    "OpenBDAP, Rendiconto, Schemi di bilancio, Allegato A Risultato di Amministrazione"
)
FONTE_INDICATORI = "OpenBDAP, Rendiconto, Piano degli indicatori, Sintetici Allegato 2-a"
PRO_CAPITE = "diviso i residenti ISTAT al 1 gennaio dell'anno dopo"
SENZA_GIRO = "senza partite di giro e restituzione delle anticipazioni di cassa"


def identificativo_gruppo(fascia: int, ambito: str) -> str:
    """Nome di file di un gruppo: fascia e ambito in minuscolo, senza accenti ne' spazi."""
    testo = unicodedata.normalize("NFKD", f"{fascia}-{ambito}").encode("ascii", "ignore")
    return re.sub(r"[^a-z0-9]+", "-", testo.decode().lower()).strip("-")


def _serie(valori: dict[int, float], anni: list[int], decimali: int | None) -> list:
    """Lista allineata agli anni, arrotondata; None dove manca. decimali None = intero."""
    uscita = []
    for anno in anni:
        valore = valori.get(anno)
        if valore is None or pd.isna(valore):
            uscita.append(None)
        elif decimali is None:
            uscita.append(int(round(float(valore))))
        else:
            uscita.append(round(float(valore), decimali))
    return uscita


def _scrivi_json(percorso: Path, dati: dict) -> int:
    testo = json.dumps(dati, ensure_ascii=False, separators=(",", ":"))
    percorso.write_text(testo, encoding="utf-8")
    return len(testo.encode("utf-8"))


def _arrotonda(colonna: pd.Series, decimali: int | None) -> list:
    """Come `_serie`, ma su una colonna intera."""
    if decimali is None:
        return [None if v != v else int(round(v)) for v in colonna.tolist()]
    return [None if v != v else round(v, decimali) for v in colonna.tolist()]


def voci_per_comune(righe: pd.DataFrame, anni: list[int]) -> dict[str, dict]:
    """Serie delle voci di ogni comune, da posizioni unite alla mediana del gruppo.

    Raises:
        ValueError: se un comune ha due righe per la stessa voce e lo stesso anno.
    """
    chiavi = ["cf", "misura", "codice", "anno"]
    if righe.duplicated(chiavi).any():
        raise ValueError("righe ripetute per comune, voce e anno")
    righe = righe.sort_values(chiavi)
    euro = {
        "importo": _arrotonda(righe["importo"], 2),
        "procapite": _arrotonda(righe["valore"], None),
        "posizione": _arrotonda(righe["posizione"], None),
        "mediana": _arrotonda(righe["mediana"], None),
        "scarto": _arrotonda(righe["scarto"], 1),
    }
    indicatore = euro | {
        "valore": _arrotonda(righe["valore"], 2), "mediana": _arrotonda(righe["mediana"], 2),
    }
    posto = {anno: i for i, anno in enumerate(anni)}
    voci = {}
    for riga, (cf, misura, codice, anno) in enumerate(
        zip(righe["cf"], righe["misura"], righe["codice"], righe["anno"].tolist())
    ):
        if anno not in posto:
            continue
        suoi = voci.setdefault(cf, {})
        chiave = f"{misura}/{codice}"
        if chiave not in suoi:
            campi = ["valore"] if misura == "indicatore" else ["importo", "procapite"]
            campi += ["posizione", "mediana"]
            if misura in MISURE_CON_ANDAMENTO:
                campi.append("scarto")
            suoi[chiave] = {campo: [None] * len(anni) for campo in campi}
        sorgente = indicatore if misura == "indicatore" else euro
        for campo, serie in suoi[chiave].items():
            serie[posto[anno]] = sorgente[campo][riga]
    return voci


def _parametri_per_comune(parametri: pd.DataFrame) -> tuple[dict, dict]:
    """Parametri accesi e giudizio di deficitarieta' per comune e anno.

    Un anno conta solo se c'e' la sintesi (parametro 0010), che da' il giudizio.
    """
    sintesi = parametri[parametri["parametro"] == "0010"].drop_duplicates(["cf", "anno"])
    deficitario = {
        (cf, anno): bool(esito)
        for cf, anno, esito in zip(sintesi["cf"], sintesi["anno"].tolist(), sintesi["esito"])
    }
    accesi = parametri[parametri["esito"] & (parametri["parametro"] != "0010")]
    accesi = accesi.groupby(["cf", "anno"])["parametro"].apply(sorted).to_dict()
    return accesi, deficitario


def _nome_indicatore(descrizione: str) -> str:
    # "10.4Indebitamento procapite (in valore assoluto)" -> "Indebitamento procapite (...)"
    return re.sub(r"^\d+\.\d+\s*", "", descrizione)


def dizionario(codici: pd.DataFrame, voci: list[str]) -> dict:
    """Descrizione di ogni voce esportata e dei parametri di deficitarieta'.

    Raises:
        ValueError: se un indicatore non ha unita' in `indicatori.csv` o un codice non ha
            descrizione.
    """
    testi = codici.set_index(["campo", "codice"])
    unita = pd.read_csv(INDICATORI_CSV, sep=";", dtype=str, keep_default_na=False)
    unita = unita.set_index("codice")

    def testo(campo: str, codice: str) -> str:
        if (campo, codice) not in testi.index:
            raise ValueError(f"manca la descrizione di {campo} {codice}")
        descrizione = testi.loc[(campo, codice), "descrizione"]
        return descrizione.capitalize() if descrizione.isupper() else descrizione

    euro = {"unita": "euro per abitante", "calcolato": True}
    voci_dizionario = {}
    for chiave in voci:
        misura, codice = chiave.split("/")
        if misura == "spesa_titolo":
            voce = euro | {
                "nome": f"Spesa: {testo('titolo_spesa', codice)}", "fonte": FONTE_SPESE,
                "misura": "impegni, competenza",
                "metodo": f"impegni del titolo {int(codice)}, {SENZA_GIRO}, {PRO_CAPITE}",
            }
        elif misura in ("spesa_corrente_missione", "spesa_corrente_programma"):
            campo = "missione" if misura == "spesa_corrente_missione" else "programma"
            voce = euro | {
                "nome": f"Spesa corrente: {testo(campo, codice)}", "fonte": FONTE_SPESE,
                "misura": "impegni, competenza",
                "metodo": f"impegni del titolo 1 per {campo} {codice}, {SENZA_GIRO}, "
                f"{PRO_CAPITE}",
            }
        elif misura == "entrate_titolo":
            voce = euro | {
                "nome": f"Entrate: {testo('titolo_entrata', codice)}", "fonte": FONTE_ENTRATE,
                "misura": "accertamenti, competenza",
                "metodo": f"accertamenti del titolo {int(codice)}, {PRO_CAPITE}",
            }
        elif misura == "entrate_proprie":
            voce = euro | {
                "nome": "Entrate proprie (tributarie ed extratributarie)",
                "fonte": FONTE_ENTRATE, "misura": "accertamenti, competenza",
                "metodo": f"accertamenti dei titoli 1 e 3, {PRO_CAPITE}",
            }
        elif misura == "risultato_disponibile":
            voce = euro | {
                "nome": "Parte disponibile del risultato di amministrazione",
                "fonte": FONTE_RISULTATO, "misura": "saldo al 31 dicembre",
                "metodo": "risultato di amministrazione meno le parti accantonata, vincolata "
                f"e destinata agli investimenti (voce {codice}), {PRO_CAPITE}; "
                "negativa = disavanzo",
            }
        elif misura == "indicatore":
            if codice not in unita.index:
                raise ValueError(f"indicatore {codice} senza unita' in {INDICATORI_CSV.name}")
            voce = {
                "nome": _nome_indicatore(testo("indicatore", codice)),
                "unita": unita.loc[codice, "unita"], "calcolato": False,
                "fonte": FONTE_INDICATORI, "misura": "indicatore ufficiale, rendiconto",
                "definizione": testi.loc[("indicatore", codice), "definizione"],
            }
            if unita.loc[codice, "nota"]:
                voce["nota"] = unita.loc[codice, "nota"]
        else:
            raise ValueError(f"misura senza descrizione: {misura}")
        voce["andamento"] = misura in MISURE_CON_ANDAMENTO
        voci_dizionario[chiave] = voce
    parametri = codici[codici["campo"] == "parametro"]
    return {
        "voci": voci_dizionario,
        "parametri": dict(zip(parametri["codice"], parametri["descrizione"])),
        "campi": {
            "importo": "euro, come nel rendiconto",
            "procapite": "euro per abitante, arrotondati all'euro",
            "valore": "valore dell'indicatore ufficiale, come nel rendiconto",
            "posizione": "percentuale degli altri comuni del gruppo con un valore piu' basso",
            "mediana": "mediana dei comuni del gruppo nello stesso anno",
            "scarto": "variazione sull'anno prima del valore pro capite del comune meno la "
            "mediana delle variazioni dei comuni del gruppo, in punti percentuali",
            "parametri_accesi": "parametri di deficitarieta' accesi (dal 2019)",
            "deficitario": "ente strutturalmente deficitario secondo i parametri (dal 2019)",
        },
    }


def _date_dei_dati(versioni: pd.DataFrame, anni: list[int]) -> dict[str, str]:
    """Data dei pacchetti OpenBDAP di ogni anno (la piu' recente dei file usati)."""
    date_anno = {}
    for anno in anni:
        righe = versioni[versioni["indirizzo"].str.contains(f"/Rendiconto/{anno}/", regex=False)]
        date_anno[str(anno)] = max(
            parsedate_to_datetime(testo).date() for testo in righe["data_file"]
        ).isoformat()
    return date_anno


def _membri_dei_gruppi(gruppi: pd.DataFrame, enti: pd.DataFrame) -> pd.DataFrame:
    """Codici ISTAT dei comuni di ogni gruppo usato: anno, fascia, ambito, membri.

    Come in `dimensione_gruppi`, un gruppo allargato contiene tutti i comuni del suo ambito.
    """
    con_fascia = gruppi[gruppi["fascia"].notna()].merge(enti[["cf", "codice_istat"]], on="cf")
    candidati = _ambiti_candidati(con_fascia)
    usati = con_fascia[["anno", "fascia", "ambito"]].drop_duplicates()
    parti = [
        con_fascia.assign(ambito=candidati[livello]).merge(usati, on=["anno", "fascia", "ambito"])
        for livello in LIVELLI
    ]
    return (
        pd.concat(parti).drop_duplicates(["anno", "fascia", "ambito", "cf"])
        .groupby(["anno", "fascia", "ambito"])["codice_istat"].apply(sorted).reset_index()
    )


def esporta(cartella: Path = PROCESSED, uscita: Path = EXPORT) -> int:
    """Scrive tutti i file dell'esportazione, dopo aver svuotato la cartella.

    Returns:
        Peso totale in byte.
    """
    con = duckdb.connect()
    enti = pd.read_parquet(cartella / "enti.parquet")
    consegne = pd.read_parquet(cartella / "consegne.parquet")
    gruppi = pd.read_parquet(cartella / "gruppi.parquet")
    confronti = pd.read_parquet(cartella / "confronti.parquet")
    dimensioni = pd.read_parquet(cartella / "dimensione_gruppi.parquet")
    codici = pd.read_parquet(cartella / "codici.parquet")
    prezzi = pd.read_parquet(cartella / "prezzi.parquet")
    versioni = pd.read_parquet(cartella / "versioni_fonti.parquet")
    posizioni = con.execute(f"""
        SELECT * FROM read_parquet('{(cartella / "posizioni" / "*.parquet").as_posix()}')
        WHERE {VOCI_ESPORTATE}
    """).df()
    parametri = pd.read_parquet(cartella / "parametri")
    anni = sorted(consegne["anno"].unique().tolist())

    gruppi["gruppo"] = [
        None if pd.isna(f) else identificativo_gruppo(int(f), a)
        for f, a in zip(gruppi["fascia"], gruppi["ambito"])
    ]
    righe = posizioni.merge(gruppi[["cf", "anno", "fascia", "ambito"]], on=["cf", "anno"])
    # left: chi non ha residenti non ha gruppo, ma gli importi restano
    righe = righe.merge(
        confronti[["anno", "misura", "codice", "fascia", "ambito", "mediana"]],
        on=["anno", "misura", "codice", "fascia", "ambito"], how="left",
    )
    istat = dict(zip(enti["cf"], enti["codice_istat"]))
    predecessori = enti[enti["successore"].notna()].groupby("successore")["codice_istat"]
    predecessori = predecessori.apply(sorted).to_dict()

    if uscita.exists():
        shutil.rmtree(uscita)
    (uscita / "comuni").mkdir(parents=True)
    (uscita / "gruppi").mkdir()
    peso = 0
    voci_cf = voci_per_comune(righe, anni)
    accesi_cf, deficitario_cf = _parametri_per_comune(parametri)
    gruppi_cf = dict(tuple(gruppi.groupby("cf")))
    consegne_cf = dict(tuple(consegne.groupby("cf")))
    indice = []
    for ente in enti.itertuples():
        comune = {
            "id": ente.codice_istat, "nome": ente.nome, "provincia": ente.provincia,
            "regione": ente.regione, "codice_fiscale": ente.cf, "stato": ente.stato,
            "successore": istat.get(ente.successore),
            "predecessori": predecessori.get(ente.cf, []), "anni": anni,
        }
        stati = consegne_cf[ente.cf].set_index("anno")["stato"].to_dict()
        comune["consegna"] = [stati.get(anno) for anno in anni]
        suoi_gruppi = gruppi_cf.get(ente.cf, gruppi.iloc[:0]).set_index("anno")
        comune["residenti"] = _serie(suoi_gruppi["residenti"].to_dict(), anni, None)
        comune["gruppo"] = [suoi_gruppi["gruppo"].to_dict().get(anno) for anno in anni]
        comune["voci"] = voci_cf.get(ente.cf, {})
        comune["parametri_accesi"] = [
            accesi_cf.get((ente.cf, anno), []) if (ente.cf, anno) in deficitario_cf else None
            for anno in anni
        ]
        comune["deficitario"] = [deficitario_cf.get((ente.cf, anno)) for anno in anni]
        peso += _scrivi_json(uscita / "comuni" / f"{ente.codice_istat}.json", comune)
        ultimi = [r for r in comune["residenti"] if r is not None]
        indice.append([
            ente.codice_istat, ente.nome, ente.provincia, ente.regione, ente.stato,
            ultimi[-1] if ultimi else None,
        ])
    peso += _scrivi_json(uscita / "comuni.json", {
        "campi": ["id", "nome", "provincia", "regione", "stato", "residenti"], "righe": indice,
    })
    voci = sorted(f"{m}/{c}" for m, c in posizioni[["misura", "codice"]].drop_duplicates()
                  .itertuples(index=False))
    peso += _esporta_gruppi(uscita, gruppi, enti, confronti, dimensioni, anni, voci)
    peso += _scrivi_json(uscita / "dizionario.json", dizionario(codici, voci))
    peso += _scrivi_json(uscita / "meta.json", {
        "esportazione": date.today().isoformat(),
        "anni": anni,
        "data_dei_dati": _date_dei_dati(versioni, anni),
        "fasce": {str(k): v for k, v in NOMI_FASCE.items()},
        "prezzi": {
            "indice": "IPCA, media annua, 2015 = 100",
            "fonte": URL_IPCA,
            "valori": dict(zip(prezzi["anno"].astype(str), prezzi["indice"])),
        },
    })
    return peso


def _esporta_gruppi(
    uscita: Path, gruppi: pd.DataFrame, enti: pd.DataFrame, confronti: pd.DataFrame,
    dimensioni: pd.DataFrame, anni: list[int], voci: list[str],
) -> int:
    """Un file per gruppo (fascia e ambito) con dimensioni, membri e percentili per anno."""
    membri = _membri_dei_gruppi(gruppi, enti)
    dimensioni = dimensioni[dimensioni["fascia"].notna()].copy()
    dimensioni["fascia"] = dimensioni["fascia"].astype(int)
    confronti = confronti.copy()
    confronti["voce"] = confronti["misura"] + "/" + confronti["codice"]
    confronti = confronti[confronti["voce"].isin(voci)]
    peso = 0
    for (fascia, ambito), dimensione in dimensioni.groupby(["fascia", "ambito"]):
        per_anno = dimensione.set_index("anno")
        suoi_membri = membri[(membri["fascia"] == fascia) & (membri["ambito"] == ambito)]
        suoi_membri = suoi_membri.set_index("anno")["codice_istat"].to_dict()
        gruppo = {
            "id": identificativo_gruppo(fascia, ambito), "fascia": NOMI_FASCE[fascia],
            "ambito": ambito, "livello": per_anno["livello"].iloc[0], "anni": anni,
            "comuni": _serie(per_anno["comuni"].to_dict(), anni, None),
            "consegnati": _serie(per_anno["consegnati"].to_dict(), anni, None),
            "non_consegnati": _serie(per_anno["non_consegnati"].to_dict(), anni, None),
            "membri": [suoi_membri.get(anno) for anno in anni],
        }
        voci = {}
        suoi = confronti[(confronti["fascia"] == fascia) & (confronti["ambito"] == ambito)]
        for voce, righe in suoi.groupby("voce"):
            per_anno_voce = righe.set_index("anno")
            decimali = 2 if voce.startswith("indicatore/") else None
            voci[voce] = {
                colonna: _serie(per_anno_voce[colonna].to_dict(), anni, decimali)
                for colonna in ("p10", "p25", "mediana", "p75", "p90")
            }
            voci[voce]["comuni"] = _serie(per_anno_voce["comuni"].to_dict(), anni, None)
            if voce.split("/")[0] in MISURE_CON_ANDAMENTO:
                voci[voce]["variazione_mediana"] = _serie(
                    per_anno_voce["variazione_mediana"].to_dict(), anni, 1
                )
        gruppo["voci"] = voci
        peso += _scrivi_json(uscita / "gruppi" / f"{gruppo['id']}.json", gruppo)
    return peso


def aggiorna() -> bool:
    """Riesporta se una tabella a monte e' piu' recente dell'ultima esportazione.

    Returns:
        True se l'esportazione e' stata riscritta.
    """
    ingressi = [
        PROCESSED / nome for nome in (
            "enti.parquet", "consegne.parquet", "gruppi.parquet", "confronti.parquet",
            "dimensione_gruppi.parquet", "codici.parquet", "prezzi.parquet",
        )
    ]
    ingressi += sorted((PROCESSED / "posizioni").glob("*.parquet"))
    ingressi += sorted((PROCESSED / "parametri").glob("*.parquet"))
    ingressi.append(INDICATORI_CSV)
    meta = EXPORT / "meta.json"
    if meta.exists() and meta.stat().st_mtime > max(i.stat().st_mtime for i in ingressi):
        return False
    peso = esporta()
    log.info("esportazione: %.1f MB in %s", peso / 1e6, EXPORT)
    return True
