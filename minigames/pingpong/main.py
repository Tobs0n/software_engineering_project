import pygame
import random
import sys

# ── Constants ──────────────────────────────────────────────────────────────────
WIDTH, HEIGHT   = 800, 600
FPS             = 60

FIELD_TOP       = 60
FIELD_BOTTOM    = 540
FIELD_HEIGHT    = FIELD_BOTTOM - FIELD_TOP

PADDLE_W        = 12
PADDLE_H        = 110
PADDLE_SPEED    = 6
PADDLE_OFFSET   = 40

BALL_SIZE       = 12
BALL_SPEED_INIT = 4
BALL_SPEED_MAX  = 12
BALL_ACCEL      = 0.3

SCORE_TO_WIN    = 3

PADDLE_STAGGER  = 60 # distance between 2 players on the same team
PADDLE_H_4P     = int(PADDLE_H * 2 / 3)

ANIM_DURATION   = 90
FADE_FRAMES     = 60   # 1 seconde fade-in
LAUNCH_FRAMES   = 20  # ~0.33s
PADDLE_FRAMES   = 40   # paddles bewegen, bal staat stil

TEAM_L_COLOR = (100, 180, 255)
TEAM_R_COLOR = (255, 120, 100)


# ── Paddle ─────────────────────────────────────────────────────────────────────
class Paddle:
    def __init__(self, x, color, key, height=PADDLE_H, start_dir=1):
        self.x      = x
        self.height = height
        self.y      = FIELD_TOP + FIELD_HEIGHT // 2 - height // 2
        self.color  = color
        self.key    = key
        self.start_dir = start_dir
        self.dir       = start_dir

    def on_keydown(self, key):
        if key != self.key:
            return
        at_top    = self.y <= FIELD_TOP
        at_bottom = self.y + self.height >= FIELD_BOTTOM

        if at_top:
            self.dir = 1
        elif at_bottom:
            self.dir = -1
        elif self.dir == 0:
            self.dir = -1
        elif self.dir == -1:
            self.dir = 1
        else:
            self.dir = -1

    def update(self):
        self.y += self.dir * PADDLE_SPEED
        if self.y <= FIELD_TOP:
            self.y   = FIELD_TOP
            self.dir = 0
        if self.y + self.height >= FIELD_BOTTOM:
            self.y   = FIELD_BOTTOM - self.height
            self.dir = 0

    def rect(self):
        return pygame.Rect(self.x, int(self.y), PADDLE_W, self.height)

    def reset_position(self):
        self.y   = FIELD_TOP + FIELD_HEIGHT // 2 - self.height // 2
        self.dir = self.start_dir

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect(), border_radius=4)


# ── Ball ───────────────────────────────────────────────────────────────────────
class Ball:
    def __init__(self):
        self.reset(direction=1)

    def reset(self, direction=1):
        self.x      = WIDTH  // 2
        self.y      = FIELD_TOP + FIELD_HEIGHT // 2
        self.vx     = BALL_SPEED_INIT * direction
        self.vy     = abs(random.uniform(BALL_SPEED_INIT * 0.3, BALL_SPEED_INIT * 0.8))
        self._speed = BALL_SPEED_INIT

    def update(self):
        self.x += self.vx
        self.y += self.vy

        if self.y - BALL_SIZE <= FIELD_TOP:
            self.y  = FIELD_TOP + BALL_SIZE
            self.vy = abs(self.vy)
        if self.y + BALL_SIZE >= FIELD_BOTTOM:
            self.y  = FIELD_BOTTOM - BALL_SIZE
            self.vy = -abs(self.vy)

    def speed_up(self):
        self._speed = min(self._speed + BALL_ACCEL, BALL_SPEED_MAX)
        factor      = self._speed / (self.vx**2 + self.vy**2) ** 0.5
        self.vx    *= factor
        self.vy    *= factor

    def rect(self):
        return pygame.Rect(
            int(self.x) - BALL_SIZE, int(self.y) - BALL_SIZE,
            BALL_SIZE * 2, BALL_SIZE * 2,
        )

    def draw(self, surface):
        pygame.draw.circle(surface, (232, 142, 16),
                           (int(self.x), int(self.y)), BALL_SIZE)


