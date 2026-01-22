# Microsoft 365 Endpoint Lists

PowerShell script for retrieving and organizing Microsoft 365 endpoint lists from the official Microsoft API.

## Features

- **API Integration**: Fetches current Microsoft 365 endpoints from Microsoft API
- **Grouping**: Organizes data by service area, address type, and category
- **Category-based lists**: Standard output format by service/type/category
- **Port-based lists**: Optional port-specific lists for fine-grained firewall rules
- **UTF-8 BOM**: Windows-compatible text file encoding

## Installation

No additional dependencies required. PowerShell 5.1+ or PowerShell Core 7+ recommended.

```powershell
# Verify PowerShell version
$PSVersionTable.PSVersion
```

## Usage

```powershell
# Basic execution (from scripts/MSEndpoints directory)
cd scripts/MSEndpoints
./Get-MSEndpoints.ps1

# Or from repository root
./scripts/MSEndpoints/Get-MSEndpoints.ps1

# With port-specific lists
./Get-MSEndpoints.ps1 -GeneratePortListsFor @("exchange:ipv4:25", "exchange:ipv6:25")

# With custom output directory
./Get-MSEndpoints.ps1 -OutputDirectory "./output"

# Multiple configurations
./Get-MSEndpoints.ps1 -GeneratePortListsFor @("exchange:ipv4:25", "exchange:url:80-443", "skype:url:443")
```

## Output Files

### Category-based (always generated)

Files are generated in the format: `ms365_{{serviceArea}}_{{addrType}}_{{category}}.txt`

Where:
- **serviceArea**: `common`, `exchange`, `sharepoint`, `skype` (Teams)
- **addrType**: `url`, `ipv4`, `ipv6`
- **category**: `opt` (Optimize), `allow` (Allow), `default` (Default)

**Examples:**
- `ms365_exchange_url_opt.txt` – URLs for Exchange (Optimize category)
- `ms365_sharepoint_ipv4_allow.txt` – IPv4 addresses for SharePoint (Allow category)
- `ms365_common_ipv6_default.txt` – IPv6 addresses for common services (Default category)

### Port-based (optional)

Files are generated in the format: `ms365_{{serviceArea}}_{{addrType}}_port{{port}}.txt`

Port-based lists are only generated when explicitly requested via the `-GeneratePortListsFor` parameter.

**Examples:**
- `ms365_exchange_ipv4_port25.txt` – IPv4 addresses for Exchange that use port 25
- `ms365_exchange_url_port80.txt` – URLs for Exchange that use port 80
- `ms365_skype_url_port443.txt` – URLs for Skype/Teams that use port 443

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-OutputDirectory` | `./lists/ms365` | Output directory (relative to script location) |
| `-ClientRequestId` | Random GUID | Client request ID for API tracking |
| `-GeneratePortListsFor` | `@()` | Array of port-specific lists to generate |

### Port List Format

Format: `servicearea:addrtype:port` or `servicearea:addrtype:port1-port2-port3`

**Components:**
- **servicearea**: `common`, `exchange`, `sharepoint`, `skype`
- **addrtype**: `url`, `ipv4`, `ipv6`
- **port**: single port or multiple ports separated by `-`

**Examples:**
```powershell
# Single port for Exchange IPv4
-GeneratePortListsFor @("exchange:ipv4:25")

# Multiple ports for Exchange URLs
-GeneratePortListsFor @("exchange:url:80-443")

# Multiple configurations
-GeneratePortListsFor @("exchange:ipv4:25", "exchange:ipv6:25", "skype:url:443")
```

## Data Source

Microsoft 365 endpoints are retrieved from the official Microsoft API:

- API Endpoint: `https://endpoints.office.com/endpoints/worldwide`
- Query Parameter: `ClientRequestId` for tracking (auto-generated GUID)

**Documentation:**
- [Office 365 URLs and IP address ranges](https://docs.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges)

## GitHub Actions

Script is CI/CD-ready for automated updates:
- Exit code handling for error detection
- Cross-platform compatible (PowerShell Core)
- Deterministic output format

Example workflow (see `.github/workflows/update-ms365.yml`):

```yaml
jobs:
  update-ms365-lists:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run MS365 endpoint script
        shell: pwsh
        run: |
          cd scripts/MSEndpoints
          ./Get-MSEndpoints.ps1
      - name: Commit changes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add lists/ms365/*.txt
          git diff --staged --quiet || git commit -m "Update MS365 endpoints"
          git push
```

## Service Area Mapping

| Service Area | Description |
|--------------|-------------|
| `common` | Common/shared Microsoft 365 services |
| `exchange` | Exchange Online (mail, calendar, contacts) |
| `sharepoint` | SharePoint Online and OneDrive for Business |
| `skype` | Skype for Business and Microsoft Teams |

## Category Descriptions

| Category | Description |
|----------|-------------|
| `opt` (Optimize) | Performance-critical endpoints requiring direct routing |
| `allow` (Allow) | Standard endpoints requiring internet connectivity |
| `default` (Default) | General endpoints with fallback to proxy/firewall |

## License

Same as main repository.
