from minigames.avoid_fireballs.avoid_fireballs_game import AvoidFireballsGame
from minigames.bomb.bomb_game import BombGame
from minigames.donkey_kong_counting.dk_counting_game import DKCountingGame
from minigames.pingpong.pingpong_game import PingpongGame
from minigames.snake.snake_game import SnakeGame
from minigames.goomba.goomba_game import GoombaGame

# ── Registry: add new minigames here ─────────────────────────────────────────
GAME_REGISTRY: dict[str, type] = {
    "bomb":            BombGame,
    "dkcounting":      DKCountingGame,
    "snake":           SnakeGame,
    "avoid_fireballs": AvoidFireballsGame,
    "pong":            PingpongGame,
    "goomba_counting": GoombaGame,
}

W, H = 800, 600
FPS  = 60

COLORS = [
    (255, 80,  80),
    (80,  160, 255),
    (80,  220, 100),
    (255, 200, 50),
    (200, 80,  220),
    (255, 140, 30),
]