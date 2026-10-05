#!/usr/bin/env python3
"""
crypto-bear-regime-system · ¿qué hacer cuando BTC NO está en régimen alcista?

Usa el estado oficial del proyecto 006 y las velas diarias del 007. La referencia
a batir es LIQUIDEZ (0%): si nada la supera de forma robusta, la conclusión válida
es "en régimen no alcista, liquidez".

CANDIDATOS (pre-registrados)
----------------------------
S1 · cortos de tendencia (espejo del sistema A del 007)
     Solo en NO ALCISTA y desde 2020-01-01 (perpetuos disponibles en Binance).
     Entrada: cierre < mínimo de los cierres de los 20 días previos.
     Stop inicial 3 x ATR(20) por encima; trailing: mínimo cierre desde la entrada
     + 3 x ATR; salida si el cierre > máximo de los 10 días previos o si el estado
     deja de ser NO ALCISTA. Riesgo 1% por operación (y 0,5% como referencia),
     máx. 20% nocional por moneda y 100% en total. Comisión 0,10% por lado y
     financiación de 0,03% diaria sobre el nocional (supuesto conservador).
     Universo: las 19 monedas del 007 (9 de desarrollo + 10 de validación).
S2 · acumulación on-chain de BTC
     En NO ALCISTA, compra BTC cuando el MVRV < 1 (precio por debajo del coste medio
     del mercado) y mantiene hasta que el 006 vuelva a ALCISTA. Comisión 0,10% por
     cambio. Datos del 006 (BTC desde 2010), evaluación desde 2012.
     Referencia propia: "BTC siempre en NO ALCISTA".

CRITERIOS DE ÉXITO (pre-registrados)
  1. Rentabilidad neta positiva en NO ALCISTA in-sample y out-of-sample
     (S1: IS 2020-2022, OOS 2023+; S2: IS 2012-2019, OOS 2020+).
  2. S1 positivo en las monedas de desarrollo y en las de validación por separado.
  3. S1 positivo con Donchian de 15, 20 y 30 días.
  4. S1 con drawdown máximo < 30% al 1% de riesgo.
  5. S2 con mejor Calmar que "BTC siempre en NO ALCISTA" en IS y en OOS.

Uso:
    python bear_system.py
    python bear_system.py --synthetic
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from dataclasses import asdict, dataclass, replace

import numpy as np
import pandas as pd

YEAR = 365
P006 = os.path.join("..", "006.BTC-REGIME-DETECTOR")
P007 = os.path.join("..", "007-CRYPTO-BULL-REGIME-SYSTEM")
DEV = ["BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "DOGE", "LINK", "AVAX"]


@dataclass
class ShortParams:
    dc_entry: int = 20
    dc_exit: int = 10
    atr_n: int = 20
    stop_atr: float = 3.0
    trail_atr: float = 3.0
    risk_pct: float = 1.0
    max_pos_pct: float = 20.0
    max_total_pct: float = 100.0
    fee_pct: float = 0.10
    funding_pct_day: float = 0.03
    short_start: str = "2020-01-01"
    warmup: int = 60
    capital: float = 100_000.0


# -----------------------------------------------------------------------------
# Datos
# -----------------------------------------------------------------------------
def load_coins(folders: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for folder in folders:
        for path in sorted(glob.glob(os.path.join(folder, "*.csv"))):
            sym = os.path.splitext(os.path.basename(path))[0].upper()
            df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
            out[sym] = df[["open", "high", "low", "close"]].astype(float)
    return out


def load_states(path: str) -> pd.Series:
    s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
    s.index = s.index.normalize()
    return s


def load_btc006(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    if "mvrv" not in df and {"market_cap", "realized_cap"} <= set(df.columns):
        df["mvrv"] = df["market_cap"] / df["realized_cap"]
    df["mvrv"] = df["mvrv"].ffill(limit=3)
    return df


def synthetic(seed: int = 5):
    """Paseos aleatorios (sin ventaja posible) + estados y MVRV derivados del 'BTC'."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2012-01-01", "2026-10-03", freq="D")
    n = len(idx)
    mkt = rng.standard_t(4, n) * 0.025
    coins = {}
    for k, sym in enumerate(DEV + ["LTC", "BCH", "TRX", "DOT"]):
        r = 0.7 * mkt + rng.standard_t(4, n) * 0.02
        c = 100 * np.exp(np.cumsum(r))
        o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.002, n))
        h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.015, n)))
        l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.015, n)))
        coins[sym] = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx).iloc[2000:]
    btc = pd.Series(100 * np.exp(np.cumsum(mkt * 1.2)), index=idx)
    realized = btc.ewm(span=500).mean()
    states = pd.Series(np.where(btc > btc.rolling(200).mean(), 2.0, 0.0), index=idx)
    states[btc.rolling(200).mean().isna()] = np.nan
    btc006 = pd.DataFrame({"price": btc, "mvrv": btc / realized})
    return coins, states, btc006


