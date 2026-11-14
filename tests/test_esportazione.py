"""Indice dei prezzi, nomi dei gruppi, serie a colonne e dizionario dell'esportazione."""
import pandas as pd
import pytest

from pipeline.esportazione import _serie, dizionario, identificativo_gruppo, voci_per_comune
from pipeline.prezzi import leggi_jsonstat


def test_indice_dei_prezzi_dal_primo_anno_dei_rendiconti():
    dati = {
        "value": {"0": 100.0, "1": 99.9, "2": 101.3},
        "dimension": {"time": {"category": {"index": {"2015": 0, "2016": 1, "2017": 2}}}},
    }
    assert leggi_jsonstat(dati).values.tolist() == [[2016, 99.9], [2017, 101.3]]


def test_identificativo_del_gruppo_senza_accenti_ne_spazi():
    valle = identificativo_gruppo(1, "Valle d'Aosta/Vallée d'Aoste")
    assert valle == "1-valle-d-aosta-vallee-d-aoste"
    assert identificativo_gruppo(5, "regioni ordinarie") == "5-regioni-ordinarie"


def test_serie_allineata_agli_anni():
    assert _serie({2017: 1.26, 2019: float("nan")}, [2016, 2017, 2018, 2019], None) == [
        None, 1, None, None,
    ]
    assert _serie({2016: 1.256}, [2016], 2) == [1.26]


@pytest.fixture
def codici():
    return pd.DataFrame({
        "campo": ["titolo_entrata", "indicatore", "parametro"],
        "codice": ["01", "09.05", "0010"],
        "descrizione": [
            "ENTRATE CORRENTI DI NATURA TRIBUTARIA", "9.5 Indicatore annuale di tempestivita'",
            "Ente strutturalmente deficitario",
        ],
        "definizione": [None, "Giorni effettivi fra scadenza e pagamento", None],
    })


def test_dizionario(codici):
    voci = dizionario(codici, ["entrate_titolo/01", "indicatore/09.05"])["voci"]
    assert voci["entrate_titolo/01"]["nome"] == "Entrate: Entrate correnti di natura tributaria"
    assert voci["entrate_titolo/01"]["andamento"] is True
    tempestivita = voci["indicatore/09.05"]
    assert (tempestivita["nome"], tempestivita["unita"]) == (
        "Indicatore annuale di tempestivita'", "giorni"
    )
    assert tempestivita["andamento"] is False and "nota" in tempestivita


def test_dizionario_senza_descrizione(codici):
    with pytest.raises(ValueError, match="manca la descrizione"):
        dizionario(codici, ["spesa_titolo/01"])


def test_voci_per_comune():
    righe = pd.DataFrame({
        "cf": ["A", "A", "A", "B"],
        "anno": [2017, 2016, 2016, 2016],
        "misura": ["spesa_titolo", "spesa_titolo", "indicatore", "spesa_titolo"],
        "codice": ["01", "01", "09.05", "01"],
        "importo": [1000.456, 900.0, float("nan"), 50.0],
        "valore": [10.6, 9.4, 12.345, 0.5],
        "posizione": [50.4, 40.0, 70.0, 10.0],
        "scarto": [12.34, float("nan"), float("nan"), float("nan")],
        "mediana": [11.2, 9.0, 5.555, float("nan")],
    })
    voci = voci_per_comune(righe, [2016, 2017, 2018])
    assert list(voci["A"]) == ["indicatore/09.05", "spesa_titolo/01"]
    assert voci["A"]["spesa_titolo/01"] == {
        "importo": [900.0, 1000.46, None], "procapite": [9, 11, None],
        "posizione": [40, 50, None], "mediana": [9, 11, None], "scarto": [None, 12.3, None],
    }
    assert voci["A"]["indicatore/09.05"] == {
        "valore": [12.35, None, None], "posizione": [70, None, None],
        "mediana": [5.55, None, None],
    }
    assert voci["B"]["spesa_titolo/01"]["mediana"] == [None, None, None]
    with pytest.raises(ValueError, match="ripetute"):
        voci_per_comune(pd.concat([righe, righe.head(1)]), [2016, 2017])
