// Guscio dello stile comune: tema, mappa sul telefono, sezioni della pagina nella mappa.
(function () {
  var CHIAVE = "trasparenza-comuni/tema";
  var radice = document.documentElement;
  var pulsante = document.getElementById("tema");
  var sistema = matchMedia("(prefers-color-scheme: dark)");

  // tema: segue il sistema finche' non si sceglie; la scelta salvata e' gia' applicata nella head
  function scuro() {
    return (radice.dataset.tema || (sistema.matches ? "scuro" : "chiaro")) === "scuro";
  }
  function applica() {
    var s = scuro();
    pulsante.querySelector(".et").textContent = s ? "Chiaro" : "Scuro";
    pulsante.setAttribute("aria-label", "Passa al tema " + (s ? "chiaro" : "scuro"));
    if (radice.dataset.tema) {
      document.querySelectorAll('meta[name="theme-color"]').forEach(function (m) {
        m.content = s ? "#232025" : "#f4f6fa"; // stile:consentito (barra del telefono, esadecimale da stile comune)
      });
    }
    document.dispatchEvent(new Event("cambiotema"));
  }
  pulsante.addEventListener("click", function () {
    radice.dataset.tema = scuro() ? "chiaro" : "scuro";
    try { localStorage.setItem(CHIAVE, radice.dataset.tema); } catch (e) { /* archivio non disponibile */ }
    applica();
  });
  sistema.addEventListener("change", applica);
  applica();

  // terzo livello della mappa: i titoli h2 della pagina, sotto la voce "sei qui"
  var mappa = document.getElementById("mappa");
  var qui = mappa.querySelector("a[aria-current]");
  var titoli = document.querySelectorAll("main h2[id]");
  if (qui && titoli.length) {
    var elenco = document.createElement("ul");
    titoli.forEach(function (h) {
      var voce = document.createElement("li");
      var link = document.createElement("a");
      link.href = "#" + h.id;
      link.textContent = h.dataset.mappa || h.textContent;
      voce.appendChild(link);
      elenco.appendChild(voce);
    });
    qui.parentNode.appendChild(elenco);
  }

  // telefono: la mappa si apre dal pulsante in basso e si chiude scegliendo una voce
  var apri = document.getElementById("apri-mappa");
  apri.addEventListener("click", function () {
    apri.textContent = document.body.classList.toggle("mappa-aperta") ? "Chiudi" : "Mappa";
  });
  mappa.addEventListener("click", function (evento) {
    if (!evento.target.closest("a")) return;
    document.body.classList.remove("mappa-aperta");
    apri.textContent = "Mappa";
  });
})();
