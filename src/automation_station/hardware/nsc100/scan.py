"""Scan utilities for NSC100-based measurements.

Provides reusable scan orchestration that can be consumed by
automation-station or any other application needing coordinated
motion + measurement sequences.
"""
from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Protocol

import numpy as np

logger = logging.getLogger(__name__)


class MotionController(Protocol):
    """Protocol for any motion controller (NSC100, MockNSC100, etc.)."""
    @property
    def position(self) -> float: ...
    def move_absolute(self, position_mm: float, timeout: float = 30.0) -> None: ...
    @property
    def is_moving(self) -> bool: ...


@dataclass
class ScanConfig:
    """Configuration for a linear scan."""
    start_mm: float = 0.0
    stop_mm: float = 25.0
    step_mm: float = 0.1
    settle_time_s: float = 0.1
    averages_per_point: int = 3
    bidirectional: bool = False

    @property
    def positions(self) -> np.ndarray:
        return np.arange(self.start_mm, self.stop_mm + self.step_mm / 2, self.step_mm)

    @property
    def n_points(self) -> int:
        return len(self.positions)


@dataclass
class ScanResult:
    """Result from a completed scan."""
    positions_mm: np.ndarray
    readings: np.ndarray
    timestamps: np.ndarray = field(default_factory=lambda: np.array([]))
    config: ScanConfig | None = None
    metadata: dict = field(default_factory=dict)


def run_linear_scan(
    controller: MotionController,
    read_fn: Callable[[], float],
    config: ScanConfig,
    progress_fn: Callable[[int, int, float, float], None] | None = None,
) -> ScanResult:
    """Execute a linear scan with coordinated motion and measurement.

    Parameters
    ----------
    controller : Motion controller implementing the MotionController protocol.
    read_fn : Callable that returns a single measurement reading.
    config : Scan configuration.
    progress_fn : Optional callback(step_index, total_steps, position, reading).

    Returns
    -------
    ScanResult with positions and readings arrays.
    """
    positions = config.positions
    n = len(positions)
    readings = np.zeros(n)
    timestamps = np.zeros(n)

    logger.info("Starting scan: %d points, %.3f to %.3f mm", n, config.start_mm, config.stop_mm)

    for i, pos in enumerate(positions):
        controller.move_absolute(pos)
        time.sleep(config.settle_time_s)

        # Average readings
        raw = []
        for _ in range(config.averages_per_point):
            raw.append(read_fn())
        readings[i] = float(np.mean(raw))
        timestamps[i] = time.time()

        if progress_fn is not None:
            progress_fn(i, n, pos, readings[i])

        logger.debug("Scan point %d/%d: pos=%.4f mm, reading=%.6e", i + 1, n, pos, readings[i])

    logger.info("Scan complete: %d points acquired", n)

    return ScanResult(
        positions_mm=positions,
        readings=readings,
        timestamps=timestamps,
        config=config,
    )
