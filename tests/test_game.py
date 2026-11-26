import unittest
from copy import deepcopy

from first_jump.collision import first_landing
from first_jump.game import Game
from first_jump.model import Color, GameState, InputFrame, Phase, Platform, Player
from first_jump.stage import FALL_STEPS, PLATFORMS, STEP


class GameTest(unittest.TestCase):
    def setUp(self):
        self.game = Game()
        self.idle = InputFrame()

    @property
    def state(self):
        return self.game.state

    @property
    def player(self):
        return self.state.player

    def test_fixed_horizontal_speed_and_continuous_jump(self):
        self.game.update(InputFrame(right=True))
        self.assertEqual(self.player, Player(70, 322, 120, 0, "P01"))
        self.game.update(InputFrame(left=True, right=True))
        self.assertEqual(self.player, Player(70, 322, ground_id="P01"))

        self.game.update(InputFrame(left=True, jump_pressed=True))
        self.assertEqual(self.player.x, 68)
        self.assertAlmostEqual(self.player.y, 317.125)
        self.assertAlmostEqual(self.player.vy, -285)
        self.assertIsNone(self.player.ground_id)
        self.assertIs(self.state.active_color, Color.BLUE)
        for frame in range(1, 20):
            # Repeated air presses cannot change the apex or the active color.
            self.game.update(InputFrame(jump_pressed=frame % 2 == 0))
        self.assertAlmostEqual(self.player.y, 272)
        self.assertAlmostEqual(self.player.vy, 0)
        self.assertIs(self.state.active_color, Color.BLUE)

    def test_jump_from_colored_platform_disables_it_only_after_takeoff(self):
        self.state.player = Player(68, 296, ground_id="P02")
        self.state.active_color = Color.BLUE
        self.game.update(InputFrame(jump_pressed=True))
        self.assertIsNone(self.player.ground_id)
        self.assertLess(self.player.y, 296)
        self.assertAlmostEqual(self.player.vy, -285)
        self.assertIs(self.state.active_color, Color.RED)

    def test_airborne_press_on_landing_frame_is_discarded(self):
        self.state.player = Player(66, 295, vy=120)
        self.state.active_color = Color.BLUE
        self.game.update(InputFrame(jump_pressed=True))
        self.assertEqual(self.player.ground_id, "P02")
        self.assertIs(self.state.active_color, Color.BLUE)
        self.game.update(self.idle)
        self.assertEqual(self.player.ground_id, "P02")
        self.game.update(InputFrame(jump_pressed=True))
        self.assertIsNone(self.player.ground_id)
        self.assertIs(self.state.active_color, Color.RED)

    def test_falling_after_walking_off_can_recover_on_a_lower_platform(self):
        self.state.player = Player(43, 296, ground_id="P02")
        self.state.active_color = Color.BLUE
        self.game.update(InputFrame(left=True))
        self.assertEqual(self.player.x, 41)
        self.assertAlmostEqual(self.player.y, 296.03125)
        self.assertAlmostEqual(self.player.vy, 7.5)
        self.assertIsNone(self.player.ground_id)
        self.assertIs(self.state.phase, Phase.PLAYING)
        for _ in range(30):
            if self.player.ground_id is not None:
                break
            self.game.update(self.idle)
        self.assertEqual(self.player.ground_id, "P01")
        self.assertIs(self.state.active_color, Color.BLUE)

    def test_horizontal_screen_limits_apply_on_the_ground_and_in_the_air(self):
        self.game = Game((PLATFORMS[0], Platform("edge", 0, 100, 640, 8, Color.ALWAYS)))
        for x, frame, expected in (
            (1, InputFrame(left=True), 0),
            (627, InputFrame(right=True), 628),
        ):
            with self.subTest(x=x):
                self.state.player = Player(x, 84, ground_id="edge")
                self.game.update(frame)
                self.assertEqual(self.player.x, expected)
                self.assertEqual(self.player.ground_id, "edge")
                frame = InputFrame(left=frame.left, right=frame.right, jump_pressed=True)
                self.game.update(frame)
                self.assertEqual(self.player.x, expected)
                self.assertIsNone(self.player.ground_id)

    def test_reenabled_platform_is_excluded_until_the_player_leaves_it(self):
        blue = Platform("blue", 60, 330, 30, 8, Color.BLUE)
        self.game = Game((PLATFORMS[0], blue))
        self.game.update(InputFrame(jump_pressed=True))
        self.assertEqual(self.state.excluded, {"blue"})
        self.assertTrue(blue.is_enabled(self.state.active_color))
        self.assertAlmostEqual(self.player.y, 317.125)
        self.game.update(self.idle)
        self.assertFalse(self.state.excluded)
        for _ in range(40):
            if self.player.ground_id is not None:
                break
            self.game.update(self.idle)
        self.assertEqual(self.player.ground_id, "blue")

    def test_exclusion_tracks_separation_even_while_color_is_disabled(self):
        blue = Platform("blue", 60, 330, 30, 8, Color.BLUE)
        self.game = Game((PLATFORMS[0], blue))
        self.state.excluded.add("blue")
        self.state.player = Player(68, 319, vy=20)
        self.game.update(self.idle)
        self.assertEqual(self.state.excluded, {"blue"})
        self.state.player.x = blue.right
        self.game.update(self.idle)
        self.assertFalse(self.state.excluded)
        self.assertIs(self.state.active_color, Color.RED)

    def test_exclusion_can_end_at_the_apex_before_landing_in_the_same_step(self):
        blue = Platform("blue", 60, 100, 30, 8, Color.BLUE)
        self.game = Game((PLATFORMS[0], blue))
        self.state.active_color = Color.BLUE
        self.state.excluded.add("blue")
        self.state.player = Player(68, 84.05, vy=-10)
        self.game.update(self.idle)
        self.assertEqual(self.player.ground_id, "blue")
        self.assertFalse(self.state.excluded)

    def test_disabled_platform_is_passed_on_the_way_down(self):
        blue = next(platform for platform in PLATFORMS if platform.id == "P02")
        self.state.player = Player(68, 295, vy=120)
        self.game.update(self.idle)
        self.assertGreater(self.player.y + 16, blue.y)
        self.assertIsNone(self.player.ground_id)
        for _ in range(30):
            if self.player.ground_id is not None:
                break
            self.game.update(self.idle)
        self.assertEqual(self.player.ground_id, "P01")

    def test_full_player_must_exit_before_30_step_fall_delay(self):
        self.state.player = Player(0, 359.5)
        self.state.active_color = Color.BLUE
        self.game.update(self.idle)
        self.assertIs(self.state.phase, Phase.PLAYING)
        self.game.update(self.idle)
        self.assertGreaterEqual(self.player.y, 360)
        self.assertIs(self.state.phase, Phase.FALLING)
        self.assertEqual(self.state.fall_steps, 0)
        player = deepcopy(self.player)
        for step in range(1, 30):
            self.assertFalse(self.game.update(InputFrame(left=True, jump_pressed=True)))
            self.assertEqual(self.state.fall_steps, step)
            self.assertEqual(self.player, player)
        self.assertTrue(self.game.update(InputFrame(right=True, jump_pressed=True)))
        self.assertEqual(FALL_STEPS, 30)
        self.assertEqual(self.state, GameState(Player(68, 322, ground_id="P01")))

    def test_only_descending_goal_landing_clears_and_freezes(self):
        self.state.player = Player(268, 40, vy=-300)
        self.game.update(self.idle)
        self.assertIs(self.state.phase, Phase.PLAYING)
        self.assertIsNone(self.player.ground_id)
        self.state.player = Player(268, 35, vy=90)
        self.game.update(self.idle)
        self.assertIs(self.state.phase, Phase.CLEAR)
        self.assertEqual(self.player, Player(268, 36, ground_id="P12"))
        frozen = deepcopy(self.state)
        self.game.update(InputFrame(right=True, jump_pressed=True))
        self.assertEqual(self.state, frozen)

    def test_reset_from_any_phase_restores_all_fields(self):
        for phase in Phase:
            with self.subTest(phase=phase):
                self.state.player = Player(211, 192, -120, 39, "P06")
                self.state.phase = phase
                self.state.active_color = Color.BLUE
                self.state.excluded.add("P02")
                self.state.fall_steps = 18
                frame = InputFrame(right=True, jump_pressed=True, reset_pressed=True)
                self.assertTrue(self.game.update(frame))
                self.assertEqual(self.state, GameState(Player(68, 322, ground_id="P01")))

    def test_start_and_ui_retry_apply_only_to_clear(self):
        for phase in Phase:
            for start, click in ((True, False), (False, True)):
                with self.subTest(phase=phase, start=start, click=click):
                    self.game.reset()
                    self.state.phase = phase
                    self.state.active_color = Color.BLUE
                    reset = self.game.update(InputFrame(start_pressed=start), retry_clicked=click)
                    self.assertEqual(reset, phase is Phase.CLEAR)
                    if reset:
                        self.assertEqual(self.state, GameState(Player(68, 322, ground_id="P01")))
                    else:
                        self.assertIs(self.state.active_color, Color.BLUE)


