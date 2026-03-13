import pygame
from entities import UnitType, Entity
from player import Player
from hud import Hud

def main(players):
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    clock = pygame.time.Clock()

    hud = Hud(players)

    running = True
    while running:
        screen.fill((0, 0, 0))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        hud.draw(screen)
        pygame.display.flip()
        clock.tick(60)
    
    
