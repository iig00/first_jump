from dataclasses import dataclass, field
from enum import Enum, auto


class Color(Enum):
    RED = auto()
    BLUE = auto()
    ALWAYS = auto()


class Role(Enum):
    START = auto()
    REST = auto()
    GOAL = auto()


class Phase(Enum):
    PLAYING = auto()
    FALLING = auto()
    CLEAR = auto()


class Device(Enum):
    KEYBOARD = auto()
    GAMEPAD = auto()


@dataclass(frozen=True)
class Platform:
    id: str
    x: int
    y: int
    width: int
    height: int
    color: Color
    role: Role | None = None

    @property
    def right(self) -> int:
        return self.x + self.width

    def is_enabled(self, active_color: Color) -> bool:
        return self.color in (Color.ALWAYS, active_color)


@dataclass
class Player:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    ground_id: str | None = None


@dataclass
class GameState:
    player: Player
    phase: Phase = Phase.PLAYING
    active_color: Color = Color.RED
    fall_steps: int = 0
    excluded: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class InputFrame:
    left: bool = False
    right: bool = False
    jump_pressed: bool = False
    reset_pressed: bool = False
    start_pressed: bool = False
    click: tuple[float, float] | None = None
