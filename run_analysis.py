"""EUR/USD options on the smile: Vanna-Volga vs Bloomberg. Run: python run_analysis.py

Reads the Bloomberg data of 29 Oct 2026 in data/ and writes charts and tables to results/.
"""
import os

import numpy as np
import pandas as pd

from fxsmile import plots
from fxsmile.barrier import barrier_price, survival_probability, vv_barrier_price
from fxsmile.black_scholes import gk_price, spot_delta, vol_greeks
from fxsmile.market import NOTIONAL_EUR, OVML_MARKET, SPOT, load_ovml, load_quotes
from fxsmile.smile import Smile, pillar_vols

OUT = "results"
os.makedirs(OUT, exist_ok=True)
pd.set_option("display.width", 140)


def to_bp(price, spot):
    """USD price per EUR -> basis points of EUR notional."""
    return price / spot * 10_000


# ---------------------------------------------------------------------------------
# 1. Market of 29 Oct 2026
# ---------------------------------------------------------------------------------
quotes = load_quotes()
summary = pd.DataFrame({
    "forward": quotes["forward"].round(5),
    "usd_rate_%": (quotes["rd"] * 100).round(3),
    "eur_rate_%": (quotes["rf"] * 100).round(3),
    "atm_%": (quotes["atm"] * 100).round(3),
    "rr25_%": (quotes["rr25"] * 100).round(3),
    "bf25_%": (quotes["bf25"] * 100).round(3),
})
summary.to_csv(f"{OUT}/market_summary.csv")
print(f"EUR/USD spot {SPOT}, 29 Oct 2026 (Bloomberg OVDV + FRD, mid)\n")
print(summary.to_string())

# ---------------------------------------------------------------------------------
# 2. Checks against Bloomberg: 1M quick pricer and 10D wings
# ---------------------------------------------------------------------------------
r = quotes.loc["1M"]
smile_1m = Smile(SPOT, r["T"], r["rd"], r["rf"], r["atm"], r["rr25"], r["bf25"])
k_atm = smile_1m.strikes[1]
check = pd.DataFrame({
    "mine": [k_atm,
             gk_price(SPOT, k_atm, r["T"], r["rd"], r["rf"], r["atm_bid"] / 100) / k_atm * 100,
             gk_price(SPOT, k_atm, r["T"], r["rd"], r["rf"], r["atm_ask"] / 100) / k_atm * 100,
             spot_delta(SPOT, k_atm, r["T"], r["rd"], r["rf"], r["atm"]) * 100],
    "bloomberg": [1.1177, 0.644, 0.674, 49.897],
}, index=["ATM strike", "call price bid (% USD)", "call price ask (% USD)", "call spot delta (%)"])
check.round(4).to_csv(f"{OUT}/check_quick_pricer.csv")
print("\nCheck 1: 1M ATM call vs Bloomberg quick pricer")
print(check.round(4).to_string())

wings, curves = [], {}
for tenor, r in quotes.iterrows():
    sm = Smile(SPOT, r["T"], r["rd"], r["rf"], r["atm"], r["rr25"], r["bf25"])
    mkt_put10, mkt_call10 = pillar_vols(r["atm"], r["rr10"], r["bf10"])
    k_put10, k_call10 = sm.strike_for_delta(0.10, "put"), sm.strike_for_delta(0.10, "call")
    wings.append({"tenor": tenor,
                  "10D put market": mkt_put10 * 100, "10D put VV": sm.vol(k_put10) * 100,
                  "10D call market": mkt_call10 * 100, "10D call VV": sm.vol(k_call10) * 100})
    curves[tenor] = (range(5), np.array([sm.vol(k_put10), *sm.vols, sm.vol(k_call10)]))
wings = pd.DataFrame(wings).set_index("tenor")
wings["max error (vol bp)"] = np.maximum(abs(wings["10D put VV"] - wings["10D put market"]),
                                         abs(wings["10D call VV"] - wings["10D call market"])) * 100
wings.round(3).to_csv(f"{OUT}/check_10d_wings.csv")
print("\nCheck 2: the smile is built on 25D quotes only. Does it find the market 10D vols?")
print(wings.round(3).to_string())
plots.smiles_by_tenor(curves, f"{OUT}/02_smiles_by_tenor.png")

# ---------------------------------------------------------------------------------
# 3. The 4 Bloomberg OVML barrier prices (6M, inputs of the OVML screen)
# ---------------------------------------------------------------------------------
m = OVML_MARKET
S, T, rd, rf, atm = m["spot"], m["T"], m["rd"], m["rf"], m["atm"]
smile = Smile(S, T, rd, rf, atm, m["rr25"], m["bf25"])
ovml = load_ovml()

