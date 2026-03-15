from dataclasses import dataclass, field


@dataclass
class WorldConfig:
    """
    All physics settings for one minigame's world.
    Returned by Game.get_world_config() so each game declares its own rules.
    """
    gravity:           float = 0.0           # pixels per frame² applied along gravity_dir
    gravity_dir:       tuple = (0, 1)        # unit vector; (0,1) = downward
    has_physics:       bool  = False         # enable velocity integration
    has_collisions:    bool  = True          # enable body-vs-body overlap checks
    bounds:            tuple = (0, 0, 800, 600)  # (x, y, width, height) world rect
    friction:          float = 0.85          # velocity multiplier per frame (horizontal)
    terminal_velocity: float = 20.0          # max speed in any axis
