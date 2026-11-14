"""Garman-Kohlhagen: Black-Scholes for FX options.

EUR/USD: EUR is the foreign currency (rate rf), USD the domestic one (rate rd).
Prices are in USD per 1 EUR of notional.
"""
import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def d1_d2(S, K, T, rd, rf, vol):
    d1 = (np.log(S / K) + (rd - rf + 0.5 * vol**2) * T) / (vol * np.sqrt(T))
    return d1, d1 - vol * np.sqrt(T)


def gk_price(S, K, T, rd, rf, vol, kind="call"):
    d1, d2 = d1_d2(S, K, T, rd, rf, vol)
    phi = 1 if kind == "call" else -1
    return phi * (S * np.exp(-rf * T) * norm.cdf(phi * d1) - K * np.exp(-rd * T) * norm.cdf(phi * d2))


def spot_delta(S, K, T, rd, rf, vol, kind="call"):
    d1, _ = d1_d2(S, K, T, rd, rf, vol)
    phi = 1 if kind == "call" else -1
    return phi * np.exp(-rf * T) * norm.cdf(phi * d1)


def implied_vol(price, S, K, T, rd, rf, kind="call"):
    return brentq(lambda v: gk_price(S, K, T, rd, rf, v, kind) - price, 1e-4, 2.0)


def atm_strike(F, T, vol):
    """Delta-neutral straddle strike: the call and the put have the same delta."""
    return F * np.exp(0.5 * vol**2 * T)


def strike_from_delta(delta, F, T, rf, vol, kind="call"):
    """Strike of a call (or put) with a given spot delta, e.g. 0.25 for a 25-delta option."""
    phi = 1 if kind == "call" else -1
    d1 = phi * norm.ppf(delta * np.exp(rf * T))
    return F * np.exp(-d1 * vol * np.sqrt(T) + 0.5 * vol**2 * T)


def vol_greeks(price_fn, S, vol, dS=1e-4, dv=1e-4):
    """Vega, vanna and volga of any pricer price_fn(S, vol), by finite differences.

    vega  = dV/dvol         (exposure to the level of vol)
    vanna = d2V/dS dvol     (exposure to the skew, i.e. the risk reversal)
    volga = d2V/dvol2       (exposure to the convexity, i.e. the butterfly)
    """
    up, down = price_fn(S, vol + dv), price_fn(S, vol - dv)
    mid = price_fn(S, vol)
    vega = (up - down) / (2 * dv)
    volga = (up - 2 * mid + down) / dv**2
    vanna = (price_fn(S + dS, vol + dv) - price_fn(S + dS, vol - dv)
             - price_fn(S - dS, vol + dv) + price_fn(S - dS, vol - dv)) / (4 * dS * dv)
    return np.array([vega, vanna, volga])
