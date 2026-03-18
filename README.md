# MiniParty

Mario Party-style local multiplayer minigame platform built with Python + Pygame.

## Structure

```
miniparty/
├── main_server.py        # Run the game server
├── main_client.py        # Run a game client (one per player)
└── src/
    ├── abstract/         # Base classes: Game, Player, PlayerGameExtension
    ├── engine/           # GameEngine, World, WorldConfig, PhysicsBody
    ├── network/          # Server, Client, NetworkMessages
    ├── session/          # Lobby, LobbyState, GamePlaylist
    └── minigames/
        ├── bomb/         # Hot Potato bomb game
        └── platformer/   # Coin-collecting platformer
```

## Running

### 1. Install dependencies
```bash
pip install pygame
```

### 2. Start the server
```bash
python main_server.py
```

### 3. Start a client (repeat for each player)
```bash
python main_client.py
```

## How to play

1. One player clicks **Create** — they become the host and get a 5-letter lobby code.
2. Other players enter the code and click **Join**.
3. Host clicks **Start** to begin.
4. Minigames are selected from the playlist (random by default).
5. Stars are awarded after each game. Most stars wins.

## Adding a new minigame

1. Create `src/minigames/<yourgame>/<yourgame_extension>.py` extending `PlayerGameExtension`
2. Create `src/minigames/<yourgame>/<yourgame>.py` extending `Game`
3. Implement all abstract methods, especially `get_world_config()` and `create_extension()`
4. Register your game class in `main_client.py`'s `GAME_REGISTRY`

## Controls

### Bomb game
| Key | Action |
|-----|--------|
| WASD | Move |
| SPACE | Throw bomb to nearest player |
