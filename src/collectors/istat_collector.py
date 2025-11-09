"""
Collector per i dati ISTAT
Recupera dati demografici e territoriali dei comuni italiani
"""
import requests
import pandas as pd
from typing import Dict, List, Optional
import json
from datetime import datetime

class IstatCollector:
    """Raccoglie dati demografici e territoriali da ISTAT"""
    
    # API ISTAT per i territori
    BASE_URL = "https://sdmx.istat.it/SDMXWS/rest"
    TERRITORI_URL = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Trasparenza-Comuni/1.0'
        })
        self.comuni_df = None
    
    def get_lista_comuni_csv(self) -> pd.DataFrame:
        """
        Scarica la lista aggiornata dei comuni italiani da ISTAT
        
        Returns:
            DataFrame con tutti i comuni italiani
        """
        print("📥 Download lista comuni da ISTAT...")
        
        try:
            # ISTAT fornisce un CSV aggiornato con tutti i comuni
            url = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv"
            
            # Scarica il CSV direttamente in un DataFrame
            df = pd.read_csv(url, encoding='latin-1', sep=';')
            
            print(f"✅ Scaricati {len(df)} comuni!")
            
            # Salva in cache
            self.comuni_df = df
            
            return df
            
        except Exception as e:
            print(f"❌ Errore: {e}")
            print("Proviamo con dati di backup locali...")
            return self.get_backup_data()
    
    def get_backup_data(self) -> pd.DataFrame:
        """Dati di backup per testing se ISTAT non risponde"""
        
        # Alcuni comuni di esempio per testing
        data = {
            'Codice Comune': ['058091', '058001', '058059'],
            'Denominazione': ['Roma', 'Albano Laziale', 'Marino'],
            'Provincia': ['Roma', 'Roma', 'Roma'],
            'Regione': ['Lazio', 'Lazio', 'Lazio'],
            'Popolazione_2023': [2872800, 41700, 43600]
        }
        
        df = pd.DataFrame(data)
        print(f"📦 Caricati {len(df)} comuni di esempio")
        return df
    
    def get_comuni_regione(self, regione: str = "Lazio", limit: int = 10) -> List[Dict]:
        """
        Filtra i comuni per regione
        
        Args:
            regione: Nome della regione
            limit: Numero massimo di comuni
            
        Returns:
            Lista di dizionari con info sui comuni
        """
        print(f"\n🔍 Cerco comuni del {regione}...")
        
        if self.comuni_df is None:
            self.comuni_df = self.get_lista_comuni_csv()
        
        # Nomi delle colonne potrebbero variare, proviamo diverse opzioni
        col_regione = None
        col_comune = None
        col_provincia = None
        
        # Cerca le colonne giuste (ISTAT usa nomi in italiano)
        for col in self.comuni_df.columns:
            if 'Regione' in col or 'regione' in col:
                col_regione = col
            if 'Denominazione' in col or 'denominazione' in col or 'Comune' in col:
                col_comune = col
            if 'Provincia' in col or 'provincia' in col:
                col_provincia = col
        
        if not col_regione:
            # Usa dati di backup
            return self.get_backup_data().head(limit).to_dict('records')
        
        # Filtra per regione
        df_filtered = self.comuni_df[
            self.comuni_df[col_regione].str.contains(regione, case=False, na=False)
        ].head(limit)
        
        # Converti in lista di dizionari
        comuni = []
        for _, row in df_filtered.iterrows():
            comuni.append({
                'codice': row.get('Codice Comune', 'N/D'),
                'nome': row.get(col_comune, 'N/D'),
                'provincia': row.get(col_provincia, 'N/D'),
                'regione': row.get(col_regione, 'N/D')
            })
        
        print(f"✅ Trovati {len(comuni)} comuni")
        return comuni


class OpenDataCollector:
    """Collector per dati da portali Open Data"""
    
    def get_bilanci_sample(self) -> Dict:
        """
        Recupera dati di esempio sui bilanci comunali
        
        Returns:
            Dizionario con dati di bilancio di esempio
        """
        print("\n💰 Genero dati di bilancio di esempio...")
        
        # Dati di esempio realistici per il POC
        bilanci = {
            "Roma": {
                "anno": 2023,
                "entrate": {
                    "tributarie": 1500000000,
                    "trasferimenti": 800000000,
                    "extratributarie": 300000000
                },
                "spese": {
                    "correnti": 2000000000,
                    "investimenti": 400000000,
                    "rimborso_prestiti": 100000000
                },
                "popolazione": 2872800,
                "spesa_procapite": 870
            },
            "Albano Laziale": {
                "anno": 2023,
                "entrate": {
                    "tributarie": 25000000,
                    "trasferimenti": 5000000,
                    "extratributarie": 3000000
                },
                "spese": {
                    "correnti": 28000000,
                    "investimenti": 3000000,
                    "rimborso_prestiti": 1000000
                },
                "popolazione": 41700,
                "spesa_procapite": 768
            },
            "Marino": {
                "anno": 2023,
                "entrate": {
                    "tributarie": 28000000,
                    "trasferimenti": 6000000,
                    "extratributarie": 4000000
                },
                "spese": {
                    "correnti": 30000000,
                    "investimenti": 5000000,
                    "rimborso_prestiti": 2000000
                },
                "popolazione": 43600,
                "spesa_procapite": 849
            }
        }
        
        print("✅ Dati di bilancio generati!")
        return bilanci


def test_collectors():
    """Test completo dei collector"""
    
    print("\n" + "="*60)
    print("🧪 TEST COLLECTOR DATI COMUNI")
    print("="*60)
    
    # Test 1: ISTAT Collector
    print("\n📊 TEST 1: ISTAT Collector")
    print("-"*40)
    
    istat = IstatCollector()
    comuni = istat.get_comuni_regione("Lazio", limit=5)
    
    if comuni:
        print("\n🏛️ Comuni trovati:")
        for comune in comuni:
            print(f"  • {comune['nome']} ({comune['provincia']})")
    
    # Test 2: Open Data Collector
    print("\n📊 TEST 2: Bilanci di Esempio")
    print("-"*40)
    
    opendata = OpenDataCollector()
    bilanci = opendata.get_bilanci_sample()
    
    print("\n💶 Bilanci comunali:")
    for comune, dati in bilanci.items():
        print(f"\n  {comune}:")
        print(f"    • Popolazione: {dati['popolazione']:,}")
        print(f"    • Entrate totali: €{sum(dati['entrate'].values()):,.0f}")
        print(f"    • Spese totali: €{sum(dati['spese'].values()):,.0f}")
        print(f"    • Spesa pro-capite: €{dati['spesa_procapite']}")
    
    # Salva i dati per analisi futura
    print("\n💾 Salvataggio dati...")
    
    import os
    os.makedirs("data/raw", exist_ok=True)
    
    # Salva comuni
    with open("data/raw/comuni_test.json", "w", encoding='utf-8') as f:
        json.dump(comuni, f, indent=2, ensure_ascii=False)
    
    # Salva bilanci
    with open("data/raw/bilanci_test.json", "w", encoding='utf-8') as f:
        json.dump(bilanci, f, indent=2, ensure_ascii=False)
    
    print("✅ Dati salvati in data/raw/")
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETATO CON SUCCESSO!")
    print("="*60)
    
    return comuni, bilanci


if __name__ == "__main__":
    comuni, bilanci = test_collectors()