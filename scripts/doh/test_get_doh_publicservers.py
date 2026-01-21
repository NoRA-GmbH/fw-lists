#!/usr/bin/env python3
"""
Test suite for get-doh-publicservers.py

Run:
    python -m pytest test_get_doh_publicservers.py -v
    python test_get_doh_publicservers.py
"""

import unittest
from pathlib import Path
import tempfile
import shutil


# Import module under test
import sys
import importlib.util
spec = importlib.util.spec_from_file_location("get_doh_publicservers", Path(__file__).parent / "get-doh-publicservers.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DoHListBuilder = module.DoHListBuilder


class TestNormalization(unittest.TestCase):
    """Test input normalization."""
    
    def test_normalize_basic(self):
        """Test basic normalization."""
        assert DoHListBuilder._normalize("  Example.COM  ") == "example.com"
        assert DoHListBuilder._normalize("DNS.GOOGLE.") == "dns.google"
        assert DoHListBuilder._normalize("") is None
        assert DoHListBuilder._normalize("   ") is None
        assert DoHListBuilder._normalize(None) is None
    
    def test_normalize_preserves_ipv6(self):
        """Test IPv6 normalization."""
        assert DoHListBuilder._normalize("2001:4860:4860::8888") == "2001:4860:4860::8888"


class TestIPValidation(unittest.TestCase):
    """Test IP address validation."""
    
    def test_ipv4_validation(self):
        """Test IPv4 detection."""
        assert DoHListBuilder._is_ipv4("8.8.8.8")
        assert DoHListBuilder._is_ipv4("192.168.1.1")
        assert not DoHListBuilder._is_ipv4("dns.google")
        assert not DoHListBuilder._is_ipv4("2001:4860:4860::8888")
        assert not DoHListBuilder._is_ipv4("999.999.999.999")
    
    def test_ipv6_validation(self):
        """Test IPv6 detection."""
        assert DoHListBuilder._is_ipv6("2001:4860:4860::8888")
        assert DoHListBuilder._is_ipv6("::1")
        assert DoHListBuilder._is_ipv6("fe80::1")
        assert not DoHListBuilder._is_ipv6("8.8.8.8")
        assert not DoHListBuilder._is_ipv6("dns.google")


class TestBaseDomainDetection(unittest.TestCase):
    """Test base domain detection."""
    
    def test_simple_domains(self):
        """Test 2-label base domains."""
        assert DoHListBuilder._is_base_domain("google.com")
        assert DoHListBuilder._is_base_domain("example.org")
        assert not DoHListBuilder._is_base_domain("dns.google.com")
        assert not DoHListBuilder._is_base_domain("sub.example.org")
    
    def test_multi_tld_domains(self):
        """Test multi-level TLD base domains."""
        # 3-label base domains with multi-level TLD
        assert DoHListBuilder._is_base_domain("example.co.uk")
        assert DoHListBuilder._is_base_domain("example.com.au")
        
        # Subdomains of multi-TLD
        assert not DoHListBuilder._is_base_domain("sub.example.co.uk")
        assert not DoHListBuilder._is_base_domain("dns.example.com.au")
    
    def test_edge_cases(self):
        """Test edge cases."""
        assert not DoHListBuilder._is_base_domain("localhost")
        assert not DoHListBuilder._is_base_domain("com")
        assert not DoHListBuilder._is_base_domain("")
        assert not DoHListBuilder._is_base_domain(".")


class TestRatioCheck(unittest.TestCase):
    """Test change ratio validation."""
    
    def setUp(self):
        """Set up test builder with 20% tolerance."""
        self.builder = DoHListBuilder(
            output_dir="test_output",
            resolve_ips=False,
            dns_servers=[],
            exclusions=[],
            exclusions_file=None,
            clean_output=False,
            warn_change_ratio=0.2,  # ±20%
            skip_ratio_check=False,
            filter_base_domains=False,
        )
    
    def test_within_range(self):
        """Test ratios within acceptable range (0.8 - 1.2)."""
        assert self.builder._check_ratio(100, 100, "test")  # 1.0
        assert self.builder._check_ratio(100, 90, "test")   # 0.9
        assert self.builder._check_ratio(100, 110, "test")  # 1.1
        assert self.builder._check_ratio(100, 80, "test")   # 0.8 (edge)
        assert self.builder._check_ratio(100, 120, "test")  # 1.2 (edge)
    
    def test_outside_range(self):
        """Test ratios outside acceptable range."""
        assert not self.builder._check_ratio(100, 79, "test")   # 0.79
        assert not self.builder._check_ratio(100, 121, "test")  # 1.21
        assert not self.builder._check_ratio(100, 50, "test")   # 0.5
        assert not self.builder._check_ratio(100, 200, "test")  # 2.0
    
    def test_zero_cases(self):
        """Test with zero counts."""
        assert self.builder._check_ratio(0, 100, "test")  # New data
        assert self.builder._check_ratio(100, 0, "test")  # All gone


class TestExclusionsLoading(unittest.TestCase):
    """Test exclusion loading."""
    
    def test_cli_exclusions(self):
        """Test exclusions from CLI args."""
        builder = DoHListBuilder(
            output_dir="test_output",
            resolve_ips=False,
            dns_servers=[],
            exclusions=["Example.COM", "  8.8.8.8  ", ""],
            exclusions_file=None,
            clean_output=False,
            warn_change_ratio=0.2,
            skip_ratio_check=False,
            filter_base_domains=False,
        )
        
        assert "example.com" in builder.exclusions
        assert "8.8.8.8" in builder.exclusions
        assert "" not in builder.exclusions
    
    def test_file_exclusions(self):
        """Test exclusions from file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("# Comment\n")
            f.write("dns.google.com\n")
            f.write("; Another comment\n")
            f.write("  1.1.1.1  \n")
            f.write("\n")
            exclusions_file = f.name
        
        try:
            builder = DoHListBuilder(
                output_dir="test_output",
                resolve_ips=False,
                dns_servers=[],
                exclusions=[],
                exclusions_file=exclusions_file,
                clean_output=False,
                warn_change_ratio=0.2,
                skip_ratio_check=False,
                filter_base_domains=False,
            )
            
            assert "dns.google.com" in builder.exclusions
            assert "1.1.1.1" in builder.exclusions
            assert "" not in builder.exclusions
        finally:
            Path(exclusions_file).unlink()


class TestListWriting(unittest.TestCase):
    """Test list writing logic."""
    
    def setUp(self):
        """Create temp directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_write_with_basedomains(self):
        """Test writing lists with base domains."""
        builder = DoHListBuilder(
            output_dir=self.temp_dir,
            resolve_ips=False,
            dns_servers=[],
            exclusions=set(),
            exclusions_file=None,
            clean_output=False,
            warn_change_ratio=0.2,
            skip_ratio_check=False,
            filter_base_domains=False,
        )
        
        items = ["google.com", "dns.google.com", "cloudflare.com"]
        
        raw_path = Path(self.temp_dir) / "test.txt"
        filtered_path = Path(self.temp_dir) / "test_filtered.txt"
        exclusions_path = Path(self.temp_dir) / "test_exclusions.txt"
        basedomains_path = Path(self.temp_dir) / "test_basedomains.txt"
        
        raw, filt, excl, bd = builder._write_lists(
            raw_path, filtered_path, exclusions_path, basedomains_path, items
        )
        
        assert raw == 3
        assert bd == 2  # google.com, cloudflare.com
        assert raw_path.exists()
        assert basedomains_path.exists()
        
        # Basedomains file should contain base domains
        with open(basedomains_path, "r", encoding="utf-8") as f:
            bd_content = f.read()
            assert "cloudflare.com" in bd_content
            assert "google.com" in bd_content
    
    def test_write_with_exclusions(self):
        """Test writing lists with exclusions."""
        builder = DoHListBuilder(
            output_dir=self.temp_dir,
            resolve_ips=False,
            dns_servers=[],
            exclusions={"dns.google.com"},
            exclusions_file=None,
            clean_output=False,
            warn_change_ratio=0.2,
            skip_ratio_check=False,
            filter_base_domains=False,
        )
        
        items = ["google.com", "dns.google.com", "cloudflare.com"]
        
        raw_path = Path(self.temp_dir) / "test.txt"
        filtered_path = Path(self.temp_dir) / "test_filtered.txt"
        exclusions_path = Path(self.temp_dir) / "test_exclusions.txt"
        basedomains_path = Path(self.temp_dir) / "test_basedomains.txt"
        
        raw, filt, excl, bd = builder._write_lists(
            raw_path, filtered_path, exclusions_path, basedomains_path, items
        )
        
        assert excl == 1  # dns.google.com
        assert exclusions_path.exists()
        
        # Exclusions file should contain excluded item
        with open(exclusions_path, "r", encoding="utf-8") as f:
            excl_content = f.read()
            assert "dns.google.com" in excl_content
    
    def test_filter_base_domains_flag(self):
        """Test --filter-base-domains behavior."""
        # Without flag (default): filtered includes basedomains
        builder1 = DoHListBuilder(
            output_dir=self.temp_dir,
            resolve_ips=False,
            dns_servers=[],
            exclusions=set(),
            exclusions_file=None,
            clean_output=False,
            warn_change_ratio=0.2,
            skip_ratio_check=False,
            filter_base_domains=False,  # Default
        )
        
        items = ["google.com", "dns.google.com"]
        
        raw_path = Path(self.temp_dir) / "test1.txt"
        filtered_path = Path(self.temp_dir) / "test1_filtered.txt"
        exclusions_path = Path(self.temp_dir) / "test1_exclusions.txt"
        basedomains_path = Path(self.temp_dir) / "test1_basedomains.txt"
        
        raw, filt, excl, bd = builder1._write_lists(
            raw_path, filtered_path, exclusions_path, basedomains_path, items
        )
        
        assert filt == 2  # Includes google.com
        
        # With flag: filtered excludes basedomains
        builder2 = DoHListBuilder(
            output_dir=self.temp_dir,
            resolve_ips=False,
            dns_servers=[],
            exclusions=set(),
            exclusions_file=None,
            clean_output=False,
            warn_change_ratio=0.2,
            skip_ratio_check=False,
            filter_base_domains=True,
        )
        
        raw_path2 = Path(self.temp_dir) / "test2.txt"
        filtered_path2 = Path(self.temp_dir) / "test2_filtered.txt"
        exclusions_path2 = Path(self.temp_dir) / "test2_exclusions.txt"
        basedomains_path2 = Path(self.temp_dir) / "test2_basedomains.txt"
        
        raw, filt, excl, bd = builder2._write_lists(
            raw_path2, filtered_path2, exclusions_path2, basedomains_path2, items
        )
        
        assert filt == 1  # Excludes google.com


class TestCountEntries(unittest.TestCase):
    """Test entry counting."""
    
    def setUp(self):
        """Create temp directory."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_count_entries(self):
        """Test counting non-empty lines."""
        builder = DoHListBuilder(
            output_dir=self.temp_dir,
            resolve_ips=False,
            dns_servers=[],
            exclusions=set(),
            exclusions_file=None,
            clean_output=False,
            warn_change_ratio=0.2,
            skip_ratio_check=False,
            filter_base_domains=False,
        )
        
        test_file = Path(self.temp_dir) / "count_test.txt"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("line1\n")
            f.write("\n")
            f.write("line2\n")
            f.write("   \n")
            f.write("line3\n")
        
        count = builder._count_entries(test_file)
        assert count == 3  # Only non-empty lines


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
