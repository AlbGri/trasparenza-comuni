"""Comando della pipeline: `python -m pipeline [passi] [--anni 2016-2025] [--comuni ...]`.

Senza argomenti esegue tutti i passi. Un passo salta cio' che alla fonte non e' cambiato. A
fine lancio confronta i numeri di controllo con quelli attesi; se uno non torna esce con
codice 1 e il sito non si genera.
"""
import argparse
import logging
import sys

from pipeline import (
    anagrafica, confronti, controlli, esportazione, popolazione, prezzi, rendiconti, sito,
)
from pipeline.fonti import PRIMO_ANNO, url_rendiconto
from pipeline.scarico import Registro, anni_pubblicati, nuova_sessione

log = logging.getLogger("pipeline")

PASSI = ["rendiconti", "anagrafica", "popolazione", "prezzi", "confronti", "esportazione", "sito"]


def _anni(testo: str) -> range:
    primo, _, ultimo = testo.partition("-")
    return range(int(primo), int(ultimo or primo) + 1)


def main() -> None:
    """Esegue i passi chiesti, nell'ordine in cui dipendono l'uno dall'altro."""
    parser = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__)
    parser.add_argument("passi", nargs="*", default=PASSI, help=f"fra {', '.join(PASSI)}")
    parser.add_argument(
        "--anni",
        type=_anni,
        help="anni dei rendiconti da aggiornare: uno solo o un intervallo, es. 2016-2025 "
        "(senza, tutti quelli pubblicati da OpenBDAP)",
    )
    parser.add_argument(
        "--comuni",
        type=lambda testo: testo.split(","),
        help="codici ISTAT separati da virgole: il sito genera solo queste pagine",
    )
    argomenti = parser.parse_args()
    if sconosciuti := set(argomenti.passi) - set(PASSI):
        parser.error(f"passi sconosciuti: {sorted(sconosciuti)}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    registro = Registro()
    sessione = nuova_sessione()

    convertiti = 0
    if "rendiconti" in argomenti.passi:
        anni = argomenti.anni or anni_pubblicati(
            PRIMO_ANNO, lambda anno: url_rendiconto(anno, "Schemi di bilancio"), sessione
        )
        log.info("rendiconti: anni %d-%d", anni[0], anni[-1])
        convertiti = rendiconti.aggiorna(anni, registro, sessione)
        log.info("rendiconti: %d file scaricati e convertiti", convertiti)
    if "anagrafica" in argomenti.passi:
        riscritta = anagrafica.aggiorna(registro, sessione, forza=convertiti > 0)
        log.info("anagrafica: %s", "riscritta" if riscritta else "invariata")
    if "popolazione" in argomenti.passi:
        riscritta = popolazione.aggiorna(registro, sessione)
        log.info("popolazione: %s", "riscritta" if riscritta else "invariata")
    if "prezzi" in argomenti.passi:
        riscritta = prezzi.aggiorna(registro, sessione)
        log.info("prezzi: %s", "riscritti" if riscritta else "invariati")
    if "confronti" in argomenti.passi:
        riscritti = confronti.aggiorna()
        log.info("confronti: %s", "ricalcolati" if riscritti else "invariati")
    if "esportazione" in argomenti.passi:
        riscritta = esportazione.aggiorna()
        log.info("esportazione: %s", "riscritta" if riscritta else "invariata")
    if not controlli.esegui():
        sys.exit(1)
    if "sito" in argomenti.passi:
        scritto = sito.aggiorna(argomenti.comuni)
        log.info("sito: %s", "generato" if scritto else "invariato")


if __name__ == "__main__":
    main()
