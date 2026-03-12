class Player:
    def __init__(self, value, name):
        self.player_value = value
        self.player_name = name
        self.goombacounter = 0

    def increment(self):
        self.goombacounter += 1