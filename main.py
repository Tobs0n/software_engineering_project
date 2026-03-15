import pygame
import sys
from src.networking.server.server import Server
from src.networking.client.client import Client
from src.networking.networkMessages import NetworkMessage

# --- Constants & Colors ---
COLOR_BG = (25, 25, 30)
COLOR_TEXT = (250, 250, 250)
COLOR_UI = (50, 50, 60)
COLOR_ACCENT = (0, 150, 200)
COLORS_PALETTE = [(255, 50, 50), (50, 255, 50), (50, 50, 255), (255, 255, 50), (255, 50, 255), (50, 255, 255)]

pygame.init()
SCREEN = pygame.display.set_mode((800, 500))
FONT_L = pygame.font.SysFont("Verdana", 40, bold=True)
FONT_M = pygame.font.SysFont("Verdana", 20, bold=True)
FONT_S = pygame.font.SysFont("Verdana", 16)

class Button:
    def __init__(self, x, y, w, h, text, color):
        self.rect = pygame.Rect(x, y, w, h)
        self.text, self.color = text, color
    def draw(self, surf):
        pygame.draw.rect(surf, self.color, self.rect, border_radius=5)
        txt = FONT_M.render(self.text, True, COLOR_TEXT)
        surf.blit(txt, (self.rect.centerx - txt.get_width()//2, self.rect.centery - txt.get_height()//2))

class App:
    def __init__(self):
        self.client = Client()
        self.server = None
        self.state = "MENU"
        
        # User Data
        self.player_name = "Player"
        self.selected_color = COLORS_PALETTE[0]
        self.lobby_code_input = ""
        self.typing_target = "name" # 'name' or 'code'

        # Buttons
        self.btn_join = Button(350, 350, 150, 50, "JOIN", (0, 150, 200))
        self.btn_create = Button(600, 350, 150, 50, "CREATE", (0, 200, 100))

    def host_game(self):
        self.server = Server()
        self.server.start("0.0.0.0", 5555)
        if self.client.connect("127.0.0.1", 5555):
            self.client.send_message(NetworkMessage.CREATE_LOBBY, {
                "name": self.player_name, 
                "color": self.selected_color
            })
            self.state = "LOBBY"

    def join_game(self):
        if self.client.connect("127.0.0.1", 5555): # Replace with specific IP
            self.client.send_message(NetworkMessage.JOIN_LOBBY, {
                "code": self.lobby_code_input,
                "name": self.player_name,
                "color": self.selected_color
            })
            self.state = "LOBBY"

    def draw_menu(self):
        SCREEN.fill(COLOR_BG)
        # --- Row 1: Title ---
        title = FONT_L.render("ULTIMATE P2P GAME", True, COLOR_TEXT)
        SCREEN.blit(title, (400 - title.get_width()//2, 30))

        # --- Row 2: Player Info ---
        # Left: Name Input
        pygame.draw.rect(SCREEN, COLOR_UI, (50, 150, 300, 50), border_radius=5)
        name_label = FONT_S.render("PLAYER NAME:", True, (150, 150, 150))
        SCREEN.blit(name_label, (50, 125))
        name_txt = FONT_M.render(self.player_name + ("|" if self.typing_target == "name" else ""), True, COLOR_TEXT)
        SCREEN.blit(name_txt, (65, 162))

        # Right: Color Picker
        color_label = FONT_S.render("PICK COLOR:", True, (150, 150, 150))
        SCREEN.blit(color_label, (450, 125))
        for i, color in enumerate(COLORS_PALETTE):
            rect = pygame.Rect(450 + (i * 55), 150, 45, 45)
            pygame.draw.rect(SCREEN, color, rect, border_radius=5)
            if self.selected_color == color:
                pygame.draw.rect(SCREEN, COLOR_TEXT, rect, 3, border_radius=5)

        # --- Row 3: Lobby Controls ---
        # Left: Code Input
        code_label = FONT_S.render("LOBBY CODE:", True, (150, 150, 150))
        SCREEN.blit(code_label, (50, 325))
        pygame.draw.rect(SCREEN, COLOR_UI, (50, 350, 200, 50), border_radius=5)
        code_txt = FONT_M.render(self.lobby_code_input + ("|" if self.typing_target == "code" else ""), True, COLOR_TEXT)
        SCREEN.blit(code_txt, (65, 362))

        # Middle/Right: Buttons
        self.btn_join.draw(SCREEN)
        self.btn_create.draw(SCREEN)

    def draw_lobby(self):
        SCREEN.fill(COLOR_BG)
        if not self.client.lobby: return

        code_txt = FONT_M.render(f"ROOM CODE: {self.client.lobby._code}", True, COLOR_ACCENT)
        SCREEN.blit(code_txt, (50, 30))

        for i, p in enumerate(self.client.lobby.players):
            y_pos = 100 + (i * 60)
            # Draw player card background
            pygame.draw.rect(SCREEN, COLOR_UI, (50, y_pos, 700, 50), border_radius=5)
            
            # Draw the player's chosen color as a small block
            pygame.draw.rect(SCREEN, p['color'], (65, y_pos + 10, 30, 30), border_radius=3)
            
            # Draw the player's name
            name_surf = FONT_M.render(p['name'], True, COLOR_TEXT)
            SCREEN.blit(name_surf, (110, y_pos + 12))

    def run(self):
        while True:
            m_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    # Switch typing focus
                    if pygame.Rect(50, 150, 300, 50).collidepoint(m_pos): self.typing_target = "name"
                    elif pygame.Rect(50, 350, 200, 50).collidepoint(m_pos): self.typing_target = "code"
                    
                    # Color selection
                    for i, color in enumerate(COLORS_PALETTE):
                        if pygame.Rect(450 + (i * 55), 150, 45, 45).collidepoint(m_pos):
                            self.selected_color = color
                    
                    # Buttons
                    if self.btn_create.rect.collidepoint(m_pos): self.host_game()
                    if self.btn_join.rect.collidepoint(m_pos): self.join_game()

                if event.type == pygame.KEYDOWN:
                    if self.typing_target == "name":
                        if event.key == pygame.K_BACKSPACE: self.player_name = self.player_name[:-1]
                        else: self.player_name += event.unicode
                    elif self.typing_target == "code":
                        if event.key == pygame.K_BACKSPACE: self.lobby_code_input = self.lobby_code_input[:-1]
                        elif len(self.lobby_code_input) < 4: self.lobby_code_input += event.unicode.upper()

            self.draw_menu() if self.state == "MENU" else self.draw_lobby()
            pygame.display.flip()

if __name__ == "__main__":
    App().run()