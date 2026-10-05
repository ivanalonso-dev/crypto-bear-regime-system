# crypto-bear-regime-system

What to do with crypto when BTC is **not** in a bull regime (as defined by project [006 · btc-regime-detector](https://github.com/ivanalonso-dev/btc-regime-detector)) — roughly half of the time. The benchmark to beat is **cash (0%)**: if no candidate beats it robustly, "stay in cash" is a valid answer.

> **TL;DR:** **Trend-following shorts fail** — they lose money and suffer a −58% drawdown, because bear phases inside crypto's long-term uptrend are choppy and short squeezes are violent. **On-chain accumulation (buy BTC when MVRV < 1, hold until the bull regime returns) passes the pre-registered criteria**, but rests on only 7 episodes since 2011, with the out-of-sample result driven mostly by one (March 2020). Official rule: **cash by default**, with MVRV accumulation as an optional, small, live-tracked module.

Project 008 of the series: **006** regime detector → **007** bull-regime system → **008** bear-regime system.

## Candidates (pre-registered)

| | Rules |
|---|---|
| **S1 · trend shorts** | Mirror of 007's system A. In *not bull* only, from 2020 (Binance perpetuals). Short when close < previous 20-day low; 3×ATR initial and trailing stop; exit on close > previous 10-day high or regime change. 1% risk per trade (0.5% shown), ≤ 20% per coin, ≤ 100% total, 0.10% fee per side **plus 0.03%/day funding** on the notional. Same 19 coins as 007. |
| **S2 · on-chain accumulation** | In *not bull*, buy BTC when **MVRV < 1** (price below the market's aggregate cost basis); hold until 006 turns bull again (007 takes over). 0.10% fee per switch. BTC history from 006 (2010+), evaluated from 2012. |

**Success criteria:** (1) positive net return in-sample and out-of-sample · (2) S1 positive on development and unseen coins separately · (3) S1 positive with Donchian 15/20/30 · (4) S1 max drawdown < 30% at 1% risk · (5) S2 Calmar above "always hold BTC when not bull" in-sample and out-of-sample.

## Results

### S1 · trend shorts — **not validated**

| | CAGR | Max DD | IS CAGR (2020–22) | OOS CAGR (2023+) | Trades | R / trade |
|---|---|---|---|---|---|---|
| 19 coins, 1% risk | −4.4% | **−58.1%** | +5.9% | −11.7% | 625 | −0.03 |
| 19 coins, 0.5% risk | −1.5% | −35.7% | +4.1% | −5.8% | 613 | −0.02 |
| Development coins only | −1.3% | −35.7% | +4.2% | −5.5% | 294 | −0.02 |
| Unseen coins only | −2.4% | −35.8% | +2.8% | −6.2% | 334 | −0.04 |
| Donchian 15 / 30 | −4.2% / −6.0% | −57% / −60% | | | | |

Worked in the deep 2022 bear (+18.9R) and 2026, lost in the shallow, choppy corrections of 2023–2025 (−54R). Fails 4 of 4 S1 criteria.

### S2 · on-chain accumulation — **passes the criteria, weak evidence**

| (cash when in bull regime) | IS CAGR 2012–19 | IS max DD | OOS CAGR 2020+ | OOS max DD | OOS Calmar |
|---|---|---|---|---|---|
| **S2 · MVRV < 1 accumulation** | +1.4% | −59.8% | **+8.1%** | −35.5% | **0.23** |
| Always hold BTC when not bull | −8.1% | −85.6% | −3.2% | −71.4% | −0.05 |
| Cash | 0% | 0% | 0% | 0% | — |

| Buy | Sell | Days | MVRV in | Return | Worst drawdown |
|---|---|---|---|---|---|
| 2011-09-09 | 2012-01-09 | 122 | 0.78 | +26% | −58% |
| 2012-02-18 | 2012-02-27 | 9 | 0.85 | +16% | 0% |
| 2014-10-04 | 2015-06-20 | 259 | 0.95 | −25% | −47% |
| 2015-08-22 | 2015-10-05 | 44 | 0.82 | +5% | −8% |
| 2018-11-19 | 2019-04-06 | 138 | 0.98 | +5% | −34% |
| 2020-03-12 | 2020-05-03 | 52 | 0.88 | **+79%** | 0% |
| 2022-06-13 | 2023-01-16 | 217 | 0.96 | −5% | −29% |

**Reading:** holding BTC through bear regimes destroys capital (−59% over the period); waiting for MVRV < 1 turns that into a positive result. But with 7 episodes — and an out-of-sample result that is essentially the March 2020 crash — this is a plausible idea, not a proven edge. Drawdowns of 30–60% inside an episode are normal. The 2025–26 bear never reached MVRV < 1, so S2 stayed in cash.

## Official rule

| 006 state | Action |
|---|---|
| Bull (strong or weak) | 008 inactive — project 007 runs |
| Not bull, MVRV ≥ 1 | **Cash** |
| Not bull, MVRV < 1 | Optional **S2**: accumulate BTC with a small allocation, hold until the bull regime returns |

`registro/decision_log.csv` records the 008 decision every day (append-only), as the live test.

## Limitations

- Very few independent bear cycles; S2 rests on 7 episodes.
- Funding is modelled as a flat 0.03%/day; real funding varies (and is sometimes positive for shorts).
- Shorting altcoins also carries delisting and liquidity risk not modelled here.
- The regime detector (006 v2) was chosen after seeing 2020–2026 data.

## Usage

```bash
pip install -r requirements.txt
python bear_system.py          # needs ../006.BTC-REGIME-DETECTOR and ../007-CRYPTO-BULL-REGIME-SYSTEM data
python bear_system.py --synthetic
```

On Windows, `run_daily.bat` writes the daily decision; schedule it after 006 and 007.

---
*Author: Ivan Alonso · [github.com/ivanalonso-dev](https://github.com/ivanalonso-dev)*
