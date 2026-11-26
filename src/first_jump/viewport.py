from dataclasses import dataclass

from .stage import HEIGHT, WIDTH


@dataclass(frozen=True)
class Rectangle:
    x: int
    y: int
    width: int
    height: int

    def contains(self, point: tuple[float, float] | None) -> bool:
        if point is None:
            return False
        x, y = point
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


@dataclass(frozen=True)
class Viewport:
    scale: float
    left: float
    top: float

    @classmethod
    def fit(cls, width: int, height: int) -> "Viewport":
        scale = min(width / WIDTH, height / HEIGHT)
        return cls(scale, (width - WIDTH * scale) / 2, (height - HEIGHT * scale) / 2)

    def to_logical(self, point: tuple[int, int]) -> tuple[float, float] | None:
        if self.scale <= 0:
            return None
        x, y = point
        if (
            self.left <= x < self.left + WIDTH * self.scale
            and self.top <= y < self.top + HEIGHT * self.scale
        ):
            return (x - self.left) / self.scale, (y - self.top) / self.scale
        return None


RETRY_BUTTON = Rectangle(250, 175, 140, 29)
