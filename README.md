# MS Endpoints

Automatische Bereitstellung von Microsoft 365 Endpoint-Listen für Firewall-Konfigurationen.

## Übersicht

Dieses Repository enthält ein PowerShell-Script, das Microsoft 365 Endpoints von der offiziellen Microsoft API abruft und daraus Listen erstellt, die in Firewalls verwendet werden können.

## Funktionsweise

Das Script `Get-MSEndpoints.ps1`:
- Ruft die aktuellen MS 365 Endpoints von der Microsoft API ab
- Gruppiert die Daten nach:
  - **Service-Bereich**: z.B. `common`, `exchange`, `sharepoint`, `skype` (Teams)
  - **Adresstyp**: `url`, `ipv4`, `ipv6`
  - **Kategorie**: `opt` (Optimize), `allow` (Allow), `default` (Default)
- Erstellt zwei Arten von Dateien:
  1. **Kategorie-basiert** (immer): `ms365_{{serviceArea}}_{{addrType}}_{{category}}.txt`
  2. **Port-basiert** (optional): `ms365_{{serviceArea}}_{{addrType}}_port{{port}}.txt`
- Speichert alle Listen im Verzeichnis `/lists`

### Port-basierte Listen (optional)

Port-basierte Listen können über den Parameter `-GeneratePortListsFor` aktiviert werden. Diese enthalten nur die IPs oder URLs, die den angegebenen Port verwenden und werden **zusätzlich** zu den kategorie-basierten Listen erstellt.

**Beispiele:**
```powershell
# Nur Exchange IPv4 für Port 25
./Get-MSEndpoints.ps1 -GeneratePortListsFor @("exchange:ipv4:25")

# Mehrere Konfigurationen (zusätzlich zu den kategorie-basierten Listen)
./Get-MSEndpoints.ps1 -GeneratePortListsFor @("exchange:ipv4:25", "exchange:url:80-443", "skype:url:443")
```

**Format:** `"servicearea:addrtype:port"` oder `"servicearea:addrtype:port1-port2-port3"`
- `servicearea`: `common`, `exchange`, `sharepoint`, `skype`
- `addrtype`: `url`, `ipv4`, `ipv6`
- `port`: Einzelner Port oder mehrere Ports getrennt durch `-`

**Standard-Konfiguration (ohne Parameter):**
Ohne Parameter werden nur die kategorie-basierten Listen generiert, keine port-spezifischen Listen.

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

**Kategorie-basiert:**
- `ms365_exchange_url_opt.txt` - URLs für Exchange (Optimize-Kategorie)
- `ms365_sharepoint_ipv4_allow.txt` - IPv4-Adressen für SharePoint (Allow-Kategorie)
- `ms365_common_ipv6_default.txt` - IPv6-Adressen für Common Services (Default-Kategorie)

**Port-basiert (wenn konfiguriert):**
- `ms365_exchange_ipv4_port25.txt` - IPv4-Adressen für Exchange, die Port 25 verwenden
- `ms365_exchange_url_port80.txt` - URLs für Exchange, die Port 80 verwenden
- `ms365_skype_url_port443.txt` - URLs für Skype/Teams, die Port 443 verwenden

## Datenquelle

Die Daten werden von der offiziellen Microsoft API abgerufen:
`https://endpoints.office.com/endpoints/worldwide`

Dokumentation: [Office 365 URLs and IP address ranges](https://docs.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges)

## Lizenz

Siehe [LICENSE](LICENSE) Datei.
