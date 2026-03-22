import pygame
import sys
import os
from timing_game import TimingGame
from player import Player

def main():
    # 1. INITIALISATIE
    pygame.init()
    WIDTH, HEIGHT = 1024, 768
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Donkey Kong Counter Challenge")
    clock = pygame.time.Clock()

    # 2. SPELERS AANMAKEN 
    players = [
        Player("Speler 1", (255, 0, 0), "P1"),
        Player("Speler 2", (0, 0, 255), "P2"),
        Player("Speler 3", (0, 0, 255), "P2"),
        Player("Speler 4", (0, 0, 255), "P2")
    ]

    # 3. MINIGAME INSTANTIE
    minigame = TimingGame(screen, players)

    # 4. GAME LOOP
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            minigame.handle_input(event)

        minigame.update() 
        minigame.draw()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()