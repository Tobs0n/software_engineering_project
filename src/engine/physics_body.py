from __future__ import annotations
import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..abstract.player_game_extension import PlayerGameExtension


class PhysicsBody:
    """
    A 2-D axis-aligned rectangular rigid body.
    Owned by a PlayerGameExtension; simulated by World.step().
    """

    def __init__(
        self,
        x: float, y: float,
        width: int, height: int,
        mass: float = 1.0,
        is_static: bool = False,
    ):
        self.position   = pygame.Vector2(x, y)
        self.velocity   = pygame.Vector2(0, 0)
        self.bbox       = pygame.Rect(0, 0, width, height)   # local, position is origin
        self.mass       = mass
        self.is_static  = is_static
        self.is_grounded = False
        self.owner: PlayerGameExtension | None = None         # back-reference

    # ── Force / impulse ───────────────────────────────────────────────────────

    def apply_force(self, f: pygame.Vector2) -> None:
        """Add a continuous force (divided by mass, accumulates over frames)."""
        if not self.is_static:
            self.velocity += f / self.mass

    def apply_impulse(self, f: pygame.Vector2) -> None:
        """Add an instant velocity change (mass-independent)."""
        if not self.is_static:
            self.velocity += f

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_world_rect(self) -> pygame.Rect:
        """Return the bounding rect in world coordinates."""
        return pygame.Rect(
            int(self.position.x), int(self.position.y),
            self.bbox.width, self.bbox.height,
        )

    def __repr__(self) -> str:
        return (
            f"PhysicsBody(pos={self.position}, "
            f"vel={self.velocity}, "
            f"size=({self.bbox.width},{self.bbox.height}))"
        )
