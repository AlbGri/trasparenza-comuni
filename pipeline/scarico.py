"""Scarico con memoria: richieste parziali sugli zip remoti e registro delle versioni."""
import codecs
import io
import logging
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import pandas as pd
import requests

from pipeline.fonti import PROCESSED, USER_AGENT

log = logging.getLogger(__name__)

BLOCCO = 8 * 1024 * 1024
TENTATIVI = 4


def nuova_sessione() -> requests.Session:
    """Sessione HTTP con il client dichiarato."""
    sessione = requests.Session()
    sessione.headers["User-Agent"] = USER_AGENT
    return sessione


def richiesta(sessione: requests.Session, url: str, **opzioni) -> requests.Response:
    """GET con qualche tentativo sugli errori di rete e del server (5xx).

    Raises:
        requests.RequestException: se la fonte non risponde dopo tutti i tentativi.
    """
    for tentativo in range(1, TENTATIVI + 1):
        try:
            risposta = sessione.get(url, timeout=300, **opzioni)
            if risposta.status_code < 500:
                risposta.raise_for_status()
                return risposta
            errore: Exception = requests.HTTPError(f"{risposta.status_code} da {url}")
        except (requests.ConnectionError, requests.Timeout) as eccezione:
            errore = eccezione
        if tentativo < TENTATIVI:
            log.warning("tentativo %d fallito su %s: %s", tentativo, url, errore)
            time.sleep(5 * tentativo)
    raise requests.RequestException(f"la fonte non risponde: {url} ({errore})")


class FileRemoto(io.RawIOBase):
    """File di sola lettura servito a blocchi con richieste Range."""

    def __init__(self, url: str, sessione: requests.Session):
        self.url = url
        self.sessione = sessione
        risposta = richiesta(sessione, url, headers={"Range": "bytes=0-0"})
        self.dimensione = int(risposta.headers["Content-Range"].split("/")[1])
        self.etag = risposta.headers.get("ETag", "")
        self.data_file = risposta.headers.get("Last-Modified", "")
        self.posizione = 0
        self.inizio_buffer = 0
        self.buffer = b""
        self.byte_scaricati = 0

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.posizione

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self.posizione = offset
        elif whence == 1:
            self.posizione += offset
        else:
            self.posizione = self.dimensione + offset
        return self.posizione

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = self.dimensione - self.posizione
        n = min(n, self.dimensione - self.posizione)
        if n <= 0:
            return b""
        fine_buffer = self.inizio_buffer + len(self.buffer)
        if not (self.inizio_buffer <= self.posizione and self.posizione + n <= fine_buffer):
            # verso la coda dello zip (indice) si legge all'indietro, altrove in avanti
            if self.posizione + n >= self.dimensione - 65536:
                inizio = max(0, self.dimensione - max(n, 2 * 1024 * 1024))
            else:
                inizio = self.posizione
            fine = min(self.dimensione, max(inizio + BLOCCO, self.posizione + n)) - 1
            risposta = richiesta(
                self.sessione, self.url, headers={"Range": f"bytes={inizio}-{fine}"}
            )
            self.buffer = risposta.content
            self.inizio_buffer = inizio
            self.byte_scaricati += len(self.buffer)
        scarto = self.posizione - self.inizio_buffer
        dati = self.buffer[scarto : scarto + n]
        self.posizione += len(dati)
        return dati


def trascrivi_utf8(origine: BinaryIO, destinazione: Path, codifica: str) -> None:
    """Copia a blocchi un flusso di testo su disco, convertendolo in UTF-8.

    La codifica va dichiarata: l'inizio di molti file e' solo ASCII e non la rivela.
    """
    decodifica = codecs.getincrementaldecoder(codifica)()
    with open(destinazione, "w", encoding="utf-8", newline="") as uscita:
        while blocco := origine.read(4 * 1024 * 1024):
            uscita.write(decodifica.decode(blocco))
        uscita.write(decodifica.decode(b"", final=True))


