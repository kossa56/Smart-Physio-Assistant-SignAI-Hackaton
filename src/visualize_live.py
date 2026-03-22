import matplotlib
matplotlib.use('TkAgg')

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec

# ── Konfiguracja ──────────────────────────────────────────────────────────────
CSV_FILE      = '../dane.csv'
REFRESH_MS    = 300
MAX_POINTS    = 300
OVERLAY_REPS  = 10       # ile ostatnich powtórzeń nakładać na siebie
# ─────────────────────────────────────────────────────────────────────────────

# ── Kolory ────────────────────────────────────────────────────────────────────
BG_MAIN      = '#FAF6F2'   # bardzo jasny beż – tło okna
BG_PANEL     = '#F2EAE0'   # beż – tło paneli wykresów
BG_CARD      = '#F2EAE0'   # beż – karty statystyk
C_LINE       = '#5C3D8F'   # ciemny fiolet – główna linia wykresu
C_FILL       = '#C9B8D4'   # jasny fiolet – wypełnienie
C_MEAN       = '#6BAE8A'   # zielony – linia średniej
C_VLINE      = '#8B5E3C'   # ciemny brąz – kreski końca powtórzeń
C_TEAL       = '#6BAE8A'   # zielony pastel – amplituda wysoka
C_PURPLE     = '#A07CC5'   # fiolet – amplituda średnia
C_CORAL      = '#C97A7A'   # róż – amplituda niska
C_TEXT       = '#1A1A1A'   # czarny – wszystkie napisy
C_MUTED      = '#7A6F66'   # szary brąz – napisy drugorzędne
C_GRID       = '#DDD0C4'   # jasna siatka
OVERLAY_COLORS = ['#A07CC5', '#6BAE8A', '#C97A7A', '#C9A96E', '#7AAEC9',
                  '#8ABE8A', '#C9966E', '#7A9EC9', '#BE7AC9', '#6EC9B0']
# ─────────────────────────────────────────────────────────────────────────────

plt.rcParams.update({
    'text.color':      C_TEXT,
    'axes.labelcolor': C_TEXT,
    'xtick.color':     C_MUTED,
    'ytick.color':     C_MUTED,
    'axes.edgecolor':  C_GRID,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
})

fig = plt.figure(figsize=(14, 7), facecolor=BG_MAIN)
fig.suptitle("Live Session Dashboard", fontsize=13, fontweight='bold',
             color=C_TEXT, y=0.98)

gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.55, wspace=0.35,
                       left=0.07, right=0.97, top=0.92, bottom=0.1)

ax_main    = fig.add_subplot(gs[0, :])
ax_amp     = fig.add_subplot(gs[1, 0])
ax_overlay = fig.add_subplot(gs[1, 1])
ax_stats   = fig.add_subplot(gs[1, 2])

for ax in (ax_main, ax_amp, ax_overlay):
    ax.set_facecolor(BG_PANEL)
ax_stats.set_facecolor(BG_MAIN)
ax_stats.axis('off')
fig.patch.set_facecolor(BG_MAIN)


def load_csv(filepath: str) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(filepath)
        df = df.dropna(subset=['distance_mm'])
        df['distance_mm']      = pd.to_numeric(df['distance_mm'],      errors='coerce')
        df['repetition_count'] = pd.to_numeric(df['repetition_count'], errors='coerce')
        df['session_time_s']   = pd.to_numeric(df['session_time_s'],   errors='coerce')
        return df.dropna() if len(df.dropna()) > 0 else None
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return None


def amp_color(amp: float) -> str:
    if amp > 350:
        return C_TEAL
    elif amp > 250:
        return C_PURPLE
    return C_CORAL


def draw_stats(ax, df: pd.DataFrame | None) -> None:
    ax.cla()
    ax.set_facecolor(BG_MAIN)
    ax.axis('off')

    if df is None:
        ax.text(0.5, 0.5, 'Brak danych', ha='center', va='center',
                color=C_MUTED, fontsize=10, transform=ax.transAxes)
        return

    reps        = int(df['repetition_count'].max())
    session_s   = int(df['session_time_s'].max() - df['session_time_s'].min())
    last_rep_df = df[df['repetition_count'] == df['repetition_count'].max()]['distance_mm']
    rep_groups  = df.groupby('repetition_count')['distance_mm']
    avg_amp     = (rep_groups.max() - rep_groups.min()).mean()

    cards = [
        ("Powtórzenia",    f"{reps}",               "w sesji"),
        ("Śr. amplituda",  f"{avg_amp:.0f} mm",     "zakres ruchu"),
        ("Czas sesji",     f"{session_s} s",         "od startu"),
        ("Ostatnie min",   f"{last_rep_df.min():.0f} mm", f"rep {reps}"),
        ("Ostatnie max",   f"{last_rep_df.max():.0f} mm", f"rep {reps}"),
    ]

    card_h = 0.16
    gap    = 0.03
    total  = len(cards) * card_h + (len(cards) - 1) * gap
    y0     = 0.5 + total / 2

    for label, value, sub in cards:
        rect = plt.Rectangle((0.02, y0 - card_h), 0.96, card_h,
                              facecolor=BG_CARD, edgecolor=C_GRID,
                              linewidth=0.5, transform=ax.transAxes, clip_on=False)
        ax.add_patch(rect)
        ax.text(0.08, y0 - 0.03, label, ha='left', va='top',
                fontsize=8, color=C_MUTED, transform=ax.transAxes)
        ax.text(0.08, y0 - 0.09, value, ha='left', va='top',
                fontsize=13, fontweight='bold', color=C_TEXT, transform=ax.transAxes)
        ax.text(0.92, y0 - 0.09, sub, ha='right', va='top',
                fontsize=8, color=C_MUTED, transform=ax.transAxes)
        y0 -= (card_h + gap)


