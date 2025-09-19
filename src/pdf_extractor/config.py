"""
Configuration Management for PDF Structure Extractor

This module handles loading and managing configuration from YAML files,
with support for precedence rules and default values.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field


@dataclass
class ExtractorConfig:
    """Configuration class for PDF extraction settings."""
    
    # Extraction modes
    mode: str = "standard"  # standard, detailed, fast
    
    # Output settings
    format: str = "hierarchical"  # hierarchical, flat, raw
    preserve_layout: bool = False
    validate_schema: bool = True
    
    # Feature flags
    extract_tables: Optional[bool] = None  # None means use mode default
    extract_images: Optional[bool] = None  # None means use mode default
    
    # File handling
    output_path: Optional[str] = None
    password: Optional[str] = None
    
    # Processing settings
    verbose: bool = False
    
    # Advanced settings (for config file)
    table_extraction_method: str = "pymupdf"  # pymupdf, camelot
    image_extraction_threshold: float = 0.5
    text_cleaning_level: str = "standard"  # minimal, standard, aggressive
    
    # Performance settings
    max_memory_mb: int = 512
    parallel_processing: bool = False
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        valid_modes = {"standard", "detailed", "fast"}
        if self.mode not in valid_modes:
            raise ValueError(f"Invalid mode '{self.mode}'. Must be one of: {valid_modes}")
        
        valid_formats = {"hierarchical", "flat", "raw"}
        if self.format not in valid_formats:
            raise ValueError(f"Invalid format '{self.format}'. Must be one of: {valid_formats}")
        
        valid_extraction_methods = {"pymupdf", "camelot"}
        if self.table_extraction_method not in valid_extraction_methods:
            raise ValueError(f"Invalid table extraction method '{self.table_extraction_method}'. Must be one of: {valid_extraction_methods}")
        
        valid_cleaning_levels = {"minimal", "standard", "aggressive"}
        if self.text_cleaning_level not in valid_cleaning_levels:
            raise ValueError(f"Invalid text cleaning level '{self.text_cleaning_level}'. Must be one of: {valid_cleaning_levels}")
    
    def get_effective_table_extraction(self) -> bool:
        """Get effective table extraction setting based on mode and explicit setting."""
        if self.extract_tables is not None:
            return self.extract_tables
        
        # Mode defaults
        mode_defaults = {
            "fast": False,
            "standard": True,
            "detailed": True
        }
        return mode_defaults.get(self.mode, True)
    
    def get_effective_image_extraction(self) -> bool:
        """Get effective image extraction setting based on mode and explicit setting."""
        if self.extract_images is not None:
            return self.extract_images
        
        # Mode defaults
        mode_defaults = {
            "fast": False,
            "standard": False,
            "detailed": True
        }
        return mode_defaults.get(self.mode, False)
    
    def get_effective_layout_preservation(self) -> bool:
        """Get effective layout preservation setting based on mode and explicit setting."""
        # In detailed mode, force layout preservation unless explicitly disabled
        if self.mode == "detailed":
            return True
        return self.preserve_layout


class ConfigManager:
    """Manages configuration loading and precedence rules."""
    
    DEFAULT_CONFIG_FILENAME = "config.yaml"
    
    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "mode": "standard",
            "format": "hierarchical",
            "preserve_layout": False,
            "validate_schema": True,
            "extract_tables": None,
            "extract_images": None,
            "output_path": None,
            "password": None,
            "verbose": False,
            "table_extraction_method": "pymupdf",
            "image_extraction_threshold": 0.5,
            "text_cleaning_level": "standard",
            "max_memory_mb": 512,
            "parallel_processing": False
        }
    
    @staticmethod
    def load_yaml_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Load configuration from a YAML file.
        
        Args:
            config_path: Path to configuration file. If None, looks for default config file.
            
        Returns:
            Dictionary with configuration values, empty if file doesn't exist.
        """
        if config_path is None:
            config_path = Path(ConfigManager.DEFAULT_CONFIG_FILENAME)
        
        if not config_path.exists():
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                return config_data if config_data is not None else {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file '{config_path}': {e}")
        except Exception as e:
            raise ValueError(f"Error reading configuration file '{config_path}': {e}")
    
    @staticmethod
    def merge_configs(defaults: Dict[str, Any], 
                     file_config: Dict[str, Any], 
                     cli_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge configurations with precedence: CLI args > file config > defaults.
        
        Args:
            defaults: Default configuration values
            file_config: Configuration loaded from YAML file
            cli_args: Configuration from command-line arguments
            
        Returns:
            Merged configuration dictionary
        """
        # Start with defaults
        merged = defaults.copy()
        
        # Override with file config (skip None values)
        for key, value in file_config.items():
            if value is not None:
                merged[key] = value
        
        # Override with CLI args (skip None values) 
        for key, value in cli_args.items():
            if value is not None:
                merged[key] = value
        
        return merged
    
    @staticmethod
    def create_extractor_config(config_path: Optional[Path] = None,
                              cli_overrides: Optional[Dict[str, Any]] = None) -> ExtractorConfig:
        """
        Create an ExtractorConfig object with proper precedence handling.
        
        Args:
            config_path: Path to YAML configuration file
            cli_overrides: Dictionary of CLI argument overrides
            
        Returns:
            ExtractorConfig object with merged settings
        """
        if cli_overrides is None:
            cli_overrides = {}
        
        # Load configurations in order of precedence
        defaults = ConfigManager.get_default_config()
        file_config = ConfigManager.load_yaml_config(config_path)
        
        # Merge all configurations
        merged_config = ConfigManager.merge_configs(defaults, file_config, cli_overrides)
        
        # Create and return ExtractorConfig object
        return ExtractorConfig(**merged_config)
    
    @staticmethod
    def save_example_config(path: Path):
        """Save an example configuration file."""
        example_config = {
            "mode": "standard",
            "format": "hierarchical",
            "preserve_layout": False,
            "validate_schema": True,
            "extract_tables": True,
            "extract_images": False,
            "verbose": False,
            "table_extraction_method": "pymupdf",  # or "camelot"
            "image_extraction_threshold": 0.5,
            "text_cleaning_level": "standard",  # minimal, standard, aggressive
            "max_memory_mb": 512,
            "parallel_processing": False
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# PDF Extractor Configuration File\n")
            f.write("# See documentation for detailed explanation of options\n\n")
            f.write("# Extraction modes: standard, detailed, fast\n")
            f.write("mode: standard\n\n")
            f.write("# Output formats: hierarchical, flat, raw\n")
            f.write("format: hierarchical\n\n")
            f.write("# Feature flags\n")
            yaml.dump({k: v for k, v in example_config.items() 
                      if k in ["preserve_layout", "validate_schema", "extract_tables", "extract_images"]}, 
                     f, default_flow_style=False, indent=2)
            f.write("\n# Processing settings\n")
            yaml.dump({k: v for k, v in example_config.items() 
                      if k in ["verbose"]}, 
                     f, default_flow_style=False, indent=2)
            f.write("\n# Advanced settings\n")
            yaml.dump({k: v for k, v in example_config.items() 
                      if k in ["table_extraction_method", "image_extraction_threshold", "text_cleaning_level"]}, 
                     f, default_flow_style=False, indent=2)
            f.write("\n# Performance settings\n")
            yaml.dump({k: v for k, v in example_config.items() 
                      if k in ["max_memory_mb", "parallel_processing"]}, 
                     f, default_flow_style=False, indent=2)


def load_config_for_cli(config_path: Optional[Path] = None, **cli_kwargs) -> ExtractorConfig:
    """
    Convenience function for CLI to load configuration with overrides.
    
    Args:
        config_path: Path to configuration file
        **cli_kwargs: CLI arguments as keyword arguments
        
    Returns:
        ExtractorConfig object with merged settings
    """
    # Remove None values from CLI kwargs
    cli_overrides = {k: v for k, v in cli_kwargs.items() if v is not None}
    
    return ConfigManager.create_extractor_config(config_path, cli_overrides)


if __name__ == "__main__":
    # Example usage and testing
    print("Creating example configuration...")
    
    # Create example config file
    example_path = Path("config.example.yaml")
    ConfigManager.save_example_config(example_path)
    print(f"Example configuration saved to: {example_path}")
    
    # Test loading
    config = ConfigManager.create_extractor_config()
    print(f"Default config: {config}")
    
    # Test with CLI overrides
    cli_config = load_config_for_cli(
        mode="detailed",
        format="flat",
        verbose=True
    )
    print(f"CLI override config: {cli_config}")