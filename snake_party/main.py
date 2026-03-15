import pygame
import sys
from entities import Snake
from entities import Apple
from player import Player

# INSTELLINGEN
WIDTH, HEIGHT = 800, 600
GRID_SIZE = 20
FPS = 10  
GROW_INTERVAL = 2000 # in miliseconden

def main(players):
    """
    De hoofd-functie van de Snake minigame.
    'players' is een lijst met Player-objecten van het hoofdbord.
    """
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Snake Survival")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)

    # PLAYER SETUP
    # Besturing instellen voor maximaal 4 spelers
    controls = [
        {'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d},      # P1
        {'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT, 'right': pygame.K_RIGHT}, # P2
        {'up': pygame.K_i, 'down': pygame.K_k, 'left': pygame.K_j, 'right': pygame.K_l},      # P3
        {'up': pygame.K_KP8, 'down': pygame.K_KP5, 'left': pygame.K_KP4, 'right': pygame.K_KP6} # P4
    ]

    # 2. Slangen aanmaken
    snakes = []
    start_positions = [
        pygame.Vector2(100, 100), 
        pygame.Vector2(WIDTH - 100, 100), 
        pygame.Vector2(100, HEIGHT - 100), 
        pygame.Vector2(WIDTH - 100, HEIGHT - 100)
    ]
    start_directions = [
        pygame.Vector2(20, 0),  
        pygame.Vector2(-20, 0), 
        pygame.Vector2(20, 0),  
        pygame.Vector2(-20, 0)  
    ]

    for i, p in enumerate(players):
        if i < len(controls):
            # Geef nu ook de richting mee aan de Snake
            new_snake = Snake(p, start_positions[i], controls[i], start_directions[i])
            snakes.append(new_snake)
    last_growth_time = pygame.time.get_ticks()

    ranking = []
    apple = Apple(GRID_SIZE, WIDTH, HEIGHT)
    floating_messages = []

    # GAME LOOP
    running = True
    while running:
        current_time = pygame.time.get_ticks()
        should_grow = False

        # Check of het tijd is om te groeien
        if current_time - last_growth_time >= GROW_INTERVAL:
            should_grow = True
            last_growth_time = current_time

        # INPUT HANDLING
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            for s in snakes:
                s.handle_input(event)

        # LOGICA (Beweging & Botsingen)
        alive_snakes = [s for s in snakes if s.is_alive]
        
        for s in alive_snakes:
            s.move(grow=should_grow)
            if s.speed_timer > 0:
                s.move(grow=False)
                s.speed_timer -= 1
            head = s.body[0]

            # Check muren
            if head.x < 0 or head.x >= WIDTH or head.y < 0 or head.y >= HEIGHT:
                s.is_alive = False
                ranking.append(s.player)
                continue 
            
            if s.ghost_timer <= 0:
            # Check lichamen
                for other_s in snakes:
                    for i, segment in enumerate(other_s.body):
                        if s == other_s and i == 0:
                            continue
                        if head == segment:
                            s.is_alive = False
                            ranking.append(s.player)
                            break 
                    if not s.is_alive:
                        break

            # Check Appels     
            if s.body[0] == apple.pos:
                msg_text = ""
                msg_color = (255, 255, 255)

                if apple.type == "gold":
                    s.double_length()
                    msg_text = "2X SIZE!"
                    msg_color = (255, 215, 0)
                elif apple.type == "white":
                    s.ghost_timer = 80 # 8 seconden bij FPS = 10
                    msg_text = "GHOST MODE"
                    msg_color = (255, 255, 255)
                elif apple.type == "blue":
                    s.speed_timer = 30 # 3 seconden turbo
                    msg_text = "2X SSSPEED!"
                    msg_color = (0, 150, 255)
                else: # Rode appeltje
                    s.body.append(pygame.Vector2(s.body[-1]))
                    msg_text = "+1"
                    msg_color = (255, 0, 0)

                # Tekstje
                floating_messages.append({
                    "text": msg_text,
                    "pos": pygame.Vector2(apple.pos),
                    "color": msg_color,
                    "life": 30
                })
                # Spawn appeltje
                apple = Apple(GRID_SIZE, WIDTH, HEIGHT)

        # CHECK WINNAAR
        if len([s for s in snakes if s.is_alive]) <= 1 and len(players) > 1:
            running = False

        # TEKENEN
        screen.fill((20, 20, 20)) # Achtergrond
        
        # Teken een grid
        for x in range(0, WIDTH, GRID_SIZE):
            pygame.draw.line(screen, (40, 40, 40), (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, GRID_SIZE):
            pygame.draw.line(screen, (40, 40, 40), (0, y), (WIDTH, y))

        # Teken appeltjes
        apple.draw(screen)

        # Teken slangetjes
        for s in snakes:
            s.draw(screen)

        # Teken Tekstjes
        for msg in floating_messages[:]: 
            if msg["life"] > 0:
                text_surf = font.render(msg["text"], True, msg["color"])
                screen.blit(text_surf, (msg["pos"].x, msg["pos"].y)) 
                # Zweefeffect
                msg["pos"].y -= 2 
                msg["life"] -= 1
            else:
            
                floating_messages.remove(msg)

        # Toon hoe lang het nog duurt tot de volgende groei
        time_left = max(0, (GROW_INTERVAL - (current_time - last_growth_time)) // 1000)
        timer_text = font.render(f"Groei over: {time_left+1}s", True, (255, 255, 255))
        screen.blit(timer_text, (WIDTH // 2 - 50, 10))

        pygame.display.flip()
        clock.tick(FPS)

    # RESULTATEN
    survivors = [s.player for s in snakes if s.is_alive]
    for p in survivors:
        if p not in ranking:
            ranking.append(p)
    ranking.reverse() 

    # Kleine test
    print(f"Game over! Winnaar: {ranking[0].player_name}")

    pygame.time.wait(2000)
    return ranking 

# --- TEST SECTIE ---
if __name__ == "__main__":
    test_players = [
        Player(1, "TEST spelertje 1", (0, 255, 0)),
        Player(2, "TEST Spelertje 2", (0, 100, 255))
    ]
    main(test_players)