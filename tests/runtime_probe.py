"""Manual Windows runtime probe. Invoke with uv run python tests/runtime_probe.py."""

import pyxel

from first_jump.app import Application, open_window
from first_jump.input import RawInput, XInput
from first_jump.render import Ink
from first_jump.viewport import Viewport


class RuntimeProbe(Application):
    raw = RawInput()
    last_click = None

    def read_input(self):
        self.raw = super().read_input()
        if self.raw.click is not None:
            self.last_click = tuple(round(value, 1) for value in self.raw.click)
        elif pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.last_click = "outside"
        return self.raw

    def draw(self):
        super().draw()
        width, height = self.window.client_size()
        viewport = Viewport.fit(width, height)
        keys = " ".join(key.name for key in sorted(self.raw.keys, key=lambda key: key.name))
        pad = self.raw.pad
        if pad is None:
            pad_status = "XInput: disconnected"
        else:
            pad_status = (
                f"XInput {pad.slot}: X={pad.stick_x:+.2f} "
                f"L/R={int(pad.left)}/{int(pad.right)} A={int(pad.south)} Start={int(pad.start)}"
            )
        lines = (
            f"Client: {width}x{height}    Scale: {viewport.scale:.3f}",
            f"Bars: left={viewport.left:.1f} top={viewport.top:.1f}",
            f"Keys: {keys}",
            pad_status,
            f"Logical click: {self.last_click}   Pyxel mouse: {pyxel.mouse_x}, {pyxel.mouse_y}",
        )
        pyxel.rect(409, 10, 224, 45, Ink.PANEL)
        for row, line in enumerate(lines):
            pyxel.text(414, 14 + 8 * row, line, Ink.WHITE)


if __name__ == "__main__":
    window = open_window(pyxel)
    try:
        app = RuntimeProbe(pyxel, window, XInput())
        pyxel.run(app.update, app.draw)
    finally:
        window.close()
