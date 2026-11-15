"""Controllo della forma dei JSON, testi della pagina e generazione di una pagina."""
import json

import pytest

from pipeline.sito import accenti, controlla, genera, numero, sopra

ANNI = [2023, 2024]
VOCI = {
    "spesa_titolo/01": {
        "nome": "Spesa: Spese correnti", "unita": "euro per abitante", "calcolato": True,
        "fonte": "OpenBDAP, Spese.csv", "misura": "impegni, competenza",
        "metodo": "impegni del titolo 1, diviso i residenti", "andamento": True,
    },
    "spesa_corrente_missione/10": {
        "nome": "Spesa corrente: Trasporti e diritto alla mobilita'", "unita": "euro per abitante",
        "calcolato": True, "fonte": "OpenBDAP, Spese.csv", "misura": "impegni, competenza",
        "metodo": "impegni", "andamento": True,
    },
}


def _voce(procapite: list, posizione: list) -> dict:
    return {
        "importo": [p * 1000 if p is not None else None for p in procapite],
        "procapite": procapite, "posizione": posizione, "mediana": [900, 950],
        "scarto": [None, 1.0],
    }


@pytest.fixture
def comune():
    return {
        "id": "099001", "nome": "Borgo Prova", "provincia": "Roma", "regione": "Lazio",
        "codice_fiscale": "00000000000", "stato": "attivo", "successore": None,
        "predecessori": [], "anni": ANNI, "consegna": ["consegnato", "consegnato"],
        "residenti": [1000, 1000], "gruppo": ["2-centro", "2-centro"],
        "voci": {
            "spesa_titolo/01": _voce([1100, 1234], [70, 84]),
            "spesa_corrente_missione/10": _voce([50, 60], [40, 45]),
        },
        "parametri_accesi": [[], ["0008"]], "deficitario": [False, False],
    }


def test_comune_in_forma(comune):
    assert controlla(comune, ANNI, VOCI, {"2-centro": {}}) == []


def test_serie_corta_consegna_e_gruppo_sconosciuti(comune):
    comune["residenti"] = [1000]
    comune["consegna"][0] = "forse"
    comune["voci"]["spesa_titolo/01"]["mediana"] = [900]
    problemi = controlla(comune, ANNI, VOCI, {})
    assert "residenti: 1 valori per 2 anni" in problemi
    assert "spesa_titolo/01 mediana: 1 valori per 2 anni" in problemi
    assert "consegna 'forse'" in problemi
    assert "gruppo 2-centro non esportato" in problemi


def test_campo_mancante(comune):
    del comune["voci"]
    assert controlla(comune, ANNI, VOCI, {}) == ["campo voci mancante o di tipo NoneType"]


def test_testi():
    assert numero(1234567.891, 1) == "1.234.567,9"
    assert numero(None) == "n.d."
    assert sopra(84) == "sopra l'84% dei comuni simili"
    assert sopra(62) == "sopra il 62% dei comuni simili"
    assert sopra(0) == "nessun comune simile ha un valore più basso"
    assert accenti("Viabilita' e dell'ambiente, attivita'") == (
        "Viabilità e dell'ambiente, attività"
    )


def test_pagina_generata(comune, tmp_path):
    export = tmp_path / "export"
    (export / "comuni").mkdir(parents=True)
    (export / "gruppi").mkdir()
    file = {
        "meta.json": {
            "esportazione": "2026-11-15", "anni": ANNI,
            "data_dei_dati": {"2023": "2026-11-03", "2024": "2026-11-03"},
            "fasce": {"2": "1.000-5.000"},
        },
        "dizionario.json": {"voci": VOCI, "parametri": {"0008": "Riscossione minore del 47%"}},
        "comuni.json": {"campi": ["id", "nome"], "righe": [["099001", "Borgo Prova"]]},
        "gruppi/2-centro.json": {
            "id": "2-centro", "fascia": "1.000-5.000", "ambito": "Centro", "consegnati": [170, 172],
        },
        "comuni/099001.json": comune,
    }
    for nome, dati in file.items():
        (export / nome).write_text(json.dumps(dati), encoding="utf-8")

    assert genera(["099001"], export, tmp_path / "sito") == 1
    pagina = (tmp_path / "sito/comuni/borgo-prova-099001/index.html").read_text(encoding="utf-8")
    assert "Comune di Borgo Prova" in pagina
    assert "1.234 €" in pagina and "sopra l&#39;84% dei comuni simili" in pagina
    assert "comuni da 1.000 a 5.000 abitanti, Centro: 172 con il rendiconto 2024" in pagina
    assert "Trasporti e diritto alla mobilità" in pagina
    assert "Riscossione minore del 47%" in pagina
    assert (tmp_path / "sito/statico/stile.css").exists()


def test_json_fuori_forma_ferma_la_generazione(comune, tmp_path):
    comune["anni"] = [2024]
    export = tmp_path / "export"
    (export / "comuni").mkdir(parents=True)
    (export / "gruppi").mkdir()
    (export / "meta.json").write_text(json.dumps({"anni": ANNI}), encoding="utf-8")
    (export / "dizionario.json").write_text(json.dumps({"voci": VOCI}), encoding="utf-8")
    (export / "comuni.json").write_text(json.dumps({"campi": ["id"], "righe": [["099001"]]}))
    (export / "comuni/099001.json").write_text(json.dumps(comune), encoding="utf-8")
    with pytest.raises(ValueError, match="099001.json fuori forma"):
        genera(["099001"], export, tmp_path / "sito")
