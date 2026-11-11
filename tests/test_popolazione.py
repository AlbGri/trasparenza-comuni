"""Lettura dei file ISTAT della popolazione."""
import zipfile

from pipeline.popolazione import leggi_posas, leggi_ricostruzione

RICOSTRUZIONE = """"Popolazione per età, vista per territorio - Comuni della Provincia di Prova"

"Ricostruzione della popolazione intercensuaria - Popolazione al 1° gennaio per età"
"Tutte le cittadinanze - Anno: 2017 - Provincia: Prova"
Territorio/Età;;0;1;2
Codice comune;Comune;Totale
084001;Alfa;10;20;30
084002;Beta;1;2;3
;Totale;11;22;33
Territorio/Età;;0;1;2
Codice comune;Comune;Maschi
084001;Alfa;4;9;14
084002;Beta;0;1;1

"Tutte le cittadinanze - Anno: 2018 - Provincia: Prova"
Territorio/Età;;0;1;2
Codice comune;Comune;Totale
084001;Alfa;11;21;31

"Cittadinanza straniera - Anno: 2017 - Provincia: Prova"
Territorio/Età;;0;1;2
Codice comune;Comune;Totale
084001;Alfa;1;1;1
"""

POSAS = """﻿"Popolazione residente per età e sesso al 1° gennaio 2026 (stima)"
"Codice comune";"Comune";"Età";"Totale maschi";"Totale femmine";"Totale"
"028001";"Abano Terme";0;60;53;113
"028001";"Abano Terme";999;9000;10000;19000
"028002";"Agna";999;1500;1600;3100
"""


def test_ricostruzione_solo_tutte_le_cittadinanze_e_totale():
    residenti = leggi_ricostruzione(RICOSTRUZIONE, {2017, 2018})
    assert residenti.values.tolist() == [
        ["084001", 2017, 60], ["084002", 2017, 6], ["084001", 2018, 63],
    ]


def test_ricostruzione_solo_gli_anni_chiesti():
    residenti = leggi_ricostruzione(RICOSTRUZIONE, {2018})
    assert residenti.values.tolist() == [["084001", 2018, 63]]


def test_posas_riga_del_totale(tmp_path):
    percorso = tmp_path / "POSAS_2026_it_Comuni.zip"
    with zipfile.ZipFile(percorso, "w") as archivio:
        archivio.writestr("POSAS_2026_it_Comuni.csv", POSAS.encode("utf-8"))
    residenti = leggi_posas(percorso)
    assert residenti.values.tolist() == [["028001", 19000], ["028002", 3100]]
