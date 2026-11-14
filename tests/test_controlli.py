"""Confronto dei numeri di controllo con quelli attesi."""
import pandas as pd

from pipeline.controlli import confronta


def test_tolleranze_per_misura():
    attesi = pd.DataFrame({
        "anno": 2024,
        "misura": [
            "comuni", "impegni_mld", "spesa_corrente_mld", "mediana_fascia_1", "residenti",
        ],
        "atteso": [7813, 111.31, 62.97, 1348, 100],
    })
    misurati = pd.DataFrame({
        "anno": 2024,
        "misura": ["comuni", "impegni_mld", "spesa_corrente_mld", "mediana_fascia_1"],
        "valore": [7813, 111.314, 62.98, 1348.9],
    })
    esiti = confronta(misurati, attesi)["esito"].tolist()
    # dieci milioni di scarto sulla spesa corrente non tornano; residenti non misurati nemmeno
    assert esiti == [True, True, False, True, False]


def test_un_comune_in_piu_non_torna():
    attesi = pd.DataFrame({"anno": [2016], "misura": ["comuni"], "atteso": [7699]})
    misurati = pd.DataFrame({"anno": [2016], "misura": ["comuni"], "valore": [7700]})
    assert not confronta(misurati, attesi)["esito"].iloc[0]
