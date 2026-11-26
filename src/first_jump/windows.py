import ctypes
from ctypes import wintypes

from .stage import WINDOW_HEIGHT, WINDOW_WIDTH
from .viewport import Viewport

_GWL_STYLE = -16
_WS_THICKFRAME = 0x00040000
_WS_MAXIMIZEBOX = 0x00010000
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SWP_FRAMECHANGED = 0x0020

_WM_KEYDOWN = 0x0100
_WM_KEYUP = 0x0101
_WM_SYSKEYDOWN = 0x0104
_WM_SYSKEYUP = 0x0105
_WM_SYSCHAR = 0x0106
_WM_SYSCOMMAND = 0x0112
_WM_LBUTTONDOWN = 0x0201
_SC_KEYMENU = 0xF100
_VK_MENU = 0x12
_VK_SPACE = 0x20
_VK_F4 = 0x73
_ALT_CONTEXT = 1 << 29
_GAME_KEYS = {ord("A"), ord("D"), ord("R"), _VK_SPACE, 0x25, 0x27}
_SYSTEM_KEYS = {_VK_MENU, _VK_F4}


def _bind(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = arguments
    return function


def enable_dpi_awareness() -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    set_context = _bind(user32, "SetProcessDpiAwarenessContext", wintypes.BOOL, ctypes.c_void_p)
    set_context(ctypes.c_void_p(-4))  # Per-monitor v2, unless already set by the host.


class WindowsWindow:
    """Native client geometry and events missing from the Pyxel public API."""

    def __init__(self, title: str) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        controls = ctypes.WinDLL("comctl32", use_last_error=True)
        hwnd, uint = wintypes.HWND, wintypes.UINT
        wparam, lparam = wintypes.WPARAM, wintypes.LPARAM
        result = ctypes.c_ssize_t
        subclass = ctypes.WINFUNCTYPE(
            result, hwnd, uint, wparam, lparam, ctypes.c_size_t, ctypes.c_size_t
        )
        self._next_message = _bind(controls, "DefSubclassProc", result, hwnd, uint, wparam, lparam)
        self._default_message = _bind(user32, "DefWindowProcW", result, hwnd, uint, wparam, lparam)
        set_subclass = _bind(
            controls, "SetWindowSubclass", wintypes.BOOL,
            hwnd, subclass, ctypes.c_size_t, ctypes.c_size_t,
        )
        self._remove_subclass = _bind(
            controls, "RemoveWindowSubclass", wintypes.BOOL, hwnd, subclass, ctypes.c_size_t
        )
        self._is_window = _bind(user32, "IsWindow", wintypes.BOOL, hwnd)
        self._client_rect = _bind(
            user32, "GetClientRect", wintypes.BOOL, hwnd, ctypes.POINTER(wintypes.RECT)
        )
        self._hwnd = self._find_window(user32, kernel32, title)
        self._resize(user32)
        self._click: tuple[float, float] | None = None
        self._subclass = subclass(self._on_message)
        if not set_subclass(self._hwnd, self._subclass, 1, 0):
            raise ctypes.WinError(ctypes.get_last_error())

    @staticmethod
    def _find_window(user32, kernel32, title: str):
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        enum_thread_windows = _bind(
            user32, "EnumThreadWindows", wintypes.BOOL,
            wintypes.DWORD, callback_type, wintypes.LPARAM,
        )
        get_thread_id = _bind(kernel32, "GetCurrentThreadId", wintypes.DWORD)
        get_title = _bind(
            user32, "GetWindowTextW", ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int
        )
        handle = None
        buffer = ctypes.create_unicode_buffer(len(title) + 2)

        @callback_type
        def find_window(hwnd, _):
            nonlocal handle
            get_title(hwnd, buffer, len(buffer))
            if buffer.value != title:
                return True
            handle = hwnd
            return False

        enum_thread_windows(get_thread_id(), find_window, 0)
        if handle is None:
            raise RuntimeError("The Pyxel window could not be found on the current thread.")
        return handle

    def _resize(self, user32) -> None:
        hwnd = wintypes.HWND
        integer = ctypes.c_int
        get_style = _bind(user32, "GetWindowLongW", ctypes.c_long, hwnd, ctypes.c_int)
        set_style = _bind(user32, "SetWindowLongW", ctypes.c_long, hwnd, ctypes.c_int, ctypes.c_long)
        set_position = _bind(
            user32, "SetWindowPos", wintypes.BOOL,
            hwnd, hwnd, integer, integer, integer, integer, wintypes.UINT,
        )
        get_window_rect = _bind(
            user32, "GetWindowRect", wintypes.BOOL, hwnd, ctypes.POINTER(wintypes.RECT)
        )
        style = get_style(self._hwnd, _GWL_STYLE)
        resizable_style = style | _WS_THICKFRAME | _WS_MAXIMIZEBOX
        flags = _SWP_NOZORDER | _SWP_NOACTIVATE
        if style != resizable_style:
            ctypes.set_last_error(0)
            if not set_style(self._hwnd, _GWL_STYLE, resizable_style) and ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())
            frame_flags = flags | _SWP_FRAMECHANGED | _SWP_NOSIZE | _SWP_NOMOVE
            if not set_position(self._hwnd, None, 0, 0, 0, 0, frame_flags):
                raise ctypes.WinError(ctypes.get_last_error())

        rect = wintypes.RECT()
        if not get_window_rect(self._hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        client_width, client_height = self.client_size()
        delta_x = WINDOW_WIDTH - client_width
        delta_y = WINDOW_HEIGHT - client_height
        if not set_position(
            self._hwnd, None,
            rect.left - delta_x // 2, rect.top - delta_y // 2,
            rect.right - rect.left + delta_x, rect.bottom - rect.top + delta_y,
            flags,
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    def _on_message(self, hwnd, message, key, data, _subclass_id, _reference):
        # Let Windows handle its system menu without SDL treating Space as a jump.
        if message in (_WM_SYSKEYDOWN, _WM_SYSCHAR) and key == _VK_SPACE and data & _ALT_CONTEXT:
            return self._default_message(hwnd, message, key, data)
        if message == _WM_SYSCOMMAND and (key & 0xFFF0) == _SC_KEYMENU and data == _VK_SPACE:
            return self._default_message(hwnd, message, key, data)
        # Forward gameplay keys and Alt+F4, suppressing Pyxel's own shortcuts.
        if message in (_WM_KEYDOWN, _WM_KEYUP) and key not in _GAME_KEYS:
            return 0
        if message == _WM_SYSKEYDOWN and key not in _SYSTEM_KEYS:
            return 0
        if message == _WM_SYSKEYUP and key not in _GAME_KEYS and key not in _SYSTEM_KEYS:
            return 0
        if message == _WM_SYSCHAR:
            return 0
        if message == _WM_LBUTTONDOWN:
            x = ctypes.c_int16(data & 0xFFFF).value
            y = ctypes.c_int16((data >> 16) & 0xFFFF).value
            try:
                self._click = Viewport.fit(*self.client_size()).to_logical((x, y))
            except OSError:
                self._click = None
        return self._next_message(hwnd, message, key, data)

    def client_size(self) -> tuple[int, int]:
        rect = wintypes.RECT()
        if not self._client_rect(self._hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        return rect.right, rect.bottom

    def take_click(self) -> tuple[float, float] | None:
        click, self._click = self._click, None
        return click

    def close(self) -> None:
        if self._is_window(self._hwnd):
            self._remove_subclass(self._hwnd, self._subclass, 1)
