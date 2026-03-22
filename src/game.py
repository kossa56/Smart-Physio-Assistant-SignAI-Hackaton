import pygame
import serial
import threading
import queue
import csv
import sys
import time
import random
import math
import os
from dataclasses import dataclass, field

# ── Konfiguracja ──────────────────────────────────────────────────────────────
PORT         = 'COM3'
BAUDRATE     = 115200
CSV_FILE     = '../dane.csv'
RANKING_FILE = '../ranking.csv'
SCREEN_W     = 700
SCREEN_H     = 700
FPS          = 60
TRACK_X      = SCREEN_W - 120
MAX_LIVES    = 3

# ── Poziomy trudności ─────────────────────────────────────────────────────────
DIFFICULTIES = {
    'easy':   {'label': 'EASY',   'spawn_start': 160, 'spawn_min': 90,  'speed_base': 2.5, 'bomb_chance': 0.25, 'spawn_count': 1, 'color': (107, 174, 138)},
    'medium': {'label': 'MEDIUM', 'spawn_start': 120, 'spawn_min': 60,  'speed_base': 3.5, 'bomb_chance': 0.35, 'spawn_count': 2, 'color': (201, 169, 110)},
    'hard':   {'label': 'HARD',   'spawn_start':  50, 'spawn_min': 20,  'speed_base': 5.0, 'bomb_chance': 0.50, 'spawn_count': 5, 'color': (200,  80,  80)},
}
# ─────────────────────────────────────────────────────────────────────────────

# ── Kolory ────────────────────────────────────────────────────────────────────
C_BG         = (242, 234, 224)
C_TEXT       = (26,  26,  26 )
C_MUTED      = (122, 111, 102)
C_BALL       = (92,  61,  143)
C_BALL_RIM   = (160, 124, 197)
C_TRACK      = (200, 185, 170)
C_BTN        = (92,  61,  143)
C_BTN_TEXT   = (250, 246, 242)
C_BTN_HOVER  = (120,  85, 170)
C_GREEN      = (107, 174, 138)
C_AMBER      = (201, 169, 110)
C_RED        = (200,  80,  80)
C_COIN       = (201, 169,  80)
C_COIN_RIM   = (230, 200, 120)
C_BOMB       = (60,   60,  60)
C_BOMB_RIM   = (100, 100, 100)
C_HEART_ON   = (210,  80,  80)
C_HEART_OFF  = (200, 185, 170)
C_FLASH      = (255, 220, 220)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SensorFrame:
    timestamp_ms:     int
    distance_mm:      float
    session_time_s:   int
    repetition_count: int


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float          # 1.0 → 0.0
    color: tuple
    size: float


@dataclass
class FlyingObj:
    x: float
    y: float
    speed: float
    kind: str            # 'coin' | 'bomb'
    radius: int = 18
    angle: float = 0.0   # obrót monety


# ── Wątek szeregowy ───────────────────────────────────────────────────────────
class SerialReader(threading.Thread):
    def __init__(self, port, baudrate, data_queue, csv_file):
        super().__init__(daemon=True)
        self.port      = port
        self.baudrate  = baudrate
        self.queue     = data_queue
        self.csv_file  = csv_file
        self.running   = True
        self.connected = False
        self.error     = None

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connected = True
        except serial.SerialException as e:
            self.error = str(e)
            print(f"[SERIAL ERROR] {e}")
            return

        print(f"[CSV] Próba zapisu do: {self.csv_file}")
        with open(self.csv_file, 'w', newline='', buffering=1) as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp_ms', 'distance_mm',
                             'session_time_s', 'repetition_count'])
            f.flush()
            print("[CSV] Plik otwarty, czekam na dane...")
            while self.running:
                try:
                    raw = ser.readline().decode('utf-8', errors='ignore').strip()
                    if not raw or not raw[0].isdigit():
                        continue
                    parts = raw.split(',')
                    if len(parts) != 4:
                        print(f"[CSV] Zła liczba kolumn ({len(parts)}): {raw}")
                        continue
                    frame = SensorFrame(
                        int(parts[0]), float(parts[1]),
                        int(parts[2]), int(parts[3])
                    )
                    writer.writerow([frame.timestamp_ms, frame.distance_mm,
                                     frame.session_time_s, frame.repetition_count])
                    f.flush()
                    print(f"[CSV] Zapisano: {raw}")
                    while not self.queue.empty():
                        try: self.queue.get_nowait()
                        except queue.Empty: break
                    self.queue.put(frame)
                except (ValueError, serial.SerialException):
                    continue
        ser.close()

    def stop(self):
        self.running = False


