"""Comando della pipeline: `python -m pipeline [passi] [--anni 2016-2025]`.

Senza argomenti esegue tutti i passi. Un passo salta cio' che alla fonte non e' cambiato.
"""
import argparse
import logging

from pipeline import anagrafica, popolazione, rendiconti
from pipeline.fonti import ANNI
from pipeline.scarico import Registro, nuova_sessione

log = logging.getLogger("pipeline")

PASSI = ["rendiconti", "anagrafica", "popolazione"]


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
        default=ANNI,
        help="anni dei rendiconti da aggiornare: uno solo o un intervallo, es. 2016-2025",
    )
    argomenti = parser.parse_args()
    if sconosciuti := set(argomenti.passi) - set(PASSI):
        parser.error(f"passi sconosciuti: {sorted(sconosciuti)}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    registro = Registro()
    sessione = nuova_sessione()

    convertiti = 0
    if "rendiconti" in argomenti.passi:
        convertiti = rendiconti.aggiorna(argomenti.anni, registro, sessione)
        log.info("rendiconti: %d file scaricati e convertiti", convertiti)
    if "anagrafica" in argomenti.passi:
        riscritta = anagrafica.aggiorna(registro, sessione, forza=convertiti > 0)
        log.info("anagrafica: %s", "riscritta" if riscritta else "invariata")
    if "popolazione" in argomenti.passi:
        riscritta = popolazione.aggiorna(registro, sessione)
        log.info("popolazione: %s", "riscritta" if riscritta else "invariata")


if __name__ == "__main__":
    main()
