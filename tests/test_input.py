import ctypes
import unittest
from unittest.mock import Mock, patch

from first_jump.input import InputAdapter, Key, PadState, RawInput, XInput, _XInputState
from first_jump.model import Device


class InputAdapterTest(unittest.TestCase):
    def setUp(self):
        self.adapter = InputAdapter()

    def update(self, *keys, pad=None, click=None):
        return self.adapter.update(RawInput(frozenset(keys), pad, click))

    def test_keys_and_pad_directions_are_combined_per_side(self):
        self.assertTrue(self.update(Key.A).left)
        self.assertTrue(self.update(Key.LEFT).left)
        self.assertTrue(self.update(Key.D).right)
        self.assertTrue(self.update(Key.RIGHT).right)
        frame = self.update(Key.A, pad=PadState(0, right=True))
        self.assertTrue(frame.left)
        self.assertTrue(frame.right)
        frame = self.update(pad=PadState(0, stick_x=-0.8, right=True))
        self.assertTrue(frame.left)
        self.assertTrue(frame.right)

    def test_combined_jump_requires_both_buttons_to_be_released(self):
        idle_pad = PadState(0)
        held_pad = PadState(0, south=True)
        self.update(pad=idle_pad)
        self.assertTrue(self.update(Key.SPACE, pad=idle_pad).jump_pressed)
        self.assertFalse(self.update(Key.SPACE, pad=held_pad).jump_pressed)
        self.assertFalse(self.update(pad=held_pad).jump_pressed)
        self.assertFalse(self.update(Key.SPACE, pad=idle_pad).jump_pressed)
        self.update(pad=idle_pad)
        self.assertTrue(self.update(pad=held_pad).jump_pressed)

    def test_stick_threshold_and_hysteresis(self):
        for axis, expected in (
            (0.0, (False, False)),
            (0.24, (False, False)),
            (0.25, (False, True)),
            (0.21, (False, True)),
            (0.20, (False, False)),
            (0.21, (False, False)),
            (-0.25, (True, False)),
            (-0.21, (True, False)),
            (-0.20, (False, False)),
        ):
            with self.subTest(axis=axis):
                frame = self.update(pad=PadState(0, stick_x=axis))
                self.assertEqual((frame.left, frame.right), expected)

    def test_disconnect_releases_input_and_new_pad_buttons_need_fresh_edges(self):
        self.update(pad=PadState(0))
        frame = self.update(pad=PadState(0, left=True, south=True, start=True))
        self.assertTrue(frame.left and frame.jump_pressed and frame.start_pressed)
        frame = self.update()
        self.assertFalse(frame.left or frame.jump_pressed or frame.start_pressed)
        frame = self.update(pad=PadState(0, right=True, south=True, start=True))
        self.assertTrue(frame.right)
        self.assertFalse(frame.jump_pressed or frame.start_pressed)
        self.update(pad=PadState(0))
        frame = self.update(pad=PadState(1, south=True, start=True))
        self.assertFalse(frame.jump_pressed or frame.start_pressed)
        self.update(pad=PadState(1))
        frame = self.update(pad=PadState(1, south=True, start=True))
        self.assertTrue(frame.jump_pressed and frame.start_pressed)

    def test_hud_uses_last_meaningful_input_with_keyboard_tie_break(self):
        self.update(pad=PadState(0))
        self.update(pad=PadState(0, stick_x=0.10), click=(0, 0))
        self.assertIs(self.adapter.device, Device.KEYBOARD)
        self.update(Key.D, pad=PadState(0, stick_x=0.3))
        self.assertIs(self.adapter.device, Device.KEYBOARD)
        self.update(Key.D, pad=PadState(0, stick_x=0.22))
        self.assertIs(self.adapter.device, Device.KEYBOARD)
        self.update(Key.D, pad=PadState(0, stick_x=0.19))
        self.update(Key.D, pad=PadState(0, stick_x=-0.3))
        self.assertIs(self.adapter.device, Device.GAMEPAD)
        self.update(pad=PadState(0, stick_x=0.02))
        self.assertIs(self.adapter.device, Device.GAMEPAD)
        self.update(Key.RIGHT, pad=PadState(0, stick_x=0.02))
        self.assertIs(self.adapter.device, Device.KEYBOARD)

    def test_held_direction_on_pad_connection_or_replacement_selects_pad_hints(self):
        for previous, pad in (
            (None, PadState(0, right=True, south=True, start=True)),
            (PadState(0, stick_x=0.8), PadState(1, stick_x=0.8)),
        ):
            with self.subTest(pad=pad):
                self.adapter = InputAdapter()
                self.update(Key.D, pad=previous)
                frame = self.update(pad=pad)
                self.assertTrue(frame.right)
                self.assertFalse(frame.jump_pressed or frame.start_pressed)
                self.assertIs(self.adapter.device, Device.GAMEPAD)

    def test_stick_reversal_between_samples_selects_pad_hints(self):
        self.update(pad=PadState(0))
        self.update(Key.SPACE, pad=PadState(0, stick_x=0.9))
        self.assertIs(self.adapter.device, Device.KEYBOARD)
        frame = self.update(pad=PadState(0, stick_x=-0.9))
        self.assertTrue(frame.left)
        self.assertIs(self.adapter.device, Device.GAMEPAD)

    def test_sync_keeps_device_and_uses_held_buttons_as_baseline(self):
        self.update(pad=PadState(0))
        self.update(pad=PadState(0, south=True, start=True, stick_x=-0.3))
        held = RawInput(
            frozenset({Key.R, Key.SPACE}),
            PadState(0, south=True, start=True, stick_x=-0.22),
        )
        self.adapter.sync(held)
        frame = self.adapter.update(held)
        self.assertFalse(frame.jump_pressed or frame.reset_pressed or frame.start_pressed)
        self.assertTrue(frame.left)
        self.assertIs(self.adapter.device, Device.GAMEPAD)
        self.update(pad=PadState(0))
        frame = self.adapter.update(held)
        self.assertTrue(frame.jump_pressed and frame.reset_pressed and frame.start_pressed)
        self.assertIs(self.adapter.device, Device.KEYBOARD)

    def test_resolving_a_keyboard_direction_conflict_counts_as_movement(self):
        self.update(Key.A, Key.D, pad=PadState(0))
        self.update(Key.A, Key.D, pad=PadState(0, start=True))
        self.assertIs(self.adapter.device, Device.GAMEPAD)
        self.update(Key.D, pad=PadState(0, start=True))
        self.assertIs(self.adapter.device, Device.KEYBOARD)


