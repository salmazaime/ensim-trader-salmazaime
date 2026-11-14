"""Replay the real market history to compare my strategy with the 3 baselines.

At tick t my signal only sees prices up to t (no look-ahead); the order executes at
the price of tick t+1 with the market's own rules: start with 1000 money + 1000 units
of each product, cannot sell more than held, cannot spend money not held, budget guard.
Baselines draw their demand like the organizer's market does: random_trader U(-1,1),
random_buyer U(0,1), random_seller U(-1,0), averaged over 20 runs.
Limitation: my own effect on prices is not simulated.
Output: docs/data/backtest.json
"""
import json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(__file__))
import algorithm as alg

PRODUCTS = ["A", "B", "C"]


def simulate(history, decide):
    h = {"money": 1000.0, **{p: 1000.0 for p in PRODUCTS}}
    values = []
    for t in range(len(history) - 1):
        for p in PRODUCTS:
            d = decide(t, p)
            price = history[t + 1][p]
            if d > 0:
                d = alg.apply_budget_guard(d, h["money"], history[t][p])
                units = min(100 * d, h["money"] / price)
                h["money"] -= units * price
                h[p] += units
            elif d < 0:
                units = min(-100 * d, h[p])
                h["money"] += units * price
                h[p] -= units
        values.append(round(h["money"] + sum(h[p] * history[t + 1][p] for p in PRODUCTS), 2))
    return values


def stats(v):
    rets = [v[i] / v[i - 1] - 1 for i in range(1, len(v))]
    peak, worst = v[0], 0.0
    for x in v:
        peak = max(peak, x)
        worst = min(worst, x / peak - 1)
    return {"final": round(v[-1], 2),
            "return_pct": round(100 * (v[-1] / v[0] - 1), 1),
            "volatility_pct": round(100 * statistics.pstdev(rets), 2),
            "max_drawdown_pct": round(100 * worst, 1)}


def main():
    history = alg.fetch_json(alg.MARKET_URL)["history"]
    prices = {p: [r[p] for r in history] for p in PRODUCTS}
    series = {"mine": simulate(history, lambda t, p: alg.compute_signal(prices[p][:t + 1]))}
    for name, lo, hi in [("random_trader", -1, 1), ("random_buyer", 0, 1), ("random_seller", -1, 0)]:
        runs = []
        for seed in range(20):
            rng = random.Random(seed)
            runs.append(simulate(history, lambda t, p: rng.uniform(lo, hi)))
        series[name] = [round(sum(r[i] for r in runs) / len(runs), 2) for i in range(len(runs[0]))]
    series["hold"] = simulate(history, lambda t, p: 0.0)

    out = {"ticks": [r["t"] for r in history[1:]], "series": series,
           "stats": {k: stats(v) for k, v in series.items()}}
    os.makedirs("docs/data", exist_ok=True)
    with open("docs/data/backtest.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    for k, s in out["stats"].items():
        print(f"{k:14s} final {s['final']:>10.2f}  return {s['return_pct']:>6.1f}%  "
              f"vol {s['volatility_pct']:.2f}%  max DD {s['max_drawdown_pct']:.1f}%")


if __name__ == "__main__":
    main()
