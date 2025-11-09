"""
Script per estrarre tutti i file di codice da un repository
e crearli in un unico file per l'analisi AI
"""
import os
from pathlib import Path

# Configurazione
BASE_PATH = r"C:\Alberto\Sito\trasparenza-comuni"
OUTPUT_FILE = "repository_code.txt"

# Estensioni di file da includere (solo codice e testo)
CODE_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss', 
    '.json', '.xml', '.yaml', '.yml', '.md', '.txt', '.sh', '.bat',
    '.sql', '.r', '.java', '.c', '.cpp', '.h', '.go', '.rs',
    '.php', '.rb', '.swift', '.kt', '.dart', '.vue', '.env.example',
    '.gitignore', '.dockerignore', 'Makefile', 'Dockerfile', 'README',
    '.ipynb'
}

# Cartelle da escludere
EXCLUDE_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv', 
    'env', '.env', 'dist', 'build', '.pytest_cache', 
    '.ipynb_checkpoints', '.vscode', '.idea', 'logs', 'tmp'
}

# File specifici da escludere
EXCLUDE_FILES = {
    'package-lock.json', 'yarn.lock', 'poetry.lock', 
    '.DS_Store', 'Thumbs.db', 'prompt.md'
}

def is_binary(file_path):
    """Verifica se un file è binario"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)  # Leggi i primi 1024 caratteri
        return False
    except (UnicodeDecodeError, PermissionError):
        return True

def should_include_file(file_path):
    """Determina se un file dovrebbe essere incluso"""
    file_name = file_path.name
    
    # Escludi file specifici
    if file_name in EXCLUDE_FILES:
        return False
    
    # Controlla l'estensione
    if file_path.suffix.lower() in CODE_EXTENSIONS:
        return True
    
    # Controlla il nome completo del file (per .gitignore, .dockerignore, etc.)
    if file_name in CODE_EXTENSIONS:
        return True
    
    # Includi file senza estensione che potrebbero essere script
    if not file_path.suffix and file_name in {'Makefile', 'Dockerfile', 'README'}:
        return True
    
    return False


def collect_files(base_path):
    """Raccoglie tutti i file di codice dal repository"""
    base_path = Path(base_path)
    collected_files = []
    
    for root, dirs, files in os.walk(base_path):
        # Rimuovi le directory da escludere dalla lista
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file_name in files:
            file_path = Path(root) / file_name
            
            # Verifica se il file dovrebbe essere incluso
            if should_include_file(file_path):
                # Verifica che non sia binario
                if not is_binary(file_path):
                    relative_path = file_path.relative_to(base_path)
                    collected_files.append((relative_path, file_path))
    
    return sorted(collected_files)

def create_combined_file(files, output_file):
    """Crea un file unico con tutti i contenuti"""
    separator = "=" * 80
    
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(f"REPOSITORY CODE EXPORT\n")
        out.write(f"Total files: {len(files)}\n")
        out.write(f"{separator}\n\n")
        
        for relative_path, file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Scrivi l'header del file
                out.write(f"\n{separator}\n")
                out.write(f"FILE: {relative_path}\n")
                out.write(f"{separator}\n\n")
                
                # Scrivi il contenuto
                out.write(content)
                out.write("\n\n")
                
                print(f"✓ Aggiunto: {relative_path}")
                
            except Exception as e:
                print(f"✗ Errore con {relative_path}: {e}")

def main():
    print(f"🔍 Scansione repository: {BASE_PATH}")
    print(f"📁 Esclusione cartelle: {', '.join(EXCLUDE_DIRS)}")
    print(f"📄 Estensioni incluse: {', '.join(sorted(CODE_EXTENSIONS))}")
    print()
    
    # Raccogli i file
    files = collect_files(BASE_PATH)
    print(f"\n✅ Trovati {len(files)} file di codice\n")
    
    # Crea il file combinato
    script_dir = Path(__file__).parent
    output_path = script_dir / OUTPUT_FILE
    create_combined_file(files, output_path)
    
    print(f"\n🎉 File creato: {output_path}")
    print(f"📊 Dimensione: {output_path.stat().st_size / 1024:.2f} KB")

if __name__ == "__main__":
    main()
