# fw-lists

Automated provisioning of firewall endpoint lists for firewall configurations.

## Overview

This repository contains firewall endpoint lists for various cloud services and custom configurations. Lists can be either:

- **Automatically generated** from official APIs (e.g., Microsoft 365 endpoints)
- **Manually maintained** for custom configurations and other services

### List organization

Lists are organized by source/vendor in dedicated directories:

- `/lists/ms365` – automatically generated lists from the official Microsoft 365 endpoint service
- `/lists/{vendor}` – other endpoint sources (cloud services, internal zones, custom configurations, etc.)

Each directory can contain either auto-generated lists (with associated automation scripts) or manually maintained lists, or both.

## List types

### Automatically generated lists

These lists are generated from official APIs and updated automatically. Currently supported:

#### DoH (DNS-over-HTTPS) lists

The script `scripts/doh/get-doh-publicservers.py` generates DNS-over-HTTPS (DoH) endpoint lists in [/lists/doh](lists/doh).

For detailed information, usage examples, and parameters, see: [scripts/doh/README.md](scripts/doh/README.md)

#### Microsoft 365 lists

The script `scripts/MSEndpoints/Get-MSEndpoints.ps1` generates Microsoft 365 endpoint lists in [/lists/ms365](lists/ms365) from the official Microsoft API.

For detailed information, usage examples, and parameters, see: [scripts/MSEndpoints/README.md](scripts/MSEndpoints/README.md)

### Manually maintained lists

For systems without accessible APIs or documented endpoints, lists can be manually maintained. These follow the same file format and naming convention as auto-generated lists.

#### Philips SpeechLive

Philips SpeechLive endpoints in [/lists/phillips](lists/phillips) ([source](https://www.speechlive.com/de/hilfe/thema/erste-schritte/administratoren-/-bueroleiter/whitelist-fuer-speechlive/))

## Automatic update

The GitHub Actions workflows automatically update the lists:

- **Microsoft 365**: `.github/workflows/update-ms365.yml` runs daily at 02:00 UTC
- **DoH**: `.github/workflows/update-doh.yml` runs weekly on Sunday at 02:00 UTC

If changes are detected, the updated lists are committed to the repository.

## Future scope

The name **fw-lists** is intentionally generic to accommodate various endpoint sources.

Planned and possible extensions include:

- Additional cloud vendors or services (other SaaS / IaaS endpoints)
- Vendor-neutral endpoint groups (e.g. remote support tools, update services)
- Alternative output formats (CSV, JSON, vendor-specific formats)
- Integration with configuration management or firewall automation pipelines

New list types should follow similar principles:

- Clear directory structure (e.g. `lists/{vendor}/...`)
- Predictable, script-friendly file naming
- Plain-text output where possible

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

**Note:** The DoH scraper script (`third_party/encrypted_dns_resolvers/scrape-doh-providers.py`) is licensed under GPL 3.0 as it is based on [cslev/encrypted_dns_resolvers](https://github.com/cslev/encrypted_dns_resolvers). See [third_party/encrypted_dns_resolvers/LICENSE](third_party/encrypted_dns_resolvers/LICENSE) for details. The scraper is a separate component; all other scripts and generated lists remain under MIT License.
