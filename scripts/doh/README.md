# DoH Public Servers List Builder

Performant Python script for scraping and filtering DoH (DNS-over-HTTPS) endpoints from curl wiki.

## Features

- **Scraping**: Calls `scrape-doh-providers.py`, extracts 340+ FQDNs
- **DNS Resolution**: Resolves FQDNs to IPv4/IPv6 with fallback DNS servers
- **Filtering**: 
  - Exclusion lists (CLI or file)
  - Base domain detection (including multi-level TLDs)
  - Deduplication and sorting
- **Ratio Check**: Warns on >20% change (configurable)
- **Conditional Writes**: _filtered, _exclusions, _basedomains only written when content exists

## Installation

```powershell
# Python environment (if not already present)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Dependencies
pip install requests dnspython
```

## Usage

```bash
# Basic (includes DNS resolution with system resolver)
python get-doh-publicservers.py

# FQDNs only (no DNS resolution)
python get-doh-publicservers.py --no-resolve

# With fallback DNS servers
python get-doh-publicservers.py --dns-server 1.1.1.1,8.8.8.8

# With exclusions
python get-doh-publicservers.py --exclusions dns.google cloudflare-dns.com
python get-doh-publicservers.py --exclusions-file exclusions.txt

# Remove base domains from _filtered
python get-doh-publicservers.py --filter-base-domains

# Custom output directory & ratio tolerance
python get-doh-publicservers.py --output-dir custom/path --warn-change-ratio 0.3

# Skip ratio check (first run)
python get-doh-publicservers.py --skip-ratio-check
```

## Output Files

### Always written
- `doh_fqdn.txt` - All FQDNs (raw)
- `doh_ipv4.txt` - All IPv4 (when --no-resolve not set)
- `doh_ipv6.txt` - All IPv6 (when --no-resolve not set)

### Conditional (only when content exists)
- `doh_fqdn_filtered.txt` - Filtered FQDNs (without exclusions, with/without basedomains depending on flag)
- `doh_fqdn_exclusions.txt` - Excluded FQDNs
- `doh_fqdn_basedomains.txt` - Base domain FQDNs (e.g., `google.com`, not `dns.google.com`)
- `doh_ipv4_filtered.txt`, `doh_ipv4_exclusions.txt`, `doh_ipv4_basedomains.txt`
- `doh_ipv6_filtered.txt`, `doh_ipv6_exclusions.txt`, `doh_ipv6_basedomains.txt`

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--output-dir` | `../../lists/doh` | Output directory (relative to script location) |
| `--no-resolve` | `false` | Skip DNS resolution |
| `--dns-server` | System | Comma-separated DNS servers (fallback mode) |
| `--exclusions` | `[]` | Exclusion entries (FQDNs/IPs) |
| `--exclusions-file` | - | File with exclusions (one per line) |
| `--no-clean` | `false` | Do not clean output directory |
| `--warn-change-ratio` | `0.2` | Warn on ±X% change (0.2 = ±20%, allowed factor: 0.8-1.2) |
| `--skip-ratio-check` | `false` | Skip ratio check |
| `--filter-base-domains` | `false` | Remove base domains from _filtered |

## Testing

```bash
# Unit tests
python test_get_doh_publicservers.py

# Or with pytest
pytest test_get_doh_publicservers.py -v
```

Test coverage:
- Normalization (HTML tags, ports, protocols)
- IP validation (IPv4/IPv6)
- Base domain detection (multi-level TLDs)
- Ratio check (0.8-1.2 factor at 20% tolerance)
- Exclusion loading (CLI + file)
- Conditional file writing

## GitHub Actions

Script is CI/CD-ready:
- Exit code 1 on errors (scraper failure, ratio check)
- No Windows-specific dependencies
- Valid UTF-8 output (BOM for Windows compatibility)

Example workflow:

```yaml
jobs:
  update-doh-lists:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install requests dnspython
      - run: python scripts/doh/get-doh-publicservers.py --dns-server 1.1.1.1,8.8.8.8
```

## Differences to Get-DoH-PublicServers.py.bak

**Advantages of new script:**
- 468 lines instead of 755 (38% reduction)
- Scraper integration (reusable)
- Multi-DNS-server with fallback
- Ratio check with configurable tolerance
- Conditional file writes (saves I/O)
- Unit tests with 16 test cases
- Clearer CLI parameters

**Removed:**
- HTML parsing from DoH wiki (replaced by scrape-doh-providers.py)
- Complex token normalization (HTML tags, ports)
- `config` dictionary handling

## Credits

- Scraper script based on [cslev/encrypted_dns_resolvers](https://github.com/cslev/encrypted_dns_resolvers)
- DoH data source: [curl DNS-over-HTTPS Wiki](https://github.com/curl/curl/wiki/DNS-over-HTTPS)

## License

Same as main repository.
