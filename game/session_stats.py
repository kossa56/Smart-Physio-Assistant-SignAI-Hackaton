import matplotlib
matplotlib.use('TkAgg')

import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ── Argumenty z game.py ───────────────────────────────────────────────────────
# Wywoływany jako: python session_stats.py <csv_file> <score> <dist_min> <dist_max>
CSV_FILE  = sys.argv[1] if len(sys.argv) > 1 else '../dane.csv'
SCORE     = int(sys.argv[2])   if len(sys.argv) > 2 else 0
DIST_MIN  = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
DIST_MAX  = float(sys.argv[4]) if len(sys.argv) > 4 else 500.0
# ─────────────────────────────────────────────────────────────────────────────

# ── Kolory (spójne z resztą projektu) ────────────────────────────────────────
BG_MAIN  = '#FAF6F2'
BG_PANEL = '#F2EAE0'
C_PURPLE = '#5C3D8F'
C_GREEN  = '#6BAE8A'
C_AMBER  = '#C9A96E'
C_CORAL  = '#C97A7A'
C_BLUE   = '#7AAEC9'
C_TEXT   = '#1A1A1A'
C_MUTED  = '#8B7D72'
C_GRID   = '#DDD0C4'
C_VLINE  = '#8B5E3C'
OVERLAY  = ['#5C3D8F', '#6BAE8A', '#C97A7A', '#C9A96E', '#7AAEC9',
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
    'font.family':     'sans-serif',
})


def amp_color(a: float) -> str:
    if a > 350: return C_GREEN
    if a > 250: return C_PURPLE
    return C_CORAL


def stat_card(ax, label: str, value: str, sub: str, color: str):
    ax.set_facecolor(BG_PANEL)
    ax.axis('off')
    ax.text(0.5, 0.74, label, ha='center', va='center',
            fontsize=10, color=C_MUTED, transform=ax.transAxes)
    ax.text(0.5, 0.40, value, ha='center', va='center',
            fontsize=26, fontweight='bold', color=color,
            transform=ax.transAxes)
    ax.text(0.5, 0.12, sub,   ha='center', va='center',
            fontsize=9,  color=C_MUTED, transform=ax.transAxes)


