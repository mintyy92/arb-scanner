from flask import Flask, render_template_string
import requests
import os
import threading

app = Flask(__name__)

API_KEY = os.environ.get("ODDS_API_KEY")
SPORT = "basketball_nba"
REGIONS = "au"

BOOKMAKERS = [
    "sportsbet",
    "pointsbetau",
    "ladbrokes_au",
    "neds",
]

MARKETS = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_steals",
    "player_blocks",
]

MARKET_LABELS = {
    "player_points": "Points",
    "player_rebounds": "Rebounds",
    "player_assists": "Assists",
    "player_threes": "Threes",
    "player_steals": "Steals",
    "player_blocks": "Blocks",
}

results = []
lock = threading.Lock()

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>NBA Player Props Scanner</title>
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
        a {
            color: #7cc4ff;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .empty {
            text-align: center;
            color: #aaa;
            margin-top: 40px;
        }
    </style>
</head>
<body>
    <h1>🏀 NBA Player Props Scanner</h1>

    {% if arbs %}
        {% for arb in arbs %}
            <div class="card">
                <div class="subtle">{{ arb.match }}</div>
                <div class="title">{{ arb.player }} — {{ arb.side }} {{ arb.line_value }} {{ arb.market_label }}</div>

                <div class="line">
                    <span class="book">Best odds</span>:
                    {{ arb.best_odds }} at {{ arb.best_bookmaker }}
                    {% if arb.best_link %}
                        — <a href="{{ arb.best_link }}" target="_blank">Open</a>
                    {% endif %}
                </div>

                {% if arb.other_prices %}
                    <div class="other-prices">
                        Other prices: {{ arb.other_prices }}
                    </div>
                {% endif %}

                {% if arb.status == "ARB" %}
                    <div class="line status-arb">Status: ARB</div>
                    <div class="line">
                        Opposite side: {{ arb.opposite_odds }} at {{ arb.opposite_bookmaker }}
                        {% if arb.opposite_link %}
                            — <a href="{{ arb.opposite_link }}" target="_blank">Open</a>
                        {% endif %}
                    </div>
                    <div class="line profit">Margin: {{ arb.profit_pct }}%</div>
                    <div class="line">
                        Bet split: This side {{ arb.this_side_bet_pct }}% / Opposite side {{ arb.opposite_side_bet_pct }}%
                    </div>
                {% elif arb.status == "NEAR ARB" %}
                    <div class="line status-near">Status: NEAR ARB</div>
                    <div class="line">
                        Opposite side: {{ arb.opposite_odds }} at {{ arb.opposite_bookmaker }}
                        {% if arb.opposite_link %}
                            — <a href="{{ arb.opposite_link }}" target="_blank">Open</a>
                        {% endif %}
                    </div>
                    <div class="line near">Margin: {{ arb.profit_pct }}%</div>
                    <div class="line">
                        Bet split: This side {{ arb.this_side_bet_pct }}% / Opposite side {{ arb.opposite_side_bet_pct }}%
                    </div>
                {% else %}
                    <div class="line status-best">Status: BEST PRICE</div>
                    <div class="line value">Edge vs market average: {{ arb.edge_vs_avg }}%</div>
                    <div class="line">Market average: {{ arb.market_average }}</div>
                {% endif %}
            </div>
        {% endfor %}
    {% else %}
        <div class="empty">
            No NBA player prop data found right now.
        </div>
    {% endif %}
