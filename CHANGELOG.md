# Changelog

## 2026-11-14

- Confronti fra comuni simili: gruppi per fascia di abitanti e area, spesa ed entrate pro capite
  per titolo, missione e programma, mediana e percentili del gruppo, posizione di ogni comune.
- Codice ISTAT anche per i comuni estinti; le consegne distinguono "non consegnato" da "non
  esisteva".
- Controlli automatici dei numeri a fine lancio.
- Indicatori ufficiali del comune confrontati con i comuni simili (mediana e posizione). Per
  personale, investimenti e debito per abitante, uno zero che il comune ha lasciato non
  compilato vale come dato assente.
- Tempestività dei pagamenti: si mostrano solo i valori fra 60 giorni di anticipo e 365 di
  ritardo, diversi da zero; gli altri sono campi non compilati o scritti in una scala sbagliata.
- Spesa di personale, investimenti e debito per abitante: un valore negativo non si mostra; per
  personale e investimenti nemmeno un valore lontano da quello che risulta dagli altri numeri
  del rendiconto (sotto la metà o oltre il doppio), segno di un'unità di misura sbagliata.
- Andamento: quanto cambiano spesa ed entrate per abitante rispetto all'anno prima, a confronto
  con il cambiamento dei comuni simili.
- Parte disponibile del risultato di amministrazione per abitante (negativa = disavanzo).
- Descrizioni ufficiali dei codici di bilancio; indice dei prezzi IPCA per mostrare gli euro a
  prezzi costanti.
- Esportazione in file JSON: una scheda per comune, indice dei comuni, gruppi di confronto,
  dizionario delle voci.

## 2026-11-12

- Pipeline dei dati di base: rendiconti dei comuni 2016-2025 da OpenBDAP (spese, entrate,
  risultato di amministrazione, indicatori ufficiali, parametri di deficitarietà), anagrafica
  degli enti con codice ISTAT, popolazione residente ISTAT.
- Lo scarico ricorda la versione di ogni file e riscarica solo ciò che alla fonte è cambiato.
