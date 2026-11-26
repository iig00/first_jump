from .model import Color, Platform, Role

WIDTH = 640
HEIGHT = 360
WINDOW_WIDTH = 960
WINDOW_HEIGHT = 540
PLAYER_WIDTH = 12
PLAYER_HEIGHT = 16
START_X = 68
START_Y = 322
FPS = 60
STEP = 1 / FPS
MOVE_SPEED = 120
JUMP_SPEED = 300
GRAVITY = 900
FALL_STEPS = FPS // 2

PLATFORMS = (
    Platform("P01", 24, 338, 100, 8, Color.ALWAYS, Role.START),
    Platform("P02", 54, 312, 44, 8, Color.BLUE),
    Platform("P03", 96, 286, 44, 8, Color.RED),
    Platform("P04", 138, 260, 44, 8, Color.BLUE),
    Platform("P05", 180, 234, 44, 8, Color.RED),
    Platform("P06", 208, 208, 76, 8, Color.ALWAYS, Role.REST),
    Platform("P07", 166, 182, 44, 8, Color.RED),
    Platform("P08", 124, 156, 44, 8, Color.BLUE),
    Platform("P09", 166, 130, 44, 8, Color.RED),
    Platform("P10", 194, 104, 76, 8, Color.ALWAYS, Role.REST),
    Platform("P11", 236, 78, 44, 8, Color.RED),
    Platform("P12", 260, 52, 50, 8, Color.ALWAYS, Role.GOAL),
    Platform("P13", 320, 78, 44, 8, Color.BLUE),
    Platform("P14", 360, 52, 44, 8, Color.RED),
    Platform("P15", 154, 286, 44, 8, Color.BLUE),
    Platform("P16", 250, 90, 52, 8, Color.BLUE),
)
START_ID = PLATFORMS[0].id