# ── Helpers ───────────────────────────────────────────────────────────────────
def draw_button(surface, rect, text, font, hovered=False, disabled=False):
    color = C_MUTED if disabled else (C_BTN_HOVER if hovered else C_BTN)
    pygame.draw.rect(surface, color, rect, border_radius=8)
    lbl = font.render(text, True, C_BTN_TEXT)
    surface.blit(lbl, (rect.x + (rect.w - lbl.get_width()) // 2,
                        rect.y + (rect.h - lbl.get_height()) // 2))


def draw_heart(surface, cx, cy, size, filled):
    color = C_HEART_ON if filled else C_HEART_OFF
    pygame.draw.circle(surface, color, (cx - size//3, cy), size//3)
    pygame.draw.circle(surface, color, (cx + size//3, cy), size//3)
    pts = [(cx - size*2//3, cy + 2),
           (cx, cy + size*4//5),
           (cx + size*2//3, cy + 2)]
    pygame.draw.polygon(surface, color, pts)


def dist_to_y(dist, dist_min, dist_max, margin=80):
    t = (dist - dist_min) / max(dist_max - dist_min, 1)
    t = max(0.0, min(1.0, t))
    return int(SCREEN_H - margin - t * (SCREEN_H - 2 * margin))


def spawn_particles(particles, x, y, color, count=18):
    for _ in range(count):
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(1.5, 5.0)
        particles.append(Particle(
            x=x, y=y,
            vx=math.cos(angle) * speed,
            vy=math.sin(angle) * speed - 1.5,
            life=1.0,
            color=color,
            size=random.uniform(3, 7)
        ))


def update_particles(particles):
    alive = []
    for p in particles:
        p.x  += p.vx
        p.y  += p.vy
        p.vy += 0.18
        p.life -= 0.04
        if p.life > 0:
            alive.append(p)
    particles[:] = alive


def draw_particles(surface, particles):
    for p in particles:
        alpha = int(255 * p.life)
        r = max(1, int(p.size * p.life))
        surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*p.color, alpha), (r, r), r)
        surface.blit(surf, (int(p.x) - r, int(p.y) - r))


def draw_coin(surface, obj):
    # Efekt "obrotu" – elipsa imituje perspektywę
    w = max(4, int(obj.radius * abs(math.cos(obj.angle))))
    h = obj.radius
    pygame.draw.ellipse(surface, C_COIN_RIM,
                        (int(obj.x)-w-2, int(obj.y)-h-2, (w+2)*2, (h+2)*2))
    pygame.draw.ellipse(surface, C_COIN,
                        (int(obj.x)-w, int(obj.y)-h, w*2, h*2))
    # znak $
    if w > 6:
        font = pygame.font.SysFont('Arial', 12, bold=True)
        lbl = font.render('$', True, (160, 120, 40))
        surface.blit(lbl, (int(obj.x) - lbl.get_width()//2,
                            int(obj.y) - lbl.get_height()//2))


def draw_bomb(surface, obj):
    r = obj.radius
    cx, cy = int(obj.x), int(obj.y)
    pygame.draw.circle(surface, C_BOMB_RIM, (cx, cy), r+2)
    pygame.draw.circle(surface, C_BOMB,     (cx, cy), r)
    # lont
    pygame.draw.line(surface, (80, 60, 40),
                     (cx, cy - r), (cx + 6, cy - r - 10), 2)
    # iskra
    if random.random() < 0.4:
        pygame.draw.circle(surface, C_COIN_RIM,
                           (cx + 6, cy - r - 10), 3)


# ── Ekrany ────────────────────────────────────────────────────────────────────
def connecting_screen(screen, clock, fonts, reader):
    font_big, font_mid, font_sm = fonts
    while True:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                reader.stop(); pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                reader.stop(); pygame.quit(); sys.exit()

        screen.fill(C_BG)
        if reader.error:
            t1 = font_big.render("Błąd połączenia", True, C_RED)
            t2 = font_sm.render(reader.error, True, C_MUTED)
            t3 = font_sm.render("ESC – wyjście", True, C_MUTED)
            screen.blit(t1, (SCREEN_W//2 - t1.get_width()//2, 260))
            screen.blit(t2, (SCREEN_W//2 - t2.get_width()//2, 315))
            screen.blit(t3, (SCREEN_W//2 - t3.get_width()//2, 360))
        elif reader.connected:
            return
        else:
            dots = '.' * (int(time.time() * 2) % 4)
            t1 = font_big.render(f"Łączenie z {PORT}{dots}", True, C_TEXT)
            t2 = font_sm.render("ESC – anuluj", True, C_MUTED)
            screen.blit(t1, (SCREEN_W//2 - t1.get_width()//2, 300))
            screen.blit(t2, (SCREEN_W//2 - t2.get_width()//2, 355))
        pygame.display.flip()


def calibration_screen(screen, clock, fonts, data_queue):
    font_big, font_mid, font_sm = fonts
    font_huge = pygame.font.SysFont('Arial', 72, bold=True)

    steps = [
        {
            'key':        'max',
            'step':       '1 / 2',
            'label':      'GÓRA',
            'icon_arrow': 'UP',
            'instruction': 'Ustaw ciało / rękę w najwyższej pozycji',
            'accent':     C_GREEN,
            'bg_accent':  (230, 248, 238),   # bardzo jasna zieleń
        },
        {
            'key':        'min',
            'step':       '2 / 2',
            'label':      'DÓŁ',
            'icon_arrow': 'DOWN',
            'instruction': 'Ustaw ciało / rękę w najniższej pozycji',
            'accent':     C_AMBER,
            'bg_accent':  (252, 244, 224),   # bardzo jasny amber
        },
    ]
    results    = {}
    btn_rect   = pygame.Rect(SCREEN_W//2 - 120, SCREEN_H - 120, 240, 54)
    last_frame = None

    for step in steps:
        confirmed = False
        accent    = step['accent']
        bg_accent = step['bg_accent']

        while not confirmed:
            clock.tick(FPS)
            mx, my = pygame.mouse.get_pos()
            hovered = btn_rect.collidepoint(mx, my)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and hovered and last_frame:
                    results[step['key']] = last_frame.distance_mm
                    confirmed = True

            try:
                last_frame = data_queue.get_nowait()
            except queue.Empty:
                pass

            # Tło podzielone – górna część w kolorze kroku
            screen.fill(C_BG)
            pygame.draw.rect(screen, bg_accent, (0, 0, SCREEN_W, 200))

            # Pasek kroku u góry
            step_lbl = font_sm.render(f"KALIBRACJA  {step['step']}", True, C_MUTED)
            screen.blit(step_lbl, (SCREEN_W//2 - step_lbl.get_width()//2, 18))

            # Duży napis GÓRA / DÓŁ
            big_lbl = font_huge.render(step['label'], True, accent)
            screen.blit(big_lbl, (SCREEN_W//2 - big_lbl.get_width()//2, 50))

            # Strzałka
            cx = SCREEN_W//2
            if step['icon_arrow'] == 'UP':
                pts = [(cx, 148), (cx - 28, 185), (cx + 28, 185)]
            else:
                pts = [(cx, 188), (cx - 28, 151), (cx + 28, 151)]
            pygame.draw.polygon(screen, accent, pts)

            # Separator
            pygame.draw.line(screen, C_TRACK, (40, 210), (SCREEN_W - 40, 210), 1)

            # Instrukcja
            inst = font_mid.render(step['instruction'], True, C_TEXT)
            screen.blit(inst, (SCREEN_W//2 - inst.get_width()//2, 230))

            sub = font_sm.render("Kliknij ZATWIERDŹ gdy jesteś gotowy", True, C_MUTED)
            screen.blit(sub, (SCREEN_W//2 - sub.get_width()//2, 270))

            # Aktualna wartość czujnika — duża i wyraźna
            if last_frame:
                box_rect = pygame.Rect(SCREEN_W//2 - 130, 310, 260, 90)
                pygame.draw.rect(screen, (255, 255, 255), box_rect, border_radius=12)
                pygame.draw.rect(screen, accent, box_rect, width=2, border_radius=12)

                dist_lbl = font_sm.render("Aktualna odległość", True, C_MUTED)
                screen.blit(dist_lbl, (SCREEN_W//2 - dist_lbl.get_width()//2, 322))

                dist_val = font_big.render(f"{last_frame.distance_mm:.0f} mm", True, accent)
                screen.blit(dist_val, (SCREEN_W//2 - dist_val.get_width()//2, 348))
            else:
                nd = font_sm.render("Oczekiwanie na dane z czujnika...", True, C_AMBER)
                screen.blit(nd, (SCREEN_W//2 - nd.get_width()//2, 350))

            # Przycisk
            btn_color = (C_BTN_HOVER if hovered else accent) if last_frame else C_MUTED
            pygame.draw.rect(screen, btn_color, btn_rect, border_radius=10)
            btn_lbl = font_mid.render("ZATWIERDŹ", True, C_BTN_TEXT)
            screen.blit(btn_lbl, (
                btn_rect.x + (btn_rect.w - btn_lbl.get_width()) // 2,
                btn_rect.y + (btn_rect.h - btn_lbl.get_height()) // 2,
            ))

            pygame.display.flip()

    d_min = min(results['min'], results['max'])
    d_max = max(results['min'], results['max'])
    if d_max - d_min < 20:
        d_max = d_min + 100
    return d_min, d_max


def show_session_stats(csv_file: str, score: int, dist_min: float, dist_max: float):
    """Odpala session_stats.py jako osobny proces."""
    import subprocess
    subprocess.Popen([
        sys.executable, 'session_stats.py',
        csv_file,
        str(score),
        str(dist_min),
        str(dist_max),
    ])


# Ranking
def load_ranking(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        return []
    try:
        entries = []
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append({
                    'name':       row['name'],
                    'score':      int(row['score']),
                    'difficulty': row['difficulty'],
                    'date':       row['date'],
                })
        return sorted(entries, key=lambda x: x['score'], reverse=True)
    except Exception:
        return []


def save_ranking(filepath: str, name: str, score: int, difficulty: str):
    exists = os.path.exists(filepath)
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'score', 'difficulty', 'date'])
        if not exists:
            writer.writeheader()
        writer.writerow({
            'name':       name,
            'score':      score,
            'difficulty': difficulty,
            'date':       time.strftime('%Y-%m-%d %H:%M'),
        })


# Ekran wyboru trudności
def difficulty_screen(screen, clock, fonts):
    font_big, font_mid, font_sm = fonts
    font_huge = pygame.font.SysFont('Arial', 48, bold=True)

    btns = {}
    btn_w, btn_h = 200, 60
    ys = {'easy': 280, 'medium': 360, 'hard': 440}
    for key, y in ys.items():
        btns[key] = pygame.Rect(SCREEN_W//2 - btn_w//2, y, btn_w, btn_h)

    btn_ranking = pygame.Rect(SCREEN_W//2 - 120, 530, 240, 44)

    while True:
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                for key, rect in btns.items():
                    if rect.collidepoint(mx, my):
                        return key
                if btn_ranking.collidepoint(mx, my):
                    ranking_screen(screen, clock, fonts)

        screen.fill(C_BG)
        title = font_huge.render("STRIKER STRENGTH", True, C_BALL)
        screen.blit(title, (SCREEN_W//2 - title.get_width()//2, 140))
        sub = font_sm.render("Wybierz poziom trudności", True, C_MUTED)
        screen.blit(sub, (SCREEN_W//2 - sub.get_width()//2, 210))

        for key, rect in btns.items():
            d      = DIFFICULTIES[key]
            hov    = rect.collidepoint(mx, my)
            color  = tuple(min(255, c + 30) for c in d['color']) if hov else d['color']
            pygame.draw.rect(screen, color, rect, border_radius=10)
            lbl = font_mid.render(d['label'], True, (255, 255, 255))
            screen.blit(lbl, (rect.x + (rect.w - lbl.get_width())//2,
                               rect.y + (rect.h - lbl.get_height())//2))

        draw_button(screen, btn_ranking, "RANKING", font_sm,
                    btn_ranking.collidepoint(mx, my))
        pygame.display.flip()


# Ekran rankingu
def ranking_screen(screen, clock, fonts):
    font_big, font_mid, font_sm = fonts
    entries  = load_ranking(RANKING_FILE)
    btn_back = pygame.Rect(SCREEN_W//2 - 100, SCREEN_H - 70, 200, 44)

    diff_colors = {
        'easy':   DIFFICULTIES['easy']['color'],
        'medium': DIFFICULTIES['medium']['color'],
        'hard':   DIFFICULTIES['hard']['color'],
    }

    while True:
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_back.collidepoint(mx, my): return

        screen.fill(C_BG)
        t = font_big.render("RANKING", True, C_BALL)
        screen.blit(t, (SCREEN_W//2 - t.get_width()//2, 30))

        if not entries:
            nd = font_mid.render("Brak wyników", True, C_MUTED)
            screen.blit(nd, (SCREEN_W//2 - nd.get_width()//2, 300))
        else:
            # Nagłówki
            y = 90
            headers = [('#', 40), ('Gracz', 140), ('Wynik', 380), ('Poziom', 490), ('Data', 570)]
            for h, x in headers:
                lbl = font_sm.render(h, True, C_MUTED)
                screen.blit(lbl, (x, y))
            pygame.draw.line(screen, C_MUTED, (30, y+20), (SCREEN_W-30, y+20), 1)
            y += 32

            for i, e in enumerate(entries[:12]):
                row_color = C_AMBER if i == 0 else C_TEXT
                rank_lbl  = font_sm.render(f"{i+1}.", True, row_color)
                name_lbl  = font_sm.render(e['name'][:14], True, row_color)
                score_lbl = font_sm.render(str(e['score']), True, row_color)
                diff_c    = diff_colors.get(e['difficulty'], C_MUTED)
                diff_lbl  = font_sm.render(e['difficulty'].upper(), True, diff_c)
                date_lbl  = font_sm.render(e['date'], True, C_MUTED)

                screen.blit(rank_lbl,  (40,  y))
                screen.blit(name_lbl,  (140, y))
                screen.blit(score_lbl, (380, y))
                screen.blit(diff_lbl,  (490, y))
                screen.blit(date_lbl,  (570, y))
                y += 28

        draw_button(screen, btn_back, "WRÓĆ", font_sm, btn_back.collidepoint(mx, my))
        pygame.display.flip()


# Ekran wpisywania nazwy
def name_entry_screen(screen, clock, fonts, score, difficulty):
    font_big, font_mid, font_sm = fonts
    name      = ""
    max_chars = 12
    btn_save  = pygame.Rect(SCREEN_W//2 - 110, 460, 220, 50)
    btn_skip  = pygame.Rect(SCREEN_W//2 - 110, 524, 220, 44)
    cursor_on = True
    cursor_t  = 0

    diff_color = DIFFICULTIES[difficulty]['color']

    while True:
        clock.tick(FPS)
        cursor_t += 1
        if cursor_t % 30 == 0:
            cursor_on = not cursor_on
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and name.strip():
                    save_ranking(RANKING_FILE, name.strip(), score, difficulty)
                    return
                elif event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                elif event.key == pygame.K_ESCAPE:
                    return
                elif len(name) < max_chars and event.unicode.isprintable():
                    name += event.unicode
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_save.collidepoint(mx, my) and name.strip():
                    save_ranking(RANKING_FILE, name.strip(), score, difficulty)
                    return
                if btn_skip.collidepoint(mx, my):
                    return

        screen.fill(C_BG)

        t1 = font_big.render("GAME OVER", True, C_RED)
        t2 = font_mid.render(f"Wynik: {score} pkt", True, C_TEXT)
        diff_badge = font_sm.render(DIFFICULTIES[difficulty]['label'], True, diff_color)
        screen.blit(t1, (SCREEN_W//2 - t1.get_width()//2, 80))
        screen.blit(t2, (SCREEN_W//2 - t2.get_width()//2, 135))
        screen.blit(diff_badge, (SCREEN_W//2 - diff_badge.get_width()//2, 175))

        prompt = font_sm.render("Wpisz swoje imię do rankingu:", True, C_MUTED)
        screen.blit(prompt, (SCREEN_W//2 - prompt.get_width()//2, 240))

        # Pole tekstowe
        input_rect = pygame.Rect(SCREEN_W//2 - 150, 270, 300, 52)
        pygame.draw.rect(screen, (255, 255, 255), input_rect, border_radius=8)
        pygame.draw.rect(screen, diff_color, input_rect, width=2, border_radius=8)
        display_text = name + ('|' if cursor_on else ' ')
        inp_lbl = font_mid.render(display_text, True, C_TEXT)
        screen.blit(inp_lbl, (input_rect.x + 12,
                               input_rect.y + (input_rect.h - inp_lbl.get_height())//2))

        draw_button(screen, btn_save, "ZAPISZ DO RANKINGU", font_sm,
                    btn_save.collidepoint(mx, my),
                    disabled=not name.strip())
        draw_button(screen, btn_skip, "POMIŃ", font_sm,
                    btn_skip.collidepoint(mx, my))
        pygame.display.flip()


def game_over_screen(screen, clock, fonts, score):
    font_big, font_mid, font_sm = fonts
    btn_play  = pygame.Rect(SCREEN_W//2 - 120, 420, 240, 50)
    btn_stats = pygame.Rect(SCREEN_W//2 - 120, 484, 240, 50)

    while True:
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_play.collidepoint(mx, my):
                    return 'play'
                if btn_stats.collidepoint(mx, my):
                    return 'stats'

        screen.fill(C_BG)
        t1 = font_big.render("GAME OVER", True, C_RED)
        t2 = font_mid.render(f"Wynik: {score} pkt", True, C_TEXT)
        screen.blit(t1, (SCREEN_W//2 - t1.get_width()//2, 240))
        screen.blit(t2, (SCREEN_W//2 - t2.get_width()//2, 300))
        draw_button(screen, btn_play,  "ZAGRAJ JESZCZE RAZ", font_sm,
                    btn_play.collidepoint(mx, my))
        draw_button(screen, btn_stats, "POKAŻ STATYSTYKI",   font_sm,
                    btn_stats.collidepoint(mx, my))
        pygame.display.flip()


def game_screen(screen, clock, fonts, data_queue, dist_min, dist_max, difficulty='medium'):
    font_big, font_mid, font_sm = fonts
    diff = DIFFICULTIES[difficulty]

    ball_y    = float(SCREEN_H // 2)
    target_y  = ball_y
    smooth    = 0.18
    trail     = []
    TRAIL_LEN = 20

    score     = 0
    lives     = MAX_LIVES
    last_rep  = 0
    last_dist = None

    objects: list[FlyingObj] = []
    particles: list[Particle] = []

    spawn_timer    = 0
    spawn_interval = diff['spawn_start']
    obj_speed_base = diff['speed_base']
    bomb_chance    = diff['bomb_chance']

    flash_timer   = 0        # czerwony flash przy utracie życia
    invincible    = 0        # klatki nietykalności po trafieniu

    btn_quit = pygame.Rect(SCREEN_W - 110, 14, 95, 34)

    while True:
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return score
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return score
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_quit.collidepoint(mx, my):
                    return score

        # Dane z czujnika
        try:
            frame = data_queue.get_nowait()
            last_dist = frame.distance_mm
            target_y  = float(dist_to_y(frame.distance_mm, dist_min, dist_max))
            if last_rep == 0:
                last_rep = frame.repetition_count
            if frame.repetition_count > last_rep:
                score   += (frame.repetition_count - last_rep) * 10
                last_rep = frame.repetition_count
        except queue.Empty:
            pass

        # Ruch kulki
        ball_y += (target_y - ball_y) * smooth
        trail.append((TRACK_X, int(ball_y)))
        if len(trail) > TRAIL_LEN:
            trail.pop(0)

        # Spawn obiektów
        spawn_timer += 1
        if spawn_timer >= spawn_interval:
            spawn_timer = 0
            spawn_interval = max(diff['spawn_min'], spawn_interval - 1)
            for _ in range(diff['spawn_count']):
                kind  = 'bomb' if random.random() < bomb_chance else 'coin'
                speed = obj_speed_base + random.uniform(0, 2.0)
                y_pos = random.uniform(100, SCREEN_H - 100)
                objects.append(FlyingObj(x=0, y=y_pos, speed=speed, kind=kind))

        # Ruch obiektów
        for obj in objects:
            obj.x += obj.speed
            if obj.kind == 'coin':
                obj.angle += 0.08

        # Kolizje
        ball_rect = pygame.Rect(TRACK_X - 22, int(ball_y) - 22, 44, 44)
        hit_objs  = []
        if invincible <= 0:
            for obj in objects:
                obj_rect = pygame.Rect(int(obj.x) - obj.radius,
                                       int(obj.y) - obj.radius,
                                       obj.radius * 2, obj.radius * 2)
                if ball_rect.colliderect(obj_rect):
                    hit_objs.append(obj)
                    if obj.kind == 'coin':
                        score += 50
                        spawn_particles(particles, obj.x, obj.y, C_COIN, 20)
                    else:
                        lives -= 1
                        flash_timer  = 20
                        invincible   = 90
                        spawn_particles(particles, obj.x, obj.y, C_RED, 25)
        else:
            invincible -= 1

        # Usuń trafione i te poza ekranem
        objects = [o for o in objects
                   if o not in hit_objs and o.x < SCREEN_W + 40]

        update_particles(particles)

        if lives <= 0:
            return score

        # Rysowanie
        if flash_timer > 0:
            screen.fill(C_FLASH)
            flash_timer -= 1
        else:
            screen.fill(C_BG)

        # Linia toru
        pygame.draw.line(screen, C_TRACK,
                         (TRACK_X, 60), (TRACK_X, SCREEN_H - 60), 2)

        # Znaczniki MIN/MAX
        y_top = dist_to_y(dist_max, dist_min, dist_max)
        y_bot = dist_to_y(dist_min, dist_min, dist_max)
        pygame.draw.line(screen, C_GREEN, (TRACK_X-30, y_top), (TRACK_X+30, y_top), 2)
        pygame.draw.line(screen, C_AMBER, (TRACK_X-30, y_bot), (TRACK_X+30, y_bot), 2)
        screen.blit(font_sm.render("MAX", True, C_GREEN), (TRACK_X + 36, y_top - 9))
        screen.blit(font_sm.render("MIN", True, C_AMBER), (TRACK_X + 36, y_bot - 9))

        # Obiekty latające
        for obj in objects:
            if obj.kind == 'coin':
                draw_coin(screen, obj)
            else:
                draw_bomb(screen, obj)

        # Cząsteczki
        draw_particles(screen, particles)

        # Ślad kulki
        for i, (tx, ty) in enumerate(trail):
            r = max(3, int(22 * 0.45 * (i / TRAIL_LEN)))
            alpha = int(80 * (i / TRAIL_LEN))
            surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*C_BALL_RIM, alpha), (r, r), r)
            screen.blit(surf, (tx - r, ty - r))

        # Kulka (miga gdy nietykalność)
        if invincible <= 0 or (invincible // 6) % 2 == 0:
            pygame.draw.circle(screen, C_BALL_RIM, (TRACK_X, int(ball_y)), 25)
            pygame.draw.circle(screen, C_BALL,     (TRACK_X, int(ball_y)), 22)

        # HUD – SCORE
        screen.blit(font_sm.render("SCORE", True, C_MUTED), (20, 18))
        screen.blit(font_big.render(str(score), True, C_TEXT), (20, 40))

        # HUD – LIVES (serduszka)
        for i in range(MAX_LIVES):
            draw_heart(screen, 20 + i * 34, 95, 13, i < lives)

        # HUD – odległość
        if last_dist is not None:
            screen.blit(font_sm.render(f"{last_dist:.0f} mm", True, C_MUTED),
                        (20, 120))

        # Przycisk wyjścia
        draw_button(screen, btn_quit, "WYJDŹ", font_sm,
                    btn_quit.collidepoint(mx, my))

        pygame.display.flip()

    return score



def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Striker Strength")
    clock  = pygame.time.Clock()

    fonts = (
        pygame.font.SysFont('Arial', 32, bold=True),
        pygame.font.SysFont('Arial', 22),
        pygame.font.SysFont('Arial', 16),
    )

    data_queue = queue.Queue()
    reader     = SerialReader(PORT, BAUDRATE, data_queue, CSV_FILE)
    reader.start()

    connecting_screen(screen, clock, fonts, reader)

    while True:
        difficulty = difficulty_screen(screen, clock, fonts)
        dist_min, dist_max = calibration_screen(
            screen, clock, fonts, data_queue
        )
        final_score = game_screen(
            screen, clock, fonts, data_queue, dist_min, dist_max, difficulty
        )
        name_entry_screen(screen, clock, fonts, final_score, difficulty)
        action = game_over_screen(screen, clock, fonts, final_score)
        if action == 'stats':
            show_session_stats(CSV_FILE, final_score, dist_min, dist_max)

    reader.stop()
    pygame.quit()


if __name__ == '__main__':
    main()