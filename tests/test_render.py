import unittest
from copy import deepcopy
from unittest.mock import Mock, call, patch

from first_jump.font import draw_text
from first_jump.game import Game
from first_jump.model import Color, Device, Phase, Player
from first_jump.render import GAMEPAD_HINTS, KEYBOARD_HINTS, RETRY_HINT, Ink, Renderer
from first_jump.stage import PLATFORMS
from first_jump.viewport import RETRY_BUTTON


class RendererTest(unittest.TestCase):
    def setUp(self):
        self.screen = Mock()
        self.renderer = Renderer(self.screen)
        self.game = Game()
        self.state = self.game.state

    def draw(self, device=Device.KEYBOARD):
        self.renderer.draw(self.state, PLATFORMS, device)

    def test_stage_appearance_uses_color_even_when_collision_is_excluded(self):
        self.state.excluded.add("P03")
        self.draw()
        self.screen.cls.assert_called_once_with(Ink.NAVY)
        self.screen.line.assert_any_call(16, 0, 16, 359, Ink.GRID)
        for platform in (PLATFORMS[0], PLATFORMS[5], PLATFORMS[9], PLATFORMS[11]):
            self.screen.rect.assert_any_call(
                platform.x, platform.y, platform.width, platform.height, Ink.WHITE
            )
        self.screen.rect.assert_any_call(96, 286, 44, 8, Ink.RED)
        self.screen.rectb.assert_any_call(54, 312, 44, 8, Ink.BLUE_DIM)
        self.assertNotIn(call(54, 312, 44, 8, Ink.BLUE), self.screen.rect.call_args_list)
        self.screen.tri.assert_called_once()
        self.assertTrue(any(args[-1] is Ink.RED_LIGHT for args, _ in self.screen.line.call_args_list))
        self.assertTrue(any(args[-1] is Ink.BLUE_DIM for args, _ in self.screen.pset.call_args_list))

    def test_robot_stays_in_12_by_16_rectangle(self):
        self.renderer._robot(Player(68, 322))
        for args, _ in self.screen.rect.call_args_list:
            x, y, width, height, _ = args
            self.assertGreaterEqual(x, 68)
            self.assertGreaterEqual(y, 322)
            self.assertLessEqual(x + width, 80)
            self.assertLessEqual(y + height, 338)
        for args, _ in self.screen.line.call_args_list:
            x1, y1, x2, y2, _ = args
            self.assertTrue(all(68 <= x < 80 for x in (x1, x2)))
            self.assertTrue(all(322 <= y < 338 for y in (y1, y2)))

    def test_hud_text_and_controls_respond_to_state_and_device(self):
        for color, device, label, hints in (
            (Color.RED, Device.KEYBOARD, "赤が有効", KEYBOARD_HINTS),
            (Color.BLUE, Device.GAMEPAD, "青が有効", GAMEPAD_HINTS),
        ):
            with self.subTest(color=color, device=device):
                self.state.active_color = color
                with patch("first_jump.render.draw_text", wraps=draw_text) as text:
                    self.draw(device)
                labels = tuple(args[3] for args, _ in text.call_args_list)
                self.assertEqual(labels, (label, *hints))

    def test_bottom_hud_moves_if_the_player_reaches_its_usual_area(self):
        self.state.player = Player(510, 340)
        self.draw()
        self.screen.rect.assert_any_call(324, 316, 150, 42, Ink.PANEL)
        self.assertNotIn(call(486, 316, 150, 42, Ink.PANEL), self.screen.rect.call_args_list)

    def test_clear_draws_the_shared_retry_button_without_changing_state(self):
        self.state.phase = Phase.CLEAR
        before = deepcopy(self.state)
        with patch("first_jump.render.draw_text", wraps=draw_text) as text:
            self.draw()
        button = RETRY_BUTTON
        self.screen.rect.assert_any_call(button.x, button.y, button.width, button.height, Ink.BUTTON)
        labels = tuple(args[3] for args, _ in text.call_args_list)
        self.assertIn("もう一度", labels)
        self.assertIn(RETRY_HINT, labels)
        self.assertEqual(self.state, before)

    def test_fall_effect_increases_opacity_and_restores_drawing_state(self):
        self.state.phase = Phase.FALLING
        self.state.fall_steps = 14
        before = deepcopy(self.state)
        self.draw()
        self.assertEqual(self.screen.dither.call_args_list, [call(0.5), call(1.0)])
        self.screen.rect.assert_any_call(0, 0, 640, 360, Ink.BLACK)
        self.assertEqual(self.state, before)
