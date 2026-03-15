
class Lobby:
    def __init__(self, code : str):
        self._code = code
        self.players = []
        self.playlist = []
        self.engine = None # game engine instance
        self.state = None # lobby state (waiting, in-game, finished)

    def add_player(self, player):
        pass

    def remove_player(self, player):
        pass

    def get_host(self):
        pass

    def start_next_game(self):
        pass

    def end_current_game(self):
        pass

    def award_points(self, results):
        pass