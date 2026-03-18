class Player:
    def __init__(self, value, name, color=(0, 255, 0)):
        self.player_value = value
        self.player_name = name
        self.color = color
        self.score = 0 # Dit mag je hernoemen naar 'score' als je wilt