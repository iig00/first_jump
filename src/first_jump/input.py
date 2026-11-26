import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum, auto

from .model import Device, InputFrame


class Key(Enum):
    A = auto()
    D = auto()
    LEFT = auto()
    RIGHT = auto()
    SPACE = auto()
    R = auto()


_LEFT_KEYS = frozenset({Key.A, Key.LEFT})
_RIGHT_KEYS = frozenset({Key.D, Key.RIGHT})


@dataclass(frozen=True)
class PadState:
    slot: int
    stick_x: float = 0.0
    left: bool = False
    right: bool = False
    south: bool = False
    start: bool = False


@dataclass(frozen=True)
class RawInput:
    keys: frozenset[Key] = frozenset()
    pad: PadState | None = None
    click: tuple[float, float] | None = None


class InputAdapter:
    def __init__(self) -> None:
        self.device = Device.KEYBOARD
        self._previous = RawInput()
        self._stick = 0

    def update(self, raw: RawInput) -> InputFrame:
        previous = self._previous
        pad = raw.pad
        old_pad = previous.pad
        same_pad = pad is not None and old_pad is not None and pad.slot == old_pad.slot
        old_stick = self._stick if same_pad else 0
        self._stick = _stick_direction(pad.stick_x, old_stick) if pad else 0
        self._previous = raw

        pressed_keys = raw.keys - previous.keys
        keyboard_left = bool(raw.keys & _LEFT_KEYS)
        keyboard_right = bool(raw.keys & _RIGHT_KEYS)
        keyboard_direction = keyboard_right - keyboard_left
        old_direction = bool(previous.keys & _RIGHT_KEYS) - bool(previous.keys & _LEFT_KEYS)
        # A newly connected pad can move immediately. Its held action buttons
        # need a fresh press before they can jump or restart.
        south_pressed = same_pad and pad.south and not old_pad.south
        start_pressed = same_pad and pad.start and not old_pad.start
        pad_used = (
            south_pressed
            or start_pressed
            or (self._stick != 0 and self._stick != old_stick)
            or (pad is not None and pad.left and not (same_pad and old_pad.left))
            or (pad is not None and pad.right and not (same_pad and old_pad.right))
        )

        if pressed_keys or (keyboard_direction != 0 and keyboard_direction != old_direction):
            self.device = Device.KEYBOARD
        elif pad_used:
            self.device = Device.GAMEPAD

        jump_was_held = Key.SPACE in previous.keys or bool(old_pad and old_pad.south)
        return InputFrame(
            left=keyboard_left or self._stick < 0 or bool(pad and pad.left),
            right=keyboard_right or self._stick > 0 or bool(pad and pad.right),
            jump_pressed=not jump_was_held and (Key.SPACE in pressed_keys or south_pressed),
            reset_pressed=Key.R in pressed_keys,
            start_pressed=start_pressed,
            click=raw.click,
        )

    def sync(self, raw: RawInput) -> None:
        """Use the current hold states as the baseline after a reset."""
        previous_pad = self._previous.pad
        if raw.pad is None or previous_pad is None or raw.pad.slot != previous_pad.slot:
            self._stick = 0
        if raw.pad is not None:
            self._stick = _stick_direction(raw.pad.stick_x, self._stick)
        self._previous = raw


def _stick_direction(axis: float, previous: int) -> int:
    if axis >= 0.25:
        return 1
    if axis <= -0.25:
        return -1
    return previous if axis * previous > 0.20 else 0


class _XInputGamepad(ctypes.Structure):
    _fields_ = [
        ("buttons", wintypes.WORD),
        ("left_trigger", ctypes.c_ubyte),
        ("right_trigger", ctypes.c_ubyte),
        ("left_x", ctypes.c_int16),
        ("left_y", ctypes.c_int16),
        ("right_x", ctypes.c_int16),
        ("right_y", ctypes.c_int16),
    ]


class _XInputState(ctypes.Structure):
    _fields_ = [("packet", wintypes.DWORD), ("gamepad", _XInputGamepad)]


class XInput:
    def __init__(self) -> None:
        # Pyxel exposes pad button values but provides no connection query.
        # XInput distinguishes an idle connected pad from a disconnected one.
        self._library = ctypes.WinDLL("xinput1_4.dll", winmode=0x800)  # System32
        self._get_state = self._library.XInputGetState
        self._get_state.argtypes = [wintypes.DWORD, ctypes.POINTER(_XInputState)]
        self._get_state.restype = wintypes.DWORD

    def read(self) -> PadState | None:
        state = _XInputState()
        for slot in range(4):
            if self._get_state(slot, ctypes.byref(state)) == 0:
                pad = state.gamepad
                return PadState(
                    slot=slot,
                    stick_x=pad.left_x / (32768 if pad.left_x < 0 else 32767),
                    left=bool(pad.buttons & 0x0004),
                    right=bool(pad.buttons & 0x0008),
                    south=bool(pad.buttons & 0x1000),
                    start=bool(pad.buttons & 0x0010),
                )
        return None