def update(frame) -> None:
    df = load_csv(CSV_FILE)

    # ── Górny wykres – surowy sygnał ─────────────────────────────────────────
    ax_main.cla()
    ax_main.set_facecolor(BG_PANEL)
    ax_main.set_title("Odległość w czasie", color=C_TEXT, fontsize=10, pad=6)
    ax_main.set_xlabel("Czas sesji (s)", fontsize=8)
    ax_main.set_ylabel("Odległość (mm)", fontsize=8)
    ax_main.grid(True, color=C_GRID, linewidth=0.5)

    if df is not None:
        tail = df.tail(MAX_POINTS)
        xs   = list(range(len(tail)))
        ys   = tail['distance_mm'].values

        ax_main.plot(xs, ys, color=C_LINE, linewidth=2.5)
        ax_main.fill_between(xs, ys, alpha=0.18, color=C_FILL)
        ax_main.axhline(ys.mean(), color=C_MEAN,
                        linestyle='--', linewidth=1.0, alpha=0.8)

        ax_main.set_xlim(0, MAX_POINTS)
        ax_main.set_ylim(max(0, int(ys.min()) - 40), int(ys.max()) + 40)

        tick_step = max(1, len(tail) // 6)
        tick_idxs = list(range(0, len(tail), tick_step))
        ax_main.set_xticks(tick_idxs)
        ax_main.set_xticklabels(
            [str(int(tail['session_time_s'].iloc[i])) for i in tick_idxs],
            fontsize=7
        )

        # pionowe kreski na końcu każdego powtórzenia
        tail_reset = tail.reset_index(drop=True)
        rep_ends = tail_reset.groupby('repetition_count').tail(1).index.tolist()
        for idx in rep_ends:
            ax_main.axvline(x=idx, color=C_VLINE, linewidth=1.0,
                            linestyle='--', alpha=0.7)
            rep_num = int(tail_reset.loc[idx, 'repetition_count'])
            ax_main.text(idx + 1, int(ys.max()) + 20, str(rep_num),
                         fontsize=6, color=C_VLINE, alpha=0.9, va='top')

    # ── Amplituda per powtórzenie ─────────────────────────────────────────────
    ax_amp.cla()
    ax_amp.set_facecolor(BG_PANEL)
    ax_amp.set_title("Amplituda per powtórzenie", color=C_TEXT, fontsize=10, pad=6)
    ax_amp.set_xlabel("Nr powtórzenia", fontsize=8)
    ax_amp.set_ylabel("Amplituda (mm)", fontsize=8)
    ax_amp.grid(True, color=C_GRID, linewidth=0.5, axis='y')

    if df is not None:
        rep_groups = df.groupby('repetition_count')['distance_mm']
        amps = (rep_groups.max() - rep_groups.min()).reset_index()
        amps.columns = ['rep', 'amp']
        ax_amp.bar(amps['rep'], amps['amp'],
                   color=[amp_color(a) for a in amps['amp']], width=0.7)

    # ── Nałożone powtórzenia ──────────────────────────────────────────────────
    ax_overlay.cla()
    ax_overlay.set_facecolor(BG_PANEL)
    ax_overlay.set_title(f"Ostatnie {OVERLAY_REPS} powtórzeń", color=C_TEXT, fontsize=10, pad=6)
    ax_overlay.set_xlabel("Próbka", fontsize=8)
    ax_overlay.set_ylabel("Odległość (mm)", fontsize=8)
    ax_overlay.grid(True, color=C_GRID, linewidth=0.5)

    if df is not None:
        last_reps = sorted(df['repetition_count'].unique())[-OVERLAY_REPS:]
        for i, rep in enumerate(last_reps):
            vals  = df[df['repetition_count'] == rep]['distance_mm'].values
            alpha = 0.4 + 0.6 * (i / max(len(last_reps) - 1, 1))
            ax_overlay.plot(range(len(vals)), vals,
                            color=OVERLAY_COLORS[i % len(OVERLAY_COLORS)],
                            linewidth=1.5, alpha=alpha,
                            marker='o', markersize=3)

    # ── Karty statystyk ───────────────────────────────────────────────────────
    draw_stats(ax_stats, df)


ani = animation.FuncAnimation(fig, update, interval=REFRESH_MS, cache_frame_data=False)
plt.show()