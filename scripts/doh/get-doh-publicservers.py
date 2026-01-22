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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        """Resolve FQDNs to IPs with multiple passes to capture round-robin pools.
        
        Performs 5 passes over all FQDNs (not 5 lookups per FQDN immediately).
        Time between passes allows DNS caches to expire and round-robin to rotate.
        This is critical for blocking lists - missing IPs allow firewall bypass.
        """
        all_ips = set()
        lookup_count = 5  # Number of passes over all FQDNs
        unique_fqdns = sorted(set(fqdns))
        
        def resolve_single_lookup(fqdn: str, pass_num: int) -> Set[str]:
            """Single DNS lookup for one FQDN with rotating DNS server."""
            fqdn_ips = set()
            
            # Rotate DNS server based on pass number for better round-robin discovery
            dns_servers = self.dns_servers if self.dns_servers else [None]
            primary_dns = dns_servers[pass_num % len(dns_servers)]
            
            # Try primary DNS server (rotated), then fallback to others
            servers_to_try = [primary_dns] + [s for s in dns_servers if s != primary_dns]
            
            for dns_server in servers_to_try:
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
                        return fqdn_ips  # Success
                        
                    except (DNSException, Exception):
                        if attempt == 0:
                            continue  # Retry once
                        else:
                            break  # Give up on this DNS server
            
            return fqdn_ips  # Return empty set or partial results
        
        # Multiple passes: Query all FQDNs in each pass with time between passes
        for pass_num in range(lookup_count):
            # Parallel execution within each pass
            with ThreadPoolExecutor(max_workers=20) as executor:
                # Submit all FQDNs for this pass
                future_to_fqdn = {}
                for fqdn in unique_fqdns:
                    future = executor.submit(resolve_single_lookup, fqdn, pass_num)
                    future_to_fqdn[future] = fqdn
                
                # Collect results as they complete
                for future in as_completed(future_to_fqdn):
                    try:
                        ips = future.result()
                        all_ips.update(ips)
                    except Exception:
                        pass  # Silently skip failed lookups
        
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
