"""Indice dei prezzi, nomi dei gruppi, serie a colonne, indicatori assenti e dizionario."""
import duckdb
import pandas as pd
import pytest

from pipeline.esportazione import (
    _date_fonti, _serie, dizionario, identificativo_gruppo, indicatori_assenti, voci_per_comune,
)
from pipeline.prezzi import leggi_jsonstat


def test_indice_dei_prezzi_dal_primo_anno_dei_rendiconti():
    dati = {
        "value": {"0": 100.0, "1": 99.9, "2": 101.3},
        "dimension": {"time": {"category": {"index": {"2015": 0, "2016": 1, "2017": 2}}}},
    }
    assert leggi_jsonstat(dati).values.tolist() == [[2016, 99.9], [2017, 101.3]]


def test_date_delle_fonti_esterne():
    versioni = pd.DataFrame({
        "indirizzo": [
            "https://demo.istat.it/data/posas/POSAS_2025_it_Comuni.zip",
            "https://demo.istat.it/data/posas/POSAS_2026_it_Comuni.zip",
            "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv",
            "https://indicepa.gov.it/ipa-dati/enti.xlsx",
            "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_aind",
        ],
        "data_file": [
            "Fri, 30 Jan 2026 20:47:28 GMT", "Mon, 30 Mar 2026 21:50:38 GMT",
            "Fri, 26 Jan 2024 10:33:38 GMT", "Sat, 14 Nov 2026 04:18:47 GMT",
            "2026-02-06T23:00:00+0100",
        ],
    })
    assert _date_fonti(versioni) == {
        "istat_popolazione": "2026-03-30", "istat_comuni": "2024-01-26", "indicepa": "2026-11-14",
        "eurostat_prezzi": "2026-02-06",
    }


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
        "motivo": [None, None, None, None],
    })
    voci = voci_per_comune(righe, [2016, 2017, 2018])
    assert list(voci["A"]) == ["indicatore/09.05", "spesa_titolo/01"]
    assert voci["A"]["spesa_titolo/01"] == {
        "importo": [900.0, 1000.46, None], "procapite": [9, 11, None],
        "posizione": [40, 50, None], "mediana": [9, 11, None], "scarto": [None, 12.3, None],
    }
    assert voci["A"]["indicatore/09.05"] == {
        "valore": [12.35, None, None], "motivo": [None, None, None],
        "posizione": [70, None, None], "mediana": [5.55, None, None],
    }
    assert voci["B"]["spesa_titolo/01"]["mediana"] == [None, None, None]
    with pytest.raises(ValueError, match="ripetute"):
        voci_per_comune(pd.concat([righe, righe.head(1)]), [2016, 2017])


def test_indicatori_assenti_con_il_motivo(tmp_path):
    # a: 9.5 scritto ma scartato, 1.1 vuoto, 3.1 assente dal piano; b senza piano; c senza
    # residenti (fuori dai confronti)
    pd.DataFrame({
        "cf": ["a", "a", "a", "c"], "anno": 2025,
        "gruppo": ["09", "01", "04", "01"], "indicatore": ["05", "01", "01", "01"],
        "valore": [0.0, None, 30.0, 5.0],
    }).to_parquet(tmp_path / "2025.parquet")
    posizioni = pd.DataFrame({
        "cf": ["a"], "anno": [2025], "misura": ["indicatore"], "codice": ["04.01"],
    })
    gruppi = pd.DataFrame({
        "cf": ["a", "b", "c"], "anno": 2025, "stato": "consegnato", "fascia": [2, 2, None],
    })
    assenti = indicatori_assenti(duckdb.connect(), tmp_path, posizioni, gruppi)
    motivi = dict(zip(assenti["codice"], assenti["motivo"]))
    assert set(assenti["cf"]) == {"a"}
    assert "04.01" not in motivi
    assert (motivi["09.05"], motivi["01.01"], motivi["03.01"]) == (
        "escluso", "non compilato", "non compilato",
    )
