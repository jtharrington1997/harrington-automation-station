"""Configuration management for Automation Station.

Same architecture as pax_americana.io.config — environment variables
take precedence, then JSON config file, then defaults.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("data/manual/config.json")


@dataclass(frozen=True)
class HardwareProfile:
    """A saved hardware device configuration."""
    name: str
    device_type: str  # "smc100", "kdc101", "ophir", "custom"
    port: str  # COM port or USB path
    baud_rate: int = 921600
    enabled: bool = True


@dataclass(frozen=True)
class AppConfig:
    """Application configuration with hardware, API keys, and preferences."""
    # Hardware
    hardware_profiles: list[HardwareProfile] = field(default_factory=list)
    auto_detect_hardware: bool = True
    scan_timeout_s: float = 30.0

    # API keys
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    # Paths
    cache_dir: Path = field(default_factory=lambda: Path("data/cache"))
    results_dir: Path = field(default_factory=lambda: Path("data/results"))

    # Analysis defaults
    default_wavelength_nm: float = 1064.0
    default_step_size_um: float = 5.0
    fit_method: str = "least_squares"  # "least_squares" or "curve_fit"


def load_config() -> AppConfig:
    """Load config from environment + JSON file."""
    anthropic_api_key = os.getenv("HW_ANTHROPIC_API_KEY")
    openai_api_key = os.getenv("HW_OPENAI_API_KEY")
    auto_detect = os.getenv("HW_AUTO_DETECT", "true").lower() == "true"

    hardware_profiles: list[HardwareProfile] = []
    data: dict = {}

    if DEFAULT_CONFIG_PATH.exists():
        data = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))

        for hp in data.get("hardware_profiles", []):
            if isinstance(hp, dict) and hp.get("port"):
                hardware_profiles.append(HardwareProfile(
                    name=hp.get("name", "Unnamed"),
                    device_type=hp.get("device_type", "custom"),
                    port=hp["port"],
                    baud_rate=hp.get("baud_rate", 921600),
                    enabled=hp.get("enabled", True),
                ))

        anthropic_api_key = anthropic_api_key or data.get("anthropic_api_key")
        openai_api_key = openai_api_key or data.get("openai_api_key")
        auto_detect = data.get("auto_detect_hardware", auto_detect)

    cache_dir = Path(data.get("cache_dir", "data/cache"))
    results_dir = Path(data.get("results_dir", "data/results"))
    if not cache_dir.is_absolute():
        cache_dir = cache_dir.resolve()
    if not results_dir.is_absolute():
        results_dir = results_dir.resolve()

    return AppConfig(
        hardware_profiles=hardware_profiles,
        auto_detect_hardware=auto_detect,
        scan_timeout_s=float(data.get("scan_timeout_s", 30.0)),
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        cache_dir=cache_dir,
        results_dir=results_dir,
        default_wavelength_nm=float(data.get("default_wavelength_nm", 1064.0)),
        default_step_size_um=float(data.get("default_step_size_um", 5.0)),
        fit_method=data.get("fit_method", "least_squares"),
    )


def save_config(cfg: AppConfig):
    """Persist config to JSON."""
    DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "hardware_profiles": [
            {
                "name": hp.name,
                "device_type": hp.device_type,
                "port": hp.port,
                "baud_rate": hp.baud_rate,
                "enabled": hp.enabled,
            }
            for hp in cfg.hardware_profiles
        ],
        "auto_detect_hardware": cfg.auto_detect_hardware,
        "scan_timeout_s": cfg.scan_timeout_s,
        "anthropic_api_key": cfg.anthropic_api_key,
        "openai_api_key": cfg.openai_api_key,
        "cache_dir": str(cfg.cache_dir),
        "results_dir": str(cfg.results_dir),
        "default_wavelength_nm": cfg.default_wavelength_nm,
        "default_step_size_um": cfg.default_step_size_um,
        "fit_method": cfg.fit_method,
    }
    DEFAULT_CONFIG_PATH.write_text(json.dumps(data, indent=2))
