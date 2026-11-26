import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from first_jump.app import TITLE, Application, open_window
from first_jump.input import Key, PadState
from first_jump.model import Color, Device, Phase, Player
from first_jump.stage import FALL_STEPS
from first_jump.viewport import RETRY_BUTTON, Viewport


class ViewportTest(unittest.TestCase):
    def test_startup_scale_and_half_open_boundaries(self):
        viewport = Viewport.fit(960, 540)
        self.assertEqual(viewport, Viewport(1.5, 0, 0))
        self.assertEqual(viewport.to_logical((480, 270)), (320, 180))
        self.assertEqual(viewport.to_logical((0, 0)), (0, 0))
        self.assertIsNone(viewport.to_logical((960, 270)))
        self.assertIsNone(viewport.to_logical((480, 540)))

    def test_letterbox_clicks_and_retry_position_in_both_aspect_ratios(self):
        tall = Viewport.fit(960, 800)
        wide = Viewport.fit(1200, 540)
        for viewport, button, margins in (
            (tall, (480, 400), ((480, 129), (480, 670))),
            (wide, (600, 270), ((119, 270), (1080, 270))),
        ):
            with self.subTest(viewport=viewport):
                self.assertTrue(RETRY_BUTTON.contains(viewport.to_logical(button)))
                for margin in margins:
                    self.assertIsNone(viewport.to_logical(margin))

    def test_fractional_offsets_and_minimized_viewport(self):
        viewport = Viewport.fit(1001, 540)
        self.assertEqual(viewport.left, 20.5)
        self.assertIsNone(viewport.to_logical((20, 0)))
        self.assertAlmostEqual(viewport.to_logical((21, 0))[0], 1 / 3)
        self.assertIsNone(Viewport.fit(0, 0).to_logical((0, 0)))


class ApplicationTest(unittest.TestCase):
    def setUp(self):
        self.held = set()
        self.pyxel = SimpleNamespace(
            btn=self.held.__contains__,
            **{f"KEY_{key.name}": key for key in Key},
        )
        self.window = Mock()
        self.window.take_click.return_value = None
        self.gamepad = Mock()
        self.gamepad.read.return_value = None
        self.app = Application(self.pyxel, self.window, self.gamepad)

    @property
    def state(self):
        return self.app.game.state

    def test_held_space_cannot_jump_again_after_landing(self):
        self.held.add(Key.SPACE)
        for _ in range(65):
            self.app.update()
        self.assertEqual(self.state.player.ground_id, "P02")
        self.assertIs(self.state.active_color, Color.BLUE)
        self.held.clear()
        self.app.update()
        self.held.add(Key.SPACE)
        self.app.update()
        self.assertIsNone(self.state.player.ground_id)
        self.assertIs(self.state.active_color, Color.RED)

    def test_pad_motion_and_jump_use_the_same_game_update(self):
        self.gamepad.read.return_value = PadState(0)
        self.app.update()
        self.held.add(Key.A)
        self.gamepad.read.return_value = PadState(0, right=True)
        self.app.update()
        self.assertEqual(self.state.player.x, 68)
        self.assertIs(self.app.input.device, Device.KEYBOARD)
        self.held.clear()
        self.gamepad.read.return_value = PadState(0, right=True, south=True)
        self.app.update()
        self.assertEqual(self.state.player.x, 70)
        self.assertIsNone(self.state.player.ground_id)
        self.assertIs(self.state.active_color, Color.BLUE)
        self.assertIs(self.app.input.device, Device.GAMEPAD)

    def test_reset_keeps_held_keys_consumed_until_released(self):
        self.held.update({Key.R, Key.SPACE})
        self.app.update()
        self.app.update()
        self.assertEqual(self.state.player, Player(68, 322, ground_id="P01"))
        self.held.remove(Key.SPACE)
        self.app.update()
        self.held.add(Key.SPACE)
        self.app.update()
        self.assertIs(self.state.active_color, Color.BLUE)

    def test_automatic_restart_does_not_replay_held_jump(self):
        self.state.phase = Phase.FALLING
        self.state.fall_steps = FALL_STEPS - 1
        self.held.add(Key.SPACE)
        self.app.update()
        self.app.update()
        self.assertEqual(self.state.player, Player(68, 322, ground_id="P01"))
        self.assertIs(self.state.phase, Phase.PLAYING)

    def test_start_held_before_clear_does_not_retry_until_repressed(self):
        self.gamepad.read.return_value = PadState(0)
        self.app.update()
        self.gamepad.read.return_value = PadState(0, start=True, south=True)
        self.app.update()
        self.state.phase = Phase.CLEAR
        frozen = deepcopy(self.state)
        self.app.update()
        self.assertEqual(self.state, frozen)
        self.gamepad.read.return_value = PadState(0, south=True)
        self.app.update()
        self.gamepad.read.return_value = PadState(0, start=True, south=True)
        self.app.update()
        self.app.update()
        self.assertIs(self.state.phase, Phase.PLAYING)
        self.assertEqual(self.state.player, Player(68, 322, ground_id="P01"))
        self.assertIs(self.app.input.device, Device.GAMEPAD)

    def test_mouse_retry_uses_the_rendered_button_bounds(self):
        self.state.phase = Phase.CLEAR
        for click in (None, (RETRY_BUTTON.x - 1, RETRY_BUTTON.y), (390, 190)):
            with self.subTest(click=click):
                self.window.take_click.return_value = click
                self.app.update()
                self.assertIs(self.state.phase, Phase.CLEAR)
        self.window.take_click.return_value = (RETRY_BUTTON.x, RETRY_BUTTON.y)
        self.app.update()
        self.assertIs(self.state.phase, Phase.PLAYING)
        self.assertEqual(self.state.player, Player(68, 322, ground_id="P01"))

    def test_pyxel_is_configured_with_the_fixed_canvas_and_fps(self):
        pyxel = Mock(KEY_NONE=0, colors=[0] * 16)
        with patch("first_jump.app.enable_dpi_awareness") as dpi, patch(
            "first_jump.app.WindowsWindow"
        ) as window:
            self.assertIs(open_window(pyxel), window.return_value)
        dpi.assert_called_once_with()
        pyxel.init.assert_called_once_with(
            640, 360, title=TITLE, fps=60, quit_key=pyxel.KEY_NONE,
            display_scale=1, capture_sec=0,
        )
        pyxel.fullscreen.assert_called_once_with(False)
        pyxel.integer_scale.assert_called_once_with(False)
        window.assert_called_once_with(TITLE)
