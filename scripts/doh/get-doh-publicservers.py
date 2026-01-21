#!/usr/bin/env python3
"""
DoH Public Servers List Builder

Scrapes DoH endpoints from curl wiki and generates filtered lists.
Supports exclusions, base-domain detection, and DNS resolution with fallback.

Usage:
    python get-doh-publicservers.py
    python get-doh-publicservers.py --no-resolve
    python get-doh-publicservers.py --dns-server 1.1.1.1,8.8.8.8 --filter-base-domains
"""

import sys
import argparse
import subprocess
import ipaddress
from pathlib import Path
from typing import List, Set, Tuple
import dns.resolver
from dns.exception import DNSException


class DoHListBuilder:
    """Build and filter DoH endpoint lists."""

    def __init__(
        self,
        output_dir: str,
        resolve_ips: bool,
        dns_servers: List[str],
        exclusions: List[str],
        exclusions_file: str,
        clean_output: bool,
        warn_change_ratio: float,
        skip_ratio_check: bool,
        filter_base_domains: bool,
    ):
        self.output_dir = Path(output_dir).resolve()
        self.resolve_ips = resolve_ips
        self.dns_servers = dns_servers or []
        self.clean_output = clean_output
        self.warn_change_ratio = warn_change_ratio
        self.skip_ratio_check = skip_ratio_check
        self.filter_base_domains = filter_base_domains
        
        # Load exclusions
        self.exclusions = self._load_exclusions(exclusions, exclusions_file)

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize FQDN/IP to lowercase, strip whitespace."""
        if not value:
            return None
        value = value.strip().lower().rstrip(".")
        return value if value else None

    @staticmethod
    def _is_ipv4(value: str) -> bool:
        """Check if value is IPv4."""
        try:
            ipaddress.IPv4Address(value)
            return True
        except (ValueError, ipaddress.AddressValueError):
            return False

    @staticmethod
    def _is_ipv6(value: str) -> bool:
        """Check if value is IPv6."""
        try:
            ipaddress.IPv6Address(value)
            return True
        except (ValueError, ipaddress.AddressValueError):
            return False

    @staticmethod
    def _is_base_domain(fqdn: str) -> bool:
        """Check if FQDN is base domain (e.g., example.com, not sub.example.com)."""
        if not fqdn or "." not in fqdn or fqdn == ".":
            return False
        
        labels = fqdn.split(".")
        
        # Filter empty labels (e.g., from ".")
        labels = [l for l in labels if l]
        if not labels:
            return False
        
        # Multi-level TLDs
        multi_tlds = {
            'co.uk', 'co.za', 'co.jp', 'co.nz', 'co.in', 'co.kr',
            'com.au', 'com.br', 'com.cn', 'com.mx', 'com.ar',
            'org.uk', 'net.au', 'gov.uk', 'ac.uk', 'edu.au'
        }
        
        if len(labels) >= 3:
            potential_tld = f"{labels[-2]}.{labels[-1]}"
            if potential_tld in multi_tlds:
                return len(labels) == 3
        
        return len(labels) == 2

    def _load_exclusions(self, exclusions: List[str], exclusions_file: str) -> Set[str]:
        """Load and normalize exclusions."""
        excl_set = set()
        
        # From CLI args
        if exclusions:
            for item in exclusions:
                normalized = self._normalize(item)
                if normalized:
                    excl_set.add(normalized)
        
        # From file
        if exclusions_file:
            excl_path = Path(exclusions_file)
            if excl_path.exists():
                with open(excl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and not line.startswith(";"):
                            normalized = self._normalize(line)
                            if normalized:
                                excl_set.add(normalized)
        
        return excl_set

    def _resolve_fqdns(self, fqdns: List[str], record_type: str) -> List[str]:
        """Resolve FQDNs to IPs with multiple lookups to capture round-robin pools.
        
        Performs 5 lookups per FQDN to discover all IPs in DNS round-robin configurations.
        This is critical for blocking lists - missing IPs allow firewall bypass.
        """
        all_ips = set()
        lookup_count = 5  # Lookups per FQDN to discover round-robin IPs
        
        for fqdn in sorted(set(fqdns)):
            fqdn_ips = set()
            
            # Multiple lookups to capture all IPs in DNS round-robin pools
            for lookup_num in range(lookup_count):
                resolved = False
                
                # Try each DNS server in order (fallback)
                for dns_server in (self.dns_servers if self.dns_servers else [None]):
                    # Retry up to 2 times for transient errors
                    for attempt in range(2):
                        try:
                            resolver = dns.resolver.Resolver()
                            if dns_server:
                                resolver.nameservers = [dns_server]
                            
                            # Increase timeouts for more reliable lookups
                            resolver.timeout = 3.0  # 3 seconds per attempt
                            resolver.lifetime = 10.0  # 10 seconds total
                            
                            answers = resolver.resolve(fqdn, record_type, tcp=False)
                            for rdata in answers:
                                fqdn_ips.add(str(rdata))
                            resolved = True
                            break  # Success, no need to retry
                            
                        except (DNSException, Exception):
                            if attempt == 0:
                                continue  # Retry once
                            else:
                                break  # Give up on this DNS server
                    
                    if resolved:
                        break  # Success, no need to try other DNS servers
                
                if not resolved:
                    break  # If first lookup fails, skip remaining lookups
                
                # Small delay between lookups to help discover round-robin IPs
                if lookup_num < lookup_count - 1:
                    import time
                    time.sleep(0.1)
            
            # Add all discovered IPs for this FQDN to the global set
            all_ips.update(fqdn_ips)
        
        # Sort IPs numerically (not lexicographically)
        if record_type == "A":
            return sorted(all_ips, key=lambda x: ipaddress.IPv4Address(x))
        elif record_type == "AAAA":
            return sorted(all_ips, key=lambda x: ipaddress.IPv6Address(x))
        else:
            return sorted(all_ips)

    def _count_entries(self, path: Path) -> int:
        """Count non-empty lines in file."""
        if not path.exists():
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def _check_ratio(self, old_count: int, new_count: int, data_type: str) -> bool:
        """Check if change is within acceptable ratio (±warn_change_ratio)."""
        if old_count == 0 or new_count == 0:
            return True
        
        ratio = new_count / old_count
        min_ratio = 1.0 - self.warn_change_ratio
        max_ratio = 1.0 + self.warn_change_ratio
        
        if ratio < min_ratio or ratio > max_ratio:
            print(
                f"WARNING: {data_type.upper()} entries changed significantly: "
                f"{old_count} → {new_count} ({ratio*100:.1f}%). "
                f"Acceptable range: {min_ratio*100:.0f}%-{max_ratio*100:.0f}%.",
                file=sys.stderr,
            )
            return False
        
        return True

    def _write_lists(
        self, 
        raw_path: Path, 
        filtered_path: Path, 
        exclusions_path: Path, 
        basedomains_path: Path, 
        items: List[str], 
        basedomain_ips: Set[str] = None
    ) -> Tuple[int, int, int, int]:
        """Write all output lists."""
        base_domains = []
        excluded = []
        filtered = []
        
        for item in items:
            normalized = self._normalize(item)
            if not normalized:
                continue
            
            # Exclusions have priority
            if normalized in self.exclusions:
                excluded.append(normalized)
                continue
            
            # Classify item
            is_basedomain = False
            if not self._is_ipv4(normalized) and not self._is_ipv6(normalized):
                is_basedomain = self._is_base_domain(normalized)
            elif basedomain_ips and normalized in basedomain_ips:
                is_basedomain = True
            
            if is_basedomain:
                base_domains.append(normalized)
            else:
                filtered.append(normalized)
        
        # Deduplicate and sort (numerically for IPs, lexicographically for FQDNs)
        def sort_items(items_list):
            unique = set(items_list)
            # Try to sort as IPv4, fallback to IPv6, then string
            try:
                return sorted(unique, key=lambda x: ipaddress.IPv4Address(x))
            except (ValueError, ipaddress.AddressValueError):
                try:
                    return sorted(unique, key=lambda x: ipaddress.IPv6Address(x))
                except (ValueError, ipaddress.AddressValueError):
                    return sorted(unique)
        
        base_domains = sort_items(base_domains)
        excluded = sort_items(excluded)
        filtered = sort_items(filtered)
        all_items = sort_items(base_domains + excluded + filtered)
        
        # Write raw file (always)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(all_items))
        
        # Filtered list
        if self.filter_base_domains:
            filtered_list = filtered
        else:
            filtered_list = sorted(set(filtered + base_domains))
        
        # Write filtered (only if different from raw or has content)
        if filtered_list and filtered_list != all_items:
            with open(filtered_path, "w", encoding="utf-8-sig") as f:
                f.write("\n".join(filtered_list))
        
        # Write exclusions (only if exist)
        if excluded:
            with open(exclusions_path, "w", encoding="utf-8-sig") as f:
                f.write("\n".join(excluded))
        
        # Write basedomains (only if exist)
        if base_domains:
            with open(basedomains_path, "w", encoding="utf-8-sig") as f:
                f.write("\n".join(base_domains))
        
        return len(all_items), len(filtered_list), len(excluded), len(base_domains)

    def run(self):
        """Main execution."""
        print(f"Output Directory: {self.output_dir}")
        
        # Count old entries
        old_fqdn = self._count_entries(self.output_dir / "doh_fqdn.txt")
        old_ipv4 = self._count_entries(self.output_dir / "doh_ipv4.txt")
        old_ipv6 = self._count_entries(self.output_dir / "doh_ipv6.txt")
        
        # Clean output directory
        if self.clean_output and self.output_dir.exists():
            for file in self.output_dir.glob("*.txt"):
                file.unlink()
            print(f"Cleaned: {self.output_dir}")
        
        # Run scraper
        scraper_path = Path(__file__).parent / "scrape-doh-providers.py"
        if not scraper_path.exists():
            print(f"ERROR: Scraper not found: {scraper_path}", file=sys.stderr)
            sys.exit(1)
        
        print("Running scraper...")
        try:
            result = subprocess.run(
                [sys.executable, str(scraper_path), "o['url']"],
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8"
            )
            endpoint_urls = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Scraper failed: {e}", file=sys.stderr)
            sys.exit(1)
        
        print(f"Scraped {len(endpoint_urls)} URLs")
        
        # Parse FQDNs from URLs
        fqdns = []
        for url in endpoint_urls:
            # Extract hostname from URL
            if "://" in url:
                host = url.split("://", 1)[1].split("/")[0]
            else:
                host = url.split("/")[0]
            
            # Remove port
            if host.startswith("["):
                # IPv6
                host = host.split("]")[0].strip("[")
            else:
                host = host.split(":")[0]
            
            normalized = self._normalize(host)
            if normalized and not self._is_ipv4(normalized) and not self._is_ipv6(normalized):
                fqdns.append(normalized)
        
        fqdns = sorted(set(fqdns))
        base_domain_fqdns = [f for f in fqdns if self._is_base_domain(f)]
        
        print(f"Extracted {len(fqdns)} FQDNs ({len(base_domain_fqdns)} base domains)")
        
        # Resolve IPs
        ipv4 = []
        ipv6 = []
        base_domain_ipv4 = set()
        base_domain_ipv6 = set()
        
        if self.resolve_ips:
            print("Resolving IPv4...")
            ipv4 = self._resolve_fqdns(fqdns, "A")
            print(f"  Resolved {len(ipv4)} IPv4")
            
            print("Resolving IPv6...")
            ipv6 = self._resolve_fqdns(fqdns, "AAAA")
            print(f"  Resolved {len(ipv6)} IPv6")
            
            if base_domain_fqdns:
                print("Resolving base domain IPs...")
                base_domain_ipv4 = set(self._resolve_fqdns(base_domain_fqdns, "A"))
                base_domain_ipv6 = set(self._resolve_fqdns(base_domain_fqdns, "AAAA"))
        
        # Check ratios
        if not self.skip_ratio_check:
            ratio_ok = True
            ratio_ok &= self._check_ratio(old_fqdn, len(fqdns), "fqdn")
            ratio_ok &= self._check_ratio(old_ipv4, len(ipv4), "ipv4")
            ratio_ok &= self._check_ratio(old_ipv6, len(ipv6), "ipv6")
            
            if not ratio_ok:
                print("ERROR: Ratio check failed. Aborting.", file=sys.stderr)
                sys.exit(1)
        
        # Write outputs
        print("\nWriting output files...")
        
        paths_fqdn = (
            self.output_dir / "doh_fqdn.txt",
            self.output_dir / "doh_fqdn_filtered.txt",
            self.output_dir / "doh_fqdn_exclusions.txt",
            self.output_dir / "doh_fqdn_basedomains.txt",
        )
        raw, filt, excl, bd = self._write_lists(*paths_fqdn, fqdns)
        print(f"  FQDN: {raw} raw, {filt} filtered, {excl} excluded, {bd} basedomains")
        
        if self.resolve_ips:
            paths_ipv4 = (
                self.output_dir / "doh_ipv4.txt",
                self.output_dir / "doh_ipv4_filtered.txt",
                self.output_dir / "doh_ipv4_exclusions.txt",
                self.output_dir / "doh_ipv4_basedomains.txt",
            )
            raw, filt, excl, bd = self._write_lists(*paths_ipv4, ipv4, base_domain_ipv4)
            print(f"  IPv4: {raw} raw, {filt} filtered, {excl} excluded, {bd} basedomains")
            
            paths_ipv6 = (
                self.output_dir / "doh_ipv6.txt",
                self.output_dir / "doh_ipv6_filtered.txt",
                self.output_dir / "doh_ipv6_exclusions.txt",
                self.output_dir / "doh_ipv6_basedomains.txt",
            )
            raw, filt, excl, bd = self._write_lists(*paths_ipv6, ipv6, base_domain_ipv6)
            print(f"  IPv6: {raw} raw, {filt} filtered, {excl} excluded, {bd} basedomains")
        
        print("\nDone!")


def main():
    parser = argparse.ArgumentParser(
        description="Build DoH endpoint lists from curl wiki",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --no-resolve
  %(prog)s --dns-server 1.1.1.1,8.8.8.8 --filter-base-domains
  %(prog)s --exclusions-file exclusions.txt --warn-change-ratio 0.3
        """
    )
    
    parser.add_argument(
        "--output-dir",
        default="../../lists/doh",
        help="Output directory (default: ../../lists/doh, relative to script location)"
    )
    parser.add_argument(
        "--no-resolve",
        action="store_true",
        help="Skip DNS resolution (FQDN lists only)"
    )
    parser.add_argument(
        "--dns-server",
        help="DNS servers for lookups, comma-separated (default: system resolver)"
    )
    parser.add_argument(
        "--exclusions",
        nargs="+",
        default=[],
        help="Exclusion entries (FQDNs/IPs)"
    )
    parser.add_argument(
        "--exclusions-file",
        help="File with exclusions (one per line)"
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not clean output directory before run"
    )
    parser.add_argument(
        "--warn-change-ratio",
        type=float,
        default=0.2,
        help="Warn if lists change by more than ±X%% (default: 0.2 = ±20%%)"
    )
    parser.add_argument(
        "--skip-ratio-check",
        action="store_true",
        help="Skip ratio check (allow any change)"
    )
    parser.add_argument(
        "--filter-base-domains",
        action="store_true",
        help="Exclude base domains from filtered lists (default: False)"
    )
    
    args = parser.parse_args()
    
    # Parse DNS servers
    dns_servers = []
    if args.dns_server:
        dns_servers = [s.strip() for s in args.dns_server.split(",") if s.strip()]
    
    builder = DoHListBuilder(
        output_dir=args.output_dir,
        resolve_ips=not args.no_resolve,
        dns_servers=dns_servers,
        exclusions=args.exclusions,
        exclusions_file=args.exclusions_file,
        clean_output=not args.no_clean,
        warn_change_ratio=args.warn_change_ratio,
        skip_ratio_check=args.skip_ratio_check,
        filter_base_domains=args.filter_base_domains,
    )
    
    builder.run()


if __name__ == "__main__":
    main()
