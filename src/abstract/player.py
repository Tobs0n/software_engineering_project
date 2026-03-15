from __future__ import annotations


class Player:
    """
    Represents one participant across all minigames.
    `stars` accumulates across rounds.
    `extension` is swapped per game via GameEngine.load_game().
    """

    def __init__(self, name: str, color: tuple):
        self.player_id: str     = ""          # assigned by Server
        self.name: str          = name
        self.color: tuple       = color
        self.stars: int         = 0
        self.is_host: bool      = False
        self.extension          = None        # PlayerGameExtension | None

    # ── Extension management ──────────────────────────────────────────────────

    def set_extension(self, ext) -> None:
        self.extension = ext
        if ext is not None:
            ext.player = self

    def reset_extension(self) -> None:
        if self.extension is not None:
            self.extension.reset()

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "name":      self.name,
            "color":     list(self.color),
            "stars":     self.stars,
            "is_host":   self.is_host,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Player:
        p = cls(data["name"], tuple(data["color"]))
        p.player_id = data.get("player_id", "")
        p.stars     = data.get("stars", 0)
        p.is_host   = data.get("is_host", False)
        return p

    def __repr__(self) -> str:
        return f"Player({self.name!r}, stars={self.stars}, host={self.is_host})"
