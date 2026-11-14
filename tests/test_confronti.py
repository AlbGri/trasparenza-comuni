"""Gruppi di confronto, allargamento, pro capite e posizioni."""
from decimal import Decimal

import pandas as pd
import pytest

from pipeline.confronti import (
    calcola_anno, costruisci_gruppi, dimensione_gruppi, residenti_per_ente,
)


def comuni(prefisso, quanti, regione, tipo, residenti, stato="consegnato"):
    """`quanti` comuni uguali, con codice regione e tipo di regione."""
    return [
        {
            "cf": f"{prefisso}{i:03d}", "codice_regione": regione, "regione": f"R{regione}",
            "tipo_regione": tipo, "stato": stato, "residenti": residenti,
        }
        for i in range(quanti)
    ]


@pytest.fixture
def gruppi():
    righe = (
        comuni("c2", 20, "09", "ordinaria", 2_000)  # Centro, fascia 2: 20 comuni, basta
        + comuni("c5", 3, "09", "ordinaria", 100_000)  # Centro, fascia 5: pochi
        + comuni("s5", 18, "15", "ordinaria", 100_000)  # Sud, fascia 5: pochi anche qui
        + comuni("x5", 5, "15", "ordinaria", 100_000, stato="non consegnato")
        + comuni("i5", 2, "19", "speciale", 100_000)  # Sicilia, fascia 5
        + comuni("n0", 1, "19", "speciale", None)  # senza popolazione
    )
    tabella = pd.DataFrame(righe).assign(anno=2024, al_1_gennaio=2025)
    enti = tabella[["cf", "codice_regione", "regione", "tipo_regione"]]
    consegne = tabella[["cf", "anno", "stato"]]
    residenti = tabella.dropna(subset="residenti")[["cf", "anno", "al_1_gennaio", "residenti"]]
    return costruisci_gruppi(enti, consegne, residenti).set_index("cf")


def test_gruppo_per_area_se_bastano_20_comuni(gruppi):
    assert gruppi.loc["c2000", ["fascia", "livello", "ambito"]].tolist() == [2, "area", "Centro"]


def test_allargamento_alle_regioni_ordinarie(gruppi):
    # 3 + 18 consegnati: i non consegnati non contano per la soglia
    assert gruppi.loc["c5000", "ambito"] == "regioni ordinarie"
    assert gruppi.loc["s5000", "ambito"] == "regioni ordinarie"


def test_le_speciali_non_si_mescolano_alle_ordinarie(gruppi):
    assert gruppi.loc["i5000", ["livello", "ambito"]].tolist() == ["Italia", "Italia"]


def test_senza_popolazione_senza_gruppo(gruppi):
    assert pd.isna(gruppi.loc["n0000", "fascia"]) and pd.isna(gruppi.loc["n0000", "ambito"])


def test_dimensione_conta_tutto_l_ambito(gruppi):
    dimensioni = dimensione_gruppi(gruppi.reset_index())
    ordinarie = dimensioni[dimensioni["ambito"] == "regioni ordinarie"].iloc[0]
    assert (ordinarie["comuni"], ordinarie["consegnati"], ordinarie["non_consegnati"]) == (
        26, 21, 5
    )
    senza = dimensioni[dimensioni["fascia"].isna()].iloc[0]
    assert (senza["ambito"], senza["comuni"]) == ("R19", 1)


def test_residenti_dell_estinto_nel_suo_ultimo_anno():
    enti = pd.DataFrame({
        "cf": ["a", "e"], "codice_istat": ["001", "002"], "stato": ["attivo", "estinto"],
        "data_cessazione": pd.to_datetime([None, "2020-12-31"]),
    })
    popolazione = pd.DataFrame({
        "codice_istat": ["001", "001", "002"], "anno": [2019, 2020, 2019],
        "al_1_gennaio": [2020, 2021, 2020], "residenti": [100, 101, 50],
    })
    residenti = residenti_per_ente(enti, popolazione).set_index(["cf", "anno"])
    assert residenti.loc[("e", 2020)].tolist() == [2020, 50]
    assert residenti.loc[("a", 2020)].tolist() == [2021, 101]


