#!/usr/bin/env python3
"""
Test script for configuration precedence and YAML loading.

This script validates that the configuration system correctly handles
precedence between defaults, YAML files, and CLI arguments.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pdf_extractor.config import ConfigManager, ExtractorConfig, load_config_for_cli


def test_default_config():
    """Test default configuration loading."""
    print("=== Testing Default Configuration ===")
    
    config = ConfigManager.create_extractor_config()
    
    assert config.mode == "standard"
    assert config.format == "hierarchical"
    assert config.verbose == False
    assert config.extract_tables is None
    assert config.get_effective_table_extraction() == True  # standard mode default
    
    print("✓ Default configuration loaded correctly")
    print(f"  Mode: {config.mode}")
    print(f"  Format: {config.format}")
    print(f"  Effective table extraction: {config.get_effective_table_extraction()}")
    print()


def test_yaml_config():
    """Test YAML configuration loading."""
    print("=== Testing YAML Configuration Loading ===")
    
    # Create a temporary YAML config file
    yaml_content = """
mode: detailed
format: flat
verbose: true
extract_tables: false
extract_images: true
table_extraction_method: camelot
max_memory_mb: 1024
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_path = Path(f.name)
    
    try:
        config = ConfigManager.create_extractor_config(config_path=temp_path)
        
        assert config.mode == "detailed"
        assert config.format == "flat"
        assert config.verbose == True
        assert config.extract_tables == False
        assert config.extract_images == True
        assert config.table_extraction_method == "camelot"
        assert config.max_memory_mb == 1024
        
        print("✓ YAML configuration loaded correctly")
        print(f"  Mode: {config.mode}")
        print(f"  Format: {config.format}")
        print(f"  Table extraction method: {config.table_extraction_method}")
        print(f"  Max memory: {config.max_memory_mb} MB")
        print()
        
    finally:
        temp_path.unlink()  # Clean up temp file


def test_precedence():
    """Test configuration precedence (CLI > YAML > defaults)."""
    print("=== Testing Configuration Precedence ===")
    
    # Create a YAML config with some settings
    yaml_content = """
mode: detailed
format: flat
verbose: false
extract_tables: true
max_memory_mb: 1024
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_path = Path(f.name)
    
    try:
        # CLI arguments should override YAML settings
        cli_overrides = {
            "mode": "fast",           # Override YAML "detailed"
            "verbose": True,          # Override YAML "false"
            "extract_images": True,   # Not in YAML, should be added
            # format and extract_tables not specified, should use YAML values
            # max_memory_mb not specified, should use YAML value
        }
        
        config = ConfigManager.create_extractor_config(
            config_path=temp_path,
            cli_overrides=cli_overrides
        )
        
        # Check CLI overrides took precedence
        assert config.mode == "fast"          # CLI override
        assert config.verbose == True         # CLI override
        assert config.extract_images == True  # CLI only
        
        # Check YAML values were preserved where CLI didn't override
        assert config.format == "flat"        # From YAML
        assert config.extract_tables == True  # From YAML
        assert config.max_memory_mb == 1024   # From YAML
        
        print("✓ Configuration precedence working correctly")
        print(f"  Mode: {config.mode} (CLI override)")
        print(f"  Format: {config.format} (from YAML)")
        print(f"  Verbose: {config.verbose} (CLI override)")
        print(f"  Extract tables: {config.extract_tables} (from YAML)")
        print(f"  Extract images: {config.extract_images} (CLI only)")
        print(f"  Max memory: {config.max_memory_mb} MB (from YAML)")
        print()
        
    finally:
        temp_path.unlink()


def test_cli_convenience_function():
    """Test the convenience function for CLI usage."""
    print("=== Testing CLI Convenience Function ===")
    
    # Test the load_config_for_cli function
    config = load_config_for_cli(
        mode="detailed",
        format="hierarchical",
        verbose=True,
        extract_tables=False,
        password="secret123"
    )
    
    assert config.mode == "detailed"
    assert config.format == "hierarchical"
    assert config.verbose == True
    assert config.extract_tables == False
    assert config.password == "secret123"
    
    print("✓ CLI convenience function working correctly")
    print(f"  Mode: {config.mode}")
    print(f"  Password set: {'Yes' if config.password else 'No'}")
    print()


def test_mode_defaults():
    """Test that different modes have correct default behaviors."""
    print("=== Testing Mode-Based Defaults ===")
    
    modes_to_test = ["fast", "standard", "detailed"]
    
    for mode in modes_to_test:
        config = load_config_for_cli(mode=mode)
        
        print(f"Mode: {mode}")
        print(f"  Table extraction: {config.get_effective_table_extraction()}")
        print(f"  Image extraction: {config.get_effective_image_extraction()}")
        print(f"  Layout preservation: {config.get_effective_layout_preservation()}")
        
        # Validate expected defaults
        if mode == "fast":
            assert config.get_effective_table_extraction() == False
            assert config.get_effective_image_extraction() == False
        elif mode == "detailed":
            assert config.get_effective_table_extraction() == True
            assert config.get_effective_image_extraction() == True
            assert config.get_effective_layout_preservation() == True
        else:  # standard
            assert config.get_effective_table_extraction() == True
            assert config.get_effective_image_extraction() == False
    
    print("✓ All mode defaults are correct")
    print()


def test_invalid_config():
    """Test handling of invalid configuration values."""
    print("=== Testing Invalid Configuration Handling ===")
    
    try:
        # This should raise a ValueError
        ExtractorConfig(mode="invalid_mode")
        assert False, "Should have raised ValueError for invalid mode"
    except ValueError as e:
        print(f"✓ Invalid mode correctly rejected: {e}")
    
    try:
        # This should raise a ValueError
        ExtractorConfig(format="invalid_format")
        assert False, "Should have raised ValueError for invalid format"
    except ValueError as e:
        print(f"✓ Invalid format correctly rejected: {e}")
    
    print()


def main():
    """Run all configuration tests."""
    print("🔧 Testing Configuration Management System\n")
    
    # Test 1: Default configuration
    test_default_config()
    
    # Test 2: YAML loading
    test_yaml_config()
    
    # Test 3: Precedence rules
    test_precedence()
    
    # Test 4: CLI convenience function
    test_cli_convenience_function()
    
    # Test 5: Mode defaults
    test_mode_defaults()
    
    # Test 6: Invalid configuration
    test_invalid_config()
    
    print("=== Test Summary ===")
    print("✓ Default configuration loading")
    print("✓ YAML configuration file parsing")
    print("✓ Configuration precedence (CLI > YAML > defaults)")
    print("✓ CLI convenience functions")
    print("✓ Mode-based default behaviors")
    print("✓ Invalid configuration rejection")
    print("\nConfiguration management testing completed!")


if __name__ == "__main__":
    main()