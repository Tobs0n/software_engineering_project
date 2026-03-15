import pygame
import random
import os

class TimingGame:
    def __init__(self, screen, players):
        self.screen = screen
        self.players = players
        
        # Start-toestand en variabelen
        self.state = "BOSJES"
        self.state_start_time = pygame.time.get_ticks()
        self.target_time = random.randint(10, 30)
        self.start_ticks = 0
        self.results = {}

        #  Afbeeldingen 
        path = os.path.dirname(__file__)
        filenames = [
            "Counter-verstopt-in-de-bosjes.png", "Counter-welkom.png",
            "Counter-spelregels-uitleggen.png", "Counter-aan-het-slapen.png",
            "Counter-tromgeroffel.png", "Counter-berekenen.png",
            "Counter-winnaar-bekend-maken.png"
        ]

        # TEKST
        font_path = os.path.join(path, "Galindo-Regular.ttf")
        self.font = pygame.font.Font(font_path, 30)
        
        self.images_data = {}
        for f in filenames:
            full_path = os.path.join(path, f)
            img = pygame.image.load(full_path).convert_alpha()
            orig_size = img.get_size()
            
            # Berekening beeldverhouding
            scale_x = screen.get_width() / orig_size[0]
            scale_y = screen.get_height() / orig_size[1]
            scale = min(scale_x, scale_y)
            final_size = (int(orig_size[0] * scale), int(orig_size[1] * scale))
            img = pygame.transform.smoothscale(img, final_size)
            self.images_data[f] = {
                'image': img,
                'pos': (screen.get_width() // 2 - final_size[0] // 2, 
                        screen.get_height() // 2 - final_size[1] // 2),
                'scale': scale,
                'orig_size': orig_size
            }

        # Tekstvak positie van tekst
        self.orig_text_box = {
            "Counter-verstopt-in-de-bosjes.png": {'top_left': (1500, 180),  'size': (1000, 220)},
            "Counter-welkom.png":               {'top_left': (1500, 180),  'size': (1000, 220)},
            "Counter-spelregels-uitleggen.png": {'top_left': (1500, 180),  'size': (1000, 225)},
            "Counter-aan-het-slapen.png":       {'top_left': (1500, 180),  'size': (1000, 200)},
            "Counter-tromgeroffel.png":         {'top_left': (1500, 180),  'size': (1000, 220)},
            "Counter-berekenen.png":           {'top_left': (1500, 180),  'size': (1000, 220)},
            "Counter-winnaar-bekend-maken.png": {'top_left': (1500, 180),  'size': (1000, 220)}
        }

    def _wrap_text(self, text, font, max_width):
        """Hulpfunctie om tekst netjes af te breken binnen een breedte"""
        words = text.split(' ')
        lines = []
        current_line = []
        for word in words:
            current_line.append(word)
            test_line = ' '.join(current_line)
            if font.size(test_line)[0] > max_width:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))
        return lines

    # Veranderen van afbeelding
    def update(self):
        """Regelt de automatische tijd-overgangen"""
        now = pygame.time.get_ticks()
        elapsed = (now - self.state_start_time) / 1000.0

        if self.state == "WELKOM" and elapsed > 8.0:
            self.change_state("UITLEG")
        elif self.state == "UITLEG" and elapsed > 8.0:
            self.change_state('UITLEG2')
        elif self.state == "UITLEG2" and elapsed > 5.0:
            self.change_state("SLAPEN")
            self.start_ticks = pygame.time.get_ticks()
        elif self.state == "BEREKENEN" and elapsed > 8.0:
            self.change_state("WINNAAR")

    def change_state(self, new_state):
        self.state = new_state
        self.state_start_time = pygame.time.get_ticks()

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if self.state == "BOSJES" and event.key == pygame.K_SPACE:
                self.change_state("WELKOM")
            elif self.state == "SLAPEN":
                # Toetsenbord indeling: 
                # P1: A | P2: S | P3: K | P4: L <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                keys = [pygame.K_a, pygame.K_s, pygame.K_k, pygame.K_l]
                
                now = pygame.time.get_ticks()
                for i, p in enumerate(self.players):
                    if i < len(keys) and event.key == keys[i]:
                        if p.player_name not in self.results:
                            diff = abs(self.target_time - (now - self.start_ticks) / 1000.0)
                            self.results[p.player_name] = diff
