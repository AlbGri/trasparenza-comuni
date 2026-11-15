// Grafico dell'andamento: il comune e la mediana dei comuni simili, voce scelta dal menu.
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

  function disegna() {
    var voce = dati.voci[menu.value];
    var decimali = voce.unita === "percentuale" || voce.unita === "giorni" ? 1 : 0;
    var formato = "%{y:,." + decimali + "f}" + SUFFISSI[voce.unita] + "<extra></extra>";
    if (notaGiorni) notaGiorni.hidden = voce.unita !== "giorni";
    var tracce = [{
      x: dati.anni, y: voce.comune, name: "Questo comune", mode: "lines+markers",
      line: { color: "#1d5c87", width: 3 }, marker: { size: 7 }, hovertemplate: formato
    }];
    if (voce.mediana) {
      tracce.push({
        x: dati.anni, y: voce.mediana, name: "Mediana comuni simili", mode: "lines+markers",
        line: { color: "#8a94a1", width: 2, dash: "dot" }, marker: { size: 5 }, hovertemplate: formato
      });
    }
    Plotly.react(area, tracce, {
      separators: ",.",
      margin: { l: 56, r: 12, t: 12, b: 40 },
      legend: { orientation: "h", y: -0.15 },
      xaxis: { dtick: 1, fixedrange: true },
      yaxis: { ticksuffix: voce.unita === "percentuale" ? "%" : "", rangemode: "tozero", fixedrange: true },
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "#ffffff",
      font: { family: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", size: 13 }
    }, { displayModeBar: false, responsive: true });
  }
  menu.addEventListener("change", disegna);
  disegna();
})();
