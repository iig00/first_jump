from enum import IntEnum

from .font import draw_text, text_width
from .model import Color, Device, GameState, Phase, Platform, Player, Role
from .stage import FALL_STEPS, HEIGHT, PLAYER_HEIGHT, PLAYER_WIDTH, WIDTH
from .viewport import RETRY_BUTTON


class Ink(IntEnum):
    NAVY = 0
    GRID = 1
    PANEL = 2
    BORDER = 3
    WHITE = 4
    SHADOW = 5
    RED = 6
    RED_LIGHT = 7
    RED_DIM = 8
    BLUE = 9
    BLUE_LIGHT = 10
    BLUE_DIM = 11
    YELLOW = 12
    BUTTON = 13
    BLACK = 14


PALETTE = (
    0x0B142D, 0x152348, 0x15203A, 0x526990, 0xF1F6FF,
    0xADBBD5, 0xD7405D, 0xFFA3AD, 0x854258, 0x2871CF,
    0x75DAFF, 0x385E91, 0xFFDB8C, 0x294B80, 0x080E20,
)

KEYBOARD_HINTS = ("A/D  ←/→ 移動", "Space ジャンプ", "R 再挑戦")
GAMEPAD_HINTS = ("十字キー/左スティック 移動", "A ジャンプ", "Start (CLEAR) 再挑戦")
RETRY_HINT = "R / Start 再挑戦"

_CLEAR = (
    "### #.. ### .#. ##.",
    "#.. #.. #.. #.# #.#",
    "#.. #.. ##. ### ##.",
    "#.. #.. #.. #.# #.#",
    "### ### ### #.# #.#",
)