# ── Helpers ────────────────────────────────────────────────────────────────────
def make_paddles(player_count, players=None):
    if player_count == 2:
        cl = players[0].color if players else TEAM_L_COLOR
        cr = players[1].color if players else TEAM_R_COLOR
        left  = [Paddle(PADDLE_OFFSET,                    cl, pygame.K_q)]
        right = [Paddle(WIDTH - PADDLE_OFFSET - PADDLE_W, cr, pygame.K_p)]
    
    elif player_count == 3:
        h  = PADDLE_H_4P
        cl = players[0].color if players else TEAM_L_COLOR
        c2 = players[1].color if players else TEAM_R_COLOR
        c3 = players[2].color if players else TEAM_R_COLOR
        left = [
            Paddle(PADDLE_OFFSET, cl, pygame.K_q),  # volle hoogte, alleen
        ]
        right = [
            Paddle(WIDTH - PADDLE_OFFSET - PADDLE_W - PADDLE_STAGGER, c2, pygame.K_p, h, start_dir=-1),
            Paddle(WIDTH - PADDLE_OFFSET - PADDLE_W,                   c3, pygame.K_l, h, start_dir=1),
        ]

    else:
        h = PADDLE_H_4P
        c1 = players[0].color if players else TEAM_L_COLOR
        c2 = players[1].color if players else TEAM_L_COLOR
        c3 = players[2].color if players else TEAM_R_COLOR
        c4 = players[3].color if players else TEAM_R_COLOR
        left = [
            Paddle(PADDLE_OFFSET,                  c1, pygame.K_q, h, start_dir=-1),
            Paddle(PADDLE_OFFSET + PADDLE_STAGGER, c2, pygame.K_a, h, start_dir=1),
        ]
        right = [
            Paddle(WIDTH - PADDLE_OFFSET - PADDLE_W - PADDLE_STAGGER, c3, pygame.K_p, h, start_dir=-1),
            Paddle(WIDTH - PADDLE_OFFSET - PADDLE_W,                   c4, pygame.K_l, h, start_dir=1),
        ]
    return left, right

