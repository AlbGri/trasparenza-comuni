"""Lettura dei CSV OpenBDAP: codifica, colonna vuota in coda, filtro dei comuni, esclusioni."""
import io
from decimal import Decimal

import pandas as pd
import pytest

from pipeline.rendiconti import CODIFICA, TABELLE, converti, converti_soggetti
from pipeline.scarico import trascrivi_utf8

COMUNI = [
    "Esercizio Finanziario", "Codice Tipologia Soggetto", "Descrizione Tipologia Soggetto",
    "Codice BDAP", "Denominazione Soggetto", "CF Soggetto", "Data Cessazione Soggetto",
    "Codice Zona Geografica", "Descrizione Zona Geografica", "Codice Regione",
    "Descrizione Regione", "Codice Provincia", "Descrizione Provincia", "Codice Comune",
    "Descrizione Comune",
]
SPESE = COMUNI + [
    "Codice Missione Arconet", "Desc Missione Arconet", "Codice Programma Arconet",
    "Desc Programma Arconet", "Codice Titolo Spese Arconet", "Desc Titolo Spese Arconet",
    "Pre.  Def. in CC", "Impegni", "Tot. Pag.",
]
ENTRATE = COMUNI + [
    "Codice Titolo Entrata Arconet", "Cod Tipologia Entrata Arconet", "Accert. in CC",
    "Tot. Riscos.",
]
FORLI = ["2024", "ELCOMU", "COMUNI", "111", "COMUNE DI FORLÌ", "00606620409", "", "2",
         "NORD-EST", "08", "EMILIA-ROMAGNA", "040", "FORLÌ-CESENA", "012", "FORLÌ"]
UNIONE = ["2024", "ELUCOM", "UNIONI DI COMUNI", "222", "UNIONE DEI COMUNI", "90000000001", "",
          "2", "NORD-EST", "08", "EMILIA-ROMAGNA", "040", "FORLÌ-CESENA", "012", "FORLÌ"]


def scrivi_csv(percorso, intestazione, righe):
    """Scrive un CSV come quelli di OpenBDAP: cp1252, virgolette, `;` anche a fine riga."""
    def riga(campi):
        return "".join(f'"{campo}";' if campo != "" else ";" for campo in campi)

    testo = "\r\n".join([riga(intestazione), *(riga(campi) for campi in righe)]) + "\r\n"
    grezzo = percorso.with_suffix(".cp1252")
    grezzo.write_bytes(testo.encode("cp1252"))
    with open(grezzo, "rb") as origine:
        trascrivi_utf8(origine, percorso, CODIFICA)
    return percorso


def spesa(ente, missione, titolo, impegni, programma="01"):
    return ente + [missione, "m", programma, "p", titolo, "t", "100", impegni, "5.5"]


@pytest.fixture
def csv_spese(tmp_path):
    righe = [
        spesa(FORLI, "01", "01", "244909.52"),
        spesa(FORLI, "01", "02", ""),
        spesa(FORLI, "60", "01", "10"),
        spesa(FORLI, "99", "07", "20"),
        spesa(FORLI, "50", "05", "30"),
        spesa(UNIONE, "01", "01", "999"),
    ]
    return scrivi_csv(tmp_path / "spese.csv", SPESE, righe)


def test_codifica_cp1252_non_si_deduce_dall_inizio(tmp_path):
    # inizio solo ASCII, poi caratteri che in UTF-8 non sono validi (0x92 e 0xE0)
    grezzo = b"a" * 5_000_000 + "l’unità".encode("cp1252")
    destinazione = tmp_path / "testo.txt"
    trascrivi_utf8(io.BytesIO(grezzo), destinazione, CODIFICA)
    assert destinazione.read_text(encoding="utf-8").endswith("l’unità")


def test_accenti_conservati(csv_spese, tmp_path):
    converti_soggetti(csv_spese, tmp_path / "soggetti.parquet")
    soggetti = pd.read_parquet(tmp_path / "soggetti.parquet")
    assert soggetti["denominazione"].tolist() == ["COMUNE DI FORLÌ"]
    assert soggetti["data_cessazione"].isna().all()


def test_colonna_vuota_finale_scartata(csv_spese, tmp_path):
    converti(csv_spese, TABELLE["spese"], tmp_path / "spese.parquet")
    spese = pd.read_parquet(tmp_path / "spese.parquet")
    assert list(spese.columns) == [
        "cf", "anno", "missione", "programma", "titolo",
        "impegni", "pagamenti_totali", "previsioni_definitive", "esclusa",
    ]


def test_solo_i_comuni(csv_spese, tmp_path):
    converti(csv_spese, TABELLE["spese"], tmp_path / "spese.parquet")
    spese = pd.read_parquet(tmp_path / "spese.parquet")
    assert set(spese["cf"]) == {"00606620409"}
    assert len(spese) == 5


def test_numeri_decimali_e_celle_vuote(csv_spese, tmp_path):
    converti(csv_spese, TABELLE["spese"], tmp_path / "spese.parquet")
    spese = pd.read_parquet(tmp_path / "spese.parquet").set_index(["missione", "titolo"])
    assert spese.loc[("01", "01"), "impegni"] == Decimal("244909.52")
    assert pd.isna(spese.loc[("01", "02"), "impegni"])


def test_esclusioni_della_spesa(csv_spese, tmp_path):
    converti(csv_spese, TABELLE["spese"], tmp_path / "spese.parquet")
    spese = pd.read_parquet(tmp_path / "spese.parquet")
    escluse = spese[spese["esclusa"]]
    assert sorted(zip(escluse["missione"], escluse["titolo"])) == [
        ("50", "05"), ("60", "01"), ("99", "07"),
    ]


def test_esclusioni_delle_entrate(tmp_path):
    righe = [FORLI + [titolo, "0100", "1", "1"] for titolo in ("01", "06", "07", "09")]
    csv = scrivi_csv(tmp_path / "entrate.csv", ENTRATE, righe)
    converti(csv, TABELLE["entrate"], tmp_path / "entrate.parquet")
    entrate = pd.read_parquet(tmp_path / "entrate.parquet")
    assert entrate[entrate["esclusa"]]["titolo"].tolist() == ["07", "09"]


def test_colonna_mancante(tmp_path):
    csv = scrivi_csv(tmp_path / "spese.csv", SPESE[:-1], [spesa(FORLI, "01", "01", "1")[:-1]])
    with pytest.raises(ValueError, match="colonne mancanti"):
        converti(csv, TABELLE["spese"], tmp_path / "spese.parquet")


def test_chiave_ripetuta(tmp_path):
    righe = [spesa(FORLI, "01", "01", "1"), spesa(FORLI, "01", "01", "2")]
    csv = scrivi_csv(tmp_path / "spese.csv", SPESE, righe)
    with pytest.raises(ValueError, match="chiavi ripetute"):
        converti(csv, TABELLE["spese"], tmp_path / "spese.parquet")
