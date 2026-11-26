from .game import Game
from .input import InputAdapter, Key, RawInput, XInput
from .render import PALETTE, Renderer
from .stage import FPS, HEIGHT, WIDTH
from .viewport import RETRY_BUTTON
from .windows import WindowsWindow, enable_dpi_awareness

TITLE = "First Jump"


class Application:
    def __init__(self, pyxel, window: WindowsWindow, gamepad: XInput) -> None:
        self.pyxel = pyxel
        self.window = window
        self.gamepad = gamepad
        self.game = Game()
        self.input = InputAdapter()
        self.renderer = Renderer(pyxel)
        self._key_codes = {key: getattr(pyxel, f"KEY_{key.name}") for key in Key}

    def read_input(self) -> RawInput:
        return RawInput(
            keys=frozenset(key for key, code in self._key_codes.items() if self.pyxel.btn(code)),
            pad=self.gamepad.read(),
            click=self.window.take_click(),
        )

    def update(self) -> None:
        raw = self.read_input()
        frame = self.input.update(raw)
        reset = self.game.update(frame, retry_clicked=RETRY_BUTTON.contains(frame.click))
        if reset:
            self.input.sync(raw)

    def draw(self) -> None:
        self.renderer.draw(self.game.state, self.game.platforms, self.input.device)


def open_window(pyxel) -> WindowsWindow:
    enable_dpi_awareness()
    pyxel.init(
        WIDTH, HEIGHT, title=TITLE, fps=FPS, quit_key=pyxel.KEY_NONE,
        display_scale=1, capture_sec=0,
    )
    pyxel.fullscreen(False)
    pyxel.integer_scale(False)
    pyxel.mouse(True)
    for index, color in enumerate(PALETTE):
        pyxel.colors[index] = color
    return WindowsWindow(TITLE)


def run() -> None:
    import pyxel

    window = open_window(pyxel)
    try:
        app = Application(pyxel, window, XInput())
        pyxel.run(app.update, app.draw)
    finally:
        window.close()