</body>
</html>
"""

def best_link(outcome_link, market_link, bookmaker_link):
    return outcome_link or market_link or bookmaker_link or None

def get_events():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": "h2h",
        "bookmakers": ",".join(BOOKMAKERS),
        "oddsFormat": "decimal",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []

def get_event_props(event_id):
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": ",".join(MARKETS),
        "bookmakers": ",".join(BOOKMAKERS),
        "oddsFormat": "decimal",
        "includeLinks": "true",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def calc_split(this_odds, opposite_odds):
    inv_this = 1 / this_odds
    inv_opp = 1 / opposite_odds
    total = inv_this + inv_opp

    this_pct = round((inv_this / total) * 100, 2)
    opp_pct = round((inv_opp / total) * 100, 2)
    profit_pct = round((1 - total) * 100, 2)

    return this_pct, opp_pct, profit_pct, total

def process_event(event):
    event_id = event.get("id")
    if not event_id:
        return

    props_data = get_event_props(event_id)
    bookmakers = props_data.get("bookmakers", [])
    match_name = f"{event.get('away_team', 'Away')} vs {event.get('home_team', 'Home')}"

    grouped = {}

    for bookmaker in bookmakers:
        bookmaker_title = bookmaker.get("title", bookmaker.get("key", "Unknown"))
        bookmaker_link = bookmaker.get("link")

        for market in bookmaker.get("markets", []):
            market_key = market.get("key")
            if market_key not in MARKETS:
                continue

            market_link = market.get("link")

            for outcome in market.get("outcomes", []):
                player = outcome.get("description")
                side = outcome.get("name")
                point = outcome.get("point")
                price = outcome.get("price")
                outcome_link = outcome.get("link")

                if not player or side not in ("Over", "Under") or point is None or price is None:
                    continue

                if price < 1.2 or price > 10:
                    continue

                key = (market_key, player, point, side)

                if key not in grouped:
                    grouped[key] = []

                grouped[key].append({
                    "price": price,
                    "bookmaker": bookmaker_title,
                    "link": best_link(outcome_link, market_link, bookmaker_link),
                })

    local_results = []

    processed_pairs = set()

    # BEST PRICE VIEW FOR EACH SIDE
    for (market_key, player, point, side), offers in grouped.items():
        if len(offers) == 0:
            continue

        sorted_offers = sorted(offers, key=lambda x: x["price"], reverse=True)
        best_offer = sorted_offers[0]

        all_prices = [offer["price"] for offer in offers]
        market_average = round(sum(all_prices) / len(all_prices), 3)
        edge_vs_avg = round(((best_offer["price"] / market_average) - 1) * 100, 2) if market_average > 0 else 0

        other_prices = []
        for offer in sorted_offers[1:]:
            other_prices.append(f"{offer['bookmaker']} {offer['price']}")

        local_results.append({
            "match": match_name,
            "player": player,
            "line_value": point,
            "market_label": MARKET_LABELS.get(market_key, market_key),
            "side": side,
            "best_odds": best_offer["price"],
            "best_bookmaker": best_offer["bookmaker"],
            "best_link": best_offer["link"],
            "other_prices": ", ".join(other_prices) if other_prices else "",
            "market_average": market_average,
            "edge_vs_avg": edge_vs_avg,
            "status": "BEST PRICE",
            "profit_pct": edge_vs_avg,
            "opposite_odds": None,
            "opposite_bookmaker": None,
            "opposite_link": None,
            "this_side_bet_pct": None,
            "opposite_side_bet_pct": None,
        })

        # ARB / NEAR ARB CHECK
        pair_key = (market_key, player, point)
        if pair_key in processed_pairs:
            continue

        over_offers = grouped.get((market_key, player, point, "Over"), [])
        under_offers = grouped.get((market_key, player, point, "Under"), [])

        if not over_offers or not under_offers:
            continue

        best_over = sorted(over_offers, key=lambda x: x["price"], reverse=True)[0]
        best_under = sorted(under_offers, key=lambda x: x["price"], reverse=True)[0]

        if best_over["bookmaker"] == best_under["bookmaker"]:
            continue

        this_pct, opp_pct, profit_pct, total = calc_split(best_over["price"], best_under["price"])

        status = None
        if total < 1:
            status = "ARB"
        elif total <= 1.02:
            status = "NEAR ARB"

        if status:
            local_results.append({
                "match": match_name,
                "player": player,
                "line_value": point,
                "market_label": MARKET_LABELS.get(market_key, market_key),
                "side": "Over",
                "best_odds": best_over["price"],
                "best_bookmaker": best_over["bookmaker"],
                "best_link": best_over["link"],
                "other_prices": ", ".join([f"{o['bookmaker']} {o['price']}" for o in sorted(over_offers, key=lambda x: x["price"], reverse=True)[1:]]),
                "market_average": None,
                "edge_vs_avg": None,
                "status": status,
                "profit_pct": round(profit_pct, 2),
                "opposite_odds": best_under["price"],
                "opposite_bookmaker": best_under["bookmaker"],
                "opposite_link": best_under["link"],
                "this_side_bet_pct": this_pct,
                "opposite_side_bet_pct": opp_pct,
            })

        processed_pairs.add(pair_key)

    with lock:
        results.extend(local_results)

def dedupe_results(items):
    seen = set()
    deduped = []

    for item in items:
        key = (
            item["match"],
            item["player"],
            item["market_label"],
            item["line_value"],
            item["side"],
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

    events = get_events()
    threads = []

    for event in events:
        t = threading.Thread(target=process_event, args=(event,))
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
    return render_template_string(HTML, arbs=results)

if __name__ == "__main__":
    app.run()
