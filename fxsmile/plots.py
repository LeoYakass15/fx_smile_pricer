"""Charts for the README."""
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"figure.dpi": 120, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False})
BLUE, ORANGE, GREY, RED, GREEN = "#1f4e79", "#e07b00", "#8c8c8c", "#b22222", "#2e7d32"


def smile_6m(smile, wings, strike, barrier, path):
    """wings: list of (label, strike, market vol) for the 10D checks."""
    K = np.linspace(1.04, 1.205, 90)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(K, [smile.vol(k) * 100 for k in K], color=BLUE, lw=2, label="Vanna-Volga smile")
    ax.axhline(smile.atm * 100, color=GREY, ls="--", label="Flat ATM vol (Black-Scholes)")
    ax.scatter(smile.strikes, smile.vols * 100, color=BLUE, s=60, zorder=3,
               label="Market pillars: 25D put, ATM, 25D call")
    for name, k, v in wings:
        ax.scatter(k, v * 100, color=ORANGE, marker="x", s=80, zorder=3)
        ax.annotate(name, (k, v * 100), textcoords="offset points", xytext=(6, 4), color=ORANGE)
    ax.scatter([], [], color=ORANGE, marker="x", label="Market 10D vols (not used in the fit)")
    ax.axvline(barrier, color=RED, lw=1, label=f"Barrier {barrier}")
    ax.axvline(strike, color=GREEN, lw=1, label=f"Strike {strike}")
    ax.set(title="EUR/USD 6M smile, 29 Oct 2026", xlabel="Strike (USD per EUR)", ylabel="Implied vol (%)")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def smiles_by_tenor(curves, path):
    """curves: dict tenor -> (deltas_label_x, vols)."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for tenor, (x, vols) in curves.items():
        ax.plot(x, vols * 100, marker="o", label=tenor)
    ax.set_xticks(range(5), ["10D put", "25D put", "ATM", "25D call", "10D call"])
    ax.set(title="EUR/USD smile by maturity: EUR puts are always richer", ylabel="Implied vol (%)")
    ax.legend()
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def barrier_prices(table, path):
    labels = ["BS (mine)", "BS (OVML)", "VV (mine)", "VV (OVML)"]
    colors = [GREY, "#c8c8c8", BLUE, ORANGE]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for ax, (name, row) in zip(axes, table.iterrows()):
        vals = [row["bs_mine"], row["bs_ovml"], row["vv_mine"], row["vv_ovml"]]
        bars = ax.bar(labels, vals, color=colors)
        ax.bar_label(bars, fmt="%.3f", fontsize=8)
        ax.set_ylim(min(vals) * 0.95, max(vals) * 1.03)
        ax.set(title=name, ylabel="Price (% of EUR notional)")
        ax.tick_params(axis="x", labelsize=8)
    fig.suptitle("6M barriers: the smile makes the KO cheaper and the KI dearer")
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def vv_split(split, path):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = np.arange(len(split))
    ax.bar(x - 0.27, split["vanna_bp"], 0.27, color=BLUE, label="Skew cost (vanna x risk reversal)")
    ax.bar(x, split["volga_bp"], 0.27, color=ORANGE, label="Convexity cost (volga x butterfly)")
    ax.bar(x + 0.27, split["ovml_bp"], 0.27, color=GREY, label="Bloomberg VV - BS")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x, split.index)
    ax.set(title="Where the smile adjustment comes from (bp of notional)", ylabel="bp of EUR notional")
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def scenarios(table, path):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(table))
    ax.bar(x - 0.2, table["unhedged_eur"], 0.4, color=GREY, label="Option alone")
    ax.bar(x + 0.2, table["hedged_eur"], 0.4, color=BLUE, label="Option + vanna-volga hedge")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x, table.index, fontsize=8)
    ax.set(title="Long 1M EUR of the 6M KI put: P&L when the smile moves (EUR)", ylabel="P&L (EUR)")
    ax.legend()
    fig.tight_layout(); fig.savefig(path); plt.close(fig)
