from flask import Flask, render_template_string
import requests
import os
import threading

app = Flask(__name__)

API_KEY = os.environ.get("ODDS_API_KEY")
REGIONS = "au"

BOOKMAKERS = [
    "sportsbet",
    "pointsbetau",
    "ladbrokes_au",
    "neds",
]

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

def calc_split(this_odds, opposite_odds):
    inv_this = 1 / this_odds
    inv_opp = 1 / opposite_odds
    total = inv_this + inv_opp

    this_pct = round((inv_this / total) * 100, 2)
    opp_pct = round((inv_opp / total) * 100, 2)
    profit_pct = round((1 - total) * 100, 2)
    return this_pct, opp_pct, profit_pct, total

def build_display_name(market_key, side, point, outcome_name):
    if market_key == "h2h":
        return f"H2H — {outcome_name}"
    if market_key == "spreads":
        return f"Spread — {outcome_name} {point:+}"
    if market_key == "totals":
        return f"Total — {side} {point}"
    return f"{market_key} — {outcome_name}"

def get_odds_for_sport(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": ",".join(MARKETS),
        "bookmakers": ",".join(BOOKMAKERS),
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

        for bookmaker in event.get("bookmakers", []):
            bookmaker_title = bookmaker.get("title", bookmaker.get("key", "Unknown"))

            for market in bookmaker.get("markets", []):
                market_key = market.get("key")
                if market_key not in MARKETS:
                    continue

                for outcome in market.get("outcomes", []):
                    price = outcome.get("price")
                    name = outcome.get("name")
                    point = outcome.get("point")

                    if price is None or name is None:
                        continue

                    if price < 1.01 or price > 20:
                        continue

                    if market_key == "h2h":
                        side_key = name
                    elif market_key == "spreads":
                        side_key = f"{name}|{point}"
                    elif market_key == "totals":
                        side_key = f"{name}|{point}"
                    else:
                        continue

                    key = (market_key, side_key)
                    if key not in grouped:
                        grouped[key] = []

                    grouped[key].append({
                        "price": price,
                        "bookmaker": bookmaker_title,
                        "name": name,
                        "point": point,
                    })

        processed_pairs = set()

        for (market_key, side_key), offers in grouped.items():
            if not offers:
                continue

            sorted_offers = sorted(offers, key=lambda x: x["price"], reverse=True)
            best_offer = sorted_offers[0]

            all_prices = [offer["price"] for offer in offers]
            market_average = round(sum(all_prices) / len(all_prices), 3)
            edge_vs_avg = round(((best_offer["price"] / market_average) - 1) * 100, 2) if market_average > 0 else 0

            other_prices = [f"{offer['bookmaker']} {offer['price']}" for offer in sorted_offers[1:]]

            # always add best price card
            if market_key == "h2h":
                side = best_offer["name"]
            else:
                side = best_offer["name"]

            local_results.append({
                "sport_label": sport_label,
                "match": match_name,
                "display_name": build_display_name(market_key, side, best_offer["point"], best_offer["name"]),
                "best_odds": best_offer["price"],
                "best_bookmaker": best_offer["bookmaker"],
                "other_prices": ", ".join(other_prices),
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

            # arb / near-arb logic
            if market_key == "h2h":
                outcomes = [o.get("name") for o in event.get("bookmakers", [])[0].get("markets", []) if False]
                # build opposite from event teams
                possible = []
                for key2, offers2 in grouped.items():
                    mk2, sk2 = key2
                    if mk2 != "h2h" or sk2 == side_key:
                        continue
                    possible.append((key2, offers2))

                if possible:
                    opp_key, opp_offers = possible[0]
                    best_opp = sorted(opp_offers, key=lambda x: x["price"], reverse=True)[0]

                    if best_offer["bookmaker"] != best_opp["bookmaker"]:
                        this_pct, opp_pct, profit_pct, total = calc_split(best_offer["price"], best_opp["price"])
                        status = "ARB" if total < 1 else "NEAR ARB" if total <= 1.02 else None

                        if status:
                            local_results.append({
                                "sport_label": sport_label,
                                "match": match_name,
                                "display_name": build_display_name(market_key, best_offer["name"], best_offer["point"], best_offer["name"]),
                                "best_odds": best_offer["price"],
                                "best_bookmaker": best_offer["bookmaker"],
                                "other_prices": ", ".join(other_prices),
                                "market_average": None,
                                "edge_vs_avg": None,
                                "status": status,
                                "profit_pct": round(profit_pct, 2),
                                "opposite_label": best_opp["name"],
                                "opposite_odds": best_opp["price"],
                                "opposite_bookmaker": best_opp["bookmaker"],
                                "this_side_bet_pct": this_pct,
                                "opposite_side_bet_pct": opp_pct,
                            })

            elif market_key in ("spreads", "totals"):
                if side_key in processed_pairs:
                    continue

                side_name, point = side_key.split("|")
                opposite_name = "Under" if side_name == "Over" else "Over" if side_name == "Under" else None

                if market_key == "spreads":
                    try:
                        opp_point = str(float(point) * -1)
                    except Exception:
                        continue
                    opposite_key = (market_key, f"{event.get('home_team') if best_offer['name']==event.get('away_team') else event.get('away_team')}|{opp_point}")
                else:
                    opposite_key = (market_key, f"{opposite_name}|{point}")

                opp_offers = grouped.get(opposite_key, [])
                if opp_offers:
                    best_opp = sorted(opp_offers, key=lambda x: x["price"], reverse=True)[0]

                    if best_offer["bookmaker"] != best_opp["bookmaker"]:
                        this_pct, opp_pct, profit_pct, total = calc_split(best_offer["price"], best_opp["price"])
                        status = "ARB" if total < 1 else "NEAR ARB" if total <= 1.02 else None

                        if status:
                            local_results.append({
                                "sport_label": sport_label,
                                "match": match_name,
                                "display_name": build_display_name(market_key, best_offer["name"], best_offer["point"], best_offer["name"]),
                                "best_odds": best_offer["price"],
                                "best_bookmaker": best_offer["bookmaker"],
                                "other_prices": ", ".join(other_prices),
                                "market_average": None,
                                "edge_vs_avg": None,
                                "status": status,
                                "profit_pct": round(profit_pct, 2),
                                "opposite_label": build_display_name(market_key, best_opp["name"], best_opp["point"], best_opp["name"]),
                                "opposite_odds": best_opp["price"],
                                "opposite_bookmaker": best_opp["bookmaker"],
                                "this_side_bet_pct": this_pct,
                                "opposite_side_bet_pct": opp_pct,
                            })

                processed_pairs.add(side_key)
                processed_pairs.add(opposite_key[1] if isinstance(opposite_key, tuple) else opposite_key)

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
