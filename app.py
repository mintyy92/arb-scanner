from flask import Flask, render_template_string
import requests
import os
import threading

app = Flask(__name__)

API_KEY = os.environ.get("ODDS_API_KEY")
REGIONS = "au"

SPORTS = [
    ("basketball_nba", "NBA"),
    ("australianrules_afl", "AFL"),
    ("rugbyleague_nrl", "NRL"),
]

MARKETS = ["h2h", "spreads", "totals"]

results = []
lock = threading.Lock()

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AU Main Markets Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="20">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #111;
            color: #fff;
            padding: 16px;
            margin: 0;
        }
        h1 {
            text-align: center;
            margin-bottom: 20px;
            font-size: 24px;
        }
        .card {
            background: #1b1b1b;
            padding: 16px;
            margin: 12px 0;
            border-radius: 12px;
            border: 1px solid #2a2a2a;
        }
        .subtle {
            color: #aaa;
            font-size: 12px;
            margin-bottom: 6px;
        }
        .title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .line {
            margin: 6px 0;
            font-size: 14px;
        }
        .book {
            color: #7cc4ff;
            font-weight: bold;
        }
        .status-arb {
            color: #00ff99;
            font-weight: bold;
        }
        .status-near {
            color: #ffd54f;
            font-weight: bold;
        }
        .status-best {
            color: #7cc4ff;
            font-weight: bold;
        }
        .profit {
            color: #00ff99;
            font-weight: bold;
        }
        .near {
            color: #ffd54f;
            font-weight: bold;
        }
        .value {
            color: #7cc4ff;
            font-weight: bold;
        }
        .other-prices {
            color: #cfcfcf;
            font-size: 13px;
            margin-top: 6px;
            line-height: 1.5;
        }
        .empty {
            text-align: center;
            color: #aaa;
            margin-top: 40px;
        }
    </style>
</head>
<body>
    <h1>🇦🇺 AU Main Markets Scanner</h1>

    {% if rows %}
        {% for row in rows %}
            <div class="card">
                <div class="subtle">{{ row.sport_label }} — {{ row.match }}</div>
                <div class="title">{{ row.display_name }}</div>

                <div class="line">
                    <span class="book">Best odds</span>:
                    {{ row.best_odds }} at {{ row.best_bookmaker }}
                </div>

                {% if row.other_prices %}
                    <div class="other-prices">
                        Other prices: {{ row.other_prices }}
                    </div>
                {% endif %}

                {% if row.status == "ARB" %}
                    <div class="line status-arb">Status: ARB</div>
                    <div class="line">
                        Opposite side: {{ row.opposite_label }} at {{ row.opposite_odds }} ({{ row.opposite_bookmaker }})
                    </div>
                    <div class="line profit">Margin: {{ row.profit_pct }}%</div>
                    <div class="line">
                        Bet split: This side {{ row.this_side_bet_pct }}% / Opposite side {{ row.opposite_side_bet_pct }}%
                    </div>
                {% elif row.status == "NEAR ARB" %}
                    <div class="line status-near">Status: NEAR ARB</div>
                    <div class="line">
                        Opposite side: {{ row.opposite_label }} at {{ row.opposite_odds }} ({{ row.opposite_bookmaker }})
                    </div>
                    <div class="line near">Margin: {{ row.profit_pct }}%</div>
                    <div class="line">
                        Bet split: This side {{ row.this_side_bet_pct }}% / Opposite side {{ row.opposite_side_bet_pct }}%
                    </div>
                {% else %}
                    <div class="line status-best">Status: BEST PRICE</div>
                    <div class="line value">Edge vs market average: {{ row.edge_vs_avg }}%</div>
                    <div class="line">Market average: {{ row.market_average }}</div>
                {% endif %}
            </div>
        {% endfor %}
    {% else %}
        <div class="empty">
            No AU market data found right now.
        </div>
    {% endif %}
