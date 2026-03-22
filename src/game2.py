import pygame
import serial
import threading
import queue
import csv
import sys
import random
import math
import subprocess
from dataclasses import dataclass

# Konfiguracja
PORT         = 'COM3'
BAUDRATE     = 115200
CSV_FILE     = '../dane.csv'
SCREEN_W     = 700
SCREEN_H     = 700
FPS          = 60
MAX_LIVES    = 3
N_ZONES      = 4
DANGER_COUNT = 2          # ile stref jednocześnie niebezpiecznych
WARN_TIME    = 2.0        # sekundy ostrzeżenia (strefa żółta) przed niebezpieczeństwem
DANGER_TIME_MIN = 5.0     # min czas na ucieczkę (sekundy)
DANGER_TIME_MAX = 7.0     # max czas na ucieczkę
SAFE_TIME_MIN   = 3.0     # min czas spokoju między falami
SAFE_TIME_MAX   = 5.0
TRACK_X      = SCREEN_W - 100   # pozycja toru kulki

# Kolory
C_BG          = (242, 234, 224)
C_TEXT        = (26,  26,  26 )
C_MUTED       = (122, 111, 102)
C_BALL        = (92,  61,  143)
C_BALL_RIM    = (160, 124, 197)
C_TRACK       = (200, 185, 170)
C_BTN         = (92,  61,  143)
C_BTN_TEXT    = (250, 246, 242)
C_BTN_HOVER   = (120,  85, 170)
C_GREEN       = (107, 174, 138)
C_AMBER       = (201, 169, 110)
C_RED         = (200,  80,  80)
C_HEART_ON    = (210,  80,  80)
C_HEART_OFF   = (200, 185, 170)

ZONE_SAFE     = (230, 245, 235, 180)   # zielonawa (RGBA)
ZONE_WARN     = (255, 240, 180, 180)   # żółtawa
ZONE_DANGER   = (255, 180, 180, 180)   # czerwonawa
ZONE_BORDER   = (180, 165, 150)


@dataclass
class SensorFrame:
    timestamp_ms:     int
    distance_mm:      float
    session_time_s:   int
    repetition_count: int


@dataclass
class Particle:
    x: float; y: float
    vx: float; vy: float
    life: float
    color: tuple
    size: float


# Serial Reader
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
            return

        print(f"[CSV] Zapis do: {self.csv_file}")
        with open(self.csv_file, 'w', newline='', buffering=1) as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp_ms', 'distance_mm',
                             'session_time_s', 'repetition_count'])
            f.flush()
            while self.running:
                try:
                    raw = ser.readline().decode('utf-8', errors='ignore').strip()
                    if not raw or not raw[0].isdigit():
                        continue
                    parts = raw.split(',')
                    if len(parts) != 4:
                        continue
                    frame = SensorFrame(
                        int(parts[0]), float(parts[1]),
                        int(parts[2]), int(parts[3])
                    )
                    writer.writerow([frame.timestamp_ms, frame.distance_mm,
                                     frame.session_time_s, frame.repetition_count])
                    f.flush()
                    while not self.queue.empty():
                        try: self.queue.get_nowait()
                        except queue.Empty: break
                    self.queue.put(frame)
                except (ValueError, serial.SerialException):
                    continue
        ser.close()

    def stop(self):
        self.running = False