class CollisionTest(unittest.TestCase):
    deck = Platform("deck", 100, 100, 40, 8, Color.ALWAYS)

    def test_only_downward_top_crossings_with_positive_overlap_land(self):
        for player in (
            Player(110, 85, vy=-300),  # rising through the top
            Player(110, 109, vy=-300),  # rising through the underside
            Player(89, 102, vx=120),  # crossing the side
            Player(88, 83, vy=120),  # right edge touches the deck's left edge
            Player(140, 83, vy=120),  # left edge touches the deck's right edge
            Player(110, 84.125, vy=-15),  # apex touches with zero vertical velocity
            Player(110, 84, vy=120),  # crossing at t=0 is outside this step
        ):
            with self.subTest(player=player):
                self.assertIsNone(first_landing(player, STEP, (self.deck,), set()))
        player = Player(110, 83.875, vy=0)
        hit = first_landing(player, STEP, (self.deck,), set())
        self.assertAlmostEqual(hit[0], STEP)
        self.assertEqual(hit[1], self.deck)

    def test_uses_horizontal_overlap_at_the_crossing_not_frame_end(self):
        player = Player(87, 83.75, vx=120, vy=60)
        self.assertIsNone(first_landing(player, STEP, (self.deck,), set()))
        player = Player(139, 83.75, vx=120, vy=60)
        hit = first_landing(player, STEP, (self.deck,), set())
        self.assertEqual(hit[1], self.deck)

    def test_screen_bound_applies_to_crossing_position(self):
        deck = Platform("right", 627, 100, 2, 8, Color.ALWAYS)
        player = Player(628, 82.5, vx=120, vy=120)
        hit = first_landing(player, STEP, (deck,), set())
        self.assertEqual(hit[1], deck)

    def test_earliest_crossing_then_id_wins(self):
        lower = Platform("A", 100, 102, 40, 8, Color.ALWAYS)
        earlier = Platform("Z", 100, 100, 40, 8, Color.ALWAYS)
        tied = Platform("B", 100, 100, 40, 8, Color.ALWAYS)
        player = Player(110, 80, vy=600)
        hit = first_landing(player, STEP, (lower, earlier, tied), set())
        self.assertEqual(hit[1], tied)