</body>
</html>
"""

ALLOWED_BOOKS = ["sportsbet", "pointsbet", "ladbrokes", "neds"]

def is_allowed_bookmaker(title: str) -> bool:
    title = title.lower()
    return any(book in title for book in ALLOWED_BOOKS)

def calc_split(this_odds, opposite_odds):
    inv_this = 1 / this_odds
    inv_opp = 1 / opposite_odds
    total = inv_this + inv_opp

    this_pct = round((inv_this / total) * 100, 2)
    opp_pct = round((inv_opp / total) * 100, 2)
    profit_pct = round((1 - total) * 100, 2)

    return this_pct, opp_pct, profit_pct, total

def build_display_name(market_key, outcome_name, point):
    if market_key == "h2h":
        return f"H2H — {outcome_name}"
    if market_key == "spreads":
        return f"Spread — {outcome_name} {point:+g}"
    if market_key == "totals":
        return f"Total — {outcome_name} {point:g}"
    return f"{market_key} — {outcome_name}"

def get_odds_for_sport(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": ",".join(MARKETS),
        "oddsFormat": "decimal",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []

def process_sport(sport_key, sport_label):
    events = get_odds_for_sport(sport_key)
    local_results = []

    for event in events:
        match_name = f"{event.get('away_team', 'Away')} vs {event.get('home_team', 'Home')}"

        grouped = {}
        market_presence = {"h2h": set(), "totals": set(), "spreads": set()}

        for bookmaker in event.get("bookmakers", []):
            bookmaker_title = bookmaker.get("title", bookmaker.get("key", "Unknown"))

            if not is_allowed_bookmaker(bookmaker_title):
                continue

            for market in bookmaker.get("markets", []):
                market_key = market.get("key")
                if market_key not in MARKETS:
                    continue

                for outcome in market.get("outcomes", []):
                    name = outcome.get("name")
                    price = outcome.get("price")
                    point = outcome.get("point")

                    if name is None or price is None:
                        continue

                    if price < 1.01 or price > 20:
                        continue

                    if market_key == "h2h":
                        key = ("h2h", name, None)
                        market_presence["h2h"].add(name)
                    elif market_key == "totals":
                        if point is None:
                            continue
                        point = float(point)
                        key = ("totals", name, point)
                        market_presence["totals"].add(point)
                    elif market_key == "spreads":
                        if point is None:
                            continue
                        point = float(point)
                        key = ("spreads", name, point)
                        market_presence["spreads"].add((name, point))
                    else:
                        continue

                    if key not in grouped:
                        grouped[key] = []

                    grouped[key].append({
                        "price": float(price),
                        "bookmaker": bookmaker_title,
                        "name": name,
                        "point": point,
                    })

        # BEST PRICE CARDS
        for (market_key, name, point), offers in grouped.items():
            if not offers:
                continue

            sorted_offers = sorted(offers, key=lambda x: x["price"], reverse=True)
            best_offer = sorted_offers[0]

            prices = [offer["price"] for offer in offers]
            market_average = round(sum(prices) / len(prices), 3)
            edge_vs_avg = round(((best_offer["price"] / market_average) - 1) * 100, 2) if market_average > 0 else 0

            other_prices = ", ".join(
                [f"{offer['bookmaker']} {offer['price']}" for offer in sorted_offers[1:]]
            )

            local_results.append({
                "sport_label": sport_label,
                "match": match_name,
                "display_name": build_display_name(market_key, name, point),
                "best_odds": best_offer["price"],
                "best_bookmaker": best_offer["bookmaker"],
                "other_prices": other_prices,
                "market_average": market_average,
                "edge_vs_avg": edge_vs_avg,
                "status": "BEST PRICE",
                "profit_pct": edge_vs_avg,
                "opposite_label": None,
                "opposite_odds": None,
                "opposite_bookmaker": None,
                "this_side_bet_pct": None,
                "opposite_side_bet_pct": None,
            })

        # ARB / NEAR ARB — H2H
        h2h_keys = [key for key in grouped.keys() if key[0] == "h2h"]
        if len(h2h_keys) == 2:
            key1, key2 = h2h_keys
            best1 = sorted(grouped[key1], key=lambda x: x["price"], reverse=True)[0]
            best2 = sorted(grouped[key2], key=lambda x: x["price"], reverse=True)[0]

            if best1["bookmaker"] != best2["bookmaker"]:
                this_pct, opp_pct, profit_pct, total = calc_split(best1["price"], best2["price"])
                status = "ARB" if total < 1 else "NEAR ARB" if total <= 1.02 else None

                if status:
                    local_results.append({
                        "sport_label": sport_label,
                        "match": match_name,
                        "display_name": f"H2H Arb — {key1[1]} / {key2[1]}",
                        "best_odds": best1["price"],
                        "best_bookmaker": best1["bookmaker"],
                        "other_prices": "",
                        "market_average": None,
                        "edge_vs_avg": None,
                        "status": status,
                        "profit_pct": round(profit_pct, 2),
                        "opposite_label": key2[1],
                        "opposite_odds": best2["price"],
                        "opposite_bookmaker": best2["bookmaker"],
                        "this_side_bet_pct": this_pct,
                        "opposite_side_bet_pct": opp_pct,
                    })

        # ARB / NEAR ARB — TOTALS
        checked_totals = set()
        for point in market_presence["totals"]:
            if point in checked_totals:
                continue

            over_key = ("totals", "Over", point)
            under_key = ("totals", "Under", point)

            if over_key in grouped and under_key in grouped:
                best_over = sorted(grouped[over_key], key=lambda x: x["price"], reverse=True)[0]
                best_under = sorted(grouped[under_key], key=lambda x: x["price"], reverse=True)[0]

                if best_over["bookmaker"] != best_under["bookmaker"]:
                    this_pct, opp_pct, profit_pct, total = calc_split(best_over["price"], best_under["price"])
                    status = "ARB" if total < 1 else "NEAR ARB" if total <= 1.02 else None

                    if status:
                        local_results.append({
                            "sport_label": sport_label,
                            "match": match_name,
                            "display_name": f"Total Arb — {point:g}",
                            "best_odds": best_over["price"],
                            "best_bookmaker": best_over["bookmaker"],
                            "other_prices": "",
                            "market_average": None,
                            "edge_vs_avg": None,
                            "status": status,
                            "profit_pct": round(profit_pct, 2),
                            "opposite_label": f"Under {point:g}",
                            "opposite_odds": best_under["price"],
                            "opposite_bookmaker": best_under["bookmaker"],
                            "this_side_bet_pct": this_pct,
                            "opposite_side_bet_pct": opp_pct,
                        })

            checked_totals.add(point)

        # ARB / NEAR ARB — SPREADS
        checked_spreads = set()
        for (market_key, name, point), offers in list(grouped.items()):
            if market_key != "spreads":
                continue

            pair_id = tuple(sorted([(name, point), ("opp", -point)]))
            if pair_id in checked_spreads:
                continue

            opposite_key = None
            for (mk, opp_name, opp_point) in grouped.keys():
                if mk == "spreads" and opp_name != name and opp_point == -point:
                    opposite_key = (mk, opp_name, opp_point)
                    break

            if opposite_key and (market_key, name, point) in grouped:
                best_a = sorted(grouped[(market_key, name, point)], key=lambda x: x["price"], reverse=True)[0]
                best_b = sorted(grouped[opposite_key], key=lambda x: x["price"], reverse=True)[0]

                if best_a["bookmaker"] != best_b["bookmaker"]:
                    this_pct, opp_pct, profit_pct, total = calc_split(best_a["price"], best_b["price"])
                    status = "ARB" if total < 1 else "NEAR ARB" if total <= 1.02 else None

                    if status:
                        local_results.append({
                            "sport_label": sport_label,
                            "match": match_name,
                            "display_name": f"Spread Arb — {name} {point:+g} / {opposite_key[1]} {opposite_key[2]:+g}",
                            "best_odds": best_a["price"],
                            "best_bookmaker": best_a["bookmaker"],
                            "other_prices": "",
                            "market_average": None,
                            "edge_vs_avg": None,
                            "status": status,
                            "profit_pct": round(profit_pct, 2),
                            "opposite_label": f"{opposite_key[1]} {opposite_key[2]:+g}",
                            "opposite_odds": best_b["price"],
                            "opposite_bookmaker": best_b["bookmaker"],
                            "this_side_bet_pct": this_pct,
                            "opposite_side_bet_pct": opp_pct,
                        })

            checked_spreads.add(pair_id)

    with lock:
        results.extend(local_results)

def dedupe_results(items):
    seen = set()
    deduped = []

    for item in items:
        key = (
            item["sport_label"],
            item["match"],
            item["display_name"],
            item["status"],
            item["best_bookmaker"],
            item["best_odds"],
        )
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped

def scan_all():
    global results
    results = []

    threads = []
    for sport_key, sport_label in SPORTS:
        t = threading.Thread(target=process_sport, args=(sport_key, sport_label))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    results = dedupe_results(results)

    status_order = {"ARB": 0, "NEAR ARB": 1, "BEST PRICE": 2}
    results.sort(key=lambda x: (status_order.get(x["status"], 3), -(x["profit_pct"] or 0)))

@app.route("/")
def home():
    scan_all()
    return render_template_string(HTML, rows=results)

if __name__ == "__main__":
    app.run()
