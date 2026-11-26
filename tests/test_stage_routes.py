import unittest
from dataclasses import replace

from first_jump.game import Game
from first_jump.model import Color, InputFrame, Phase, Role
from first_jump.stage import GRAVITY, JUMP_SPEED, PLATFORMS


IDLE = InputFrame()
LEFT = InputFrame(left=True)
RIGHT = InputFrame(right=True)

# Direction and number of held frames, counting the takeoff frame.
TO_P09 = (
    ("P02", Color.BLUE, IDLE, 0),
    ("P03", Color.RED, RIGHT, 22),
    ("P04", Color.BLUE, RIGHT, 21),
    ("P05", Color.RED, RIGHT, 21),
    ("P06", Color.BLUE, RIGHT, 22),
    ("P07", Color.RED, LEFT, 29),
    ("P08", Color.BLUE, LEFT, 21),
    ("P09", Color.RED, RIGHT, 29),
)


class StageRoutesTest(unittest.TestCase):
    def setUp(self):
        self.game = Game()
        self.landings = [("P01", self.game.state.active_color)]

    @property
    def player(self):
        return self.game.state.player

    def jump(self, destination, color, direction=IDLE, held_frames=0, *, pass_through=None):
        departure = self.player.ground_id
        self.assertIsNotNone(departure)
        direction_at_takeoff = direction if held_frames else IDLE
        self.game.update(replace(direction_at_takeoff, jump_pressed=True))
        self.assertIsNone(self.player.ground_id, f"{departure}: takeoff failed")
        self.assertLess(self.player.vy, 0)
        self.assertIs(self.game.state.active_color, color)
        if pass_through is not None:
            self.assertFalse(pass_through.is_enabled(self.game.state.active_color))
            self.assertNotIn(pass_through.id, self.game.state.excluded)

        passed_top = False
        for frame in range(1, 45):
            if pass_through is not None and self.player.vy < 0:
                self.assertGreater(self.player.x + 12, pass_through.x)
                self.assertLess(self.player.x, pass_through.right)
                passed_top |= self.player.y + 16 <= pass_through.y
            self.game.update(direction if frame < held_frames else IDLE)
            self.assertIsNot(self.game.state.phase, Phase.FALLING)
            if self.player.ground_id is not None:
                self.landings.append((self.player.ground_id, self.game.state.active_color))
                self.assertEqual(self.landings[-1], (destination, color), f"jump from {departure}")
                if pass_through is not None:
                    self.assertTrue(passed_top)
                return
        self.fail(f"{departure} did not land on {destination}")

    def follow(self, steps):
        for step in steps:
            self.jump(*step)

    def walk(self, steps, direction, ground):
        for _ in range(steps):
            self.game.update(direction)
            self.assertEqual(self.player.ground_id, ground)

    def reach_p10(self):
        self.follow(TO_P09)
        # Stay left of P16 at its earlier downward crossing, then walk on P10.
        self.jump("P10", Color.BLUE, RIGHT, 13)
        self.walk(14, RIGHT, "P10")
        self.assertAlmostEqual(self.player.x, 252)

    def test_exact_stage_and_rest_roles(self):
        expected = (
            ("P01", 24, 338, 100, "ALWAYS", "START"),
            ("P02", 54, 312, 44, "BLUE", None),
            ("P03", 96, 286, 44, "RED", None),
            ("P04", 138, 260, 44, "BLUE", None),
            ("P05", 180, 234, 44, "RED", None),
            ("P06", 208, 208, 76, "ALWAYS", "REST"),
            ("P07", 166, 182, 44, "RED", None),
            ("P08", 124, 156, 44, "BLUE", None),
            ("P09", 166, 130, 44, "RED", None),
            ("P10", 194, 104, 76, "ALWAYS", "REST"),
            ("P11", 236, 78, 44, "RED", None),
            ("P12", 260, 52, 50, "ALWAYS", "GOAL"),
            ("P13", 320, 78, 44, "BLUE", None),
            ("P14", 360, 52, 44, "RED", None),
            ("P15", 154, 286, 44, "BLUE", None),
            ("P16", 250, 90, 52, "BLUE", None),
        )
        actual = tuple(
            (p.id, p.x, p.y, p.width, p.color.name, p.role.name if p.role else None)
            for p in PLATFORMS
        )
        self.assertEqual(actual, expected)
        self.assertTrue(all(p.height == 8 for p in PLATFORMS))
        self.assertEqual(sum(p.role is Role.REST for p in PLATFORMS), 2)
        for departure, destination in zip(PLATFORMS[:11], PLATFORMS[1:12]):
            self.assertEqual(departure.y - destination.y, 26)
            center_distance = abs(
                departure.x + departure.width / 2 - destination.x - destination.width / 2
            )
            self.assertLessEqual(center_distance, 58)
        self.assertEqual((self.player.x, self.player.y, self.player.ground_id), (68, 322, "P01"))

    def test_standard_route_clears_in_11_jumps(self):
        self.reach_p10()
        self.jump("P11", Color.RED, pass_through=PLATFORMS[-1])
        self.jump("P12", Color.BLUE, RIGHT, 13)
        expected = [
            (f"P{number:02}", Color.RED if number % 2 else Color.BLUE)
            for number in range(1, 13)
        ]
        self.assertEqual(self.landings, expected)
        self.assertIs(self.game.state.phase, Phase.CLEAR)

    def test_advanced_route_clears_in_10_jumps(self):
        self.follow(TO_P09)
        self.assertAlmostEqual(self.player.x, 198)  # center x=204
        self.jump("P16", Color.BLUE, RIGHT, 29)
        self.jump("P12", Color.RED)
        expected = [("P01", Color.RED)] + [
            (destination, color) for destination, color, _, _ in TO_P09
        ] + [("P16", Color.BLUE), ("P12", Color.RED)]
        self.assertEqual(self.landings, expected)
        self.assertEqual(len(self.landings) - 1, 10)
        self.assertIs(self.game.state.phase, Phase.CLEAR)

    def test_upper_practice_branch_avoids_early_clear(self):
        self.reach_p10()
        self.jump("P11", Color.RED)
        self.walk(8, RIGHT, "P11")  # center x=274
        self.jump("P13", Color.BLUE, RIGHT, 40)
        self.assertIs(self.game.state.phase, Phase.PLAYING)
        self.jump("P14", Color.RED, RIGHT, 7)  # center x=368
        self.assertIs(self.game.state.phase, Phase.PLAYING)
        self.jump("P12", Color.BLUE, LEFT, 40)
        self.assertIs(self.game.state.phase, Phase.CLEAR)

    def test_lower_practice_branch_avoids_p04_and_returns_to_main_route(self):
        self.follow(TO_P09[:2])
        self.walk(9, RIGHT, "P03")
        # P04 is also blue. Clear its right edge before descending through it.
        self.jump("P15", Color.BLUE, RIGHT, 28)
        self.jump("P03", Color.RED, LEFT, 37)
        self.jump("P04", Color.BLUE, RIGHT, 21)

    def test_p16_color_prevents_landing_even_without_p11_intercepting(self):
        # Remove P11 so it cannot mask an unintended collision with lower P16.
        without_p11 = tuple(p for p in PLATFORMS if p.id != "P11")
        p16 = PLATFORMS[-1]
        for platform, destination in ((p16, "P10"), (replace(p16, color=Color.ALWAYS), "P16")):
            with self.subTest(p16_color=platform.color):
                self.game = Game(without_p11[:-1] + (platform,))
                self.reach_p10()
                self.jump(destination, Color.RED)

    def test_neither_rest_platform_becomes_a_checkpoint(self):
        for route in (TO_P09[:5], TO_P09 + (("P10", Color.BLUE, RIGHT, 13),)):
            with self.subTest(rest=route[-1][0]):
                self.game.reset()
                self.follow(route)
                for _ in range(180):
                    if self.game.update(RIGHT):
                        break
                self.assertEqual((self.player.x, self.player.y, self.player.ground_id), (68, 322, "P01"))
                self.assertIs(self.game.state.active_color, Color.RED)

    def test_height_and_color_bounds_allow_only_p16_as_a_short_clear_approach(self):
        # This overestimates reachable landings by allowing any horizontal
        # distance and loss of height. Walking/falling cannot gain height.
        max_rise = JUMP_SPEED**2 / (2 * GRAVITY)
        possible = {PLATFORMS[0]}
        active = Color.RED
        for jump in range(1, 11):
            active = Color.BLUE if active is Color.RED else Color.RED
            reaches = {
                (departure, target)
                for departure in possible
                for target in PLATFORMS
                if target.is_enabled(active) and departure.y - target.y < max_rise
            }
            for target_id, expected_from in (
                ("P12", {"P16"} if jump == 10 else set()),
                ("P16", {"P09"} if jump == 9 else set()),
            ):
                from_ids = {departure.id for departure, target in reaches if target.id == target_id}
                self.assertEqual(from_ids, expected_from, f"jump {jump} to {target_id}")
            possible = {target for _, target in reaches}
