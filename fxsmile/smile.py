"""Build the smile from ATM / risk reversal / butterfly quotes, then fill it with Vanna-Volga."""
import numpy as np

from fxsmile.black_scholes import (atm_strike, gk_price, implied_vol,
                                   strike_from_delta, vol_greeks)


def pillar_vols(atm, rr, bf):
    """25-delta (or 10-delta) put and call vols from the broker quotes.

    RR = vol(call) - vol(put)           -> the skew
    BF = (vol(call) + vol(put))/2 - ATM -> the convexity of the smile
    (Simplification: I treat the broker butterfly as a smile strangle.)
    """
    return atm + bf - rr / 2, atm + bf + rr / 2


class Smile:
    """Smile of one tenor, built on 3 pillars: 25D put, ATM, 25D call."""

    def __init__(self, S, T, rd, rf, atm, rr25, bf25):
        self.S, self.T, self.rd, self.rf = S, T, rd, rf
        self.F = S * np.exp((rd - rf) * T)
        self.atm = atm
        vol_put, vol_call = pillar_vols(atm, rr25, bf25)
        self.vols = np.array([vol_put, atm, vol_call])
        self.strikes = np.array([
            strike_from_delta(0.25, self.F, T, rf, vol_put, "put"),
            atm_strike(self.F, T, atm),
            strike_from_delta(0.25, self.F, T, rf, vol_call, "call"),
        ])

    # --- the 3 hedging instruments ------------------------------------------------
    def pillar_price(self, i, S, vol):
        return gk_price(S, self.strikes[i], self.T, self.rd, self.rf, vol, "call")

    def smile_costs(self):
        """Market price minus flat-vol price of each pillar call (ATM cost is 0)."""
        return np.array([self.pillar_price(i, self.S, self.vols[i])
                         - self.pillar_price(i, self.S, self.atm) for i in range(3)])

    def vv_weights(self, price_fn):
        """Amounts of the 3 pillar calls that copy the vega, vanna and volga of an option.

        price_fn(S, vol) is the option's flat-vol price. All Greeks are at the ATM vol.
        """
        greeks_option = vol_greeks(price_fn, self.S, self.atm)
        greeks_pillars = np.column_stack([
            vol_greeks(lambda s, v, i=i: self.pillar_price(i, s, v), self.S, self.atm)
            for i in range(3)])
        return np.linalg.solve(greeks_pillars, greeks_option)

    def vv_adjustment(self, price_fn):
        """Vanna-Volga: the option costs what its hedge costs on top of flat vol."""
        return self.vv_weights(price_fn) @ self.smile_costs()

    # --- vanillas -------------------------------------------------------------------
    def vanilla_price(self, K, kind="call"):
        def flat(s, v):
            return gk_price(s, K, self.T, self.rd, self.rf, v, kind)
        return flat(self.S, self.atm) + self.vv_adjustment(flat)

    def vol(self, K):
        """Smile vol at strike K (implied from the Vanna-Volga call price)."""
        price = self.vanilla_price(K, "call")
        return implied_vol(price, self.S, K, self.T, self.rd, self.rf, "call")

    def strike_for_delta(self, delta, kind):
        """Strike of a 10D or 25D option on the smile (the vol depends on the strike)."""
        K = strike_from_delta(delta, self.F, self.T, self.rf, self.atm, kind)
        for _ in range(20):
            K = strike_from_delta(delta, self.F, self.T, self.rf, self.vol(K), kind)
        return K
