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
    # nato da fusione il 1 marzo 2024: il 2023 non esisteva
    soggetto("004", 2024, "COMUNE DI NUOVO", "061", "016", regione="15"),
])
IPA = pd.DataFrame({"cf": ["001", "004", "999"], "catastale": ["B354", "N001", "Z999"]})
ISTAT = pd.DataFrame({
    "codice_regione": ["20", "15", "15"], "codice_istat": ["092009", "061015", "061016"],
    "nome": ["Cagliari", "Capua", "Nuovo"], "regione": ["Sardegna", "Campania", "Campania"],
    "provincia": ["Cagliari", "Caserta", "Caserta"], "catastale": ["B354", "B715", "N001"],
})
ECCEZIONI = pd.DataFrame({"cf": ["002"], "codice_istat": ["061015"]})
VARIAZIONI = pd.DataFrame({
    "tipo": ["ES", "ES", "CS"],
    "codice": ["092100", "013100", "061016"],
    # stesso nome in un'altra provincia: si distingue per il comune di arrivo
    "nome": ["Vecchio", "Vecchio", "Nuovo"],
    "codice_associato": ["092009", "013999", "061015"],
    "data": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-03-01"]),
})


@pytest.fixture
def enti():
    return costruisci_enti(SOGGETTI, IPA, ISTAT, ECCEZIONI, VARIAZIONI).set_index("cf")


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
    assert enti.loc["001", "stato"] == "attivo"


def test_estinto_con_il_suo_codice_storico(enti):
    assert enti.loc["003", "codice_istat"] == "092100"
    assert enti.loc["003", "nome"] == "Vecchio"


def test_estinto_per_nome_se_il_comune_di_arrivo_non_coincide():
    enti = costruisci_enti(SOGGETTI, IPA, ISTAT, ECCEZIONI, VARIAZIONI.iloc[1:])
    assert enti.set_index("cf").loc["003", "codice_istat"] == "013100"


def test_estinto_senza_codice_storico():
    with pytest.raises(ValueError, match="senza codice ISTAT storico"):
        costruisci_enti(SOGGETTI, IPA, ISTAT, ECCEZIONI, VARIAZIONI.iloc[2:])


def test_data_di_nascita_dalle_costituzioni(enti):
    assert enti.loc["004", "data_istituzione"] == pd.Timestamp("2024-03-01")
    assert pd.isna(enti.loc["001", "data_istituzione"])


def test_eccezione_su_ente_inesistente():
    eccezioni = pd.DataFrame({"cf": ["777"], "codice_istat": ["061015"]})
    with pytest.raises(ValueError, match="inesistenti"):
        costruisci_enti(SOGGETTI, IPA, ISTAT, eccezioni, VARIAZIONI)


def test_due_enti_attivi_sullo_stesso_codice():
    ipa = pd.DataFrame({"cf": ["001", "002"], "catastale": ["B354", "B354"]})
    senza_eccezioni = pd.DataFrame({"cf": [], "codice_istat": []}, dtype=str)
    with pytest.raises(ValueError, match="stesso codice ISTAT"):
        costruisci_enti(SOGGETTI, ipa, ISTAT, senza_eccezioni, VARIAZIONI)


def test_consegne_assenza_come_dato(enti):
    consegne = costruisci_consegne(SOGGETTI, enti.reset_index())
    stato = consegne.set_index(["cf", "anno"])["stato"]
    assert len(consegne) == 8
    assert stato[("001", 2023)] == stato[("001", 2024)] == "consegnato"
    assert stato[("002", 2023)] == "non consegnato"
    # estinto il 31/12/2023, nato il 1/3/2024: l'anno fuori dalla loro vita non e' un'assenza
    assert stato[("003", 2024)] == "non esisteva"
    assert stato[("004", 2023)] == "non esisteva"


def test_consegne_estinto_a_fine_anno_senza_rendiconto(enti):
    senza_2023 = SOGGETTI[~((SOGGETTI["cf"] == "003") & (SOGGETTI["anno"] == 2023))]
    senza_2023 = pd.concat([senza_2023, SOGGETTI.iloc[[0]].assign(anno=2022)])
    stato = costruisci_consegne(senza_2023, enti.reset_index()).set_index(["cf", "anno"])
    assert stato.loc[("003", 2023), "stato"] == "non consegnato"
