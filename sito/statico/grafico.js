// Grafico dell'andamento: il comune e la mediana dei comuni simili, voce scelta dal menu.
// Colori, griglia e caratteri dalle variabili dello stile comune, rilette a ogni cambio di tema.
// Senza Plotly (rete assente) resta la tabella sotto il grafico.
(function () {
  var nodo = document.getElementById("dati-grafico");
  var area = document.getElementById("grafico");
  var menu = document.getElementById("scelta-voce");
  var notaGiorni = document.getElementById("nota-giorni");
  if (!nodo || !area || !window.Plotly) return;
  var dati = JSON.parse(nodo.textContent);
  if (!dati.voci.length) return;

  var SUFFISSI = { "percentuale": "%", "giorni": " giorni", "euro per abitante": " € per abitante", "euro": " €" };

  dati.voci.forEach(function (voce, i) {
    var opzione = document.createElement("option");
    opzione.value = i;
    opzione.textContent = voce.nome;
    menu.appendChild(opzione);
  });
  menu.parentNode.hidden = false;
  area.classList.add("pronto");

  function variabile(nome) {
    return getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
  }

  // colore per voce, uguale in ogni pagina: il comune al posto 1, la mediana al posto 2
  function traccia(x, y, nome, colore, formato) {
    return {
      x: x, y: y, name: nome, mode: "lines+markers", hovertemplate: formato,
      line: { color: colore, width: 2 },
      marker: { size: 7, color: colore, line: { color: variabile("--surface"), width: 2 } }
    };
  }

  function disegna() {
    var voce = dati.voci[menu.value];
    var decimali = voce.unita === "percentuale" || voce.unita === "giorni" ? 1 : 0;
    var formato = "%{y:,." + decimali + "f}" + SUFFISSI[voce.unita] + "<extra></extra>";
    var testo = variabile("--muted"), linea = variabile("--line");
    if (notaGiorni) notaGiorni.hidden = voce.unita !== "giorni";
    var tracce = [traccia(dati.anni, voce.comune, "Questo comune", variabile("--s1"), formato)];
    var note = [];
    if (voce.mediana) {
      tracce.push(traccia(dati.anni, voce.mediana, "Mediana comuni simili", variabile("--s2"), formato));
    } else {
      // una serie sola: niente legenda, il valore finale accanto all'ultimo punto
      var i = voce.comune.length - 1;
      while (i >= 0 && voce.comune[i] === null) i--;
      if (i >= 0) {
        note.push({
          x: dati.anni[i], y: voce.comune[i], xanchor: "left", xshift: 8, showarrow: false,
          font: { color: variabile("--ink") },
          text: voce.comune[i].toLocaleString("it-IT", { minimumFractionDigits: decimali, maximumFractionDigits: decimali }) + SUFFISSI[voce.unita]
        });
      }
    }
    var asse = { gridcolor: linea, linecolor: linea, zerolinecolor: linea, fixedrange: true };
    Plotly.react(area, tracce, {
      separators: ",.",
      margin: { l: 56, r: voce.mediana ? 12 : 110, t: 12, b: 40 },
      showlegend: !!voce.mediana,
      legend: { orientation: "h", y: -0.15 },
      annotations: note,
      xaxis: Object.assign({ dtick: 1 }, asse),
      yaxis: Object.assign({ ticksuffix: voce.unita === "percentuale" ? "%" : "", rangemode: "tozero" }, asse),
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: variabile("--sans"), size: 13, color: testo },
      hoverlabel: { bgcolor: variabile("--surface"), bordercolor: variabile("--ink"), font: { color: variabile("--ink") } }
    }, { displayModeBar: false, responsive: true });
  }
  menu.addEventListener("change", disegna);
  document.addEventListener("cambiotema", disegna);
  // i caratteri del sito arrivano dopo: si ridisegna quando ci sono, per misurare i testi giusti
  disegna();
  document.fonts.ready.then(disegna);
})();
