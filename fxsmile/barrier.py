"""Barrier options: closed-form Black-Scholes (Haug) and the Vanna-Volga correction."""
import numpy as np
from scipy.stats import norm

from fxsmile.black_scholes import gk_price


def barrier_price(S, K, H, T, rd, rf, vol, kind="call", barrier_type="down-and-out"):
    """Continuous down barrier, no rebate (Reiner-Rubinstein formulas, as in Haug)."""
    phi = 1 if kind == "call" else -1
    eta = 1                                   # down barrier
    mu = (rd - rf - 0.5 * vol**2) / vol**2
    sT = vol * np.sqrt(T)
    x1 = np.log(S / K) / sT + (1 + mu) * sT
    x2 = np.log(S / H) / sT + (1 + mu) * sT
    y1 = np.log(H**2 / (S * K)) / sT + (1 + mu) * sT
    y2 = np.log(H / S) / sT + (1 + mu) * sT
    dfS, dfK = S * np.exp(-rf * T), K * np.exp(-rd * T)
    A = phi * dfS * norm.cdf(phi * x1) - phi * dfK * norm.cdf(phi * x1 - phi * sT)
    B = phi * dfS * norm.cdf(phi * x2) - phi * dfK * norm.cdf(phi * x2 - phi * sT)
    C = (phi * dfS * (H / S) ** (2 * (mu + 1)) * norm.cdf(eta * y1)
         - phi * dfK * (H / S) ** (2 * mu) * norm.cdf(eta * y1 - eta * sT))
    D = (phi * dfS * (H / S) ** (2 * (mu + 1)) * norm.cdf(eta * y2)
         - phi * dfK * (H / S) ** (2 * mu) * norm.cdf(eta * y2 - eta * sT))
    if S <= H:                                # barrier already touched
        vanilla = gk_price(S, K, T, rd, rf, vol, kind)
        return 0.0 if barrier_type == "down-and-out" else vanilla
    if kind == "call":
        knock_in = C if K > H else A - B + D
    else:
        knock_in = B - C + D if K > H else A
    if barrier_type == "down-and-in":
        return knock_in
    return gk_price(S, K, T, rd, rf, vol, kind) - knock_in   # in + out = vanilla


def survival_probability(S, H, T, rd, rf, vol):
    """Risk-neutral probability that spot never touches the down barrier H."""
    nu = rd - rf - 0.5 * vol**2
    x = np.log(S / H)
    sT = vol * np.sqrt(T)
    return norm.cdf((x + nu * T) / sT) - np.exp(-2 * nu * x / vol**2) * norm.cdf((-x + nu * T) / sT)


def vv_barrier_price(smile, K, H, kind="call", barrier_type="down-and-out", S=None):
    """Vanna-Volga price of a down barrier.

    Knock-out: flat-vol price + survival probability x cost of the vanna-volga hedge.
    The hedge only matters while the option is alive, hence the survival weight.
    Knock-in: in-out parity, KI = vanilla (on the smile) - KO.
    """
    S = smile.S if S is None else S

    def flat_ko(s, v):
        return barrier_price(s, K, H, smile.T, smile.rd, smile.rf, v, kind, "down-and-out")

    p_alive = survival_probability(S, H, smile.T, smile.rd, smile.rf, smile.atm)
    ko = flat_ko(S, smile.atm) + p_alive * smile.vv_adjustment(flat_ko)
    if barrier_type == "down-and-out":
        return ko
    return smile.vanilla_price(K, kind) - ko