def test_pro_capite_zeri_e_posizioni():
    gruppi = pd.DataFrame({
        "cf": ["a", "b", "c"], "anno": 2024, "stato": "consegnato",
        "residenti": [1_000, 2_000, 4_000], "al_1_gennaio": 2025, "fascia": 2,
        "area": "Centro", "livello": "area", "ambito": "Centro",
    })
    spese = pd.DataFrame({
        "cf": ["a", "a", "b", "c", "c"],
        "missione": ["01", "01", "01", "01", "99"],
        "programma": ["01", "01", "01", "01", "01"],
        "titolo": ["01", "02", "01", "01", "07"],
        "impegni": [Decimal(v) for v in ("1000", "500", "6000", "4000", "9999")],
        "esclusa": [False, False, False, False, True],
    })
    # "c" non ha consegnato le entrate: niente zeri inventati
    entrate = pd.DataFrame({
        "cf": ["a", "a", "b"], "titolo": ["01", "09", "03"],
        "accertamenti": [Decimal(v) for v in ("300", "7000", "800")],
        "esclusa": [False, True, False],
    })
    risultato = pd.DataFrame({
        "cf": ["a", "b"], "voce": ["0502", "0502"],
        "valore": [Decimal("-500"), Decimal("200")],
    })
    # 4.4 a zero: per a il 4.1 e' positivo (non compilato), per b il 4.1 manca (resta zero)
    indicatori = pd.DataFrame({
        "cf": ["a", "b", "c", "a", "b"], "gruppo": "04",
        "indicatore": ["01", "01", "01", "04", "04"],
        "valore": [Decimal("20"), None, Decimal("30"), Decimal("0"), Decimal("0")],
    })
    tabelle = {
        "spese": spese, "entrate": entrate, "risultato": risultato,
        "indicatori_ufficiali": indicatori,
    }
    posizioni, confronti = calcola_anno(tabelle, gruppi)
    valori = posizioni.set_index(["misura", "codice", "cf"]).sort_index()
    # corrente pro capite: a 1, b 3, c 1; la partita di giro di c resta fuori
    assert valori.loc[("spesa_titolo", "01"), "valore"].tolist() == [1.0, 3.0, 1.0]
    assert valori.loc[("spesa_titolo", "01"), "posizione"].tolist() == [0.0, 100.0, 0.0]
    assert valori.loc[("spesa_titolo", "02", "b"), "importo"] == 0
    assert valori.loc[("entrate_proprie", "01+03"), "valore"].tolist() == [0.3, 0.4]
    assert ("entrate_titolo", "09", "a") not in valori.index
    assert valori.loc[("risultato_disponibile", "0502"), "valore"].tolist() == [-0.5, 0.1]
    # l'indicatore vuoto di b resta fuori, non vale zero
    assert valori.loc[("indicatore", "04.01"), "valore"].tolist() == [20.0, 30.0]
    assert valori.loc[("indicatore", "04.04")].index.tolist() == ["b"]
    corrente = confronti.set_index(["misura", "codice"]).loc[("spesa_titolo", "01")]
    assert (corrente["comuni"], corrente["mediana"], corrente["ambito"]) == (3, 1.0, "Centro")


def test_andamento_scarto_dalla_mediana_delle_variazioni():
    gruppi = pd.DataFrame({
        "cf": ["a", "b", "c", "d"], "anno": 2024, "stato": "consegnato",
        "residenti": 1_000, "al_1_gennaio": 2025, "fascia": 2,
        "area": "Centro", "livello": "area", "ambito": "Centro",
    })
    spese = pd.DataFrame({
        "cf": ["a", "b", "c", "d"], "missione": "01", "programma": "01", "titolo": "01",
        "impegni": [Decimal(v) for v in ("1100", "1200", "1300", "500")],
        "esclusa": False,
    })
    vuota = pd.DataFrame({"cf": pd.Series(dtype=str)})
    tabelle = {
        "spese": spese,
        "entrate": vuota.assign(titolo="", accertamenti=0, esclusa=False),
        "risultato": vuota.assign(voce="", valore=0),
        "indicatori_ufficiali": vuota.assign(gruppo="", indicatore="", valore=0),
    }
    # l'anno prima d valeva zero: niente variazione
    precedente = pd.DataFrame({
        "cf": ["a", "b", "c", "d"], "misura": "spesa_titolo", "codice": "01",
        "valore": [1.0, 1.0, 1.0, 0.0],
    })
    posizioni, confronti = calcola_anno(tabelle, gruppi, precedente)
    corrente = posizioni[posizioni["misura"] == "spesa_titolo"].set_index("cf")
    assert corrente["variazione"].round(6).tolist()[:3] == [10.0, 20.0, 30.0]
    assert pd.isna(corrente.loc["d", "variazione"])
    # mediana delle variazioni 20: scarti -10, 0, +10
    assert corrente["scarto"].round(6).tolist()[:3] == [-10.0, 0.0, 10.0]
    riga = confronti.set_index(["misura", "codice"]).loc[("spesa_titolo", "01")]
    assert round(riga["variazione_mediana"], 6) == 20.0
