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

    calib_range = DIST_MAX - DIST_MIN if DIST_MAX > DIST_MIN else 1

    # Płynność – odchylenie standardowe pochodnej (różnice między kolejnymi próbkami)
    diffs       = abs(pd.Series(ys).diff().dropna())
    smoothness_per_rep = {}
    for rep in df['repetition_count'].unique():
        rep_vals = df[df['repetition_count'] == rep]['distance_mm'].values
        if len(rep_vals) > 1:
            d = abs(pd.Series(rep_vals).diff().dropna())
            smoothness_per_rep[rep] = float(d.std())   # mniejsze = płynniej

    smooth_df = pd.DataFrame(list(smoothness_per_rep.items()),
                             columns=['rep', 'jerk']).sort_values('rep')
    global_jerk = diffs.std()

    # Zakres ruchu – ile % zakresu kalibracji pokrywa każde powtórzenie
    range_per_rep = {}
    for rep in df['repetition_count'].unique():
        rep_vals = df[df['repetition_count'] == rep]['distance_mm'].values
        used = rep_vals.max() - rep_vals.min()
        range_per_rep[rep] = min(100.0, used / calib_range * 100)

    range_df = pd.DataFrame(list(range_per_rep.items()),
                            columns=['rep', 'pct']).sort_values('rep')
    avg_range_pct = range_df['pct'].mean()

    # Ogólna ocena płynności (0–100, wyższa = lepsza)
    max_jerk  = diffs.max() if diffs.max() > 0 else 1
    smooth_score = max(0, int(100 - (global_jerk / max_jerk) * 100))

    # Komentarze
    comments = []
    if smooth_score >= 75:
        comments.append(("Ruch płynny", C_GREEN,
                         "Dobra kontrola — małe skoki między próbkami."))
    elif smooth_score >= 45:
        comments.append(("Ruch umiarkowany", C_AMBER,
                         "Kilka gwałtownych zmian — spróbuj poruszać się równiej."))
    else:
        comments.append(("Ruch szarpany", C_CORAL,
                         "Duże wahania sygnału — zwolnij i zadbaj o kontrolę."))

    if avg_range_pct >= 80:
        comments.append(("Zakres: pełny", C_GREEN,
                         f"Średnio {avg_range_pct:.0f}% zakresu — świetnie!"))
    elif avg_range_pct >= 55:
        comments.append(("Zakres: częściowy", C_AMBER,
                         f"Średnio {avg_range_pct:.0f}% zakresu — możesz zejść niżej lub wyżej."))
    else:
        comments.append(("Zakres: zbyt mały", C_CORAL,
                         f"Średnio {avg_range_pct:.0f}% zakresu — ruch zbyt płytki."))

    low_range_reps = range_df[range_df['pct'] < 40]['rep'].tolist()
    if low_range_reps:
        comments.append(("Słabe powtórzenia", C_CORAL,
                         f"Rep {', '.join(str(int(r)) for r in low_range_reps[:5])}"
                         f" — zakres < 40%."))

    # ── Layout 4×3
    fig = plt.figure(figsize=(15, 12), facecolor=BG_MAIN)
    fig.patch.set_facecolor(BG_MAIN)
    fig.suptitle("Podsumowanie sesji", fontsize=15, fontweight='bold',
                 color=C_TEXT, y=0.98)

    gs = gridspec.GridSpec(4, 3, figure=fig,
                           hspace=0.60, wspace=0.35,
                           left=0.06, right=0.97, top=0.93, bottom=0.05)

    # ── Wiersz 1: karty ────────────────────
    stat_card(fig.add_subplot(gs[0, 0]),
              "Wynik końcowy", str(SCORE),               "punktów",   C_PURPLE)
    stat_card(fig.add_subplot(gs[0, 1]),
              "Powtórzenia",   str(total_reps),          "w sesji",   C_GREEN)
    stat_card(fig.add_subplot(gs[0, 2]),
              "Czas sesji",    f"{session_s} s",         "od startu", C_AMBER)

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
    ax_main.axhline(DIST_MAX, color=C_GREEN, linestyle=':', linewidth=1.0, alpha=0.5)
    ax_main.axhline(DIST_MIN, color=C_AMBER, linestyle=':', linewidth=1.0, alpha=0.5)
    ax_main.text(len(df)*0.01, DIST_MAX + 8, 'MAX', fontsize=7,
                 color=C_GREEN, alpha=0.8)
    ax_main.text(len(df)*0.01, DIST_MIN + 8, 'MIN', fontsize=7,
                 color=C_AMBER, alpha=0.8)

    df_r     = df.reset_index(drop=True)
    rep_ends = df_r.groupby('repetition_count').tail(1).index.tolist()
    for idx in rep_ends:
        ax_main.axvline(x=idx, color=C_VLINE, linewidth=0.8,
                        linestyle='--', alpha=0.5)
    tick_step = max(1, len(df) // 8)
    tick_idxs = list(range(0, len(df), tick_step))
    ax_main.set_xticks(tick_idxs)
    ax_main.set_xticklabels(
        [str(int(df['session_time_s'].iloc[i])) for i in tick_idxs], fontsize=7)

    ax_amp.set_facecolor(BG_PANEL)
    ax_amp.set_title("Amplituda per powtórzenie", color=C_TEXT, fontsize=10, pad=5)
    ax_amp.set_xlabel("Nr powtórzenia", fontsize=8)
    ax_amp.set_ylabel("Amplituda (mm)", fontsize=8)
    ax_amp.grid(True, color=C_GRID, linewidth=0.5, axis='y')
    ax_amp.bar(amps['rep'], amps['amp'],
               color=[amp_color(a) for a in amps['amp']], width=0.7)
    ax_amp.axhline(avg_amp, color=C_AMBER, linestyle='--',
                   linewidth=0.9, alpha=0.8)

    # Wiersz 3: płynność + zakres + overlay
    ax_smooth  = fig.add_subplot(gs[2, 0])
    ax_range   = fig.add_subplot(gs[2, 1])
    ax_ov      = fig.add_subplot(gs[2, 2])

    # Płynność per powtórzenie (niższe = lepiej)
    ax_smooth.set_facecolor(BG_PANEL)
    ax_smooth.set_title("Płynność ruchu per powtórzenie", color=C_TEXT,
                        fontsize=10, pad=5)
    ax_smooth.set_xlabel("Nr powtórzenia", fontsize=8)
    ax_smooth.set_ylabel("Wahania sygnału (mm)", fontsize=8)
    ax_smooth.grid(True, color=C_GRID, linewidth=0.5, axis='y')

    jerk_threshold_hi = smooth_df['jerk'].quantile(0.66)
    jerk_threshold_lo = smooth_df['jerk'].quantile(0.33)
    jerk_colors = []
    for j in smooth_df['jerk']:
        if j <= jerk_threshold_lo:   jerk_colors.append(C_GREEN)
        elif j <= jerk_threshold_hi: jerk_colors.append(C_AMBER)
        else:                        jerk_colors.append(C_CORAL)

    ax_smooth.bar(smooth_df['rep'], smooth_df['jerk'],
                  color=jerk_colors, width=0.7)
    ax_smooth.axhline(smooth_df['jerk'].mean(), color=C_PURPLE,
                      linestyle='--', linewidth=0.9, alpha=0.8)

    # Legenda płynności
    from matplotlib.patches import Patch
    ax_smooth.legend(handles=[
        Patch(color=C_GREEN, label='płynny'),
        Patch(color=C_AMBER, label='umiarkowany'),
        Patch(color=C_CORAL, label='szarpany'),
    ], fontsize=7, loc='upper right')

    # Zakres ruchu per powtórzenie (%)
    ax_range.set_facecolor(BG_PANEL)
    ax_range.set_title("Zakres ruchu per powtórzenie (%)", color=C_TEXT,
                       fontsize=10, pad=5)
    ax_range.set_xlabel("Nr powtórzenia", fontsize=8)
    ax_range.set_ylabel("% zakresu MIN–MAX", fontsize=8)
    ax_range.set_ylim(0, 110)
    ax_range.grid(True, color=C_GRID, linewidth=0.5, axis='y')

    range_colors = []
    for p in range_df['pct']:
        if p >= 80:   range_colors.append(C_GREEN)
        elif p >= 50: range_colors.append(C_AMBER)
        else:         range_colors.append(C_CORAL)

    ax_range.bar(range_df['rep'], range_df['pct'],
                 color=range_colors, width=0.7)
    ax_range.axhline(80, color=C_GREEN, linestyle=':', linewidth=0.8,
                     alpha=0.6, label='cel 80%')
    ax_range.axhline(avg_range_pct, color=C_PURPLE, linestyle='--',
                     linewidth=0.9, alpha=0.8, label=f'śr. {avg_range_pct:.0f}%')
    ax_range.legend(fontsize=7, loc='lower right')

    # Nałożone powtórzenia
    ax_ov.set_facecolor(BG_PANEL)
    ax_ov.set_title("Powtórzenia nałożone (ostatnie 10)", color=C_TEXT,
                    fontsize=10, pad=5)
    ax_ov.set_xlabel("Próbka", fontsize=8)
    ax_ov.set_ylabel("Odległość (mm)", fontsize=8)
    ax_ov.grid(True, color=C_GRID, linewidth=0.5)

    for i, rep in enumerate(sorted(df['repetition_count'].unique())[-10:]):
        vals  = df[df['repetition_count'] == rep]['distance_mm'].values
        alpha = 0.35 + 0.65 * (i / 9)
        ax_ov.plot(range(len(vals)), vals,
                   color=OVERLAY[i % len(OVERLAY)],
                   linewidth=1.5, alpha=alpha, marker='o', markersize=3)

    # ── Wiersz 4: komentarze ─────────────────────────────────────────────────
    ax_comments = fig.add_subplot(gs[3, :])
    ax_comments.set_facecolor(BG_PANEL)
    ax_comments.axis('off')

    ax_comments.text(0.0, 0.95, "Ocena sesji", ha='left', va='top',
                     fontsize=10, color=C_MUTED,
                     transform=ax_comments.transAxes)

    card_w  = 1.0 / len(comments) - 0.02
    for i, (title, color, desc) in enumerate(comments):
        x0 = i * (card_w + 0.02)
        rect = plt.Rectangle((x0, 0.05), card_w, 0.78,
                              facecolor=BG_MAIN, edgecolor=color,
                              linewidth=1.5, transform=ax_comments.transAxes,
                              clip_on=False)
        ax_comments.add_patch(rect)
        # Kolorowy pasek u góry karty
        top_bar = plt.Rectangle((x0, 0.78), card_w, 0.08,
                                 facecolor=color, alpha=0.25,
                                 transform=ax_comments.transAxes, clip_on=False)
        ax_comments.add_patch(top_bar)
        ax_comments.text(x0 + card_w/2, 0.82, title,
                         ha='center', va='center', fontsize=9,
                         fontweight='bold', color=color,
                         transform=ax_comments.transAxes)
        ax_comments.text(x0 + card_w/2, 0.38, desc,
                         ha='center', va='center', fontsize=8,
                         color=C_TEXT, wrap=True,
                         transform=ax_comments.transAxes)

    plt.show()


if __name__ == '__main__':
    main()