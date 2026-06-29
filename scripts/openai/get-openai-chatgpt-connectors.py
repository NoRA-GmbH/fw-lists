#!/usr/bin/env python3
"""
OpenAI ChatGPT Connectors IP List Builder

Fetches the official OpenAI ChatGPT connector egress IP ranges and writes
plain-text firewall lists.
"""

import argparse
import ipaddress
import json
import sys
import urllib.request
from pathlib import Path
from typing import Iterable, List, Tuple


DEFAULT_SOURCE_URL = "https://openai.com/chatgpt-connectors.json"


def fetch_json(source_url: str) -> dict:
    """Fetch JSON from source URL."""
    request = urllib.request.Request(source_url, headers={"User-Agent": "fw-lists/openai-updater"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Failed to fetch OpenAI connector ranges: HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def extract_prefixes(data: dict) -> Tuple[List[str], List[str]]:
    """Extract and validate IPv4/IPv6 CIDR prefixes from OpenAI JSON."""
    ipv4 = set()
    ipv6 = set()

    for item in data.get("prefixes", []):
        prefix = item.get("ipv4Prefix") or item.get("ipv6Prefix")
        if not prefix:
            continue

        network = ipaddress.ip_network(prefix, strict=False)
        normalized = str(network)

        if network.version == 4:
            ipv4.add(normalized)
        elif network.version == 6:
            ipv6.add(normalized)

    return sort_networks(ipv4), sort_networks(ipv6)


def sort_networks(prefixes: Iterable[str]) -> List[str]:
    """Sort CIDR prefixes numerically."""
    return sorted(prefixes, key=lambda value: ipaddress.ip_network(value, strict=False))


def write_list(path: Path, items: Iterable[str]) -> None:
    """Write newline-delimited firewall list."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(items)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate OpenAI ChatGPT connector firewall lists.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL, help="OpenAI connector JSON URL")
    parser.add_argument("--output-dir", default="./lists/openai", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    data = fetch_json(args.source_url)
    ipv4, ipv6 = extract_prefixes(data)

    if not ipv4 and not ipv6:
        print("No OpenAI connector prefixes found.", file=sys.stderr)
        return 1

    write_list(output_dir / "openai_chatgpt_connectors_ipv4.txt", ipv4)
    write_list(output_dir / "openai_chatgpt_connectors_ipv6.txt", ipv6)

    print(f"Wrote {len(ipv4) + len(ipv6)} total prefixes ({len(ipv4)} IPv4, {len(ipv6)} IPv6) to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