class XInputTest(unittest.TestCase):
    def test_reads_first_connected_slot_even_if_its_inputs_are_idle(self):
        def get_state(slot, pointer):
            if slot == 0:
                return 1167  # ERROR_DEVICE_NOT_CONNECTED
            state = ctypes.cast(pointer, ctypes.POINTER(_XInputState)).contents
            if slot == 2:
                state.gamepad.buttons = 0x1000
            return 0

        library = Mock()
        library.XInputGetState.side_effect = get_state
        with patch("first_jump.input.ctypes.WinDLL", return_value=library, create=True):
            pad = XInput().read()
        self.assertEqual(pad, PadState(1))
        self.assertEqual([call.args[0] for call in library.XInputGetState.call_args_list], [0, 1])

    def test_converts_signed_axis_and_button_masks(self):
        def get_state(slot, pointer):
            state = ctypes.cast(pointer, ctypes.POINTER(_XInputState)).contents
            state.gamepad.left_x = -32768
            state.gamepad.buttons = 0x1000 | 0x0010 | 0x0004
            return 0

        library = Mock()
        library.XInputGetState.side_effect = get_state
        with patch("first_jump.input.ctypes.WinDLL", return_value=library, create=True):
            pad = XInput().read()
        self.assertEqual(pad, PadState(0, -1.0, left=True, south=True, start=True))
