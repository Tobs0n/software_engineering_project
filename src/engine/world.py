from __future__ import annotations
import pygame

from .world_config import WorldConfig
from .physics_body import PhysicsBody


class World:
    """
    The simulated world-space a Game lives in.
    Runs a fixed-style physics integration and AABB collision detection.
    Games register a collision callback via add_collision_callback().
    """

    def __init__(self, config: WorldConfig):
        self.config:     WorldConfig      = config
        self.bodies:     list[PhysicsBody] = []
        self.tick_rate:  int               = 60
        self._callbacks: list              = []

    # ── Body management ───────────────────────────────────────────────────────

    def add_body(self, body: PhysicsBody) -> None:
        self.bodies.append(body)

    def remove_body(self, body: PhysicsBody) -> None:
        if body in self.bodies:
            self.bodies.remove(body)

    def clear(self) -> None:
        self.bodies.clear()
        self._callbacks.clear()

    def add_collision_callback(self, cb) -> None:
        """cb(a: PhysicsBody, b: PhysicsBody) — called for every overlapping pair."""
        self._callbacks.append(cb)

    # ── Simulation ────────────────────────────────────────────────────────────

    def step(self, dt: float) -> None:
        """Advance the simulation by dt seconds."""
        if not self.config.has_physics:
            if self.config.has_collisions:
                self.resolve_collisions()
            return

        gx = self.config.gravity * self.config.gravity_dir[0]
        gy = self.config.gravity * self.config.gravity_dir[1]
        tv = self.config.terminal_velocity
        bounds = pygame.Rect(*self.config.bounds)

        for body in self.bodies:
            if body.is_static:
                continue

            # Gravity
            body.velocity.x += gx * dt
            body.velocity.y += gy * dt

            # Clamp to terminal velocity
            body.velocity.x = max(-tv, min(tv, body.velocity.x))
            body.velocity.y = max(-tv, min(tv, body.velocity.y))

            # Integrate position
            body.position.x += body.velocity.x
            body.position.y += body.velocity.y

            # Horizontal friction
            body.velocity.x *= self.config.friction

            # World boundary response
            rect = body.get_world_rect()
            body.is_grounded = False

            if rect.bottom >= bounds.bottom:
                body.position.y = bounds.bottom - rect.height
                body.velocity.y = 0.0
                body.is_grounded = True
            if rect.top <= bounds.top:
                body.position.y = float(bounds.top)
                body.velocity.y = 0.0
            if rect.left <= bounds.left:
                body.position.x = float(bounds.left)
                body.velocity.x = 0.0
            if rect.right >= bounds.right:
                body.position.x = float(bounds.right - rect.width)
                body.velocity.x = 0.0

        if self.config.has_collisions:
            self.resolve_collisions()

    def resolve_collisions(self) -> None:
        """Broad-phase O(n^2) AABB check — fires callbacks for overlapping bodies."""
        for i in range(len(self.bodies)):
            for j in range(i + 1, len(self.bodies)):
                a = self.bodies[i]
                b = self.bodies[j]
                if a.is_static and b.is_static:
                    continue
                if a.get_world_rect().colliderect(b.get_world_rect()):
                    for cb in self._callbacks:
                        cb(a, b)

    # ── Queries ───────────────────────────────────────────────────────────────

    def query_rect(self, rect: pygame.Rect) -> list[PhysicsBody]:
        """Return all bodies whose world rect overlaps the given rect."""
        return [b for b in self.bodies if b.get_world_rect().colliderect(rect)]
