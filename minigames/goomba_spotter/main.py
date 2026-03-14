import pygame
from entities import UnitType, Entity
from player import Player
from hud import Hud
import random

def main(players):
    """
    Runs the minigame
    """
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    clock = pygame.time.Clock()

    unit_1 = UnitType(color=(139, 90, 43), radius=20) # Goomba
    unit_2 = UnitType(color=(50, 50, 180), radius=15) # Buzzy Beetle
    unit_types = [unit_1, unit_2]

    hud = Hud(players)
    active_units = []
    spawn_timer = 0
    correct_count = 0

    KEY_BINDINGS = {                # Temporary keybinds for testing purposes
        pygame.K_q: 0,  # speler 1
        pygame.K_p: 1,  # speler 2
        pygame.K_z: 2,  # speler 3
        pygame.K_m: 3,  # speler 4
    }


    running = True
    while running:
        screen.fill((0, 0, 0))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # TODO: replace with network input when multiplayer is implemented
            if event.type == pygame.KEYDOWN:
                if event.key in KEY_BINDINGS:
                    player_index = KEY_BINDINGS[event.key]
                    if player_index < len(players):
                        players[player_index].increment()
            

        for unit in active_units[:]: # Move the units
            unit.move()
            unit.draw(screen)
            if unit.is_offscreen(screen.get_width()): # Remove the unit if offscreen
                active_units.remove(unit)

        hud.draw(screen)
        pygame.display.flip()
        clock.tick(60)
    
        spawn_timer += 1
        if spawn_timer % 60 == 0: # If the timer hits 60 (every second), spawn a new random unit
            spawn = random.choice(unit_types)
            position = pygame.Vector2(-20, random.randint(50, 550))
            speed = pygame.Vector2(random.uniform(2, 5), 0)
            unit = Entity(speed, position, spawn.color, spawn.radius)
            active_units.append(unit)
            if spawn == unit_1:
                correct_count += 1
            
        if spawn_timer == 600:
            show_results(screen, players, correct_count)
            running = False


def show_results(screen, players, correct_count):
    font_big = pygame.font.SysFont(None, 72)
    font_small = pygame.font.SysFont(None, 36)
    screen.fill((0, 0, 0))

    winner = min(players, key=lambda p: abs(p.goombacounter - correct_count))

    for i, player in enumerate(players):
        if player == winner:
            color = (0, 255, 0)
            text = font_big.render(f"The winner is {player.player_name}: {player.goombacounter}", True, color)
        else: 
            color = (255, 255, 255)
            text = font_small.render(f"{player.player_name}: {player.goombacounter}", True, color)
        screen.blit(text, (200, 200 + i * 50))

    pygame.display.flip()
    pygame.time.wait(5000) # Show for 5 seconds

if __name__ == "__main__":
    players = [Player(1, "Speler 1"), Player(2, "Speler 2")]
    main(players)
