from player import Player
import pygame

class Hud:
    def __init__(self, players: list[Player]):
        
        self.players = players

    def draw(self, surface):
        """
        Display the players on the screen with their name and counter
        """
        width, height = surface.get_size()
        font = pygame.font.SysFont(None, 36)
        for player in self.players:
            if player.player_value in [1,2]: # places player 1 and 2 at the top of the screen
                y = height - 50
            else:
                y = 0
            if player.player_value in [2,4]: # places player 2 and 4 at the right of the screen
                x = width - 200
            else:
                x = 0
            text = font.render(f"{player.player_name}: {player.goombacounter}", True, (255, 255, 255))
            surface.blit(text, (x, y))  # display at location (x, y)