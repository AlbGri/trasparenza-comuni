# Changelog

## 2026-11-21

- Nuovo aspetto, con lo stile comune dei siti di AlbGri: mappa del sito a sinistra (sul telefono
  dal pulsante "Mappa"), con le sezioni della pagina aperta; briciole in alto; caratteri
  Alegreya e Atkinson Hyperlegible Next, serviti dal sito.
- Tema scuro, che segue il sistema finché non si sceglie con il pulsante in alto; anche il
  grafico dell'andamento cambia colori.
- "Dati aggiornati al" nella barra in alto.
- Pagina iniziale più breve: ricerca e riquadri verso i comuni senza rendiconto e il metodo.
- Pagina del comune: i dati in tabella sotto il grafico si aprono con "Dati in tabella".
- Piede di due righe, con il contatto, chi cura il sito e l'indipendenza dalla Ragioneria
  Generale dello Stato.

## 2026-11-15

- Sito pubblicato su https://trasparenza-comuni.albgri.com/ (indirizzo di riserva
  https://albgri.github.io/trasparenza-comuni/).
- Sito statico: una pagina per ognuno degli 8.057 comuni, estinti
  compresi, con indicatori ufficiali del rendiconto, numeri calcolati dal sito con mediana e
  posizione fra i comuni simili, spesa per servizio, entrate, parametri di deficitarietà,
  andamento dal 2016 e fonti con la data dei dati.
- Pagina iniziale con la ricerca del comune per nome, anche scritto senza accenti.
- Pagina dei comuni senza rendiconto, anno per anno e per regione.
- Pagina del metodo: impegni e pagamenti, comuni simili, mediana e posizione, indicatori
  ufficiali e voci calcolate, valori trattati come assenti, rendiconti non consegnati, fusioni,
  limiti dei numeri, fonti con le date.
- Sitemap di tutte le pagine e indirizzo canonico su trasparenza-comuni.albgri.com, per i
  motori di ricerca.
- Revisione prima della pubblicazione: ogni pagina dice sotto il titolo che il progetto è
  indipendente; le entrate proprie non comprendono più i fondi perequativi dello Stato; gli
  indicatori ufficiali assenti restano come "n.d." con il motivo; i parametri di
  deficitarietà mancanti nella banca dati sono detti tali; avvisi per i comuni estinti (con la
  data) e per quelli con l'ultimo rendiconto vecchio; il 2025 è indicato come provvisorio;
  "N su M con il rendiconto" accanto ai comuni simili; nota sui comuni sotto i 300 abitanti.
- Metodo: entrate proprie, comuni piccolissimi, differenze con i gruppi del portale OpenBDAP,
  ultimo anno provvisorio, licenze delle fonti, come citare, contatti e privacy.
- Indirizzo email per le segnalazioni; nessun file caricato da altri siti (il grafico è servito
  dal sito stesso), nessun cookie del sito: solo quello tecnico di Cloudflare, dichiarato nel
  metodo.
- Debito per abitante (indicatore 10.4): un valore molto lontano dagli altri anni dello stesso
  comune, o dal rimborso dei prestiti dell'anno dopo, è trattato come scritto in un'unità
  sbagliata e si mostra come "n.d." (935 valori in tutti gli anni).
- Testi più neutri: gli indicatori ufficiali sono "calcolati dal comune e allegati al suo
  rendiconto"; la sezione si chiama "Parametri di deficitarietà" e ricorda che non è un
  giudizio di dissesto.
- Nei gruppi con meno di 30 comuni la posizione si dice contando ("sopra 7 dei 9 comuni
  simili"); una voce a zero non ha posizione, con una nota sui servizi svolti da un'unione o da
  un altro ente.
- Tempi di pagamento in giorni prima o dopo la scadenza, con un decimale.
- Date scritte per esteso ("dell'8 maggio"), segno meno leggibile nelle definizioni ufficiali,
  "7.893 comuni attivi" nella pagina iniziale.
- Una pagina per ogni gruppo di comuni simili e per ogni anno, collegata da "Confrontato con":
  regola del gruppo ed elenco dei comuni con provincia, residenti e rendiconto consegnato o no.
- In fondo alla pagina di ogni comune, "Usare questi dati": l'andamento delle voci principali
  in CSV per Excel, la citazione già compilata con l'indirizzo della pagina e la segnalazione di
  un errore.

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
- La spesa corrente comprende gli interessi pagati sulle anticipazioni di cassa, come nel
  portale OpenBDAP; restano fuori solo partite di giro e restituzione delle anticipazioni.
- Andamento: quanto cambiano spesa ed entrate per abitante rispetto all'anno prima, a confronto
  con il cambiamento dei comuni simili.
- Comuni estinti senza dati ISTAT sui residenti (131 rendiconti del 2016, 104 del 2017): la
  scheda mostra gli importi, senza valori per abitante né confronti.
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