def blend_colors(c1, c2):           # Used for the scoring animation in teams
    return ((c1[0] + c2[0]) // 2,
            (c1[1] + c2[1]) // 2,
            (c1[2] + c2[2]) // 2)

def team_color(paddles):
    if len(paddles) == 1:
        return paddles[0].color
    return blend_colors(paddles[0].color, paddles[1].color)

def handle_paddle_collision(ball, paddles, side):
    for paddle in paddles:
        if ball.rect().colliderect(paddle.rect()):
            hit_pos  = (ball.y - paddle.y) / paddle.height
            ball.vy  = (hit_pos - 0.5) * 2 * ball._speed * 0.8
            ball.vx  = abs(ball.vx) if side == "left" else -abs(ball.vx)
            ball.speed_up()
            return True
    return False


def start_round(all_paddles, ball, direction):
    """Reset paddles and ball, return initial phase state."""
    for p in all_paddles:
        p.reset_position()
    ball.reset(direction=direction)
    return "fade_in", 0


# ── Main ───────────────────────────────────────────────────────────────────────
def main(player_count=2, players=None):
    assert player_count in (2,3, 4)

    pygame.init()
    screen  = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Ping Pong")
    clock   = pygame.time.Clock()
    font_lg = pygame.font.SysFont("monospace", 28, bold=True)
    font_sm = pygame.font.SysFont("monospace", 18)

    left_paddles, right_paddles = make_paddles(player_count, players)
    all_paddles = left_paddles + right_paddles
    ball        = Ball()
    scores      = [0, 0]
    anim_timer  = 0
    last_scorer = 0

    # ── Opstartfase ────────────────────────────────────────────────────────────
    phase, phase_timer = start_round(all_paddles, ball, direction=1)

    hint_text = ("Q  /  P  — toggle direction"       if player_count == 2
             else "Q  /  P L  — toggle direction"    if player_count == 3
             else "Q A  /  P L  — toggle direction")

    running = True
    while running:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
                break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if anim_timer == 0 and phase == "playing":
                    for p in all_paddles:
                        p.on_keydown(event.key)

        # ── Update ─────────────────────────────────────────────────────────────
        if anim_timer > 0:
            anim_timer -= 1
            if anim_timer == 0:
                phase, phase_timer = start_round(
                    all_paddles, ball,
                    direction=1 if last_scorer == 0 else -1,
                )

        elif phase == "fade_in":
            phase_timer += 1
            if phase_timer >= FADE_FRAMES:
                phase       = "paddle_start"
                phase_timer = 0

        elif phase == "paddle_start":
            for p in all_paddles:
                p.update()
            phase_timer += 1
            if phase_timer >= PADDLE_FRAMES:
                phase       = "ball_launch"
                phase_timer = 0

        elif phase == "ball_launch":
            for p in all_paddles:
                p.update()
            phase_timer += 1
            if phase_timer >= LAUNCH_FRAMES:
                phase = "playing"


        else:  # "playing"
            for p in all_paddles:
                p.update()
            ball.update()
            handle_paddle_collision(ball, left_paddles,  "left")
            handle_paddle_collision(ball, right_paddles, "right")

            scored = -1
            if ball.x < 0:
                scores[1] += 1
                scored = 1
            if ball.x > WIDTH:
                scores[0] += 1
                scored = 0
            if scored >= 0:
                last_scorer = scored
                anim_timer  = ANIM_DURATION

        # ── Render ─────────────────────────────────────────────────────────────
        screen.fill((18, 18, 36))

        pygame.draw.line(screen, (80, 80, 120), (0, FIELD_TOP),    (WIDTH, FIELD_TOP),    2)
        pygame.draw.line(screen, (80, 80, 120), (0, FIELD_BOTTOM), (WIDTH, FIELD_BOTTOM), 2)

        for y in range(FIELD_TOP, FIELD_BOTTOM, 20):
            pygame.draw.rect(screen, (50, 50, 80),
                             pygame.Rect(WIDTH//2 - 2, y, 4, 12))

        for p in all_paddles:
            p.draw(screen)

        # Bal renderen afhankelijk van fase
        if anim_timer == 0:
            if phase == "playing":
                ball.draw(screen)

            elif phase == "paddle_start":
                ball_surf = pygame.Surface((BALL_SIZE * 2, BALL_SIZE * 2), pygame.SRCALPHA)
                pygame.draw.circle(ball_surf, (232, 142, 16, 255),
                                   (BALL_SIZE, BALL_SIZE), BALL_SIZE)
                screen.blit(ball_surf, (int(ball.x) - BALL_SIZE, int(ball.y) - BALL_SIZE))

            elif phase == "ball_launch":
                ball.draw(screen)
                # Uitdijende ring rond de bal
                progress = phase_timer / LAUNCH_FRAMES       # 0.0 → 1.0
                ring_r   = int(BALL_SIZE + 30 * progress)
                alpha    = int(200 * (1 - progress))
                ring_surf = pygame.Surface((ring_r * 2, ring_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(ring_surf, (240, 240, 240, alpha),
                                (ring_r, ring_r), ring_r, 3)
                screen.blit(ring_surf, (int(ball.x) - ring_r, int(ball.y) - ring_r))

                fade_go   = 1.0 - (phase_timer / LAUNCH_FRAMES)
                flash_col = (232, 142, 16)
                flash     = pygame.Surface((WIDTH // 2, HEIGHT), pygame.SRCALPHA)
                flash.fill((*flash_col, int(60 * fade_go)))
                screen.blit(flash, (0, 0))

                pt_font = pygame.font.SysFont("monospace", int(70 + 20 * fade_go), bold=True)
                pt_lbl  = pt_font.render("GO!", True, flash_col)
                pt_lbl.set_alpha(int(255 * min(fade_go * 2, 1.0)))
                screen.blit(pt_lbl, (WIDTH//2 - pt_lbl.get_width()//2,
                                    FIELD_TOP + FIELD_HEIGHT//2 - pt_lbl.get_height()//2 - 100))

            elif phase == "fade_in":
                alpha     = int(255 * phase_timer / FADE_FRAMES)
                ball_surf = pygame.Surface((BALL_SIZE * 2, BALL_SIZE * 2), pygame.SRCALPHA)
                pygame.draw.circle(ball_surf, (232, 142, 16, alpha),
                                   (BALL_SIZE, BALL_SIZE), BALL_SIZE)
                screen.blit(ball_surf, (int(ball.x) - BALL_SIZE, int(ball.y) - BALL_SIZE))

        s1 = font_lg.render(str(scores[0]), True, team_color(left_paddles))
        s2 = font_lg.render(str(scores[1]), True, team_color(right_paddles))
        screen.blit(s1, (WIDTH//2 - 60 - s1.get_width(), 16))
        screen.blit(s2, (WIDTH//2 + 60, 16))

        hint = font_sm.render(hint_text, True, (70, 70, 100))
        screen.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 28))

        if anim_timer > 0:
            fade      = anim_timer / ANIM_DURATION
            flash_col = team_color(left_paddles) if last_scorer == 0 else team_color(right_paddles)
            flash     = pygame.Surface((WIDTH // 2, HEIGHT), pygame.SRCALPHA)
            flash.fill((*flash_col, int(80 * fade)))
            screen.blit(flash, (0 if last_scorer == 0 else WIDTH // 2, 0))

            pt_font = pygame.font.SysFont("monospace", int(36 + 20 * fade), bold=True)
            pt_lbl  = pt_font.render("POINT!", True, flash_col)
            pt_lbl.set_alpha(int(255 * min(fade * 2, 1.0)))
            screen.blit(pt_lbl, (WIDTH//2 - pt_lbl.get_width()//2,
                                  FIELD_TOP + FIELD_HEIGHT//2 - pt_lbl.get_height()//2))

        pygame.display.flip()

        for i, score in enumerate(scores):
            if score >= SCORE_TO_WIN:
                show_winner(screen, font_lg, font_sm, i, player_count)
                running = False
                break

        clock.tick(FPS)

    pygame.quit()
    sys.exit()


def show_winner(screen, font_lg, font_sm, team, player_count):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    color = TEAM_L_COLOR if team == 0 else TEAM_R_COLOR
    name  = ("Player 1" if player_count == 2 else "Team 1") if team == 0 \
            else ("Player 2" if player_count == 2 else "Team 2")

    lbl = font_lg.render(f"{name} wins!", True, color)
    screen.blit(lbl, (WIDTH//2 - lbl.get_width()//2, HEIGHT//2 - 30))

    sub = font_sm.render("Closing in 3 seconds…", True, (160, 160, 160))
    screen.blit(sub, (WIDTH//2 - sub.get_width()//2, HEIGHT//2 + 20))
    pygame.display.flip()
    pygame.time.wait(3000)


if __name__ == "__main__":
    class FakePlayer:
        def __init__(self, color):
            self.color = color

    test_players = [
        FakePlayer((255, 0,   0)),    # rood
        FakePlayer((0,   255, 0)),    # groen
        FakePlayer((255, 255, 0)),    # geel
        FakePlayer((255, 0,   255)),  # paars
    ]

    main(player_count=4, players=test_players)