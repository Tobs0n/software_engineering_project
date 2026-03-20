import pygame
import sys
import random 
import os
from player import Player
from tiles import Tiles

class Game:
    def __init__(self):
        #Initializing game 
        pygame.init()
        self.current_path = os.path.dirname(__file__)
        bg_path = os.path.join(self.current_path, "sprites", "background", "bg.png")       
        self.SPAWN_EVENT = pygame.USEREVENT + 1
        pygame.time.set_timer(self.SPAWN_EVENT, 1000) 

        # Display 
        self.screen_width = 800
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))

        try:
            self.background = pygame.image.load(bg_path).convert()
            self.background = pygame.transform.scale(self.background, (800, 600))
        except pygame.error as e:
            print(f"Fout bij achtergrond: {e}")
            self.background = pygame.Surface((800, 600))
            self.background.fill((30, 30, 30))

        pygame.display.set_caption("Platformer")
        

        #Init player controls
        
        p1_controls = {
            'left': pygame.K_a,
            'right': pygame.K_d,
            'up': pygame.K_w,
            'down': pygame.K_s
        }

        p2_controls = {
            'left': pygame.K_LEFT,
            'right': pygame.K_RIGHT,
            'up': pygame.K_UP,
            'down': pygame.K_DOWN
        }

        p3_controls = {
            'left': pygame.K_j,
            'right': pygame.K_l,
            'up': pygame.K_i,
            'down': pygame.K_k
        }

        p4_controls = {
            'left': pygame.K_f,
            'right': pygame.K_h,
            'up': pygame.K_t,
            'down': pygame.K_g
        }
        
        self.player_one = Player(100, 100, 1, p1_controls)
        self.player_two = Player(200, 100, 2, p2_controls)
        self.player_three = Player(100, 200, 3, p3_controls)
        self.player_four = Player(200, 200, 4, p4_controls)
        
        
        # Fps control 
        self.clock = pygame.time.Clock()
        self.running = True
        self.game_over = False
        self.winner = None

        #Set up sprite group and tiles group
        self.all_sprites = pygame.sprite.Group()
        self.all_sprites.add(self.player_one)
        self.all_sprites.add(self.player_two)
        self.all_sprites.add(self.player_three)
        self.all_sprites.add(self.player_four)

        self.player_group = pygame.sprite.Group()
        self.player_group.add(self.player_one)
        self.player_group.add(self.player_two)
        self.player_group.add(self.player_three)
        self.player_group.add(self.player_four)

        self.tiles = pygame.sprite.Group()

       

    def run(self):
        while self.running:
            self.handle_events()  # Checking inputs 
            self.update()         # Movement/collision handling
            self.draw()           # Showing attributes
            self.clock.tick(60)   # 60 fps

    def handle_events(self): #Shutdown 
        for event in pygame.event.get():  
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == self.SPAWN_EVENT and not self.game_over:
                self.spawn_tile()

    def update(self): 
        if self.game_over:
            return

        self.player_one.update()
        self.player_two.update()
        self.player_three.update()
        self.player_four.update()

        # Update falling fireballs
        for tile in self.tiles.sprites():
            tile.update()

        # Player-fireball collisions: decrement lives only
        for p in list(self.player_group):
            hit_tiles = pygame.sprite.spritecollide(p, self.tiles, True)
            if hit_tiles:
                decrement = len(hit_tiles)
                p.lives -= decrement
                if p.lives <= 0:
                    p.lives = 0
                    p.kill()  # remove player when lives are gone

        # Check for last player alive
        alive_players = self.player_group.sprites()
        if len(alive_players) <= 1:
            self.game_over = True
            pygame.time.set_timer(self.SPAWN_EVENT, 0)
            if len(alive_players) == 1:
                self.winner = alive_players[0].player_num
            else:
                self.winner = None

        # Bounce players apart on collision
        for p in self.player_group:
            hits = pygame.sprite.spritecollide(p, self.player_group, False)
            for other in hits:
                if other is p:
                    continue
                dx = p.rect.centerx - other.rect.centerx
                dy = p.rect.centery - other.rect.centery
                if dx == 0 and dy == 0:
                    dx = 1
                dist = (dx * dx + dy * dy) ** 0.5
                nx = dx / dist
                ny = dy / dist
                p.rect.x += int(nx * 10)
                p.rect.y += int(ny * 10)

        # Bounce players apart on collision
        for p in self.player_group:
            hits = pygame.sprite.spritecollide(p, self.player_group, False)
            for other in hits:
                if other is p:
                    continue
                dx = p.rect.centerx - other.rect.centerx
                dy = p.rect.centery - other.rect.centery
                if dx == 0 and dy == 0:
                    dx = 1
                dist = (dx * dx + dy * dy) ** 0.5
                nx = dx / dist
                ny = dy / dist
                p.rect.x += int(nx * 10)
                p.rect.y += int(ny * 10)


    def draw(self): #BACKGROUND 
        self.screen.fill((30, 30, 30)) 
        self.screen.blit(self.background, (0, 0))
        middle_x = self.screen_width //2 
        pygame.draw.line(self.screen, (0,0,0), (middle_x, 0), (middle_x, self.screen_height), 5)
        self.font = pygame.font.SysFont(None, 36)

        # Draw lives for each player
        lives_text_1 = self.font.render(f"P1 Lives: {self.player_one.lives}", True, (255,255,255))
        lives_text_2 = self.font.render(f"P2 Lives: {self.player_two.lives}", True, (255,255,255))
        lives_text_3 = self.font.render(f"P3 Lives: {self.player_three.lives}", True, (255,255,255))
        lives_text_4 = self.font.render(f"P4 Lives: {self.player_four.lives}", True, (255,255,255))
        self.screen.blit(lives_text_1, (10, 10))
        self.screen.blit(lives_text_2, (10, 40))
        self.screen.blit(lives_text_3, (10, 70))
        self.screen.blit(lives_text_4, (10, 100))

        # No score display; using lives only

        # Draw everything
        self.all_sprites.draw(self.screen)

        if self.game_over:
            overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            self.screen.blit(overlay, (0, 0))

            done_text = self.font.render("Game done", True, (255, 255, 255))
            if self.winner is not None:
                win_text = self.font.render(f"Player {self.winner} wins!", True, (255, 215, 0))
            else:
                win_text = self.font.render("No winner", True, (255, 215, 0))

            self.screen.blit(done_text, (self.screen_width // 2 - done_text.get_width() // 2, self.screen_height // 2 - 40))
            self.screen.blit(win_text, (self.screen_width // 2 - win_text.get_width() // 2, self.screen_height // 2 + 10))

        pygame.display.flip()

    def spawn_tile(self):
        random_x = random.randint(0, 760)

        new_tile = Tiles(random_x, -50) 
 
        self.all_sprites.add(new_tile)
        self.tiles.add(new_tile)


if __name__ == "__main__":
    game = Game()
    game.run()
    pygame.quit()
    sys.exit()