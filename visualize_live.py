import time
import matplotlib
matplotlib.use('TkAgg')
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.gridspec import GridSpec

# ── Konfiguracja ──────────────────────────────────────────────────────────────
CSV_FILE      = 'dane.csv'
REFRESH_MS    = 300        # co ile ms odświeżać wykres
MAX_POINTS    = 300        # ile ostatnich próbek pokazywać na żywym wykresie
# ─────────────────────────────────────────────────────────────────────────────

# ── Setup figury ──────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(12, 6))
fig.suptitle("Live – czujnik odległości", fontsize=14, fontweight='bold')
gs = GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)

ax_dist  = fig.add_subplot(gs[0, :])   # szeroki – distance vs czas
ax_rep   = fig.add_subplot(gs[1, 0])   # licznik powtórzeń
ax_stats = fig.add_subplot(gs[1, 1])   # min/max/avg bieżącego powtórzenia

for ax in (ax_dist, ax_rep, ax_stats):
    ax.set_facecolor('#1e1e2e')
fig.patch.set_facecolor('#13131f')

LINE_COLOR   = '#cba6f7'
ACCENT_COLOR = '#89dceb'
TEXT_COLOR   = '#cdd6f4'

plt.rcParams.update({'text.color': TEXT_COLOR, 'axes.labelcolor': TEXT_COLOR,
                     'xtick.color': TEXT_COLOR, 'ytick.color': TEXT_COLOR,
                     'axes.edgecolor': '#45475a'})
# ─────────────────────────────────────────────────────────────────────────────


def load_csv(filepath: str) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(filepath)
        df = df.dropna(subset=['distance_mm'])
        df['distance_mm'] = pd.to_numeric(df['distance_mm'], errors='coerce')
        df['repetition_count'] = pd.to_numeric(df['repetition_count'], errors='coerce')
        df = df.dropna()
        return df
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return None


def update(frame):
    df = load_csv(CSV_FILE)

    # ── Wykres distance_mm ────────────────────────────────────────────────────
    ax_dist.cla()
    ax_dist.set_facecolor('#1e1e2e')
    ax_dist.set_title("Odległość w czasie (ostatnie próbki)", color=TEXT_COLOR, fontsize=10)
    ax_dist.set_xlabel("Czas sesji (s)", fontsize=8)
    ax_dist.set_ylabel("Odległość (mm)", fontsize=8)

    if df is not None and len(df) > 0:
        tail = df.tail(MAX_POINTS)
        ax_dist.plot(tail['session_time_s'], tail['distance_mm'],
                     color=LINE_COLOR, linewidth=1.2)
        ax_dist.fill_between(tail['session_time_s'], tail['distance_mm'],
                              alpha=0.15, color=LINE_COLOR)
        ax_dist.axhline(tail['distance_mm'].mean(), color=ACCENT_COLOR,
                        linestyle='--', linewidth=0.8, alpha=0.7)

    ax_dist.grid(True, color='#45475a', linewidth=0.5, alpha=0.5)

    # ── Licznik powtórzeń ─────────────────────────────────────────────────────
    ax_rep.cla()
    ax_rep.set_facecolor('#1e1e2e')
    ax_rep.set_title("Powtórzenia", color=TEXT_COLOR, fontsize=10)
    ax_rep.axis('off')

    if df is not None and len(df) > 0:
        current_rep = int(df['repetition_count'].max())
        ax_rep.text(0.5, 0.5, str(current_rep),
                    ha='center', va='center', fontsize=56,
                    fontweight='bold', color=ACCENT_COLOR,
                    transform=ax_rep.transAxes)
        ax_rep.text(0.5, 0.12, "powtórzeń",
                    ha='center', va='center', fontsize=10,
                    color=TEXT_COLOR, transform=ax_rep.transAxes)
    else:
        ax_rep.text(0.5, 0.5, "–", ha='center', va='center',
                    fontsize=56, color='#45475a', transform=ax_rep.transAxes)

    # ── Statystyki bieżącego powtórzenia ──────────────────────────────────────
    ax_stats.cla()
    ax_stats.set_facecolor('#1e1e2e')
    ax_stats.set_title("Bieżące powt. – statystyki", color=TEXT_COLOR, fontsize=10)
    ax_stats.axis('off')

    if df is not None and len(df) > 0:
        last_rep = df[df['repetition_count'] == df['repetition_count'].max()]
        d = last_rep['distance_mm']

        lines = [
            ("min",  f"{d.min():.0f} mm"),
            ("max",  f"{d.max():.0f} mm"),
            ("avg",  f"{d.mean():.0f} mm"),
            ("próbki", str(len(d))),
        ]
        y = 0.82
        for label, val in lines:
            ax_stats.text(0.15, y, label, ha='left', fontsize=9,
                          color='#a6adc8', transform=ax_stats.transAxes)
            ax_stats.text(0.85, y, val, ha='right', fontsize=9,
                          fontweight='bold', color=TEXT_COLOR,
                          transform=ax_stats.transAxes)
            y -= 0.20
    else:
        ax_stats.text(0.5, 0.5, "Brak danych",
                      ha='center', va='center', fontsize=10,
                      color='#45475a', transform=ax_stats.transAxes)


ani = animation.FuncAnimation(fig, update, interval=REFRESH_MS, cache_frame_data=False)

plt.show()