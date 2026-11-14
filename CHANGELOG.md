# Changelog

## 2026-11-14

- Confronti fra comuni simili: gruppi per fascia di abitanti e area, spesa ed entrate pro capite
  per titolo, missione e programma, mediana e percentili del gruppo, posizione di ogni comune.
- Codice ISTAT anche per i comuni estinti; le consegne distinguono "non consegnato" da "non
  esisteva".
- Controlli automatici dei numeri a fine lancio.

## 2026-11-12

- Pipeline dei dati di base: rendiconti dei comuni 2016-2025 da OpenBDAP (spese, entrate,
  risultato di amministrazione, indicatori ufficiali, parametri di deficitarietà), anagrafica
  degli enti con codice ISTAT, popolazione residente ISTAT.
- Lo scarico ricorda la versione di ogni file e riscarica solo ciò che alla fonte è cambiato.
