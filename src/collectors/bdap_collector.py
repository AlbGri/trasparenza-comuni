"""
Collector per i dati BDAP (Banca Dati Amministrazioni Pubbliche)
Recupera i bilanci dei comuni italiani
"""
import requests
import pandas as pd
from typing import Dict, List, Optional
import json
from datetime import datetime

class BDAPCollector:
    """Raccoglie dati dalla BDAP del MEF"""
    
    BASE_URL = "https://bdap-opendata.mef.gov.it/api/v1"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Trasparenza-Comuni/1.0'
        })
    
    def test_connection(self) -> bool:
        """Testa la connessione alle API BDAP"""
        try:
            response = self.session.get(f"{self.BASE_URL}/public/elenco_amministrazioni")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Errore connessione: {e}")
            return False
    
    def get_lista_comuni(self, regione: str = "LAZIO", limit: int = 5) -> List[Dict]:
        """
        Ottiene la lista dei comuni di una regione
        
        Args:
            regione: Nome della regione (es. "LAZIO")
            limit: Numero massimo di comuni da recuperare
        
        Returns:
            Lista di dizionari con info sui comuni
        """
        print(f"📍 Recupero comuni del {regione}...")
        
        # Endpoint per l'elenco amministrazioni
        url = f"{self.BASE_URL}/public/elenco_amministrazioni"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            # Filtra solo i comuni della regione specificata
            comuni = []
            for ente in data.get('data', []):
                if (ente.get('tipo_ente') == 'COMUNE' and 
                    ente.get('regione', '').upper() == regione.upper()):
                    comuni.append({
                        'codice': ente.get('codice_ente'),
                        'nome': ente.get('denominazione'),
                        'provincia': ente.get('provincia'),
                        'regione': ente.get('regione'),
                        'popolazione': ente.get('popolazione', 0)
                    })
                    
                    if len(comuni) >= limit:
                        break
            
            print(f"✅ Trovati {len(comuni)} comuni")
            return comuni
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Errore nel recupero dati: {e}")
            return []
    
    def get_bilancio_comune(self, codice_comune: str, anno: int = 2022) -> Dict:
        """
        Recupera il bilancio di un comune per un anno specifico
        
        Args:
            codice_comune: Codice del comune
            anno: Anno di riferimento
            
        Returns:
            Dizionario con i dati di bilancio
        """
        print(f"💰 Recupero bilancio {codice_comune} per l'anno {anno}...")
        
        # Nota: questo è un esempio - l'endpoint reale potrebbe essere diverso
        url = f"{self.BASE_URL}/public/bilanci/{codice_comune}/{anno}"
        
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️ Nessun dato per {codice_comune} anno {anno}")
                return {}
        except Exception as e:
            print(f"❌ Errore: {e}")
            return {}


def test_bdap():
    """Funzione di test per il collector BDAP"""
    print("\n" + "="*50)
    print("🧪 TEST COLLECTOR BDAP")
    print("="*50 + "\n")
    
    # Inizializza il collector
    collector = BDAPCollector()
    
    # Test 1: Connessione
    print("Test 1: Verifica connessione...")
    if collector.test_connection():
        print("✅ Connessione OK!\n")
    else:
        print("❌ Connessione fallita\n")
        return
    
    # Test 2: Lista comuni
    print("Test 2: Recupero 3 comuni del Lazio...")
    comuni = collector.get_lista_comuni("LAZIO", limit=3)
    
    if comuni:
        print("\n📊 Comuni trovati:")
        for comune in comuni:
            print(f"  - {comune['nome']} ({comune['provincia']})")
            print(f"    Codice: {comune['codice']}")
            print(f"    Popolazione: {comune.get('popolazione', 'N/D')}")
    
    # Test 3: Salva i dati
    if comuni:
        print("\n💾 Salvo i dati in data/raw/test_comuni.json")
        
        # Assicurati che la cartella esista
        import os
        os.makedirs("data/raw", exist_ok=True)
        
        with open("data/raw/test_comuni.json", "w", encoding='utf-8') as f:
            json.dump(comuni, f, indent=2, ensure_ascii=False)
        
        print("✅ Dati salvati!")
    
    print("\n" + "="*50)
    print("✅ TEST COMPLETATO")
    print("="*50)


if __name__ == "__main__":
    test_bdap()