class ZipRemoto:
    """Zip remoto di cui si leggono solo l'indice e i file richiesti."""

    def __init__(self, url: str, sessione: requests.Session):
        self.url = url
        self.remoto = FileRemoto(url, sessione)
        self._zip: zipfile.ZipFile | None = None

    @property
    def etag(self) -> str:
        return self.remoto.etag

    @property
    def data_file(self) -> str:
        return self.remoto.data_file

    @property
    def zip(self) -> zipfile.ZipFile:
        """Indice dello zip, letto alla prima richiesta."""
        if self._zip is None:
            self._zip = zipfile.ZipFile(self.remoto)
        return self._zip

    def membro(self, finale: str) -> str:
        """Nome completo dell'unico file dello zip che termina con `finale`."""
        trovati = [nome for nome in self.zip.namelist() if nome.endswith(finale)]
        if len(trovati) != 1:
            raise ValueError(f"{self.url}: attesi 1 file '*{finale}', trovati {trovati}")
        return trovati[0]

    def estrai_utf8(self, membro: str, destinazione: Path, codifica: str) -> None:
        """Scrive su disco un file di testo dello zip, convertito in UTF-8."""
        with self.zip.open(membro) as origine:
            trascrivi_utf8(origine, destinazione, codifica)


class Registro:
    """Versione (ETag e data) di ogni file scaricato, in `versioni_fonti.parquet`."""

    COLONNE = ["indirizzo", "etag", "data_file", "data_scarico"]

    def __init__(self, percorso: Path = PROCESSED / "versioni_fonti.parquet"):
        self.percorso = percorso
        if percorso.exists():
            self.righe = pd.read_parquet(percorso).set_index("indirizzo")
        else:
            self.righe = pd.DataFrame(columns=self.COLONNE).set_index("indirizzo")

    def invariato(self, indirizzo: str, etag: str, data_file: str) -> bool:
        """Vero se la versione registrata e' quella che la fonte espone adesso."""
        if indirizzo not in self.righe.index:
            return False
        riga = self.righe.loc[indirizzo]
        return (riga["etag"], riga["data_file"]) == (etag, data_file)

    def registra(self, indirizzo: str, etag: str, data_file: str) -> None:
        """Annota la versione scaricata e salva il registro."""
        if indirizzo in self.righe.index and not self.invariato(indirizzo, etag, data_file):
            vecchia = self.righe.loc[indirizzo]
            log.warning(
                "fonte cambiata: %s (era %s del %s, ora %s del %s)",
                indirizzo, vecchia["etag"], vecchia["data_file"], etag, data_file,
            )
        adesso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.righe.loc[indirizzo] = [etag, data_file, adesso]
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        self.righe.reset_index().to_parquet(self.percorso, index=False)


def scarica_file(
    url: str, destinazione: Path, registro: Registro, sessione: requests.Session
) -> bool:
    """Scarica un file intero se manca o se alla fonte e' cambiato.

    Returns:
        True se il file e' stato scaricato, False se era gia' aggiornato.
    """
    # stream: chi ignora Range (IndicePA) risponde con il file intero, che qui non si legge
    testa = richiesta(sessione, url, headers={"Range": "bytes=0-0"}, stream=True)
    etag = testa.headers.get("ETag", "")
    data_file = testa.headers.get("Last-Modified", "")
    testa.close()
    if destinazione.exists() and registro.invariato(url, etag, data_file):
        return False
    log.info("scarico %s", url)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    parziale = destinazione.with_name(destinazione.name + ".part")
    risposta = richiesta(sessione, url, stream=True)
    with open(parziale, "wb") as uscita:
        for blocco in risposta.iter_content(1024 * 1024):
            uscita.write(blocco)
    parziale.replace(destinazione)
    registro.registra(url, etag, data_file)
    return True
