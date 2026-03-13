class Player:
    def __init__(self, value, name):
        """
        A player has a chosen name and a player id used for placement on the screen.
        Id ranges from 1 to 4, which is consistent across all minigames in the project.
        """
        self.player_value = value
        self.player_name = name
        self.goombacounter = 0

    def increment(self):
        """
        Used when a player 'counts' an entity
        """
        self.goombacounter += 1