# -----------------------------------------------------------------------------
# S1 · cortos de tendencia
# -----------------------------------------------------------------------------
def panel(coins, p: ShortParams):
    dates = pd.DatetimeIndex(sorted(set().union(*[df.index for df in coins.values()])))
    F = {k: [] for k in ["o", "h", "l", "c", "atr", "dc_lo", "dc_hi", "ok"]}
    for df in coins.values():
        df = df.reindex(dates)
        c, h, l = df["close"], df["high"], df["low"]
        pc = c.shift(1)
        tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
        F["o"].append(df["open"]); F["h"].append(h); F["l"].append(l); F["c"].append(c)
        F["atr"].append(tr.rolling(p.atr_n).mean())
        F["dc_lo"].append(c.rolling(p.dc_entry).min().shift(1))
        F["dc_hi"].append(c.rolling(p.dc_exit).max().shift(1))
        F["ok"].append((c.notna().cumsum() >= p.warmup) & c.notna())
    return dates, {k: pd.concat(v, axis=1).values for k, v in F.items()}


def backtest_short(coins, states, p: ShortParams):
    syms = list(coins)
    dates, X = panel(coins, p)
    st = states.reindex(dates).ffill(limit=3).fillna(1).values   # sin dato -> no operar cortos
    T, N = X["c"].shape
    fee, fund = p.fee_pct / 100, p.funding_pct_day / 100
    t_start = np.searchsorted(dates, pd.Timestamp(p.short_start))
    cash = p.capital
    pos, pending, trades = {}, [], []
    equity = np.full(T, np.nan)

    def cover(j, px, t, reason):
        nonlocal cash
        q = pos.pop(j)
        pnl_trade = q["qty"] * (q["entry"] - px) - q["qty"] * px * fee
        cash += pnl_trade
        total = pnl_trade - q["qty"] * q["entry"] * fee - q["funding"]
        trades.append({"moneda": syms[j], "entrada": dates[q["t0"]].date(), "salida": dates[t].date(),
                       "precio_entrada": q["entry"], "precio_salida": px, "dias": t - q["t0"],
                       "R": total / q["risk_usd"], "pnl": total, "motivo": reason})

    for t in range(T):
        o, h, l, c = X["o"][t], X["h"][t], X["l"][t], X["c"][t]
        for j in [j for j, q in pos.items() if q["exit"]]:
            if not np.isnan(o[j]):
                cover(j, o[j], t, pos[j]["exit"])
        for j, dist, qty in pending:
            if j in pos or np.isnan(o[j]):
                continue
            cash -= qty * o[j] * fee
            pos[j] = {"qty": qty, "entry": o[j], "t0": t, "risk_usd": qty * dist, "stop": o[j] + dist,
                      "lo": o[j], "exit": None, "funding": 0.0}
        pending = []
        for j in list(pos):
            q = pos[j]
            if not np.isnan(h[j]) and h[j] >= q["stop"]:
                cover(j, max(o[j], q["stop"]) if not np.isnan(o[j]) else q["stop"], t, "STOP")
        for j, q in pos.items():                      # financiación diaria del corto
            if not np.isnan(c[j]):
                f = q["qty"] * c[j] * fund
                cash -= f
                q["funding"] += f
        upnl = sum(q["qty"] * (q["entry"] - (c[j] if not np.isnan(c[j]) else q["entry"]))
                   for j, q in pos.items())
        eq = cash + upnl
        equity[t] = eq
        s = st[t]
        for j, q in pos.items():
            if np.isnan(c[j]):
                continue
            q["lo"] = min(q["lo"], c[j])
            q["stop"] = min(q["stop"], q["lo"] + p.trail_atr * X["atr"][t, j])
            q["exit"] = "REGIMEN" if s != 0 else ("SALIDA_DONCHIAN" if c[j] > X["dc_hi"][t, j] else None)
        if s == 0 and t >= t_start and t < T - 1:
            live = sum(q["qty"] * c[j] for j, q in pos.items() if not q["exit"] and not np.isnan(c[j]))
            room = p.max_total_pct / 100 * eq - live
            for j in range(N):
                if (j in pos or not X["ok"][t, j] or np.isnan(X["atr"][t, j])
                        or room <= 0.01 * eq or not c[j] < X["dc_lo"][t, j]):
                    continue
                dist = p.stop_atr * X["atr"][t, j]
                notional = min((p.risk_pct / 100 * eq) / dist * c[j], p.max_pos_pct / 100 * eq, room)
                if notional < 0.01 * eq:
                    continue
                pending.append((j, dist, notional / c[j]))
                room -= notional
    return pd.Series(equity, index=dates).ffill(), pd.DataFrame(trades), dates, st


