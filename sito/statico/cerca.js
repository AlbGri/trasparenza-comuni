// Ricerca del comune: l'indice si scarica al primo uso della casella, non all'apertura.
(function () {
  var casella = document.getElementById("cerca");
  var lista = document.getElementById("risultati");
  var esito = document.getElementById("esito");
  if (!casella) return;
  var MASSIMO = 10;
  var comuni = null, province = null, scaricando = false, trovati = [], scelto = -1;

  // Stessa trasformazione di in_ascii in pipeline/esportazione.py, con spazi al posto dei
  // trattini: serve sia per confrontare sia per ricostruire l'indirizzo della pagina.
  function piano(testo) {
    return testo.normalize("NFKD").replace(/[^\x00-\x7f]/g, "").toLowerCase()
      .replace(/[^a-z0-9]+/g, " ").trim();
  }

  function scarica() {
    if (comuni || scaricando) return;
    scaricando = true;
    fetch("cerca.json").then(function (risposta) {
      if (!risposta.ok) throw new Error(risposta.status);
      return risposta.json();
    }).then(function (dati) {
      province = dati.province;
      comuni = dati.comuni.map(function (r) {
        return { id: r[0], nome: r[1], provincia: r[2], residenti: r[3], estinto: r[4] === 1, chiave: piano(r[1]) };
      });
      cerca();
    }).catch(function () {
      scaricando = false;
      esito.textContent = "Elenco dei comuni non disponibile: riprova fra poco.";
    });
  }

  function livello(chiave, testo) {
    if (chiave === testo) return 0;
    if (chiave.indexOf(testo) === 0) return 1;
    if ((" " + chiave).indexOf(" " + testo) >= 0) return 2;
    return chiave.indexOf(testo) >= 0 ? 3 : -1;
  }

  function cerca() {
    var testo = piano(casella.value);
    trovati = [];
    scelto = -1;
    if (testo && comuni) {
      comuni.forEach(function (c) {
        var l = livello(c.chiave, testo);
        if (l >= 0) trovati.push({ c: c, l: l });
      });
      trovati.sort(function (a, b) {
        return (a.c.estinto - b.c.estinto) || (a.l - b.l) || (b.c.residenti - a.c.residenti) ||
          a.c.nome.localeCompare(b.c.nome, "it");
      });
      trovati = trovati.slice(0, MASSIMO).map(function (t) { return t.c; });
    }
    mostra(testo);
  }

  function indirizzo(c) {
    return "comuni/" + piano(c.nome).replace(/ /g, "-") + "-" + c.id + "/";
  }

  function mostra(testo) {
    lista.textContent = "";
    trovati.forEach(function (c, i) {
      var voce = document.createElement("li");
      var link = document.createElement("a");
      voce.id = "risultato-" + i;
      voce.setAttribute("role", "option");
      link.href = indirizzo(c);
      link.tabIndex = -1;
      var nome = document.createElement("strong");
      nome.textContent = c.nome;
      var dove = document.createElement("span");
      dove.textContent = province[c.provincia] + (c.estinto ? " · non esiste più" : "");
      link.appendChild(nome);
      link.appendChild(dove);
      voce.appendChild(link);
      lista.appendChild(voce);
    });
    lista.hidden = !trovati.length;
    casella.setAttribute("aria-expanded", trovati.length ? "true" : "false");
    casella.removeAttribute("aria-activedescendant");
    if (comuni) esito.textContent = testo && !trovati.length ? "Nessun comune trovato con questo nome." : "";
  }

  function evidenzia(i) {
    var voci = lista.children;
    if (scelto >= 0) voci[scelto].removeAttribute("aria-selected");
    scelto = i;
    voci[i].setAttribute("aria-selected", "true");
    casella.setAttribute("aria-activedescendant", voci[i].id);
  }

  casella.addEventListener("focus", scarica);
  casella.addEventListener("input", function () { scarica(); cerca(); });
  casella.addEventListener("keydown", function (evento) {
    if (!trovati.length) return;
    if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
      evento.preventDefault();
      var passo = evento.key === "ArrowDown" ? 1 : -1;
      evidenzia((scelto + passo + trovati.length) % trovati.length);
    }
  });
  casella.form.addEventListener("submit", function (evento) {
    evento.preventDefault();
    if (trovati.length) location.href = indirizzo(trovati[Math.max(scelto, 0)]);
  });
})();
