import unittest
from unittest.mock import Mock

from first_jump.windows import WindowsWindow


class WindowsWindowTest(unittest.TestCase):
    def setUp(self):
        self.window = WindowsWindow.__new__(WindowsWindow)
        self.window._click = None
        self.window._next_message = Mock(return_value=1)
        self.window._default_message = Mock(return_value=2)
        self.window.client_size = Mock(return_value=(1200, 540))

    def message(self, message, key=0, data=0):
        return self.window._on_message(1, message, key, data, 1, 0)

    def test_forwards_game_keys_and_close_but_blocks_engine_shortcuts(self):
        self.assertEqual(self.message(0x0100, ord("A")), 1)  # WM_KEYDOWN
        self.assertEqual(self.message(0x0101, ord("A")), 1)  # WM_KEYUP
        self.assertEqual(self.message(0x0100, 0x1B), 0)  # Escape
        self.assertEqual(self.message(0x0100, 0x7A), 0)  # F11
        self.assertEqual(self.message(0x0104, 0x0D), 0)  # Alt+Enter
        self.assertEqual(self.message(0x0104, ord("R")), 0)  # Alt+R
        self.assertEqual(self.message(0x0104, 0x73), 1)  # Alt+F4
        self.assertEqual(self.message(0x0010), 1)  # WM_CLOSE

    def test_converts_client_click_once_and_rejects_letterbox_and_negative_coordinates(self):
        self.message(0x0201, data=(270 << 16) | 600)
        self.assertEqual(self.window.take_click(), (320, 180))
        self.assertIsNone(self.window.take_click())
        for x in (119, 1080, 0xFFFF):
            self.message(0x0201, data=(270 << 16) | x)
            self.assertIsNone(self.window.take_click())

    def test_alt_space_reaches_windows_without_sending_jump_to_pyxel(self):
        alt_down = 1 << 29
        for message in (0x0104, 0x0106):  # WM_SYSKEYDOWN, WM_SYSCHAR
            self.assertEqual(self.message(message, 0x20, alt_down), 2)
            self.window._default_message.assert_called_with(1, message, 0x20, alt_down)
        self.assertEqual(self.message(0x0112, 0xF100, 0x20), 2)  # SC_KEYMENU for Space
        self.assertEqual(self.message(0x0106, 0x0D, alt_down), 0)  # Alt+Enter
        self.window._next_message.assert_not_called()
        self.assertEqual(self.message(0x0100, 0x20), 1)  # ordinary Space
        self.assertEqual(self.message(0x0105, 0x20, alt_down), 1)  # release a held Space

    def test_click_uses_size_at_event_time(self):
        self.message(0x0201, data=(270 << 16) | 600)
        self.window.client_size.return_value = (1200, 800)
        self.assertEqual(self.window.take_click(), (320, 180))
