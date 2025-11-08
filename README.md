# MS Endpoints

Automatische Bereitstellung von Microsoft 365 Endpoint-Listen für Firewall-Konfigurationen.

## Übersicht

Dieses Repository enthält ein PowerShell-Script, das Microsoft 365 Endpoints von der offiziellen Microsoft API abruft und daraus Listen erstellt, die in Firewalls verwendet werden können.

## Funktionsweise

Das Script `Get-MSEndpoints.ps1`:
- Ruft die aktuellen MS 365 Endpoints von der Microsoft API ab
- Gruppiert die Daten nach:
  - **Adresstyp**: `url`, `ipv4`, `ipv6`
  - **Kategorie**: `opt` (Optimize), `allow` (Allow), `default` (Default)
  - **Service-Bereich**: z.B. `common`, `exchange`, `sharepoint`, `teams`
- Erstellt Dateien im Format: `ms365_{{addrType}}_{{category}}_{{serviceArea}}.txt`
- Speichert alle Listen im Verzeichnis `/lists`

## Automatische Aktualisierung

Der GitHub Actions Workflow (`.github/workflows/update-endpoints.yml`) führt das Script automatisch einmal täglich um 2:00 Uhr UTC aus. Bei Änderungen werden die aktualisierten Listen automatisch ins Repository committed.

## Manuelle Ausführung

### Lokal
```powershell
# Standard-Ausführung (Listen werden in ./lists gespeichert)
./Get-MSEndpoints.ps1

# Mit benutzerdefiniertem Ausgabeverzeichnis
./Get-MSEndpoints.ps1 -OutputDirectory "./output"
```

### GitHub Actions
Der Workflow kann auch manuell über die GitHub Actions UI ausgelöst werden.

## Beispiel-Dateien

Nach der Ausführung werden Dateien wie diese erstellt:
- `ms365_url_opt_exchange.txt` - URLs für Exchange (Optimize-Kategorie)
- `ms365_ipv4_allow_sharepoint.txt` - IPv4-Adressen für SharePoint (Allow-Kategorie)
- `ms365_ipv6_default_common.txt` - IPv6-Adressen für Common Services (Default-Kategorie)

## Datenquelle

Die Daten werden von der offiziellen Microsoft API abgerufen:
`https://endpoints.office.com/endpoints/worldwide`

Dokumentation: [Office 365 URLs and IP address ranges](https://docs.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges)

## Lizenz

Siehe [LICENSE](LICENSE) Datei.