# -----------------------------------------------------------------------------
# S2 · acumulación on-chain
# -----------------------------------------------------------------------------
def s2_hold(btc006: pd.DataFrame, states: pd.Series) -> pd.Series:
    """1 = mantener BTC (entró con MVRV < 1 dentro de NO ALCISTA y el estado sigue NO ALCISTA)."""
    st = states.reindex(btc006.index).ffill(limit=3)
    b = (st == 0).values
    m = btc006["mvrv"].values
    hold = np.zeros(len(b))
    for i in range(len(b)):
        if not b[i]:
            hold[i] = 0
        elif i and hold[i - 1]:
            hold[i] = 1
        else:
            hold[i] = 1.0 if (not np.isnan(m[i]) and m[i] < 1) else 0.0
    return pd.Series(hold, index=btc006.index)


def s2_episodes(btc006: pd.DataFrame, hold: pd.Series) -> pd.DataFrame:
    px = btc006["price"]
    ch = hold.diff().fillna(hold)
    ent, ext = hold.index[ch == 1], hold.index[ch == -1]
    rows = []
    for e in ent:
        x = ext[ext > e]
        x = x[0] if len(x) else None
        end = x if x is not None else px.index[-1]
        seg = px[e:end]
        rows.append({"compra": e.date(), "venta": x.date() if x is not None else "abierta",
                     "días": (end - e).days, "mvrv_entrada": round(float(btc006["mvrv"][e]), 2),
                     "precio_compra": round(float(px[e]), 2), "precio_venta": round(float(px[end]), 2),
                     "rentabilidad_%": round(100 * (px[end] / px[e] - 1), 1),
                     "peor_caída_%": round(100 * (seg.min() / px[e] - 1), 1)})
    return pd.DataFrame(rows)


