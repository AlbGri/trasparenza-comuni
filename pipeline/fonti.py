"""Indirizzi delle fonti e cartelle dei dati."""
from pathlib import Path
from urllib.parse import quote

USER_AGENT = (
    "trasparenza-comuni/0.1 (osservatorio civico sui bilanci comunali; "
    "+https://github.com/AlbGri/trasparenza-comuni)"
)

RADICE = Path(__file__).resolve().parent.parent
RAW = RADICE / "data" / "raw"
PROCESSED = RADICE / "data" / "processed"

# primo esercizio dei bilanci armonizzati e primo file POSAS; gli ultimi si chiedono alla fonte
PRIMO_ANNO = 2016
PRIMA_DATA_POSAS = 2019

OPENBDAP = "https://openbdap.rgs.mef.gov.it"
URL_ELENCO_ISTAT = (
    "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv"
)
URL_POSAS = "https://demo.istat.it/data/posas/POSAS_{anno}_it_Comuni.zip"
URL_RICOSTRUZIONE = "https://demo.istat.it/data/ricostruzione/PopolazioneEta-Territorio-Comuni.zip"
URL_VARIAZIONI = (
    "https://www.istat.it/storage/codici-unita-amministrative/"
    "Variazioni-amministrative-e-territoriali-dal-1991.zip"
)
URL_INDICEPA = "https://indicepa.gov.it/ipa-dati/api/3/action/package_show?id=enti"
# IPCA (indice armonizzato dei prezzi al consumo) dell'Italia, media annua: lo calcola ISTAT,
# lo distribuisce Eurostat, la cui API risponde mentre quella SDMX di ISTAT no
URL_IPCA = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_aind"
    "?geo=IT&coicop=CP00&unit=INX_A_AVG"
)
EXPORT = RADICE / "data" / "export"


def url_rendiconto(anno: int, pacchetto: str) -> str:
    """Indirizzo dello zip nazionale di un anno.

    Args:
        anno: esercizio finanziario.
        pacchetto: "Schemi di bilancio" oppure "Piano degli indicatori".
    """
    return f"{OPENBDAP}/Datasets_FET/Rendiconto/{anno}/" + quote(
        f"{anno}_Rendiconto - {pacchetto}.zip"
    )