rows, greeks, split = [], [], []
for name, trade in ovml.groupby("option", sort=False):
    t = trade.iloc[0]
    K, H, kind, btype = t["strike"], t["barrier"], t["kind"], t["barrier_type"]
    ovml_bs = trade.loc[trade["model"] == "BS"].iloc[0]
    ovml_vv = trade.loc[trade["model"] == "VV"].iloc[0]

    bs = barrier_price(S, K, H, T, rd, rf, atm, kind, btype)
    vv = vv_barrier_price(smile, K, H, kind, btype)
    rows.append({"option": name, "bs_mine": bs / S * 100, "bs_ovml": ovml_bs["price_pct_eur"],
                 "vv_mine": vv / S * 100, "vv_ovml": ovml_vv["price_pct_eur"],
                 "smile_effect_mine_bp": to_bp(vv - bs, S),
                 "smile_effect_ovml_bp": (ovml_vv["price_pct_eur"] - ovml_bs["price_pct_eur"]) * 100,
                 "premium_vv_mine_eur": vv / S * NOTIONAL_EUR})

    # Black-Scholes Greeks in Bloomberg units, to compare with the OVML screen
    def flat(s, v):
        return barrier_price(s, K, H, T, rd, rf, v, kind, btype)
    h = 1e-4
    delta = (flat(S + h, atm) - flat(S - h, atm)) / (2 * h)
    gamma = (flat(S + h, atm) - 2 * flat(S, atm) + flat(S - h, atm)) / h**2
    vega, vanna, volga = vol_greeks(flat, S, atm)
    greeks.append({"option": name,
                   "delta % (premium-adjusted)": (delta - bs / S) * 100,
                   "delta % OVML": {"call": 49.374, "put": -46.7956}[kind],
                   "gamma EUR (1% move)": gamma * S * 0.01 * NOTIONAL_EUR,
                   "gamma EUR OVML": ovml_bs["gamma_eur"],
                   "vega EUR (1 vol pt)": vega * 0.01 / S * NOTIONAL_EUR,
                   "vega EUR OVML": ovml_bs["vega_eur"],
                   "vanna EUR (1 vol pt x 1% spot)": vanna * 0.01 * 0.01 * S / S * NOTIONAL_EUR,
                   "volga EUR (1 vol pt squared)": volga * 1e-4 / S * NOTIONAL_EUR})

    # Split of the smile cost: skew (vanna, priced by the risk reversal) and
    # convexity (volga, priced by the butterfly). Simple 2-instrument version.
    costs = smile.smile_costs()
    pillar_greeks = np.column_stack([
        vol_greeks(lambda s, v, i=i: smile.pillar_price(i, s, v), S, atm) for i in range(3)])
    rr, bf = np.array([-1, 0, 1.0]), np.array([0.5, -1, 0.5])
    split.append({"option": name,
                  "vanna_bp": to_bp(vanna / (pillar_greeks @ rr)[1] * (costs @ rr), S),
                  "volga_bp": to_bp(volga / (pillar_greeks @ bf)[2] * (costs @ bf), S),
                  "survival_prob": survival_probability(S, H, T, rd, rf, atm),
                  "ovml_bp": (ovml_vv["price_pct_eur"] - ovml_bs["price_pct_eur"]) * 100})

prices = pd.DataFrame(rows).set_index("option")
greeks = pd.DataFrame(greeks).set_index("option")
split = pd.DataFrame(split).set_index("option")
prices.round(4).to_csv(f"{OUT}/barrier_prices.csv")
greeks.round(1).to_csv(f"{OUT}/barrier_greeks.csv")
split.round(2).to_csv(f"{OUT}/smile_cost_split.csv")
print("\n6M barriers, % of EUR notional (Bloomberg OVML inputs)")
print(prices.round(4).to_string())
print("\nBlack-Scholes Greeks vs OVML screen (1M EUR notional)")
print(greeks.round(1).T.to_string())
print("\nSmile cost split, bp of notional")
print(split.round(2).to_string())

plots.smile_6m(smile, [("10D put", smile.strike_for_delta(0.10, "put"), pillar_vols(atm, -0.014125, 0.009675)[0]),
                       ("10D call", smile.strike_for_delta(0.10, "call"), pillar_vols(atm, -0.014125, 0.009675)[1])],
               1.1248, 1.0604, f"{OUT}/01_smile_6m.png")
plots.barrier_prices(prices, f"{OUT}/03_barrier_prices.png")
plots.vv_split(split.rename(index=lambda s: s.replace("Call EUR ", "").replace("Put EUR ", "")
                            .replace("down-and-out", "Call KO").replace("down-and-in", "Put KI")),
               f"{OUT}/04_smile_cost_split.png")