def update_log(path: str, btc006: pd.DataFrame, states: pd.Series, hold: pd.Series) -> pd.DataFrame:
    """Registro en vivo de la decisión del 008 (append-only)."""
    names = {2: "ALCISTA FUERTE", 1: "ALCISTA DÉBIL / LATERAL", 0: "NO ALCISTA"}
    d = btc006.index[-1]
    s = states.reindex(btc006.index).ffill(limit=3).iloc[-1]
    if pd.isna(s):
        return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
    if s != 0:
        action = "INACTIVO (régimen alcista: manda el 007)"
    elif hold.iloc[-1] == 1:
        action = "S2: MANTENER BTC (acumulación MVRV<1)"
    else:
        action = "LIQUIDEZ"
    row = {"fecha": str(d.date()), "estado_006": names.get(int(s), "n/d"),
           "precio_btc": round(float(btc006["price"].iloc[-1]), 2),
           "mvrv": round(float(btc006["mvrv"].iloc[-1]), 4), "decision_008": action,
           "registrado_en": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
    log = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
    if not len(log) or row["fecha"] not in set(log["fecha"].astype(str)):
        log = pd.concat([log, pd.DataFrame([row])], ignore_index=True)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        log.to_csv(path, index=False)
    return log


def s2_returns(btc006: pd.DataFrame, states: pd.Series, fee_pct: float) -> dict[str, pd.Series]:
    px = btc006["price"]
    st = states.reindex(px.index).ffill(limit=3)
    bear = (st == 0)
    r = px.pct_change().fillna(0)
    fee = fee_pct / 100

    hold = s2_hold(btc006, states)
    out = {}
    for name, sig in [("S2 · acumulación MVRV<1", hold), ("BTC siempre en NO ALCISTA", bear.astype(float))]:
        pos = sig.shift(1).fillna(0)
        out[name] = pos * r - pos.diff().abs().fillna(pos) * fee
    out["Liquidez"] = pd.Series(0.0, index=px.index)
    return out


# -----------------------------------------------------------------------------
# Métricas
# -----------------------------------------------------------------------------
def perf_eq(eq: pd.Series) -> dict:
    eq = eq.dropna()
    if len(eq) < 30 or eq.iloc[0] <= 0:
        return {}
    r = eq.pct_change().fillna(0)
    years = len(eq) / YEAR
    tot = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = (1 + tot) ** (1 / years) - 1
    dd = (eq / eq.cummax() - 1).min()
    vol = r.std() * np.sqrt(YEAR)
    return {"total_%": 100 * tot, "CAGR_%": 100 * cagr, "maxDD_%": 100 * dd,
            "Sharpe": r.mean() * YEAR / vol if vol > 0 else np.nan,
            "Calmar": cagr / abs(dd) if dd < 0 else np.nan}


def segs(eq: pd.Series, cuts: list[tuple[str, str, str | None]]) -> dict:
    out = {}
    for tag, lo, hi in cuts:
        e = eq[(eq.index >= lo) & ((eq.index < hi) if hi else True)]
        for k, v in perf_eq(e).items():
            out[f"{tag} {k}"] = round(v, 2)
    return out


def main():
    ap = argparse.ArgumentParser(description="Sistema para régimen no alcista (proyecto 008)")
    ap.add_argument("--coins", nargs="+", default=[os.path.join(P007, "data"), os.path.join(P007, "data_val")])
    ap.add_argument("--states", default=os.path.join(P006, "resultados", "estados_oficiales.csv"))
    ap.add_argument("--btc006", default=os.path.join(P006, "data", "btc_daily.csv"))
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out", default="resultados")
    ap.add_argument("--log", default=os.path.join("registro", "decision_log.csv"))
    a = ap.parse_args()

    if a.synthetic:
        coins, states, btc006 = synthetic()
    else:
        coins = load_coins(a.coins)
        states = load_states(a.states)
        btc006 = load_btc006(a.btc006)
    dev = {k: v for k, v in coins.items() if k in DEV}
    val = {k: v for k, v in coins.items() if k not in DEV}
    os.makedirs(a.out, exist_ok=True)
    print(f"Monedas: {len(coins)} ({len(dev)} desarrollo, {len(val)} validación) · BTC 006 desde {btc006.index[0].date()}")

    # ---- S1
    p1 = ShortParams()
    cuts1 = [("TOTAL", p1.short_start, None), ("IS", p1.short_start, "2023-01-01"), ("OOS", "2023-01-01", None)]
    rows = {}
    s1 = {}
    for risk in [1.0, 0.5]:
        eq, tr, dates, st = backtest_short(coins, states, replace(p1, risk_pct=risk))
        s1[risk] = (eq, tr)
        rows[f"S1 cortos · todas · riesgo {risk}%"] = {
            **segs(eq, cuts1), "trades": len(tr),
            "esperanza_R": round(tr["R"].mean(), 3) if len(tr) else np.nan,
            "sin_top5_R": round(tr.drop(tr["R"].nlargest(5).index)["R"].mean(), 3) if len(tr) > 10 else np.nan}
    for name, cset in [("desarrollo", dev), ("validación", val)]:
        if cset:
            eq, tr, *_ = backtest_short(cset, states, p1)
            rows[f"S1 · solo {name} (1%)"] = {**segs(eq, cuts1), "trades": len(tr),
                                              "esperanza_R": round(tr["R"].mean(), 3) if len(tr) else np.nan}
    for dc in [15, 30]:
        eq, tr, *_ = backtest_short(coins, states, replace(p1, dc_entry=dc))
        rows[f"S1 · Donchian {dc} (1%)"] = {**segs(eq, cuts1), "trades": len(tr),
                                            "esperanza_R": round(tr["R"].mean(), 3) if len(tr) else np.nan}
    s1_df = pd.DataFrame(rows).T
    eq1, tr1 = s1[1.0]
    tr1.to_csv(os.path.join(a.out, "trades_s1.csv"), index=False)
    by_year = (tr1.assign(año=pd.to_datetime(tr1["entrada"]).dt.year).groupby("año")["R"]
               .agg(trades="count", esperanza="mean", total="sum").round(2)) if len(tr1) else pd.DataFrame()

    # ---- S2
    cuts2 = [("TOTAL", "2012-01-01", None), ("IS", "2012-01-01", "2020-01-01"), ("OOS", "2020-01-01", None)]
    s2 = {name: segs((1 + r).cumprod(), cuts2) for name, r in s2_returns(btc006, states, 0.10).items()}
    s2_df = pd.DataFrame(s2).T
    hold = s2_hold(btc006, states)
    episodes = s2_episodes(btc006, hold)
    episodes.to_csv(os.path.join(a.out, "s2_episodios.csv"), index=False)

    # ---- criterios
    R1 = s1_df.loc["S1 cortos · todas · riesgo 1.0%"]
    S2r, Bref = s2_df.loc["S2 · acumulación MVRV<1"], s2_df.loc["BTC siempre en NO ALCISTA"]
    g = lambda d, k: d.get(k, np.nan)
    crit = [
        ("1a. S1 positivo IS y OOS", g(R1, "IS CAGR_%") > 0 and g(R1, "OOS CAGR_%") > 0,
         f"IS {g(R1, 'IS CAGR_%')}%, OOS {g(R1, 'OOS CAGR_%')}%"),
        ("1b. S2 positivo IS y OOS", g(S2r, "IS CAGR_%") > 0 and g(S2r, "OOS CAGR_%") > 0,
         f"IS {g(S2r, 'IS CAGR_%')}%, OOS {g(S2r, 'OOS CAGR_%')}%"),
        ("2. S1 positivo en desarrollo y validación",
         all(g(s1_df.loc[k], "TOTAL CAGR_%") > 0 for k in s1_df.index if k.startswith("S1 · solo")),
         ", ".join(f"{k.split('solo ')[1].split(' ')[0]} {g(s1_df.loc[k], 'TOTAL CAGR_%')}%"
                   for k in s1_df.index if k.startswith("S1 · solo"))),
        ("3. S1 positivo con Donchian 15/20/30",
         all(g(s1_df.loc[k], "TOTAL CAGR_%") > 0 for k in s1_df.index
             if "Donchian" in k or k == "S1 cortos · todas · riesgo 1.0%"),
         ", ".join(f"{g(s1_df.loc[k], 'TOTAL CAGR_%')}%" for k in
                   ["S1 · Donchian 15 (1%)", "S1 cortos · todas · riesgo 1.0%", "S1 · Donchian 30 (1%)"])),
        ("4. S1 drawdown < 30% (1%)", g(R1, "TOTAL maxDD_%") > -30, f"{g(R1, 'TOTAL maxDD_%')}%"),
        ("5. S2 Calmar > BTC siempre en NO ALCISTA (IS y OOS)",
         g(S2r, "IS Calmar") > g(Bref, "IS Calmar") and g(S2r, "OOS Calmar") > g(Bref, "OOS Calmar"),
         f"IS {g(S2r, 'IS Calmar')} vs {g(Bref, 'IS Calmar')}, OOS {g(S2r, 'OOS Calmar')} vs {g(Bref, 'OOS Calmar')}"),
    ]
    crit_df = pd.DataFrame(crit, columns=["criterio", "cumple", "detalle"])
    s1_ok = all(crit_df.loc[i, "cumple"] for i in [0, 2, 3, 4])
    s2_ok = bool(crit_df.loc[1, "cumple"] and crit_df.loc[5, "cumple"])

    s1_df.to_csv(os.path.join(a.out, "s1_cortos.csv"))
    s2_df.to_csv(os.path.join(a.out, "s2_acumulacion.csv"))
    by_year.to_csv(os.path.join(a.out, "s1_por_año.csv"))
    crit_df.to_csv(os.path.join(a.out, "criterios.csv"), index=False)
    with open(os.path.join(a.out, "veredicto.json"), "w", encoding="utf-8") as f:
        json.dump({"S1_validado": bool(s1_ok), "S2_validado": s2_ok, "params_S1": asdict(p1)}, f, indent=2)

    show = ["TOTAL CAGR_%", "TOTAL maxDD_%", "TOTAL Calmar", "IS CAGR_%", "IS maxDD_%", "OOS CAGR_%",
            "OOS maxDD_%", "OOS Calmar", "trades", "esperanza_R", "sin_top5_R"]
    with pd.option_context("display.width", 260, "display.max_columns", 30):
        print(f"\n=== S1 · CORTOS DE TENDENCIA (desde {p1.short_start}; IS < 2023 <= OOS) ===")
        print(s1_df[[c for c in show if c in s1_df]].to_string())
        print("\n  Por año (riesgo 1%):")
        print(by_year.to_string() if len(by_year) else "  sin operaciones")
        print("\n=== S2 · ACUMULACIÓN ON-CHAIN (IS 2012-2019, OOS 2020+; en ALCISTA = liquidez) ===")
        print(s2_df.to_string())
        print("\n  Episodios de acumulación:")
        print(episodes.to_string(index=False))
    print("\n=== CRITERIOS PRE-REGISTRADOS ===")
    for _, r in crit_df.iterrows():
        print(f"  [{'CUMPLE' if r['cumple'] else 'NO    '}] {r['criterio']}: {r['detalle']}")
    print(f"\n  S1 (cortos): {'VALIDADO' if s1_ok else 'NO validado'}   ·   "
          f"S2 (acumulación): {'VALIDADO' if s2_ok else 'NO validado'}")
    if not s1_ok and not s2_ok:
        print("  -> Conclusión: en régimen NO ALCISTA, liquidez.")
    if not a.synthetic:
        log = update_log(a.log, btc006, states, hold)
        if len(log):
            last = log.iloc[-1]
            print(f"\n=== HOY ({last['fecha']}) ===\n  006: {last['estado_006']} · MVRV {last['mvrv']} "
                  f"-> 008: {last['decision_008']}")
            print(f"  Registro en vivo: {a.log} ({len(log)} días)")
    print(f"\nFicheros en ./{a.out}/")


if __name__ == "__main__":
    main()
