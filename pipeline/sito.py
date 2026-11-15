"""Sito statico: una pagina HTML per comune, generata dai file di `data/export/`.

Prima di scrivere controlla la forma di ogni JSON e si ferma al primo file fuori forma: una
pagina con un numero sbagliato di colonne mostrerebbe numeri sotto l'anno sbagliato.
"""
import json
import logging
import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from pipeline.esportazione import in_ascii
from pipeline.fonti import EXPORT, RADICE

log = logging.getLogger(__name__)

SITO = RADICE / "data" / "sito"
MODELLI = RADICE / "sito" / "modelli"
STATICO = RADICE / "sito" / "statico"
REPO = "https://github.com/AlbGri/trasparenza-comuni"
SEGNO_FATTO = SITO / ".generato"

CAMPI = {
    "id": str, "nome": str, "provincia": str, "regione": str, "codice_fiscale": str,
    "stato": str, "successore": (str, type(None)), "predecessori": list, "anni": list,
    "consegna": list, "residenti": list, "gruppo": list, "voci": dict,
    "parametri_accesi": list, "deficitario": list,
}
SERIE = ("consegna", "residenti", "gruppo", "parametri_accesi", "deficitario")
CONSEGNA = {"consegnato", "non consegnato", "non esisteva"}
STATI = {"attivo", "estinto"}

PRINCIPALI = (
    "spesa_titolo/01", "spesa_titolo/02", "entrate_proprie/01+03", "risultato_disponibile/0502",
)
NOMI_BREVI = {
    "spesa_titolo/01": "Spesa corrente",
    "spesa_titolo/02": "Spesa per investimenti",
    "entrate_proprie/01+03": "Entrate proprie",
    "risultato_disponibile/0502": "Parte disponibile del risultato",
    "indicatore/01.01": "Spese rigide (personale, debito, disavanzo) sulle entrate correnti",
    "indicatore/03.01": "Uso delle anticipazioni di tesoreria",
    "indicatore/04.01": "Spesa per il personale sulla spesa corrente",
    "indicatore/04.04": "Spesa per il personale, per abitante",
    "indicatore/05.01": "Spesa per servizi affidati all'esterno",
    "indicatore/07.04": "Investimenti, per abitante",
    "indicatore/09.05": "Tempi di pagamento delle fatture, rispetto alla scadenza",
    "indicatore/10.04": "Debito, per abitante",
    "indicatore/13.01": "Debiti fuori bilancio riconosciuti e finanziati",
    "indicatore/13.02": "Debiti fuori bilancio in corso di riconoscimento",
    "indicatore/13.03": "Debiti fuori bilancio riconosciuti, da finanziare",
}
DEBITI_FUORI_BILANCIO = ("indicatore/13.01", "indicatore/13.02", "indicatore/13.03")
MESI = (
    "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre "
    "dicembre"
).split()
AMBITI = {
    "regioni speciali": "regioni a statuto speciale",
    "regioni ordinarie": "regioni a statuto ordinario",
    "Italia": "tutta Italia",
}
PARAMETRO_DEFICITARIO = "0010"
ACCENTATE = dict(zip("aeiou", "àèìòù"))


def controlla(comune: dict, anni: list[int], voci: dict, gruppi: dict) -> list[str]:
    """Differenze fra un JSON di comune e la forma attesa; lista vuota se e' in forma.

    Args:
        comune: contenuto di `comuni/{id}.json`.
        anni: anni di `meta.json`.
        voci: voci del dizionario.
        gruppi: gruppi esportati, per identificativo.
    """
    problemi = [
        f"campo {campo} mancante o di tipo {type(comune.get(campo)).__name__}"
        for campo, tipo in CAMPI.items() if not isinstance(comune.get(campo), tipo)
    ]
    if problemi:
        return problemi
    if comune["anni"] != anni:
        problemi.append(f"anni {comune['anni']} invece di {anni}")
    lunghezze = {campo: comune[campo] for campo in SERIE}
    for voce, campi in comune["voci"].items():
        if voce not in voci:
            problemi.append(f"voce {voce} assente dal dizionario")
        lunghezze.update({f"{voce} {campo}": serie for campo, serie in campi.items()})
    problemi += [
        f"{nome}: {len(serie)} valori per {len(anni)} anni"
        for nome, serie in lunghezze.items() if len(serie) != len(anni)
    ]
    problemi += [f"consegna {valore!r}" for valore in set(comune["consegna"]) - CONSEGNA]
    problemi += [
        f"gruppo {gruppo} non esportato"
        for gruppo in set(comune["gruppo"]) - {None} if gruppo not in gruppi
    ]
    if comune["stato"] not in STATI:
        problemi.append(f"stato {comune['stato']!r}")
    return problemi


