from .collision import (
    first_landing,
    horizontal_overlap,
    horizontal_position,
    overlaps,
    rose_clear_of,
    vertical_position,
)
from .model import Color, GameState, InputFrame, Phase, Platform, Player, Role
from .stage import (
    FALL_STEPS,
    GRAVITY,
    HEIGHT,
    JUMP_SPEED,
    MOVE_SPEED,
    PLATFORMS,
    PLAYER_HEIGHT,
    PLAYER_WIDTH,
    START_ID,
    START_X,
    START_Y,
    STEP,
)


class Game:
    def __init__(self, platforms: tuple[Platform, ...] = PLATFORMS) -> None:
        self.platforms = platforms
        self._platforms_by_id = {platform.id: platform for platform in platforms}
        self.reset()

    def reset(self) -> None:
        self.state = GameState(Player(START_X, START_Y, ground_id=START_ID))

    def update(self, frame: InputFrame, *, retry_clicked: bool = False) -> bool:
        """Advance a fixed step and report whether the input adapter must resync."""
        state = self.state
        if frame.reset_pressed or (
            state.phase is Phase.CLEAR and (frame.start_pressed or retry_clicked)
        ):
            self.reset()
            return True
        if state.phase is Phase.CLEAR:
            return False
        if state.phase is Phase.FALLING:
            state.fall_steps += 1
            if state.fall_steps == FALL_STEPS:
                self.reset()
                return True
            return False

        player = state.player
        player.vx = MOVE_SPEED * (frame.right - frame.left)
        self._remove_separated_exclusions()
        if player.ground_id is not None and frame.jump_pressed:
            self._jump()
        seconds = self._move_on_ground(STEP)
        self._remove_separated_exclusions()
        if seconds > 0:
            self._move_in_air(seconds)
        self._remove_separated_exclusions()

        if state.phase is Phase.PLAYING and player.y >= HEIGHT:
            state.phase = Phase.FALLING
        return False

    def _jump(self) -> None:
        state = self.state
        player = state.player
        player.ground_id = None
        player.vy = -JUMP_SPEED
        state.active_color = Color.BLUE if state.active_color is Color.RED else Color.RED
        state.excluded.update(
            platform.id
            for platform in self.platforms
            if platform.color is state.active_color and overlaps(player, platform)
        )

    def _remove_separated_exclusions(self) -> None:
        state = self.state
        state.excluded.intersection_update(
            platform.id
            for platform in self.platforms
            if platform.id in state.excluded and overlaps(state.player, platform)
        )

    def _move_on_ground(self, seconds: float) -> float:
        player = self.state.player
        if player.ground_id is None:
            return seconds

        ground = self._platforms_by_id[player.ground_id]
        target_x = horizontal_position(player, seconds)
        if horizontal_overlap(target_x, ground):
            player.x = target_x
            return 0.0

        # The exact edge is unsupported. Apply gravity only after reaching it.
        edge = ground.right if player.vx > 0 else ground.x - PLAYER_WIDTH
        time_to_edge = (edge - player.x) / player.vx
        player.x = edge
        player.ground_id = None
        return max(0.0, seconds - time_to_edge)

    def _move_in_air(self, seconds: float) -> None:
        state = self.state
        player = state.player
        landing = first_landing(
            player,
            seconds,
            (platform for platform in self.platforms if platform.is_enabled(state.active_color)),
            state.excluded,
        )
        elapsed = seconds if landing is None else landing[0]
        state.excluded.difference_update(
            platform.id
            for platform in self.platforms
            if platform.id in state.excluded and rose_clear_of(player, platform, elapsed)
        )
        player.x = horizontal_position(player, elapsed)
        if landing is None:
            player.y = vertical_position(player, elapsed)
            player.vy += GRAVITY * elapsed
            return

        ground = landing[1]
        player.y = ground.y - PLAYER_HEIGHT
        player.vy = 0.0
        player.ground_id = ground.id
        if ground.role is Role.GOAL:
            state.phase = Phase.CLEAR
            player.vx = 0.0
            return

        # Preserve the remaining horizontal motion on the landing frame.
        # A second landing cannot occur in this remainder: platform heights
        # are integral and the fall from rest in a frame is less than one pixel.
        airborne = self._move_on_ground(seconds - elapsed)
        if airborne > 0:
            player.x = horizontal_position(player, airborne)
            player.y = vertical_position(player, airborne)
            player.vy = GRAVITY * airborne
