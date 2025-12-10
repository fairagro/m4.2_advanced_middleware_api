# Git LFS Setup für FAIRagro Middleware API

Dieses Repository verwendet Git LFS (Large File Storage) für große Dateien wie SQL-Dumps.

## 🎯 Problem gelöst

Große Dateien wie `dev_environment/FAIRagro.sql` (241 MB) können nicht direkt in Git gespeichert werden, da sie:

- Den 500 KB Limit des pre-commit Hooks überschreiten
- Das Repository aufblähen würden
- Clone- und Pull-Operationen verlangsamen würden

## 🔧 Installation und Setup

### Für neue Entwickler (nach dem Klonen)

```bash
# 1. Repository klonen
git clone <repository-url>
cd m4.2_advanced_middleware_api

# 2. Git LFS Hooks installieren
./scripts/setup-git-lfs.sh

# 3. Große Dateien herunterladen
git lfs pull
```

### Für bestehende Entwicklungsumgebungen

Wenn Sie bereits eine lokale Kopie des Repositories haben:

```bash
# Git LFS Hooks einrichten
./scripts/setup-git-lfs.sh

# Bestehende große Dateien von LFS abrufen
git lfs pull
```

## 📋 Was passiert beim Setup

1. **Git LFS Installation** - Falls nicht vorhanden, wird Git LFS automatisch installiert
2. **Hook Integration** - Git LFS Hooks werden mit bestehenden pre-commit Hooks kombiniert
3. **Kompatibilität** - Existierende pre-commit Hooks bleiben funktionsfähig
4. **Backup** - Bestehende Hooks werden gesichert (`.backup` Dateien)

## 🔍 Verifikation

Nach dem Setup können Sie prüfen:

```bash
# Git LFS Status
git lfs env

# Welche Dateien werden von LFS verwaltet
git lfs ls-files

# LFS Konfiguration
cat .gitattributes
```

## 📁 Dateien und Verzeichnisse

```text
scripts/
├── setup-git-lfs.sh          # Automatisches Setup-Script
└── git-hooks/                 # Versionierte Hook-Dateien
    ├── pre-push              # Kombiniert LFS + pre-commit
    ├── post-checkout         # LFS post-checkout
    ├── post-commit           # LFS post-commit
    └── post-merge            # LFS post-merge

.gitattributes                 # LFS Konfiguration (*.sql files)
dev_environment/FAIRagro.sql  # Große SQL-Datei (via LFS)
```

## 🚨 Wichtige Hinweise

### Für Git Commits

Nach dem Setup funktionieren Commits normal:

```bash
git add .
git commit -m "Your commit message"
git push
```

Die große SQL-Datei wird automatisch von LFS verwaltet und triggert **nicht mehr** den 500KB pre-commit Hook.

### Für neue große Dateien

Neue SQL-Dateien werden automatisch von LFS verwaltet. Für andere Dateitypen:

```bash
# Neue Dateitypen zu LFS hinzufügen
git lfs track "*.zip"
git lfs track "*.tar.gz"

# .gitattributes committen
git add .gitattributes
git commit -m "Track new file types with LFS"
```

### Bei Problemen

```bash
# LFS Status überprüfen
git lfs status

# LFS Logs anzeigen
git lfs logs last

# Hooks neu installieren
./scripts/setup-git-lfs.sh
```

## 🔧 Technische Details

- **LFS Version**: Git LFS 3.3.0+
- **Tracked Files**: `*.sql`
- **Hook Integration**: pre-push Hook kombiniert LFS + pre-commit
- **Storage**: LFS Dateien werden in `.git/lfs/` lokal zwischengespeichert
- **Remote**: Große Dateien werden in einem separaten LFS Store auf GitHub gespeichert

## 💡 Development Workflow

1. **Clone** → `./scripts/setup-git-lfs.sh` → `git lfs pull`
2. **Entwickeln** → Normale Git-Kommandos funktionieren
3. **Commit** → Große Dateien werden automatisch zu LFS hochgeladen
4. **Push** → Sowohl Git-Commits als auch LFS-Dateien werden synchronisiert
