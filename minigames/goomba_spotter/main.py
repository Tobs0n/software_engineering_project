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
    unit_3 = UnitType(color=(100, 10, 30), radius=30)
    unit_types = [unit_1, unit_1, unit_2, unit_3] # Bigger chance of spawning 'Goomba'

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
            unit.move(screen.get_height())
            unit.draw(screen)
            if unit.is_offscreen(screen.get_width()): # Remove the unit if offscreen
                bounce = random.randint(0, 1)
                if bounce == 0:
                    active_units.remove(unit)
                else:
                    unit.x_speed *= -1

        hud.draw(screen)
        pygame.display.flip()
        clock.tick(60)
    
        spawn_timer += 1
        if spawn_timer % 30 == 0 and spawn_timer < 3600: # If the timer hits 30 (every 0.5 seconds), spawn a new random unit
            spawn = random.choice(unit_types)            # Also stop spawning after a minute
            y_position = random.randint(50, 550)
            y_speed = random.uniform(-2, 2)
            
            side = random.choice(["left", "right"])
            if side == "left":
                x_position = -10
                x_speed = random.uniform(4, 10)
            else:
                x_position = screen.get_width() + 10
                x_speed = random.uniform(-4, -10)
            
            unit = Entity(x_speed, y_speed, x_position, y_position, spawn.color, spawn.radius)
            active_units.append(unit)
            if spawn == unit_1:
                correct_count += 1
        
        if spawn_timer == 3780: # Players get three extra seconds to increase their counter
            show_results(screen, players, correct_count)
            running = False


def show_results(screen, players, correct_count):
    font_big = pygame.font.SysFont(None, 72)
    font_small = pygame.font.SysFont(None, 36)
    screen.fill((0, 0, 0))

    correct_text = font_small.render(f"The correct count was {correct_count}", True, (0, 0, 255))
    x_pos = (screen.get_width() - correct_text.get_width()) // 2
    screen.blit(correct_text, (x_pos, 100))

    ranking = sorted(players, key=lambda p: abs(p.goombacounter - correct_count))
    best_score = abs(ranking[0].goombacounter - correct_count)
    winners = [p for p in ranking if abs(p.goombacounter - correct_count) == best_score]
    
    for i, player in enumerate(ranking):
        if player in winners:
            color = (0, 255, 0)
            text = font_big.render(f"Winner: {player.player_name}: {player.goombacounter}", True, color)
        else:
            color = (255, 255, 255)
            text = font_small.render(f"{player.player_name}: {player.goombacounter}", True, color)
        screen_width = screen.get_width()
        x_pos = (screen_width - text.get_width()) // 2
        screen.blit(text, (x_pos, 200 + i * 70))

    pygame.display.flip()
    pygame.time.wait(5000) # Show for 5 seconds

if __name__ == "__main__":
    players = [Player(1, "Speler 1"), Player(2, "Speler 2"), Player(3, "Speler 3"), Player(4, "Speler 4")]
    main(players)