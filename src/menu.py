import pygame
import subprocess
import sys
import os

# ── Konfiguracja ──────────────────────────────────────────────────────────────
SCREEN_W = 700
SCREEN_H = 700
FPS      = 60
# ─────────────────────────────────────────────────────────────────────────────

# ── Kolory ────────────────────────────────────────────────────────────────────
C_BG        = (242, 234, 224)
C_BG_LIGHT  = (250, 246, 242)
C_TEXT      = (26,  26,  26 )
C_MUTED     = (122, 111, 102)
C_BALL      = (92,  61,  143)
C_BALL_RIM  = (160, 124, 197)
C_GREEN     = (107, 174, 138)
C_AMBER     = (201, 169, 110)
C_RED       = (200,  80,  80)
C_BLUE      = (122, 174, 201)
C_BORDER    = (220, 208, 196)
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def script_path(name: str) -> str:
    return os.path.join(SCRIPT_DIR, name)


# ── Przyciski menu ────────────────────────────────────────────────────────────
MENU_ITEMS = [
    {
        'label':   'GRA 1',
        'sub':     'Łap monety, unikaj bomb',
        'script':  'game.py',
        'color':   C_BALL,
        'color2':  C_BALL_RIM,
    },
    {
        'label':   'GRA 2',
        'sub':     'Uciekaj ze stref zagrożenia',
        'script':  'game2.py',
        'color':   C_RED,
        'color2':  (230, 140, 140),
    },
    {
        'label':   'LIVE DASHBOARD',
        'sub':     'Wizualizacja na żywo + zapis danych',
        'script':  None,   # specjalny – odpala 2 skrypty
        'color':   C_GREEN,
        'color2':  (160, 210, 180),
    },
    {
        'label':   'ANALIZA SESJI',
        'sub':     'Wykresy z ostatniej sesji',
        'script':  'session_stats.py',
        'color':   C_AMBER,
        'color2':  (230, 200, 150),
    },
]


def draw_card(surface, rect, item, hovered, font_mid, font_sm):
    color  = item['color2'] if hovered else item['color']
    border = item['color']

    pygame.draw.rect(surface, C_BG_LIGHT, rect, border_radius=14)
    pygame.draw.rect(surface, border, rect, width=2, border_radius=14)

    # Pasek koloru po lewej
    bar_rect = pygame.Rect(rect.x, rect.y + 14, 5, rect.h - 28)
    pygame.draw.rect(surface, color, bar_rect, border_radius=3)

    # Napis główny
    lbl = font_mid.render(item['label'], True, C_TEXT)
    surface.blit(lbl, (rect.x + 24, rect.y + rect.h//2 - lbl.get_height() - 4))

    # Napis drugorzędny
    sub = font_sm.render(item['sub'], True, C_MUTED)
    surface.blit(sub, (rect.x + 24, rect.y + rect.h//2 + 4))


def launch(item, screen, clock, fonts):
    """Odpala skrypt — gry w tym samym procesie, reszta jako subprocess."""
    env_kwargs = {'cwd': SCRIPT_DIR}

    if item['script'] in ('game.py', 'game2.py'):
        # Chowamy okno menu, odpalamy grę jako osobny proces i czekamy
        pygame.display.iconify()
        proc = subprocess.Popen(
            [sys.executable, script_path(item['script'])],
            cwd=SCRIPT_DIR
        )
        proc.wait()   # czekamy aż gra się zamknie
        pygame.init()
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Smart Physio – Menu")
        pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SHOWN)
        # Wymuś okno na wierzch przez WM
        import ctypes
        try:
            hwnd = pygame.display.get_wm_info()['window']
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        except Exception:
            pass

    elif item['script'] is None:
        # Live Dashboard = dwa osobne procesy
        subprocess.Popen([sys.executable, script_path('collect_data.py')], **env_kwargs)
        subprocess.Popen([sys.executable, script_path('visualize_live.py')], **env_kwargs)

    elif item['script'] == 'session_stats.py':
        csv_path = os.path.join(SCRIPT_DIR, '..', 'dane.csv')
        subprocess.Popen([
            sys.executable, script_path('session_stats.py'),
            csv_path, '0', '0', '9999',
        ], **env_kwargs)


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Smart Physio – Menu")
    clock = pygame.time.Clock()

    font_huge = pygame.font.SysFont('Arial', 44, bold=True)
    font_mid  = pygame.font.SysFont('Arial', 20, bold=True)
    font_sm   = pygame.font.SysFont('Arial', 14)
    font_hint = pygame.font.SysFont('Arial', 12)
    fonts     = (font_huge, font_mid, font_sm)

    # Karty – rozmieszczenie
    card_w = SCREEN_W - 100
    card_h = 90
    card_x = 50
    gap    = 18
    total_h = len(MENU_ITEMS) * card_h + (len(MENU_ITEMS) - 1) * gap
    start_y = (SCREEN_H - total_h) // 2 + 60

    cards = []
    for i, item in enumerate(MENU_ITEMS):
        y = start_y + i * (card_h + gap)
        cards.append((pygame.Rect(card_x, y, card_w, card_h), item))

    running = True
    while running:
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for rect, item in cards:
                    if rect.collidepoint(mx, my):
                        launch(item, screen, clock, fonts)
                        # Pełna reinicjalizacja po powrocie z gry
                        pygame.init()
                        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
                        pygame.display.set_caption("Smart Physio – Menu")
                        clock  = pygame.time.Clock()
                        font_huge = pygame.font.SysFont('Arial', 44, bold=True)
                        font_mid  = pygame.font.SysFont('Arial', 20, bold=True)
                        font_sm   = pygame.font.SysFont('Arial', 14)
                        font_hint = pygame.font.SysFont('Arial', 12)
                        fonts     = (font_huge, font_mid, font_sm)
                        cards = []
                        for j, mi in enumerate(MENU_ITEMS):
                            y = start_y + j * (card_h + gap)
                            cards.append((pygame.Rect(card_x, y, card_w, card_h), mi))
                        break

        # ── Rysowanie ────────────────────────────────────────────────────────
        screen.fill(C_BG)

        # Tytuł
        title = font_huge.render("DON PEDROS", True, C_BALL)
        screen.blit(title, (SCREEN_W//2 - title.get_width()//2, 48))

        # Linia pod tytułem
        pygame.draw.line(screen, C_BORDER,
                         (50, 115), (SCREEN_W - 50, 115), 1)

        # Karty
        for rect, item in cards:
            hovered = rect.collidepoint(mx, my)
            draw_card(screen, rect, item, hovered, font_mid, font_sm)

            # Strzałka przy hover
            if hovered:
                arr = font_mid.render("→", True, item['color'])
                screen.blit(arr, (rect.right - 36,
                                  rect.y + rect.h//2 - arr.get_height()//2))

        # Hint na dole
        hint = font_hint.render("ESC – wyjście", True, C_MUTED)
        screen.blit(hint, (SCREEN_W//2 - hint.get_width()//2, SCREEN_H - 30))

        pygame.display.flip()

    pygame.quit()


if __name__ == '__main__':
    main()