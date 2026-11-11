"""Aggancio degli enti al codice ISTAT, eccezioni, estinti e consegne."""
import pandas as pd
import pytest

from pipeline.anagrafica import costruisci_consegne, costruisci_enti


def soggetto(cf, anno, denominazione, provincia, comune, regione="20", cessazione=None):
    return {
        "cf": cf, "anno": anno, "codice_bdap": "B" + cf, "denominazione": denominazione,
        "data_cessazione": cessazione, "codice_regione": regione, "regione": "X",
        "codice_provincia": provincia, "provincia": "PROVINCIA", "codice_comune": comune,
        "comune": denominazione,
    }


SOGGETTI = pd.DataFrame([
    # sardo: BDAP usa la provincia nuova (118), l'elenco ISTAT la vecchia (092)
    soggetto("001", 2023, "COMUNE DI CAGLIARI", "118", "009"),
    soggetto("001", 2024, "COMUNE DI CAGLIARI", "118", "009"),
    # IndicePA non lo conosce: il codice arriva dalle eccezioni
    soggetto("002", 2024, "COMUNE DI CAPUA", "061", "015", regione="15"),
    # estinto: BDAP gli scrive i codici del comune che lo ha assorbito
    soggetto("003", 2023, "COMUNE DI VECCHIO", "092", "009", cessazione="31/12/2023"),
])
IPA = pd.DataFrame({"cf": ["001", "999"], "catastale": ["B354", "Z999"]})
ISTAT = pd.DataFrame({
    "codice_regione": ["20", "15"], "codice_istat": ["092009", "061015"],
    "nome": ["Cagliari", "Capua"], "regione": ["Sardegna", "Campania"],
    "provincia": ["Cagliari", "Caserta"], "catastale": ["B354", "B715"],
})
ECCEZIONI = pd.DataFrame({"cf": ["002"], "codice_istat": ["061015"]})


@pytest.fixture
def enti():
    return costruisci_enti(SOGGETTI, IPA, ISTAT, ECCEZIONI).set_index("cf")


def test_codice_istat_dal_catastale_non_dai_codici_bdap(enti):
    assert enti.loc["001", "codice_istat"] == "092009"
    assert enti.loc["001", "tipo_regione"] == "speciale"


def test_eccezione_a_mano(enti):
    assert enti.loc["002", "codice_istat"] == "061015"
    assert enti.loc["002", "nome"] == "Capua"
    assert enti.loc["002", "tipo_regione"] == "ordinaria"


def test_estinto_con_successore(enti):
    assert enti.loc["003", "stato"] == "estinto"
    assert enti.loc["003", "successore"] == "001"
    assert pd.isna(enti.loc["003", "codice_istat"])
    assert enti.loc["001", "stato"] == "attivo"


def test_eccezione_su_ente_inesistente():
    eccezioni = pd.DataFrame({"cf": ["777"], "codice_istat": ["061015"]})
    with pytest.raises(ValueError, match="inesistenti"):
        costruisci_enti(SOGGETTI, IPA, ISTAT, eccezioni)


def test_due_enti_attivi_sullo_stesso_codice():
    ipa = pd.DataFrame({"cf": ["001", "002"], "catastale": ["B354", "B354"]})
    senza_eccezioni = pd.DataFrame({"cf": [], "codice_istat": []}, dtype=str)
    with pytest.raises(ValueError, match="stesso codice ISTAT"):
        costruisci_enti(SOGGETTI, ipa, ISTAT, senza_eccezioni)


def test_consegne_assenza_come_dato(enti):
    consegne = costruisci_consegne(SOGGETTI, enti.reset_index())
    presenti = consegne.set_index(["cf", "anno"])["presente"]
    assert len(consegne) == 6
    assert presenti[("001", 2023)] and presenti[("001", 2024)]
    assert not presenti[("002", 2023)]
    assert not presenti[("003", 2024)]
