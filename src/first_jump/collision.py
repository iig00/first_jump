from collections.abc import Iterable
from math import sqrt

from .model import Platform, Player
from .stage import GRAVITY, PLAYER_HEIGHT, PLAYER_WIDTH, WIDTH


def horizontal_overlap(x: float, platform: Platform) -> bool:
    return x < platform.right and x + PLAYER_WIDTH > platform.x


def overlaps(player: Player, platform: Platform) -> bool:
    return (
        horizontal_overlap(player.x, platform)
        and player.y < platform.y + platform.height
        and player.y + PLAYER_HEIGHT > platform.y
    )


def horizontal_position(player: Player, seconds: float) -> float:
    return min(max(player.x + player.vx * seconds, 0.0), WIDTH - PLAYER_WIDTH)


def vertical_position(player: Player, seconds: float) -> float:
    return player.y + player.vy * seconds + GRAVITY * seconds**2 / 2


def _descending_time(player: Player, top: int, seconds: float) -> float | None:
    distance = top - (player.y + PLAYER_HEIGHT)
    discriminant = player.vy**2 + 2 * GRAVITY * distance
    if discriminant <= 0:
        return None
    time = (sqrt(discriminant) - player.vy) / GRAVITY
    # Keep frame-end contacts despite roundoff in the quadratic solution.
    if 0 < time <= seconds + 1e-12:
        return min(time, seconds)
    return None


def rose_clear_of(player: Player, platform: Platform, seconds: float) -> bool:
    apex = min(max(-player.vy / GRAVITY, 0.0), seconds)
    return vertical_position(player, apex) + PLAYER_HEIGHT <= platform.y


def first_landing(
    player: Player,
    seconds: float,
    platforms: Iterable[Platform],
    excluded: set[str],
) -> tuple[float, Platform] | None:
    best = None
    for platform in platforms:
        time = _descending_time(player, platform.y, seconds)
        if time is None or not horizontal_overlap(horizontal_position(player, time), platform):
            continue
        # Horizontal motion is monotonic in a step. An overlapping excluded
        # platform can only be reentered by rising clear of it before landing.
        if platform.id in excluded and not rose_clear_of(player, platform, time):
            continue
        if best is None or (time, platform.id) < (best[0], best[1].id):
            best = (time, platform)
    return best