# debug
                            print(f"{p.player_name} stopte op {diff:.2f}s verschil!" )
                if len(self.results) == len(self.players):
                    self.change_state("BEREKENEN")

    # geeft ranking
    def get_leaderboard(self):
        """Geeft een lijst terug van (naam, verschil) gesorteerd op winst"""
        sorted_results = sorted(self.results.items(), key=lambda item: item[1])
        
        return sorted_results 
    
    # Scherm vullen
    def draw(self):
        self.screen.fill((50, 50, 50))
        
        img_map = {
            "BOSJES": "Counter-verstopt-in-de-bosjes.png", "WELKOM": "Counter-welkom.png",
            "UITLEG": "Counter-spelregels-uitleggen.png", "UITLEG2": "Counter-spelregels-uitleggen.png", "SLAPEN": "Counter-aan-het-slapen.png",
            "BEREKENEN": "Counter-tromgeroffel.png", "WINNAAR": "Counter-winnaar-bekend-maken.png"
        }
        
        # Teken de gecentreerde afbeelding
        current_img_key = img_map[self.state]
        img_data = self.images_data[current_img_key]
        self.screen.blit(img_data['image'], img_data['pos'])
        
        # Teken de tekst in het tekstvak
        current_text_box = self.orig_text_box[current_img_key]
        if current_text_box:
            scale = img_data['scale']
            offset_x, offset_y = img_data['pos']
            scr_x = offset_x + current_text_box['top_left'][0] * scale
            scr_y = offset_y + current_text_box['top_left'][1] * scale
            scr_w = current_text_box['size'][0] * scale
            scr_h = current_text_box['size'][1] * scale
            
            # Tekst bepalen en word-wrappen
            text_str = ""
            if self.state == 'BOSJES':
                text_str = 'Press on SPACE-button to start the game and to reveal your game-host.'
            elif self.state == "WELKOM":
                namen_lijst = [str(p.player_name) for p in self.players]
                namen = ", ".join(namen_lijst)
                text_str = f"It's me Donkey Kong! Welcome {namen}. Let's play a simple game!"
            elif self.state == "UITLEG":
                text_str = f"Count the target seconds in your head.Press your button at the perfect moment to prove your timing and win the game!"
            elif self.state == "UITLEG2":
                text_str = f"The target seconds are: {self.target_time}. We begin in 3... 2... 1..."
            elif self.state == "SLAPEN":
                text_str = "COUNT NOW. ZZZzzzzzz..."
            elif self.state == "BEREKENEN":
                text_str = "Hmmm... very interesting. You were all close, but only one of you can win."
            elif self.state == "WINNAAR":
                leaderboard = self.get_leaderboard()
                text_lines = ["Scores:"]
                for i, (name, diff) in enumerate(leaderboard):
                    pos = i + 1
                    text_lines.append(f"{pos}. {name} ({self.target_time - diff:.2f}s)")
                text_str = " ".join(text_lines)
    
            # Zorgt ervoor dat de tekst op de juiste plek komt:
            wrapped_lines = self._wrap_text(text_str, self.font, scr_w)
            line_spacing = -10 
            total_text_height = len(wrapped_lines) * self.font.get_height() + (len(wrapped_lines) - 1) * line_spacing
            y_offset = (scr_h - total_text_height) // 2

            for line in wrapped_lines:
                txt_surf = self.font.render(line, True, (0, 0, 0))
                centered_x = scr_x + (scr_w - txt_surf.get_width()) // 2
                self.screen.blit(txt_surf, (centered_x, scr_y + y_offset))
                y_offset += self.font.get_height() + line_spacing