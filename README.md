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

The script `scripts/doh/get-doh-publicservers.py` generates DNS-over-HTTPS (DoH) endpoint lists.

For detailed information, usage examples, and parameters, see: [scripts/doh/README.md](scripts/doh/README.md)

#### Microsoft 365 lists

The script `scripts/MSEndpoints/Get-MSEndpoints.ps1` generates Microsoft 365 endpoint lists:

- Retrieves the current Microsoft 365 endpoints from the Microsoft API
- Groups the data by:
  - **Service area**: e.g. `common`, `exchange`, `sharepoint`, `skype` (Teams)
  - **Address type**: `url`, `ipv4`, `ipv6`
  - **Category**: `opt` (Optimize), `allow` (Allow), `default` (Default)
- Creates two types of files:
  1. **Category-based** (always):  
     `ms365_{{serviceArea}}_{{addrType}}_{{category}}.txt`
  2. **Port-based** (optional):  
     `ms365_{{serviceArea}}_{{addrType}}_port{{port}}.txt`
- Stores all lists in the directory `/lists/ms365`

#### Port-based lists (optional)

Port-based lists can be enabled via the `-GeneratePortListsFor` parameter.  
These lists contain only the IPs or URLs that use the specified port(s) and are created **in addition** to the category-based lists.

**Examples:**

    # Only Exchange IPv4 for port 25
    ./scripts/MSEndpoints/Get-MSEndpoints.ps1 -GeneratePortListsFor @("exchange:ipv4:25")

    # Multiple configurations (in addition to the category-based lists)
    ./scripts/MSEndpoints/Get-MSEndpoints.ps1 -GeneratePortListsFor @("exchange:ipv4:25", "exchange:url:80-443", "skype:url:443")

**Format:**

- `servicearea:addrtype:port`  
- or `servicearea:addrtype:port1-port2-port3`

Where:

- `servicearea`: `common`, `exchange`, `sharepoint`, `skype`
- `addrtype`: `url`, `ipv4`, `ipv6`
- `port`: single port or multiple ports separated by `-`

**Default configuration (no parameter):**  
Without `-GeneratePortListsFor`, only the category-based lists are generated and no port-specific lists are created.

### Manually maintained lists

In addition to automatically generated lists, this repository can contain manually maintained endpoint lists for:

- Cloud services other than Microsoft 365
- Internal network zones and custom configurations
- Third-party services or applications

Manually maintained lists follow the same naming convention and file format as the auto-generated lists, making them easy to integrate with firewall configurations. Simply add them to the appropriate `/lists/{vendor}` directory.

**Example structure for manually maintained lists:**

```
lists/
├── ms365/                              # Auto-generated Microsoft 365 lists
│   ├── ms365_exchange_url_allow.txt
│   └── ...
├── custom/                             # Manually maintained custom lists
│   ├── custom_internal_ipv4_allow.txt
│   └── custom_vpn_url_allow.txt
└── aws/                                # Manually maintained AWS lists (example)
    └── aws_cloudfront_ipv4_allow.txt
```

## Automatic update

The GitHub Actions workflow (`.github/workflows/update-endpoints.yml`) runs the script automatically once per day at 02:00 UTC.  
If changes are detected, the updated lists are committed to the repository.

## Manual execution

### Local

#### Microsoft 365 endpoints

    # Standard execution (from scripts/MSEndpoints directory)
    cd scripts/MSEndpoints
    ./Get-MSEndpoints.ps1

    # Or from repository root
    ./scripts/MSEndpoints/Get-MSEndpoints.ps1

    # With port-specific lists
    ./scripts/MSEndpoints/Get-MSEndpoints.ps1 -GeneratePortListsFor @("exchange:ipv4:25", "exchange:ipv6:25")

    # With a custom output directory
    ./scripts/MSEndpoints/Get-MSEndpoints.ps1 -OutputDirectory "./output"

#### DoH endpoints

For DoH script usage, parameters, and examples, see: [scripts/doh/README.md](scripts/doh/README.md)

### GitHub Actions

The workflow can also be triggered manually via the GitHub Actions UI.

## Example files

After execution, files like the following will be created:

**DoH lists:**

See [scripts/doh/README.md](scripts/doh/README.md) for details on output files.

**Microsoft 365 lists:**

**Category-based:**

- `ms365_exchange_url_opt.txt` – URLs for Exchange (Optimize category)
- `ms365_sharepoint_ipv4_allow.txt` – IPv4 addresses for SharePoint (Allow category)
- `ms365_common_ipv6_default.txt` – IPv6 addresses for common services (Default category)

**Port-based (if configured):**

- `ms365_exchange_ipv4_port25.txt` – IPv4 addresses for Exchange that use port 25
- `ms365_exchange_url_port80.txt` – URLs for Exchange that use port 80
- `ms365_skype_url_port443.txt` – URLs for Skype/Teams that use port 443

## Data source

The Microsoft 365 data is retrieved from the official Microsoft API:

- `https://endpoints.office.com/endpoints/worldwide`

Documentation:

- [Office 365 URLs and IP address ranges](https://docs.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges)

The DoH data is retrieved from the curl project wiki. See [scripts/doh/README.md](scripts/doh/README.md) for details.

## Future scope

Currently this repository only contains Microsoft 365 endpoint lists, but the name **fw-lists** is intentionally generic.

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

See the [LICENSE](LICENSE) file.
