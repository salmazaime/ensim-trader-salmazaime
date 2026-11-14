import json, math, os, time
import requests

# Organizer feeds (ENSIM Trade Center)
BASE = "https://raw.githubusercontent.com/exofri/ensim-trade-center/refs/heads/main"
MARKET_URL = f"{BASE}/docs/data/market.json"
HOLDINGS_URL = f"{BASE}/traders/salmazaime/holdings.json"
LEADERBOARD_URL = f"{BASE}/docs/data/leaderboard.json"

MIN_MONEY_RESERVE = 50  # never let a buy signal spend below this much money

# --- My signal: mean reversion on a z-score ------------------------------------
# Observation: prices on this market oscillate around a level instead of trending
# (on 340 ticks, trend-following lost 39 % while mean reversion gained 84 %).
# z = (current price - mean of last WINDOW prices) / std of last WINDOW prices
#   z > 0 : price above its recent normal -> expected to come back down -> SELL
#   z < 0 : price below its recent normal -> expected to come back up   -> BUY
# signal = -z / Z_FULL, clipped to [-1, 1]: the further from the mean, the bigger
# the order; a price 1 standard deviation away already gives a full-size order.
WINDOW = 20     # ticks of history used for the mean and the standard deviation
Z_FULL = 1.0    # |z| at which the signal reaches +/-1
DEAD_ZONE = 0.2 # |z| below this -> hold (avoid trading on noise)


def fetch_json(url):
    resp = requests.get(url, proxies={"http": None, "https": None}, timeout=(10, 20))
    resp.raise_for_status()
    return resp.json()


def zscore_info(prices):
    """All the indicators behind the decision (also shown on the dashboard)."""
    if len(prices) < WINDOW:
        return {"signal": 0.0, "z": None, "mean": None, "std": None,
                "reason": f"only {len(prices)} ticks (< {WINDOW}): hold"}
    window = prices[-WINDOW:]
    mean = sum(window) / WINDOW
    std = math.sqrt(sum((p - mean) ** 2 for p in window) / WINDOW)
    z = (prices[-1] - mean) / std if std > 0 else 0.0
    signal = 0.0 if abs(z) < DEAD_ZONE else max(-1.0, min(1.0, -z / Z_FULL))
    action = "buy" if signal > 0 else "sell" if signal < 0 else "hold"
    return {
        "signal": round(signal, 3),
        "z": round(z, 3),
        "mean": round(mean, 4),
        "std": round(std, 4),
        "price": round(prices[-1], 4),
        "reason": f"{action}: price {prices[-1]:.3f} is {z:+.2f} std from its {WINDOW}-tick mean {mean:.3f}",
    }


def compute_signal(prices):
    return zscore_info(prices)["signal"]


def apply_budget_guard(raw_signal, money, price, reserve=MIN_MONEY_RESERVE):
    # Provided by the manual, unchanged.
    if raw_signal <= 0:
        return raw_signal
    if money <= reserve:
        return 0.0
    max_affordable_units = (money - reserve) / price
    desired_units = 100 * raw_signal
    if desired_units <= max_affordable_units:
        return raw_signal
    return round(max_affordable_units / 100, 3)


def main():
    market = fetch_json(MARKET_URL)
    try:
        holdings = fetch_json(HOLDINGS_URL)
        registered = True
    except Exception:
        # Not created yet by the organizer: use the market's own starting values.
        holdings = {"money": 1000.0, "products": {p: 1000.0 for p in market["products"]}}
        registered = False
    try:
        leaderboard = {r["id"]: r["total_value"] for r in fetch_json(LEADERBOARD_URL)["leaderboard"]}
    except Exception:
        leaderboard = {}

    products, history = market["products"], market["history"]
    decision, details = {}, {}
    for p in products:
        prices = [row[p] for row in history]
        info = zscore_info(prices)
        final = round(apply_budget_guard(info["signal"], holdings["money"], prices[-1]), 3)
        decision[p] = final
        details[p] = {**info, "final": final}

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    decision["updated_at"] = now
    with open("decision.json", "w") as f:
        json.dump(decision, f, indent=2)

    # Decision log: one entry per run, used by the dashboard.
    path = "docs/data/decision_log.json"
    log = {"entries": []}
    if os.path.exists(path):
        with open(path) as f:
            log = json.load(f)
    log["entries"].append({
        "run_at": now,
        "market_tick": history[-1]["t"],
        "registered": registered,
        "money": round(holdings["money"], 2),
        "holdings": {p: round(holdings["products"][p], 2) for p in products},
        "decision": {p: decision[p] for p in products},
        "details": details,
        "leaderboard": leaderboard,
    })
    log["entries"] = log["entries"][-500:]
    os.makedirs("docs/data", exist_ok=True)
    with open(path, "w") as f:
        json.dump(log, f, indent=2)

    print(f"Registered: {registered}")
    print(f"Wrote decision.json: {decision}")
    for p in products:
        print(f"  {p}: {details[p]['reason']}")


if __name__ == "__main__":
    main()