class Renderer:
    def __init__(self, screen) -> None:
        self._screen = screen

    def draw(self, state: GameState, platforms: tuple[Platform, ...], device: Device) -> None:
        screen = self._screen
        screen.cls(Ink.NAVY)
        for x in range(0, WIDTH, 16):
            screen.line(x, 0, x, HEIGHT - 1, Ink.GRID)
        for y in range(0, HEIGHT, 16):
            screen.line(0, y, WIDTH - 1, y, Ink.GRID)

        for platform in platforms:
            self._platform(platform, platform.is_enabled(state.active_color))
        for platform in platforms:
            if platform.role is Role.GOAL:
                self._flag(platform)
        self._robot(state.player)
        if state.phase is Phase.FALLING:
            screen.dither(min(0.85, (state.fall_steps + 1) / FALL_STEPS))
            screen.rect(0, 0, WIDTH, HEIGHT, Ink.BLACK)
            screen.dither(1.0)
        self._hud(state, device)
        if state.phase is Phase.CLEAR:
            self._clear()

    def _platform(self, platform: Platform, enabled: bool) -> None:
        screen = self._screen
        x, y, w, h = platform.x, platform.y, platform.width, platform.height
        if platform.color is Color.ALWAYS:
            screen.rect(x, y, w, h, Ink.WHITE)
            screen.rect(x, y + h - 2, w, 2, Ink.SHADOW)
            return
        self._color_tile(x, y, w, h, platform.color, enabled)

    def _color_tile(self, x: int, y: int, w: int, h: int, color: Color, enabled: bool) -> None:
        screen = self._screen
        red = color is Color.RED
        base, accent, dim = (
            (Ink.RED, Ink.RED_LIGHT, Ink.RED_DIM) if red else (Ink.BLUE, Ink.BLUE_LIGHT, Ink.BLUE_DIM)
        )
        if enabled:
            screen.rect(x, y, w, h, base)
        else:
            screen.rectb(x, y, w, h, dim)
        self._pattern(x + 1, y + 1, w - 2, h - 2, red, accent if enabled else dim, enabled)

    def _pattern(self, x: int, y: int, w: int, h: int, red: bool, ink: Ink, enabled: bool) -> None:
        screen = self._screen
        if red:
            stride = 5 if enabled else 9
            for start in range(1 - h, w, stride):
                first = max(start, 0)
                last = min(start + h - 1, w - 1)
                screen.line(
                    x + first, y + h - 1 - (first - start),
                    x + last, y + h - 1 - (last - start), ink,
                )
        else:
            stride = 4 if enabled else 7
            for row in range(1, h, 3):
                for col in range(1 + (row // 3) % 2, w, stride):
                    screen.pset(x + col, y + row, ink)

    def _flag(self, goal: Platform) -> None:
        screen = self._screen
        x, y = goal.right - 17, goal.y
        screen.rect(x - 2, y - 2, 6, 2, Ink.SHADOW)
        screen.line(x, y - 20, x, y - 1, Ink.WHITE)
        screen.rect(x - 1, y - 22, 3, 3, Ink.YELLOW)
        screen.tri(x + 1, y - 19, x + 1, y - 9, x + 13, y - 14, Ink.RED_LIGHT)
        screen.line(x + 1, y - 19, x + 13, y - 14, Ink.RED)

    def _robot(self, player: Player) -> None:
        screen = self._screen
        x, y = round(player.x), round(player.y)
        screen.line(x + 5, y + 1, x + 5, y + 3, Ink.SHADOW)
        screen.rect(x + 4, y, 3, 2, Ink.BLUE_LIGHT)
        screen.rect(x + 1, y + 3, 10, 7, Ink.WHITE)
        screen.rect(x, y + 5, 1, 3, Ink.SHADOW)
        screen.rect(x + 11, y + 5, 1, 3, Ink.SHADOW)
        screen.rect(x + 2, y + 4, 8, 4, Ink.NAVY)
        screen.line(x + 4, y + 5, x + 4, y + 6, Ink.BLUE_LIGHT)
        screen.line(x + 7, y + 5, x + 7, y + 6, Ink.BLUE_LIGHT)
        screen.rect(x + 2, y + 10, 8, 4, Ink.WHITE)
        screen.rect(x + 5, y + 11, 2, 2, Ink.BLUE)
        screen.rect(x + 2, y + 14, 3, 2, Ink.SHADOW)
        screen.rect(x + 7, y + 14, 3, 2, Ink.SHADOW)

    def _hud(self, state: GameState, device: Device) -> None:
        screen = self._screen
        label = "赤が有効" if state.active_color is Color.RED else "青が有効"
        screen.rect(12, 3, 74, 18, Ink.PANEL)
        screen.rectb(12, 3, 74, 18, Ink.BORDER)
        self._color_tile(18, 7, 12, 10, state.active_color, True)
        draw_text(screen, 35, 5, label, Ink.WHITE)

        x, y, w, h = 486, 316, 150, 42
        player = state.player
        # Two panel positions leave the bottom platforms and the robot visible.
        if (
            player.x < x + w and player.x + PLAYER_WIDTH > x
            and player.y < y + h and player.y + PLAYER_HEIGHT > y
        ):
            x = 324
        screen.rect(x, y, w, h, Ink.PANEL)
        screen.rectb(x, y, w, h, Ink.BORDER)
        hints = GAMEPAD_HINTS if device is Device.GAMEPAD else KEYBOARD_HINTS
        for row, hint in enumerate(hints):
            draw_text(screen, x + 5, y + 2 + 13 * row, hint, Ink.WHITE)

    def _clear(self) -> None:
        screen = self._screen
        screen.dither(0.55)
        screen.rect(0, 24, WIDTH, 292, Ink.BLACK)
        screen.dither(1.0)
        screen.rect(235, 130, 170, 100, Ink.PANEL)
        screen.rectb(235, 130, 170, 100, Ink.BORDER)
        scale = 4
        origin = (WIDTH - len(_CLEAR[0]) * scale) // 2
        for row, pixels in enumerate(_CLEAR):
            for col, pixel in enumerate(pixels):
                if pixel == "#":
                    screen.rect(origin + col * scale, 145 + row * scale, scale, scale, Ink.WHITE)

        button = RETRY_BUTTON
        screen.rect(button.x, button.y, button.width, button.height, Ink.BUTTON)
        screen.rectb(button.x, button.y, button.width, button.height, Ink.BLUE_LIGHT)
        label = "もう一度"
        draw_text(screen, (WIDTH - text_width(label)) // 2, button.y + 8, label, Ink.WHITE)
        draw_text(screen, (WIDTH - text_width(RETRY_HINT)) // 2, 210, RETRY_HINT, Ink.SHADOW)