def indirizzo(identificativo: str, nome: str) -> str:
    """Cartella della pagina di un comune, es. `comuni/bologna-037006`."""
    return f"comuni/{in_ascii(nome)}-{identificativo}"


def accenti(testo: str) -> str:
    """Accenti al posto degli apostrofi in fondo alle parole, come li scrive la fonte."""
    return re.sub(r"([aeiou])'(?=[\s,.;:)]|$)", lambda m: ACCENTATE[m[1]], testo)


def numero(valore: float | None, decimali: int = 0) -> str:
    """Numero all'italiana: punto per le migliaia, virgola per i decimali."""
    if valore is None:
        return "n.d."
    testo = f"{valore:,.{decimali}f}"
    return testo.replace(",", " ").replace(".", ",").replace(" ", ".")


def con_unita(valore: float | None, unita: str) -> str:
    """Valore con la sua unita', nella forma breve delle tabelle."""
    if valore is None:
        return "n.d."
    if unita == "percentuale":
        return f"{numero(valore, 1)}%"
    if unita == "giorni":
        return f"{numero(valore)} giorni"
    return f"{numero(valore)} €"


def sopra(posizione: int | None) -> str:
    """Posizione nel gruppo detta a parole, senza giudizi."""
    if posizione is None:
        return ""
    if posizione == 0:
        return "nessun comune simile ha un valore più basso"
    if posizione == 100:
        return "più alto di tutti i comuni simili"
    articolo = "l'" if posizione in (1, 8, 11) or 80 <= posizione <= 89 else "il "
    return f"sopra {articolo}{posizione}% dei comuni simili"


def _riga(voce: str, dati: dict, i: int, dizionario: dict) -> dict | None:
    """Numeri di una voce nell'anno di indice i, pronti per il modello; None se manca."""
    definizione = dizionario[voce]
    if "valore" in dati:
        valore, unita = dati["valore"][i], definizione["unita"]
    elif dati["procapite"][i] is not None:
        valore, unita = dati["procapite"][i], definizione["unita"]
    else:
        # ente senza residenti: resta l'importo, senza pro capite ne' confronto
        valore, unita = dati["importo"][i], "euro"
    if valore is None:
        return None
    nome = NOMI_BREVI.get(voce, definizione["nome"].split(": ", 1)[-1])
    return {
        "voce": voce,
        "nome": nome,
        "nome_ufficiale": definizione["nome"],
        "valore": valore,
        "unita": unita,
        "testo": con_unita(valore, unita),
        "mediana": dati["mediana"][i] if unita != "euro" else None,
        "posizione": dati["posizione"][i] if unita != "euro" else None,
        "importo": dati["importo"][i] if "importo" in dati else None,
        "misura": definizione["misura"],
        "fonte": definizione["fonte"],
        "calcolato": definizione["calcolato"],
        "spiegazione": definizione.get("metodo") or definizione.get("nota", ""),
        "definizione": definizione.get("definizione", ""),
    }


def _gruppo(identificativo: str | None, i: int, gruppi: dict) -> dict | None:
    if identificativo is None:
        return None
    gruppo = gruppi[identificativo]
    fascia = gruppo["fascia"]
    if fascia.startswith(("sotto", "oltre")):
        abitanti = fascia.replace(" ", " i ", 1)
    else:
        primo, ultimo = fascia.split("-")
        abitanti = f"da {primo} a {ultimo}"
    ambito = AMBITI.get(gruppo["ambito"], gruppo["ambito"])
    return {
        "descrizione": f"comuni {abitanti} abitanti, {ambito}",
        "consegnati": gruppo["consegnati"][i],
    }


