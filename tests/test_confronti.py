"""Gruppi di confronto, allargamento, pro capite e posizioni."""
from decimal import Decimal

import pandas as pd
import pytest

from pipeline.confronti import (
    calcola_anno, costruisci_gruppi, debiti_fuori_scala, dimensione_gruppi, residenti_per_ente,
    rimborsi_pro_capite,
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
    # il fondo perequativo di a (tipologia 0301) sta nel titolo 1 ma non fra le entrate proprie
    entrate = pd.DataFrame({
        "cf": ["a", "a", "a", "b"], "titolo": ["01", "01", "09", "03"],
        "tipologia": ["0101", "0301", "0100", "0300"],
        "accertamenti": [Decimal(v) for v in ("300", "200", "7000", "800")],
        "esclusa": [False, False, True, False],
    })
    risultato = pd.DataFrame({
        "cf": ["a", "b"], "voce": ["0502", "0502"],
        "valore": [Decimal("-500"), Decimal("200")],
    })
    # 4.4 a zero: per a il 4.1 e' positivo (non compilato), per b il 4.1 manca (resta zero)
    # 9.5: zero (a) e fuori scala (b) vuoti, -12 giorni (c) valido.
    # 7.4 atteso = 7.1 per la spesa dei titoli 1 e 2 pro capite: a 0,75 (scritto 750, fuori
    # scala), b 0,3 con il 7.1 scritto come frazione (0,1 per 10%: valido); c negativo senza
    # gemello, fuori scala
    indicatori = pd.DataFrame({
        "cf": ["a", "b", "c", "a", "b", "a", "b", "c", "a", "b", "a", "b", "c"],
        "gruppo": ["04"] * 5 + ["09"] * 3 + ["07"] * 5,
        "indicatore": ["01", "01", "01", "04", "04", "05", "05", "05",
                       "01", "01", "04", "04", "04"],
        "valore": [Decimal(v) if v else None
                   for v in ("20", None, "30", "0", "0", "0", "-1200", "-12",
                             "50", "0.1", "750", "0.3", "-5")],
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
    assert valori.loc[("entrate_titolo", "01", "a"), "valore"] == 0.5
    assert ("entrate_titolo", "09", "a") not in valori.index
    assert valori.loc[("risultato_disponibile", "0502"), "valore"].tolist() == [-0.5, 0.1]
    # l'indicatore vuoto di b resta fuori, non vale zero
    assert valori.loc[("indicatore", "04.01"), "valore"].tolist() == [20.0, 30.0]
    assert valori.loc[("indicatore", "04.04")].index.tolist() == ["b"]
    assert valori.loc[("indicatore", "09.05")].index.tolist() == ["c"]
    assert valori.loc[("indicatore", "07.04")].index.tolist() == ["b"]
    corrente = confronti.set_index(["misura", "codice"]).loc[("spesa_titolo", "01")]
    assert (corrente["comuni"], corrente["mediana"], corrente["ambito"]) == (3, 1.0, "Centro")


def test_senza_residenti_solo_importi():
    gruppi = pd.DataFrame({
        "cf": ["a", "b", "x"], "anno": 2017, "stato": "consegnato",
        "residenti": [1_000, 3_000, None], "al_1_gennaio": 2018, "fascia": [2, 2, None],
        "area": "Sud", "livello": ["area", "area", None], "ambito": ["Sud", "Sud", None],
    })
    gruppi["fascia"] = gruppi["fascia"].astype("Int8")
    spese = pd.DataFrame({
        "cf": ["a", "b", "x"], "missione": "01", "programma": "01", "titolo": "01",
        "impegni": [Decimal(v) for v in ("1000", "6000", "50000")], "esclusa": False,
    })
    vuota = pd.DataFrame({"cf": pd.Series(dtype=str)})
    tabelle = {
        "spese": spese,
        "entrate": vuota.assign(titolo="", tipologia="", accertamenti=0, esclusa=False),
        "risultato": vuota.assign(voce="", valore=0),
        "indicatori_ufficiali": pd.DataFrame({
            "cf": ["x"], "gruppo": ["04"], "indicatore": ["04"], "valore": [Decimal("12")],
        }),
    }
    posizioni, confronti = calcola_anno(tabelle, gruppi)
    di_x = posizioni[posizioni["cf"] == "x"]
    # titolo, missione e programma; l'indicatore resta fuori
    assert di_x["misura"].tolist() == [
        "spesa_corrente_missione", "spesa_corrente_programma", "spesa_titolo"
    ]
    assert di_x["importo"].tolist() == [50000.0] * 3
    assert di_x[["valore", "posizione", "scarto"]].isna().all().all()
    riga = confronti.set_index(["misura", "codice"]).loc[("spesa_titolo", "01")]
    assert (riga["comuni"], riga["mediana"]) == (2, 1.5)


def test_debito_escluso_fuori_dal_calcolo():
    gruppi = pd.DataFrame({
        "cf": ["a", "b", "c", "d"], "anno": 2024, "stato": "consegnato",
        "residenti": 1_000, "al_1_gennaio": 2025, "fascia": 2,
        "area": "Centro", "livello": "area", "ambito": "Centro",
    })
    vuota = pd.DataFrame({"cf": pd.Series(dtype=str)})
    tabelle = {
        "spese": pd.DataFrame({
            "cf": ["a", "b", "c", "d"], "missione": "01", "programma": "01", "titolo": "01",
            "impegni": Decimal("1000"), "esclusa": False,
        }),
        "entrate": vuota.assign(titolo="", tipologia="", accertamenti=0, esclusa=False),
        "risultato": vuota.assign(voce="", valore=0),
        "indicatori_ufficiali": pd.DataFrame({
            "cf": ["a", "b", "c", "d"], "gruppo": "10", "indicatore": "04",
            "valore": [Decimal(v) for v in ("1.04", "300", "1", "2")],
        }),
    }
    posizioni, _ = calcola_anno(tabelle, gruppi, debiti_esclusi=pd.DataFrame({"cf": ["a", "c"]}))
    debito = posizioni[(posizioni["misura"] == "indicatore") & (posizioni["codice"] == "10.04")]
    assert sorted(debito["cf"]) == ["b", "d"]


def test_rimborsi_pro_capite():
    gruppi = pd.DataFrame({
        "cf": ["a", "b", "x"], "stato": "consegnato", "residenti": [1_000, 2_000, None],
    })
    spese = pd.DataFrame({
        "cf": ["a", "a", "b", "x"], "titolo": ["04", "01", "01", "04"],
        "impegni": [Decimal(v) for v in ("30000", "5000", "100", "999")],
    })
    rimborsi = rimborsi_pro_capite(spese, gruppi).set_index("cf")["rimborso"].to_dict()
    assert rimborsi == {"a": 30.0, "b": 0.0}


def test_debiti_fuori_scala():
    righe = {
        # migliaia scritte come euro: 1 euro di debito e 30 rimborsati l'anno dopo
        "car": {2016: 1.04, 2017: 999, 2018: 1.05, 2019: 990},
        # centesimi scritti come euro nel 2024; il 2025 giusto non paga l'errore dell'anno prima
        "dou": {2022: 1090, 2023: 796, 2024: 54133, 2025: 308},
        # mutuo vero: da 30 a 1.000 euro, sotto la soglia alta
        "mut": {2022: 30, 2023: 30, 2024: 1000, 2025: 1000},
        # ultimo anno senza rimborso dopo: cento volte sotto gli altri anni
        "ult": {2024: 500, 2025: 2},
        # l'unico altro anno e' troppo alto: non conta per giudicare l'ultimo
        "sca": {2021: 127292, 2022: 20, 2025: 292},
        # un anno solo, senza confronti: oltre il tetto e' comunque fuori
        "tet": {2019: 1412691},
    }
    debiti = pd.DataFrame(
        [(cf, anno, v) for cf, anni in righe.items() for anno, v in anni.items()],
        columns=["cf", "anno", "valore"],
    )
    rimborsi = pd.DataFrame(
        [("car", a, 30.0) for a in (2017, 2018, 2019)]
        + [(cf, a, 2.0) for cf in ("dou", "mut") for a in (2023, 2024, 2025)]
        + [("ult", 2025, 20.0), ("sca", 2022, 1.0)],
        columns=["cf", "anno", "rimborso"],
    )
    esclusi = debiti_fuori_scala(debiti, rimborsi)
    assert list(esclusi.itertuples(index=False, name=None)) == [
        ("car", 2016), ("car", 2018), ("dou", 2024), ("sca", 2021), ("tet", 2019),
        ("ult", 2025),
    ]


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
        "entrate": vuota.assign(titolo="", tipologia="", accertamenti=0, esclusa=False),
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