# Helpers
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
    pygame.draw.polygon(surface, color, [
        (cx - size*2//3, cy + 2),
        (cx, cy + size*4//5),
        (cx + size*2//3, cy + 2),
    ])


def dist_to_y(dist, dist_min, dist_max, margin=60):
    t = (dist - dist_min) / max(dist_max - dist_min, 1)
    t = max(0.0, min(1.0, t))
    return int(SCREEN_H - margin - t * (SCREEN_H - 2 * margin))


def spawn_particles(particles, x, y, color, count=14):
    for _ in range(count):
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(1.5, 4.5)
        particles.append(Particle(
            x=x, y=y,
            vx=math.cos(angle) * speed,
            vy=math.sin(angle) * speed - 1.5,
            life=1.0, color=color,
            size=random.uniform(3, 6)
        ))


def update_draw_particles(surface, particles):
    alive = []
    for p in particles:
        p.x += p.vx; p.y += p.vy; p.vy += 0.18; p.life -= 0.04
        if p.life > 0:
            r = max(1, int(p.size * p.life))
            surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*p.color, int(255 * p.life)), (r, r), r)
            surface.blit(surf, (int(p.x)-r, int(p.y)-r))
            alive.append(p)
    particles[:] = alive


def zone_y_range(zone_idx, margin=60):
    """Zwraca (y_top, y_bottom) dla strefy na ekranie (0=góra, 3=dół)."""
    usable = SCREEN_H - 2 * margin
    h = usable / N_ZONES
    y_top = margin + zone_idx * h
    y_bot = y_top + h
    return int(y_top), int(y_bot)


def ball_zone(ball_y, margin=60):
    """Zwraca indeks strefy w której jest kulka."""
    usable = SCREEN_H - 2 * margin
    h = usable / N_ZONES
    idx = int((ball_y - margin) / h)
    return max(0, min(N_ZONES - 1, idx))


def zone_label(idx):
    return ["GÓRA", "GÓR. ŚRODEK", "DOL. ŚRODEK", "DÓŁ"][idx]


# Ekrany
def connecting_screen(screen, clock, fonts, reader):
    import time
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
            screen.blit(t1, (SCREEN_W//2 - t1.get_width()//2, 280))
            screen.blit(t2, (SCREEN_W//2 - t2.get_width()//2, 330))
        elif reader.connected:
            return
        else:
            dots = '.' * (int(time.time() * 2) % 4)
            t = font_big.render(f"Łączenie z {PORT}{dots}", True, C_TEXT)
            screen.blit(t, (SCREEN_W//2 - t.get_width()//2, 310))
        pygame.display.flip()


def calibration_screen(screen, clock, fonts, data_queue):
    font_big, font_mid, font_sm = fonts
    font_huge = pygame.font.SysFont('Arial', 72, bold=True)
    steps = [
        ('1 / 2', 'GÓRA',  'Ustaw ciało / rękę w najwyższej pozycji', 'max',
         C_GREEN, (230, 248, 238)),
        ('2 / 2', 'DÓŁ',   'Ustaw ciało / rękę w najniższej pozycji', 'min',
         C_AMBER, (252, 244, 224)),
    ]
    results    = {}
    btn_rect   = pygame.Rect(SCREEN_W//2 - 120, SCREEN_H - 120, 240, 54)
    last_frame = None

    for step_lbl, big_lbl, instruction, key, accent, bg_accent in steps:
        confirmed = False
        while not confirmed:
            clock.tick(FPS)
            mx, my = pygame.mouse.get_pos()
            hovered = btn_rect.collidepoint(mx, my)
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and hovered and last_frame:
                    results[key] = last_frame.distance_mm
                    confirmed = True
            try: last_frame = data_queue.get_nowait()
            except queue.Empty: pass

            screen.fill(C_BG)
            pygame.draw.rect(screen, bg_accent, (0, 0, SCREEN_W, 200))
            sl = font_sm.render(f"KALIBRACJA  {step_lbl}", True, C_MUTED)
            screen.blit(sl, (SCREEN_W//2 - sl.get_width()//2, 18))
            bl = font_huge.render(big_lbl, True, accent)
            screen.blit(bl, (SCREEN_W//2 - bl.get_width()//2, 50))
            cx = SCREEN_W//2
            if key == 'max':
                pts = [(cx, 148), (cx-28, 185), (cx+28, 185)]
            else:
                pts = [(cx, 188), (cx-28, 151), (cx+28, 151)]
            pygame.draw.polygon(screen, accent, pts)
            pygame.draw.line(screen, C_TRACK, (40, 210), (SCREEN_W-40, 210), 1)
            inst = font_mid.render(instruction, True, C_TEXT)
            screen.blit(inst, (SCREEN_W//2 - inst.get_width()//2, 230))
            sub = font_sm.render("Kliknij ZATWIERDŹ gdy jesteś gotowy", True, C_MUTED)
            screen.blit(sub, (SCREEN_W//2 - sub.get_width()//2, 268))

            if last_frame:
                box = pygame.Rect(SCREEN_W//2 - 130, 308, 260, 90)
                pygame.draw.rect(screen, (255, 255, 255), box, border_radius=12)
                pygame.draw.rect(screen, accent, box, width=2, border_radius=12)
                dl = font_sm.render("Aktualna odległość", True, C_MUTED)
                screen.blit(dl, (SCREEN_W//2 - dl.get_width()//2, 320))
                dv = font_big.render(f"{last_frame.distance_mm:.0f} mm", True, accent)
                screen.blit(dv, (SCREEN_W//2 - dv.get_width()//2, 348))
            else:
                nd = font_sm.render("Oczekiwanie na dane z czujnika...", True, C_AMBER)
                screen.blit(nd, (SCREEN_W//2 - nd.get_width()//2, 350))

            btn_color = (C_BTN_HOVER if hovered else accent) if last_frame else C_MUTED
            pygame.draw.rect(screen, btn_color, btn_rect, border_radius=10)
            bl2 = font_mid.render("ZATWIERDŹ", True, C_BTN_TEXT)
            screen.blit(bl2, (btn_rect.x + (btn_rect.w - bl2.get_width())//2,
                               btn_rect.y + (btn_rect.h - bl2.get_height())//2))
            pygame.display.flip()

    d_min = min(results['min'], results['max'])
    d_max = max(results['min'], results['max'])
    if d_max - d_min < 20:
        d_max = d_min + 100
    return d_min, d_max


def game_over_screen(screen, clock, fonts, score):
    font_big, font_mid, font_sm = fonts
    btn_play  = pygame.Rect(SCREEN_W//2 - 120, 400, 240, 50)
    btn_stats = pygame.Rect(SCREEN_W//2 - 120, 464, 240, 50)
    while True:
        clock.tick(FPS)
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_play.collidepoint(mx, my):  return 'play'
                if btn_stats.collidepoint(mx, my): return 'stats'
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


# Główna gra
def game_screen(screen, clock, fonts, data_queue, dist_min, dist_max):
    font_big, font_mid, font_sm = fonts
    font_zone = pygame.font.SysFont('Arial', 13, bold=True)

    ball_y    = float(SCREEN_H // 2)
    target_y  = ball_y
    smooth    = 0.14
    trail     = []
    TRAIL_LEN = 22

    score      = 0
    lives      = MAX_LIVES
    last_dist  = None
    particles  = []

    # Stan stref
    # Każda strefa: 'safe' | 'warning' | 'danger'
    zone_states  = ['safe'] * N_ZONES
    zone_timer   = 0.0        # czas do następnej zmiany fazy (sekundy)
    phase        = 'safe'     # globalna faza: 'safe' | 'warning' | 'danger'
    danger_zones = []         # indeksy aktualnie niebezpiecznych stref
    warn_zones   = []
    danger_left  = 0.0        # ile czasu zostało na ucieczkę
    danger_total = 1.0        # całkowity czas fazy danger (do paska)
    invincible   = 0          # klatki nietykalności

    # Rozpocznij od fazy spokoju
    zone_timer = random.uniform(SAFE_TIME_MIN, SAFE_TIME_MAX)

    btn_quit = pygame.Rect(SCREEN_W - 110, 14, 95, 34)

    def pick_danger_zones():
        idxs = list(range(N_ZONES))
        random.shuffle(idxs)
        return idxs[:DANGER_COUNT]

    while True:
        dt = clock.tick(FPS) / 1000.0   # delta time w sekundach
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:    return score
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return score
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_quit.collidepoint(mx, my): return score

        # Dane z czujnika
        try:
            frame = data_queue.get_nowait()
            last_dist = frame.distance_mm
            target_y  = float(dist_to_y(frame.distance_mm, dist_min, dist_max))
        except queue.Empty:
            pass

        ball_y += (target_y - ball_y) * smooth
        trail.append((TRACK_X, int(ball_y)))
        if len(trail) > TRAIL_LEN: trail.pop(0)

        # Logika faz
        zone_timer -= dt

        if phase == 'safe' and zone_timer <= 0:
            # Przejdź do ostrzeżenia
            phase      = 'warning'
            warn_zones = pick_danger_zones()
            zone_timer = WARN_TIME

        elif phase == 'warning' and zone_timer <= 0:
            # Przejdź do niebezpieczeństwa
            phase        = 'danger'
            danger_zones = warn_zones
            warn_zones   = []
            danger_total = random.uniform(DANGER_TIME_MIN, DANGER_TIME_MAX)
            danger_left  = danger_total
            zone_timer   = danger_total

        elif phase == 'danger':
            danger_left = zone_timer
            if zone_timer <= 0:
                # Koniec fazy niebezpieczeństwa
                phase        = 'safe'
                danger_zones = []
                zone_timer   = random.uniform(SAFE_TIME_MIN, SAFE_TIME_MAX)
                score       += 20    # przeżyłeś falę

            elif invincible <= 0:
                # Sprawdź czy kulka jest w niebezpiecznej strefie
                cur_zone = ball_zone(ball_y)
                if cur_zone in danger_zones:
                    lives      -= 1
                    invincible  = int(1.5 * FPS)
                    spawn_particles(particles, TRACK_X, int(ball_y), C_RED, 20)
                    if lives <= 0:
                        return score

        if invincible > 0: invincible -= 1

        # Rysowanie
        screen.fill(C_BG)

        # Strefy – kolorowe prostokąty
        zone_surf = pygame.Surface((TRACK_X, SCREEN_H), pygame.SRCALPHA)
        for i in range(N_ZONES):
            y_top, y_bot = zone_y_range(i)

            if phase == 'danger' and i in danger_zones:
                # Pulsowanie czerwieni
                pulse = abs(math.sin(pygame.time.get_ticks() * 0.005))
                alpha = int(80 + 100 * pulse)
                color = (*C_RED, alpha)
            elif phase == 'warning' and i in warn_zones:
                pulse = abs(math.sin(pygame.time.get_ticks() * 0.008))
                alpha = int(60 + 80 * pulse)
                color = (*C_AMBER, alpha)
            else:
                color = (200, 220, 205, 40)

            pygame.draw.rect(zone_surf, color, (0, y_top, TRACK_X, y_bot - y_top))

            # Linia podziału strefy
            pygame.draw.line(zone_surf, (*ZONE_BORDER, 120),
                             (0, y_bot), (TRACK_X, y_bot), 1)

            # Etykieta strefy
            lbl = font_zone.render(zone_label(i), True,
                                   C_RED if (phase == 'danger' and i in danger_zones)
                                   else C_MUTED)
            zone_surf.blit(lbl, (14, y_top + (y_bot - y_top)//2 - lbl.get_height()//2))

        screen.blit(zone_surf, (0, 0))

        # Timer ostrzeżenia / niebezpieczeństwa
        if phase == 'warning':
            bar_w   = int((WARN_TIME - (WARN_TIME - zone_timer)) / WARN_TIME * (TRACK_X - 40))
            pygame.draw.rect(screen, C_AMBER, (20, SCREEN_H - 20, bar_w, 8), border_radius=4)
            txt = font_sm.render(f"UWAGA! Zaraz niebezpiecznie!", True, C_AMBER)
            screen.blit(txt, (SCREEN_W//2 - txt.get_width()//2, SCREEN_H - 40))

        elif phase == 'danger':
            bar_frac = max(0.0, danger_left / danger_total)
            bar_w    = int(bar_frac * (TRACK_X - 40))
            pygame.draw.rect(screen, C_RED, (20, SCREEN_H - 20, bar_w, 8), border_radius=4)
            txt = font_sm.render(f"UCIEKAJ!  {danger_left:.1f}s", True, C_RED)
            screen.blit(txt, (SCREEN_W//2 - txt.get_width()//2, SCREEN_H - 40))

        # Linia toru
        pygame.draw.line(screen, C_TRACK, (TRACK_X, 50), (TRACK_X, SCREEN_H - 50), 2)

        # Ślad kulki
        update_draw_particles(screen, particles)
        for i, (tx, ty) in enumerate(trail):
            r = max(3, int(22 * 0.45 * (i / TRAIL_LEN)))
            alpha = int(80 * (i / TRAIL_LEN))
            surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*C_BALL_RIM, alpha), (r, r), r)
            screen.blit(surf, (tx-r, ty-r))

        # Kulka (miga gdy nietykalność)
        if invincible <= 0 or (invincible // 6) % 2 == 0:
            pygame.draw.circle(screen, C_BALL_RIM, (TRACK_X, int(ball_y)), 25)
            pygame.draw.circle(screen, C_BALL,     (TRACK_X, int(ball_y)), 22)

        # HUD – score
        screen.blit(font_sm.render("SCORE",   True, C_MUTED), (TRACK_X + 10, 18))
        screen.blit(font_big.render(str(score), True, C_TEXT), (TRACK_X + 10, 40))

        # HUD – lives
        for i in range(MAX_LIVES):
            draw_heart(screen, TRACK_X + 14 + i * 30, 95, 12, i < lives)

        # HUD – dystans
        if last_dist is not None:
            screen.blit(font_sm.render(f"{last_dist:.0f}mm", True, C_MUTED),
                        (TRACK_X + 10, 120))

        # Przycisk wyjścia
        draw_button(screen, btn_quit, "WYJDŹ", font_sm,
                    btn_quit.collidepoint(mx, my))

        pygame.display.flip()

    return score


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Zone Dodge")
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
        dist_min, dist_max = calibration_screen(screen, clock, fonts, data_queue)
        final_score        = game_screen(screen, clock, fonts,
                                         data_queue, dist_min, dist_max)
        action = game_over_screen(screen, clock, fonts, final_score)
        if action == 'stats':
            subprocess.Popen([
                sys.executable, 'session_stats.py',
                CSV_FILE, str(final_score),
                str(dist_min), str(dist_max),
            ])

    reader.stop()
    pygame.quit()


if __name__ == '__main__':
    main()