def main():
    # ── Wczytaj dane ─────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(CSV_FILE)
        df['distance_mm']      = pd.to_numeric(df['distance_mm'],      errors='coerce')
        df['repetition_count'] = pd.to_numeric(df['repetition_count'], errors='coerce')
        df['session_time_s']   = pd.to_numeric(df['session_time_s'],   errors='coerce')
        df = df.dropna()
    except Exception as e:
        print(f"Błąd wczytywania CSV: {e}")
        sys.exit(1)

    if len(df) < 2:
        print("Za mało danych do analizy.")
        sys.exit(1)

    # ── Oblicz statystyki ─────────────────────────────────────────────────────
    rep_groups  = df.groupby('repetition_count')['distance_mm']
    amps        = (rep_groups.max() - rep_groups.min()).reset_index()
    amps.columns = ['rep', 'amp']
    total_reps  = int(df['repetition_count'].max())
    session_s   = int(df['session_time_s'].max() - df['session_time_s'].min())
    avg_amp     = amps['amp'].mean()
    best_rep    = int(amps.loc[amps['amp'].idxmax(), 'rep'])
    best_amp    = amps['amp'].max()
    ys          = df['distance_mm'].values

    # ── Layout ───────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(15, 9), facecolor=BG_MAIN)
    fig.patch.set_facecolor(BG_MAIN)
    fig.suptitle("Podsumowanie sesji", fontsize=15, fontweight='bold',
                 color=C_TEXT, y=0.98)

    gs = gridspec.GridSpec(3, 3, figure=fig,
                           hspace=0.55, wspace=0.35,
                           left=0.06, right=0.97, top=0.92, bottom=0.07)

    # ── Wiersz 1: karty ───────────────────────────────────────────────────────
    stat_card(fig.add_subplot(gs[0, 0]),
              "Wynik końcowy", str(SCORE),         "punktów",   C_PURPLE)
    stat_card(fig.add_subplot(gs[0, 1]),
              "Powtórzenia",   str(total_reps),    "w sesji",   C_GREEN)
    stat_card(fig.add_subplot(gs[0, 2]),
              "Czas sesji",    f"{session_s} s",   "od startu", C_AMBER)

    # ── Wiersz 2: główny wykres + amplituda ───────────────────────────────────
    ax_main = fig.add_subplot(gs[1, :2])
    ax_amp  = fig.add_subplot(gs[1, 2])

    ax_main.set_facecolor(BG_PANEL)
    ax_main.set_title("Odległość w czasie", color=C_TEXT, fontsize=10, pad=5)
    ax_main.set_xlabel("Czas sesji (s)", fontsize=8)
    ax_main.set_ylabel("Odległość (mm)", fontsize=8)
    ax_main.grid(True, color=C_GRID, linewidth=0.5)

    xs = list(range(len(df)))
    ax_main.plot(xs, ys, color=C_PURPLE, linewidth=2.0)
    ax_main.fill_between(xs, ys, alpha=0.15, color=C_PURPLE)
    ax_main.axhline(ys.mean(), color=C_GREEN, linestyle='--',
                    linewidth=0.9, alpha=0.8)

    # Linie kalibracji
    ax_main.axhline(DIST_MAX, color=C_GREEN, linestyle=':', linewidth=1.0, alpha=0.6)
    ax_main.axhline(DIST_MIN, color=C_AMBER, linestyle=':', linewidth=1.0, alpha=0.6)
    ax_main.text(len(df) * 0.01, DIST_MAX + 8, 'MAX kalibracja',
                 fontsize=7, color=C_GREEN, alpha=0.8)
    ax_main.text(len(df) * 0.01, DIST_MIN + 8, 'MIN kalibracja',
                 fontsize=7, color=C_AMBER, alpha=0.8)

    # Kreski końca powtórzeń
    df_r     = df.reset_index(drop=True)
    rep_ends = df_r.groupby('repetition_count').tail(1).index.tolist()
    for idx in rep_ends:
        ax_main.axvline(x=idx, color=C_VLINE, linewidth=0.8,
                        linestyle='--', alpha=0.5)

    tick_step = max(1, len(df) // 8)
    tick_idxs = list(range(0, len(df), tick_step))
    ax_main.set_xticks(tick_idxs)
    ax_main.set_xticklabels(
        [str(int(df['session_time_s'].iloc[i])) for i in tick_idxs], fontsize=7
    )

    ax_amp.set_facecolor(BG_PANEL)
    ax_amp.set_title("Amplituda per powtórzenie", color=C_TEXT, fontsize=10, pad=5)
    ax_amp.set_xlabel("Nr powtórzenia", fontsize=8)
    ax_amp.set_ylabel("Amplituda (mm)", fontsize=8)
    ax_amp.grid(True, color=C_GRID, linewidth=0.5, axis='y')
    ax_amp.bar(amps['rep'], amps['amp'],
               color=[amp_color(a) for a in amps['amp']], width=0.7)
    ax_amp.axhline(avg_amp, color=C_AMBER, linestyle='--',
                   linewidth=0.9, alpha=0.8)

    # ── Wiersz 3: overlay + histogram + tabelka ───────────────────────────────
    ax_ov   = fig.add_subplot(gs[2, 0])
    ax_hist = fig.add_subplot(gs[2, 1])
    ax_tbl  = fig.add_subplot(gs[2, 2])

    ax_ov.set_facecolor(BG_PANEL)
    ax_ov.set_title("Powtórzenia nałożone (ostatnie 10)", color=C_TEXT, fontsize=10, pad=5)
    ax_ov.set_xlabel("Próbka", fontsize=8)
    ax_ov.set_ylabel("Odległość (mm)", fontsize=8)
    ax_ov.grid(True, color=C_GRID, linewidth=0.5)

    for i, rep in enumerate(sorted(df['repetition_count'].unique())[-10:]):
        vals  = df[df['repetition_count'] == rep]['distance_mm'].values
        alpha = 0.35 + 0.65 * (i / 9)
        ax_ov.plot(range(len(vals)), vals,
                   color=OVERLAY[i % len(OVERLAY)],
                   linewidth=1.5, alpha=alpha, marker='o', markersize=3)

    ax_hist.set_facecolor(BG_PANEL)
    ax_hist.set_title("Rozkład odległości", color=C_TEXT, fontsize=10, pad=5)
    ax_hist.set_xlabel("Odległość (mm)", fontsize=8)
    ax_hist.set_ylabel("Liczba próbek", fontsize=8)
    ax_hist.grid(True, color=C_GRID, linewidth=0.5, axis='y')
    ax_hist.hist(df['distance_mm'], bins=20, color=C_BLUE,
                 edgecolor=BG_MAIN, linewidth=0.5)
    ax_hist.axvline(ys.mean(), color=C_PURPLE, linestyle='--',
                    linewidth=1.0, label=f"śr. {ys.mean():.0f} mm")
    ax_hist.legend(fontsize=7)

    ax_tbl.set_facecolor(BG_PANEL)
    ax_tbl.axis('off')
    rows = [
        ("Śr. amplituda",   f"{avg_amp:.0f} mm",  C_PURPLE),
        ("Najlepsza rep",   f"#{best_rep}",         C_GREEN),
        ("Maks. amplituda", f"{best_amp:.0f} mm",  C_GREEN),
        ("Min dystans",     f"{ys.min():.0f} mm",  C_AMBER),
        ("Maks dystans",    f"{ys.max():.0f} mm",  C_CORAL),
    ]
    y0 = 0.90
    for label, val, color in rows:
        ax_tbl.text(0.05, y0, label, ha='left', fontsize=9,
                    color=C_MUTED, transform=ax_tbl.transAxes)
        ax_tbl.text(0.95, y0, val, ha='right', fontsize=9,
                    fontweight='bold', color=color, transform=ax_tbl.transAxes)
        ax_tbl.plot([0.05, 0.95], [y0 - 0.05, y0 - 0.05],
                    color=C_GRID, linewidth=0.5, transform=ax_tbl.transAxes)
        y0 -= 0.17

    plt.show()


if __name__ == '__main__':
    main()
