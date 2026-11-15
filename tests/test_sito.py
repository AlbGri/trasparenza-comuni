"""Controllo della forma dei JSON, testi delle pagine, elenchi e generazione del sito."""
import json

import pytest

from pipeline.sito import (
    accenti, controlla, elenca, genera, indice_ricerca, mancanti, numero, sopra,
)

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
    "indicatore/09.05": {
        "nome": "Indicatore annuale di tempestivita' dei pagamenti", "unita": "giorni",
        "calcolato": False, "fonte": "OpenBDAP, Piano degli indicatori",
        "misura": "indicatore ufficiale, rendiconto", "definizione": "giorni", "andamento": False,
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
        "cessazione": None,
        "predecessori": [], "anni": ANNI, "consegna": ["consegnato", "consegnato"],
        "residenti": [1000, 1000], "gruppo": ["2-centro", "2-centro"],
        "voci": {
            "spesa_titolo/01": _voce([1100, 1234], [70, 84]),
            "spesa_corrente_missione/10": _voce([50, 60], [40, 45]),
            "indicatore/09.05": {
                "valore": [-5.0, None], "motivo": [None, "escluso"],
                "posizione": [30, None], "mediana": [2.0, 3.0],
            },
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
    assert elenca([2019, 2020, 2021]) == "2019, 2020 e 2021"
    assert elenca([2025]) == "2025"
    assert accenti("Viabilita' e dell'ambiente, attivita'") == (
        "Viabilità e dell'ambiente, attività"
    )


def test_pagina_generata(comune, tmp_path):
    # parametri del 2023 assenti dalla fonte, con il rendiconto consegnato
    comune["parametri_accesi"][0] = None
    comune["deficitario"][0] = None
    export = tmp_path / "export"
    (export / "comuni").mkdir(parents=True)
    (export / "gruppi").mkdir()
    file = {
        "meta.json": {
            "esportazione": "2026-11-15", "anni": ANNI,
            "data_dei_dati": {"2023": "2026-11-03", "2024": "2026-11-03"},
            "fasce": {"2": "1.000-5.000"},
            "date_fonti": {
                "istat_popolazione": "2026-03-30", "istat_comuni": "2025-01-09",
                "indicepa": "2026-11-14", "eurostat_prezzi": "2026-02-06",
            },
            "prezzi": {"valori": {"2023": 120.9, "2024": 122.3}},
        },
        "dizionario.json": {"voci": VOCI, "parametri": {"0008": "Riscossione minore del 47%"}},
        "comuni.json": {
            "campi": ["id", "nome", "provincia", "regione", "stato", "residenti"],
            "righe": [["099001", "Borgo Prova", "Roma", "Lazio", "attivo", 1000]],
        },
        "gruppi/2-centro.json": {
            "id": "2-centro", "fascia": "1.000-5.000", "ambito": "Centro",
            "comuni": [175, 180], "consegnati": [170, 172],
        },
        "comuni/099001.json": comune,
    }
    for nome, dati in file.items():
        (export / nome).write_text(json.dumps(dati), encoding="utf-8")

    assert genera(["099001"], export, tmp_path / "sito") == 1
    pagina = (tmp_path / "sito/comuni/borgo-prova-099001/index.html").read_text(encoding="utf-8")
    assert "Comune di Borgo Prova" in pagina
    assert "1.234 €" in pagina and "sopra l&#39;84% dei comuni simili" in pagina
    assert "comuni da 1.000 a 5.000 abitanti, Centro: 172 su 180 con il rendiconto 2024" in pagina
    assert "progetto indipendente: non è del Comune di Borgo Prova" in pagina
    assert "escluso da una regola del sito" in pagina
    assert "Parametri non presenti nella banca dati OpenBDAP per il 2023" in pagina
    assert "trasparenza-comuni@albgri.com" in pagina
    assert "cdn.plot.ly" not in pagina
    assert (tmp_path / "sito/statico/plotly-basic-2.35.2.min.js").exists()
    assert "Trasporti e diritto alla mobilità" in pagina
    assert "Riscossione minore del 47%" in pagina
    assert (tmp_path / "sito/statico/stile.css").exists()
    iniziale = (tmp_path / "sito/index.html").read_text(encoding="utf-8")
    assert "Rendiconto 2024: 1 comuni presenti nella banca dati, 0 assenti" in iniziale
    elenco = (tmp_path / "sito/comuni-senza-rendiconto/index.html").read_text(encoding="utf-8")
    assert "Rendiconto 2024 non presente: 0 comuni" in elenco
    metodo = (tmp_path / "sito/metodo/index.html").read_text(encoding="utf-8")
    assert "Sei fasce di abitanti: 1.000-5.000." in metodo
    assert "saliti di circa il 1%" in metodo and "2023-2024: 3 novembre 2026" in metodo
    sito = "https://trasparenza-comuni.albgri.com/"
    assert f'<link rel="canonical" href="{sito}comuni/borgo-prova-099001/">' in pagina
    assert f'<link rel="canonical" href="{sito}metodo/">' in metodo
    mappa = (tmp_path / "sito/sitemap.xml").read_text(encoding="utf-8")
    assert mappa.count("<lastmod>2026-11-15</lastmod>") == 4
    assert f"<loc>{sito}</loc>" in mappa and f"<loc>{sito}comuni/borgo-prova-099001/</loc>" in mappa
    assert json.loads((tmp_path / "sito/cerca.json").read_text(encoding="utf-8")) == {
        "province": ["Roma"], "comuni": [["099001", "Borgo Prova", 0, 1000]],
    }


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


def _indice(*righe) -> dict:
    campi = ["id", "nome", "provincia", "regione", "stato", "residenti"]
    return {riga[0]: dict(zip(campi, riga)) for riga in righe}


def test_comuni_senza_rendiconto():
    indice = _indice(
        ("001", "Zeta", "Torino", "Piemonte", "attivo", 500),
        ("002", "Alfa", "Torino", "Piemonte", "attivo", 900),
        ("003", "Beta", "Roma", "Lazio", "estinto", None),
        ("004", "Gamma", "Roma", "Lazio", "attivo", 2000),
    )
    consegne = {
        "001": ["non consegnato", "non consegnato", "non consegnato"],
        "002": ["consegnato", "non consegnato", "non consegnato"],
        "003": ["non consegnato", "consegnato", "non esisteva"],
        "004": ["consegnato", "consegnato", "consegnato"],
    }
    meta = {
        "anni": [2023, 2024, 2025],
        "data_dei_dati": dict.fromkeys(["2023", "2024", "2025"], "2026-11-03"),
    }
    risultato = mancanti({i: {"consegna": c} for i, c in consegne.items()}, indice, meta)
    assert [(a["anno"], a["consegnati"], a["mancanti"]) for a in risultato["conteggi"]] == [
        (2023, 2, 2), (2024, 2, 2), (2025, 1, 2),
    ]
    assert risultato["conteggi"][0]["data"] == "3 novembre 2026"
    assert [(r["nome"], r["anni"]) for r in risultato["ultimo"]["Piemonte"]] == [
        ("Alfa", [2024]), ("Zeta", [2023, 2024]),
    ]
    assert list(risultato["prima"]) == ["Lazio"]
    beta = risultato["prima"]["Lazio"][0]
    assert beta["estinto"] and beta["indirizzo"] == "comuni/beta-003"


def test_indice_ricerca():
    indice = _indice(
        ("002", "Sant'Agata", "Torino", "Piemonte", "attivo", 900),
        ("001", "Beta", "Roma", "Lazio", "estinto", None),
    )
    assert indice_ricerca(indice) == {
        "province": ["Roma", "Torino"],
        "comuni": [["001", "Beta", 0, 0, 1], ["002", "Sant'Agata", 1, 900]],
    }