# ---------------------------------------------------------------------------------
# 4. Risk: long the KI put when the smile moves, alone and vanna-volga hedged
# ---------------------------------------------------------------------------------
K, H = 1.1249, 1.0605


def ki_value(sm):
    return vv_barrier_price(sm, K, H, "put", "down-and-in")


def pillar_values(sm, strikes):
    """Market value of the 3 hedge calls (fixed strikes) on a given smile."""
    return np.array([gk_price(S, k, T, rd, rf, sm.vol(k), "call") for k in strikes])


def quote_risk(value_fn, bump=0.001):
    """Sensitivity to the 3 market quotes (ATM, 25D RR, 25D BF): bump each by 0.1 vol, reprice.

    This is how a desk sees smile risk: in the quotes it trades, not in model Greeks.
    """
    base = value_fn(smile)
    out = []
    for d in [(bump, 0, 0), (0, bump, 0), (0, 0, bump)]:
        bumped = Smile(S, T, rd, rf, atm + d[0], m["rr25"] + d[1], m["bf25"] + d[2])
        out.append((value_fn(bumped) - base) / bump * 0.01)   # per 1 vol point
    return np.array(out)


ki_risk = quote_risk(ki_value)
hedge_risk = np.column_stack([quote_risk(lambda sm, k=k: gk_price(S, k, T, rd, rf, sm.vol(k), "call"))
                              for k in smile.strikes])
weights = np.linalg.solve(hedge_risk, ki_risk)   # calls to SELL so that ATM, RR and BF risk is 0
print("\nKI put risk per 1 vol pt of each quote (EUR, 1M EUR):",
      dict(zip(["ATM", "RR", "BF"], [round(float(x)) for x in ki_risk / S * NOTIONAL_EUR])))
# Check: smile-consistent vega (bump the ATM quote, keep RR and BF) vs the OVML VV vega
vv_vega = pd.DataFrame({
    "VV vega mine (EUR)": [quote_risk(lambda sm: vv_barrier_price(sm, 1.1248, 1.0604, "call", "down-and-out"))[0],
                           ki_risk[0]],
    "VV vega OVML (EUR)": ovml.loc[ovml["model"] == "VV", "vega_eur"].values,
    "BS vega OVML (EUR)": ovml.loc[ovml["model"] == "BS", "vega_eur"].values,
}, index=["Call EUR down-and-out", "Put EUR down-and-in"])
vv_vega.iloc[:, 0] = vv_vega.iloc[:, 0] / S * NOTIONAL_EUR
vv_vega.round(0).to_csv(f"{OUT}/check_vv_vega.csv")
print("\nCheck 3: vega once the smile is taken into account")
print(vv_vega.round(0).to_string())
base_ki, base_hedge = ki_value(smile), pillar_values(smile, smile.strikes)
shocks = {"RR -0.5 (skew steeper)": (0, -0.005, 0), "RR +0.5 (skew flatter)": (0, 0.005, 0),
          "BF +0.2 (fatter wings)": (0, 0, 0.002), "ATM +1 vol": (0.01, 0, 0),
          "ATM -1 vol": (-0.01, 0, 0), "Risk-off: ATM +1, RR -0.5": (0.01, -0.005, 0)}
scen = []
for label, (d_atm, d_rr, d_bf) in shocks.items():
    new = Smile(S, T, rd, rf, atm + d_atm, m["rr25"] + d_rr, m["bf25"] + d_bf)
    pnl_ki = ki_value(new) - base_ki
    pnl_hedge = -weights @ (pillar_values(new, smile.strikes) - base_hedge)
    scen.append({"scenario": label, "unhedged_eur": pnl_ki / S * NOTIONAL_EUR,
                 "hedged_eur": (pnl_ki + pnl_hedge) / S * NOTIONAL_EUR})
scen = pd.DataFrame(scen).set_index("scenario")
scen.round(0).to_csv(f"{OUT}/smile_scenarios.csv")
print("\nLong 1M EUR of the 6M KI put: P&L in EUR when the smile moves (spot unchanged)")
print("Hedge (calls per EUR of notional, short):", dict(zip(["25D put strike", "ATM", "25D call strike"],
                                                            [round(float(w), 3) for w in weights])))
print(scen.round(0).to_string())
plots.scenarios(scen, f"{OUT}/05_smile_scenarios.png")
pd.DataFrame({"strike": smile.strikes, "vol_%": smile.vols * 100, "hedge_amount": -weights},
             index=["25D put", "ATM", "25D call"]).round(4).to_csv(f"{OUT}/ki_hedge.csv")
print(f"\nCharts and tables written to {OUT}/")
