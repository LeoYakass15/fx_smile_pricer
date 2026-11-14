import numpy as np

from fxsmile.barrier import barrier_price, vv_barrier_price
from fxsmile.black_scholes import gk_price, implied_vol, spot_delta, strike_from_delta
from fxsmile.smile import Smile

S, T, rd, rf, vol = 1.1163, 0.5, 0.0418, 0.0264, 0.0646


def test_put_call_parity():
    K = 1.12
    call, put = gk_price(S, K, T, rd, rf, vol, "call"), gk_price(S, K, T, rd, rf, vol, "put")
    assert abs(call - put - (S * np.exp(-rf * T) - K * np.exp(-rd * T))) < 1e-12


def test_strike_from_delta_round_trip():
    F = S * np.exp((rd - rf) * T)
    K = strike_from_delta(0.25, F, T, rf, vol, "call")
    assert abs(spot_delta(S, K, T, rd, rf, vol, "call") - 0.25) < 1e-10
    assert abs(implied_vol(gk_price(S, K, T, rd, rf, vol), S, K, T, rd, rf) - vol) < 1e-8


def test_knock_in_plus_knock_out_is_vanilla():
    for kind in ["call", "put"]:
        ki = barrier_price(S, 1.12, 1.06, T, rd, rf, vol, kind, "down-and-in")
        ko = barrier_price(S, 1.12, 1.06, T, rd, rf, vol, kind, "down-and-out")
        assert abs(ki + ko - gk_price(S, 1.12, T, rd, rf, vol, kind)) < 1e-12


def test_far_barrier_ko_is_vanilla():
    ko = barrier_price(S, 1.12, 0.50, T, rd, rf, vol, "call", "down-and-out")
    assert abs(ko - gk_price(S, 1.12, T, rd, rf, vol)) < 1e-10


def test_vanna_volga_reprices_the_three_pillars():
    sm = Smile(S, T, rd, rf, vol, -0.0075, 0.0027)
    for K, v in zip(sm.strikes, sm.vols):
        assert abs(sm.vol(K) - v) < 1e-6


def test_flat_smile_gives_black_scholes():
    sm = Smile(S, T, rd, rf, vol, 0.0, 0.0)
    bs = barrier_price(S, 1.12, 1.06, T, rd, rf, vol, "call", "down-and-out")
    assert abs(vv_barrier_price(sm, 1.12, 1.06, "call", "down-and-out") - bs) < 1e-10


def test_negative_risk_reversal_makes_knock_in_put_dearer():
    sm = Smile(S, T, rd, rf, vol, -0.0075, 0.0)
    bs = barrier_price(S, 1.125, 1.06, T, rd, rf, vol, "put", "down-and-in")
    assert vv_barrier_price(sm, 1.125, 1.06, "put", "down-and-in") > bs