def _parametri(comune: dict, testi: dict) -> dict:
    """Parametri di deficitarieta' accesi almeno una volta, anno per anno, dal 2019."""
    anni = [
        (anno, accesi, deficitario)
        for anno, accesi, deficitario in zip(
            comune["anni"], comune["parametri_accesi"], comune["deficitario"]
        ) if accesi is not None
    ]
    codici = sorted({c for _, accesi, _ in anni for c in accesi} - {PARAMETRO_DEFICITARIO})
    return {
        "anni": [anno for anno, _, _ in anni],
        "righe": [
            {"testo": testi[c], "accesi": [c in accesi for _, accesi, _ in anni]} for c in codici
        ],
        "deficitario": [deficitario for _, _, deficitario in anni],
    }


def _in_parole(data: str) -> str:
    """Data ISO in parole, es. '8 maggio 2026'."""
    anno, mese, giorno = data.split("-")
    return f"{int(giorno)} {MESI[int(mese) - 1]} {anno}"


def _date_dei_dati(date: dict) -> list[str]:
    """Data dei dati per gruppi di anni consecutivi, es. '2016-2021: 8 maggio 2026'."""
    gruppi: list[list] = []
    for anno, data in date.items():
        if gruppi and gruppi[-1][2] == data:
            gruppi[-1][1] = anno
        else:
            gruppi.append([anno, anno, data])
    return [
        f"{primo if primo == ultimo else f'{primo}-{ultimo}'}: {_in_parole(data)}"
        for primo, ultimo, data in gruppi
    ]


def contesto(comune: dict, indice: dict, dizionario: dict, gruppi: dict, meta: dict) -> dict:
    """Tutto cio' che il modello della pagina mostra, gia' scelto e ordinato."""
    voci = dizionario["voci"]
    consegnati = [i for i, stato in enumerate(comune["consegna"]) if stato == "consegnato"]
    i = consegnati[-1] if consegnati else None
    righe = {}
    if i is not None:
        righe = {
            voce: riga for voce in voci if voce in comune["voci"]
            and (riga := _riga(voce, comune["voci"][voce], i, voci)) is not None
        }

    def scegli(prefisso: str) -> list[dict]:
        return [riga for voce, riga in righe.items() if voce.startswith(prefisso)]

    missioni = scegli("spesa_corrente_missione/")
    indicatori = scegli("indicatore/")
    # tre indicatori quasi sempre a zero: se lo sono tutti, una riga sola
    debiti_zero = all(righe.get(v, {}).get("valore") == 0 for v in DEBITI_FUORI_BILANCIO)
    if debiti_zero:
        indicatori = [r for r in indicatori if r["voce"] not in DEBITI_FUORI_BILANCIO]
    grafico = []
    for voce in [*PRINCIPALI, *(v for v in voci if v not in PRINCIPALI)]:
        if voce not in comune["voci"]:
            continue
        dati = comune["voci"][voce]
        serie = dati.get("valore") or dati["procapite"]
        unita = voci[voce]["unita"]
        if all(v is None for v in serie):
            serie, unita = dati.get("importo", serie), "euro"
        if any(v is not None for v in serie):
            grafico.append({
                "nome": NOMI_BREVI.get(voce, voci[voce]["nome"]),
                "unita": unita,
                "comune": serie,
                "mediana": dati["mediana"] if unita != "euro" else None,
            })
    andamento = [
        {"nome": NOMI_BREVI[voce], "unita": voci[voce]["unita"], **comune["voci"][voce]}
        for voce in PRINCIPALI
        if voce in comune["voci"] and any(v is not None for v in comune["voci"][voce]["procapite"])
    ]
    fonti = sorted({voci[voce]["fonte"] for voce in comune["voci"]})
    return {
        "c": comune,
        "radice": "../../",
        "anno": comune["anni"][i] if i is not None else None,
        "residenti": comune["residenti"][i] if i is not None else None,
        "senza_residenti": i is not None and comune["residenti"][i] is None,
        "gruppo": _gruppo(comune["gruppo"][i], i, gruppi) if i is not None else None,
        "consegne": list(zip(comune["anni"], comune["consegna"])),
        "principali": [righe[v] for v in PRINCIPALI if v in righe],
        "indicatori": indicatori,
        "debiti_zero": debiti_zero,
        "data_anno": _in_parole(meta["data_dei_dati"][str(comune["anni"][i])])
        if i is not None else None,
        "missioni": sorted(
            (r for r in missioni if r["valore"]), key=lambda r: r["valore"], reverse=True
        ),
        "missioni_zero": [r["nome"] for r in missioni if not r["valore"]],
        "programmi": scegli("spesa_corrente_programma/"),
        "entrate": [r for r in scegli("entrate_titolo/") if r["valore"]],
        "parametri": _parametri(comune, dizionario["parametri"]),
        "grafico": {"anni": comune["anni"], "voci": grafico},
        "andamento": andamento,
        "collegati": {
            ident: {
                "nome": indice[ident]["nome"],
                "indirizzo": indirizzo(ident, indice[ident]["nome"]),
            }
            for ident in [*comune["predecessori"], comune["successore"]] if ident in indice
        },
        "date_dei_dati": _date_dei_dati(meta["data_dei_dati"]),
        "esportazione": meta["esportazione"],
        "fonti": fonti,
        "segnala": f"{REPO}/issues/new",
    }


