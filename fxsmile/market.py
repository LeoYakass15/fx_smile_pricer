"""Bloomberg EUR/USD market data of 29 Oct 2026 (OVDV vol surface, FRD forward points)."""
import numpy as np
import pandas as pd

SPOT = 1.11625            # mid of 1.1162 / 1.1163 (BGN, 14:52 New York)
TRADE_DATE = "2026-10-29"


def load_quotes(path="data/eurusd_vol_quotes.csv"):
    """One row per tenor, with mid quotes, the forward and both interest rates."""
    q = pd.read_csv(path)
    for col in ["atm", "rr25", "bf25", "rr10", "bf10", "fwd_pts"]:
        q[col] = (q[f"{col}_bid"] + q[f"{col}_ask"]) / 2
    for col in ["atm", "rr25", "bf25", "rr10", "bf10", "usd_rate"]:
        q[col] = q[col] / 100                      # vols and rates in decimals
    q["T"] = q["days"] / 365
    q["forward"] = SPOT + q["fwd_pts"] / 10_000     # forward points are in pips
    q["rd"] = np.log(1 + q["usd_rate"] * q["days"] / 360) / q["T"]   # USD deposit, ACT/360
    # EUR rate implied by covered interest parity: F = S * exp((rd - rf) * T)
    q["rf"] = q["rd"] - np.log(q["forward"] / SPOT) / q["T"]
    return q.set_index("tenor")


def load_ovml(path="data/ovml_barriers.csv"):
    return pd.read_csv(path)


# Inputs shown on the Bloomberg OVML screens of the 4 barrier prices (6M, 29 Oct 2026).
# I reuse exactly these inputs so that my prices can be compared with Bloomberg's.
OVML_MARKET = {
    "spot": 1.1163,
    "T": 182 / 365,        # 29 Oct 2026 -> expiry 29 Apr 2027
    "rd": 0.04180,         # USD deposit (SOFR)
    "rf": 0.02638,         # EUR deposit implied by the forward
    "atm": 0.06457,        # 6M ATM vol, mid
    "rr25": -0.00748,      # 6M 25D risk reversal (EUR call - EUR put), mid
    "bf25": 0.00267,       # 6M 25D butterfly, mid
}
NOTIONAL_EUR = 1_000_000
