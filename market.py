"""LMSR market maker math.

LMSR (Logarithmic Market Scoring Rule) e' il meccanismo classico dei
prediction market: il prezzo di YES e NO somma sempre a 1 e si muove
in modo continuo in funzione dell'esposizione totale del market maker.

Stato: (q_yes, q_no) = numero di share gia' vendute al pubblico.
Parametro: b = liquidity (piu' alto -> prezzo si muove piu' lentamente).
"""

from __future__ import annotations
import math


def _logsumexp(a: float, b: float) -> float:
    m = max(a, b)
    return m + math.log(math.exp(a - m) + math.exp(b - m))


def cost_function(q_yes: float, q_no: float, b: float) -> float:
    return b * _logsumexp(q_yes / b, q_no / b)


def price_yes(q_yes: float, q_no: float, b: float) -> float:
    # sigmoid stabile
    return 1.0 / (1.0 + math.exp((q_no - q_yes) / b))


def price_no(q_yes: float, q_no: float, b: float) -> float:
    return 1.0 - price_yes(q_yes, q_no, b)


def trade_cost(q_yes: float, q_no: float, b: float, side: str, shares: float) -> float:
    """Costo (puo' essere negativo se shares<0, cioe' vendita) per muovere
    lo stato di `shares` share del lato `side`."""
    side = side.upper()
    if side == "YES":
        new_y, new_n = q_yes + shares, q_no
    elif side == "NO":
        new_y, new_n = q_yes, q_no + shares
    else:
        raise ValueError(f"side deve essere YES o NO, ricevuto {side!r}")
    return cost_function(new_y, new_n, b) - cost_function(q_yes, q_no, b)


def apply_trade(q_yes: float, q_no: float, side: str, shares: float) -> tuple[float, float]:
    side = side.upper()
    if side == "YES":
        return q_yes + shares, q_no
    if side == "NO":
        return q_yes, q_no + shares
    raise ValueError(f"side deve essere YES o NO, ricevuto {side!r}")