def _leggi(percorso: Path) -> dict:
    return json.loads(percorso.read_text(encoding="utf-8"))


def genera(scelti: list[str] | None = None, ingresso: Path = EXPORT, uscita: Path = SITO) -> int:
    """Scrive le pagine dei comuni e i file statici.

    Args:
        scelti: codici ISTAT dei comuni da generare; None = tutti, e le pagine vecchie si
            cancellano.
        ingresso: cartella dell'esportazione.
        uscita: cartella del sito.

    Returns:
        Numero di pagine scritte.

    Raises:
        ValueError: se un JSON non ha la forma attesa.
    """
    meta = _leggi(ingresso / "meta.json")
    dizionario = _leggi(ingresso / "dizionario.json")
    for definizione in dizionario["voci"].values():
        for campo in ("nome", "metodo", "nota"):
            if campo in definizione:
                definizione[campo] = accenti(definizione[campo])
    gruppi = {p.stem: _leggi(p) for p in (ingresso / "gruppi").glob("*.json")}
    elenco = _leggi(ingresso / "comuni.json")
    indice = {riga[0]: dict(zip(elenco["campi"], riga)) for riga in elenco["righe"]}
    identificativi = scelti or sorted(indice)
    comuni = {}
    for ident in identificativi:
        comune = _leggi(ingresso / "comuni" / f"{ident}.json")
        if problemi := controlla(comune, meta["anni"], dizionario["voci"], gruppi):
            raise ValueError(f"comuni/{ident}.json fuori forma: {'; '.join(problemi[:5])}")
        comuni[ident] = comune

    ambiente = Environment(
        loader=FileSystemLoader(MODELLI), autoescape=True, undefined=StrictUndefined,
        trim_blocks=True, lstrip_blocks=True,
    )
    ambiente.filters.update(numero=numero, con_unita=con_unita, sopra=sopra)
    modello = ambiente.get_template("comune.html")
    if scelti is None:
        shutil.rmtree(uscita / "comuni", ignore_errors=True)
    shutil.copytree(STATICO, uscita / "statico", dirs_exist_ok=True)
    for ident, comune in comuni.items():
        cartella = uscita / indirizzo(ident, comune["nome"])
        cartella.mkdir(parents=True, exist_ok=True)
        pagina = modello.render(contesto(comune, indice, dizionario, gruppi, meta))
        (cartella / "index.html").write_text(pagina, encoding="utf-8")
    return len(comuni)


def aggiorna(scelti: list[str] | None = None) -> bool:
    """Rigenera il sito se esportazione, modelli o file statici sono piu' recenti.

    Una scelta di comuni si genera sempre e non segna il sito come fatto.

    Returns:
        True se ha scritto delle pagine.
    """
    if scelti:
        log.info("sito: %d pagine in %s", genera(scelti), SITO)
        return True
    ingressi = [EXPORT / "meta.json", *MODELLI.iterdir(), *STATICO.iterdir()]
    if SEGNO_FATTO.exists() and SEGNO_FATTO.stat().st_mtime > max(
        i.stat().st_mtime for i in ingressi
    ):
        return False
    log.info("sito: %d pagine in %s", genera(), SITO)
    SEGNO_FATTO.touch()
    return True
