# Secrets Management mit SOPS

Dieses Projekt verwendet [SOPS](https://github.com/mozilla/sops) zur sicheren Verwaltung von Secrets wie API-Tokens.

## Setup

### 1. SOPS installieren

```bash
# macOS
brew install sops

# Linux
curl -LO https://github.com/mozilla/sops/releases/latest/download/sops-latest.linux.amd64
sudo mv sops-latest.linux.amd64 /usr/local/bin/sops
sudo chmod +x /usr/local/bin/sops
```

### 2. Age Key generieren (einmalig)

```bash
# Generiere neuen Age Key
age-keygen -o ~/.config/sops/age/keys.txt

# Zeige Public Key an (für .sops.yaml)
age-keygen -y ~/.config/sops/age/keys.txt
```

### 3. Secrets konfigurieren

```bash
# Verschlüsselte Secrets-Datei bearbeiten
sops .env.integration.enc

# GitLab Token hinzufügen:
# GITLAB_API_TOKEN=glpat-your-actual-token-here
```

## Verwendung

### Für lokale Entwicklung

```bash
# Integration Tests ausführen (Secrets werden automatisch geladen)
uv run pytest tests/integration/

# Oder mit explizitem Laden:
source ./scripts/load-env.sh
uv run pytest tests/integration/
```

### In VSCode

VSCode lädt automatisch die `.env.integration` Datei für pytest.

**Für Integration Tests in VSCode:**

1. Die .env.integration Datei wird automatisch geladen
2. Öffne VSCode Test Explorer
3. Tests werden mit den geladenen Secrets ausgeführt

### In CI/CD

```bash
# Secrets als Environment Variables exportieren
eval "$(sops -d .env.integration)"

# Oder für Docker/Compose:
sops -d .env.integration > .env.decrypted
docker run --env-file .env.decrypted myapp
```

### Secrets verwalten

```bash
# Secrets anzeigen (entschlüsselt)
sops -d .env.integration

# Secrets bearbeiten
sops .env.integration

# .env.integration verschlüsseln (für Git)
sops -e -i .env.integration
```

## Sicherheit

- ✅ Secrets sind mit SOPS verschlüsselt
- ✅ Nur verschlüsselte Dateien werden in Git eingecheckt
- ✅ Unverschlüsselte `.env*` Dateien sind in `.gitignore`
- ✅ Environment Variables sind nur in der aktuellen Session verfügbar

## Struktur

```
.env.integration                     # Verschlüsselte Secrets (SOPS-managed)
.sops.yaml                          # SOPS Konfiguration
scripts/
├── load-env.sh                     # Universal secrets loader
├── quality-check.sh                # Code quality checks
└── quality-fix.sh                  # Code quality fixes
.vscode/
└── settings.json                   # VSCode Konfiguration für pytest und Terminal
```

## Troubleshooting

### "No suitable keys found"

```bash
# Prüfe ob Age Key existiert
ls ~/.config/sops/age/keys.txt

# Teste SOPS Konfiguration
sops -d .env.integration
```

### "GITLAB_API_TOKEN not set"

```bash
# Prüfe .env.integration Datei
sops -d .env.integration

# Lade Secrets manuell
source ./scripts/load-env.sh
echo $GITLAB_API_TOKEN
```

### Integration Tests in VSCode funktionieren nicht

1. Prüfe ob .env.integration existiert: `ls -la .env.integration`
2. Teste SOPS: `sops -d .env.integration`
3. Starte VSCode neu nach Änderungen an .env.integration
