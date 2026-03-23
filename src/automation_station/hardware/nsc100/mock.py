"""Mock NSC100 for testing and simulation without hardware.

Drop-in replacement for NSC100 that simulates motion behavior.
Useful for UI development and integration testing.

Usage:
    from automation_station.hardware.nsc100.mock import MockNSC100
    stage = MockNSC100()
    stage.connect()
    stage.move_absolute(10.0)
    print(stage.position)  # 10.0
"""
from __future__ import annotations

import time
import logging
from automation_station.hardware.nsc100 import ControllerState

logger = logging.getLogger(__name__)


class MockNSC100:
    """Simulated NSC100 controller for development and testing."""

    def __init__(
        self,
        port: str = "MOCK",
        axis: int = 1,
        travel_range_mm: tuple[float, float] = (0.0, 50.0),
        velocity_mm_s: float = 5.0,
    ):
        self.port = port
        self.axis = axis
        self._travel_range = travel_range_mm
        self._position = 0.0
        self._velocity = velocity_mm_s
        self._acceleration = 10.0
        self._connected = False
        self._homed = False
        self._state = ControllerState.NOT_REFERENCED_RESET

    def connect(self) -> str:
        self._connected = True
        self._state = ControllerState.NOT_REFERENCED_READY
        logger.info("MockNSC100 connected on %s", self.port)
        return "Connected: MockNSC100 v1.0 (simulated)"

    def disconnect(self) -> None:
        self._connected = False
        logger.info("MockNSC100 disconnected")

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def state(self) -> ControllerState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._state.is_ready

    @property
    def is_moving(self) -> bool:
        return self._state.is_moving

    @property
    def position(self) -> float:
        return self._position

    @position.setter
    def position(self, value: float) -> None:
        self.move_absolute(value)

    def home(self, timeout: float = 60.0) -> None:
        if not self._connected:
            raise ConnectionError("Not connected")
        self._state = ControllerState.HOMING
        travel_time = abs(self._position) / self._velocity
        time.sleep(min(travel_time, 0.1))  # abbreviated for mock
        self._position = 0.0
        self._homed = True
        self._state = ControllerState.READY_HOMED
        logger.info("MockNSC100 homed")

    def move_absolute(self, position_mm: float, timeout: float = 30.0) -> None:
        if not self._connected:
            raise ConnectionError("Not connected")
        pos = max(self._travel_range[0], min(self._travel_range[1], position_mm))
        self._state = ControllerState.MOVING
        travel_time = abs(pos - self._position) / self._velocity
        time.sleep(min(travel_time, 0.05))  # abbreviated
        self._position = pos
        self._state = ControllerState.READY_HOMED
        logger.debug("MockNSC100 moved to %.4f mm", pos)

    def move_relative(self, displacement_mm: float, timeout: float = 30.0) -> None:
        self.move_absolute(self._position + displacement_mm, timeout)

    def stop(self) -> None:
        self._state = ControllerState.READY_HOMED

    @property
    def velocity(self) -> float:
        return self._velocity

    @velocity.setter
    def velocity(self, value: float) -> None:
        self._velocity = max(0.01, value)

    @property
    def acceleration(self) -> float:
        return self._acceleration

    @acceleration.setter
    def acceleration(self, value: float) -> None:
        self._acceleration = max(0.01, value)

    @property
    def negative_limit(self) -> float:
        return self._travel_range[0]

    @negative_limit.setter
    def negative_limit(self, value: float) -> None:
        self._travel_range = (value, self._travel_range[1])

    @property
    def positive_limit(self) -> float:
        return self._travel_range[1]

    @positive_limit.setter
    def positive_limit(self, value: float) -> None:
        self._travel_range = (self._travel_range[0], value)

    def get_error(self) -> str | None:
        return None

    def get_stage_model(self) -> str:
        return "MockStage-50mm"

    def reset(self) -> None:
        self._position = 0.0
        self._homed = False
        self._state = ControllerState.NOT_REFERENCED_RESET

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"MockNSC100(port={self.port!r}, axis={self.axis}, {status})"
