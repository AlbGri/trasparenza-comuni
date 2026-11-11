"""Registro delle versioni: decide se un file va riscaricato."""
from pipeline.scarico import Registro


def test_registro_ricorda_la_versione(tmp_path):
    percorso = tmp_path / "versioni_fonti.parquet"
    registro = Registro(percorso)
    assert not registro.invariato("https://fonte/a.zip#Spese.csv", '"e1"', "data 1")

    registro.registra("https://fonte/a.zip#Spese.csv", '"e1"', "data 1")
    riletto = Registro(percorso)
    assert riletto.invariato("https://fonte/a.zip#Spese.csv", '"e1"', "data 1")
    # pacchetto rigenerato alla fonte: stesso indirizzo, versione diversa
    assert not riletto.invariato("https://fonte/a.zip#Spese.csv", '"e2"', "data 2")
    # ogni CSV dello stesso zip ha la sua riga
    assert not riletto.invariato("https://fonte/a.zip#Entrate.csv", '"e1"', "data 1")


def test_registro_aggiorna_senza_doppioni(tmp_path):
    registro = Registro(tmp_path / "versioni_fonti.parquet")
    registro.registra("https://fonte/a.zip", '"e1"', "data 1")
    registro.registra("https://fonte/a.zip", '"e2"', "data 2")
    riletto = Registro(tmp_path / "versioni_fonti.parquet")
    assert len(riletto.righe) == 1
    assert riletto.invariato("https://fonte/a.zip", '"e2"', "data 2")
