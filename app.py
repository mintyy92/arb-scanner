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
        .profit {
            color: #00ff99;
            font-weight: bold;
        }
        .near {
            color: #ffd54f;
            font-weight: bold;
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
                <div class="title">{{ arb.player }} — {{ arb.line_value }} {{ arb.market_label }}</div>

                <div class="line">
                    <span class="book">Over</span>:
                    {{ arb.over_odds }} at {{ arb.over_bookmaker }}
                    {% if arb.over_link %}
                        — <a href="{{ arb.over_link }}" target="_blank">Open</a>
                    {% endif %}
                </div>

                <div class="line">
                    <span class="book">Under</span>:
                    {{ arb.under_odds }} at {{ arb.under_bookmaker }}
                    {% if arb.under_link %}
                        — <a href="{{ arb.under_link }}" target="_blank">Open</a>
                    {% endif %}
                </div>

                {% if arb.status == "ARB" %}
                    <div class="line status-arb">Status: ARB</div>
                    <div class="line profit">Margin: {{ arb.profit_pct }}%</div>
                {% else %}
                    <div class="line status-near">Status: NEAR ARB</div>
                    <div class="line near">Margin: {{ arb.profit_pct }}%</div>
                {% endif %}

                <div class="line">
                    Bet split: Over {{ arb.over_bet_pct }}% / Under {{ arb.under_bet_pct }}%
                </div>
            </div>
        {% endfor %}
    {% else %}
        <div class="empty">
            No NBA prop arbs or near arbs found right now.
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

def calc_split(over_odds, under_odds):
    inv_over = 1 / over_odds
    inv_under = 1 / under_odds
    total = inv_over + inv_under

    over_pct = round((inv_over / total) * 100, 2)
    under_pct = round((inv_under / total) * 100, 2)
    profit_pct = round((1 - total) * 100, 2)

    return over_pct, under_pct, profit_pct, total

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

                key = (market_key, player, point)

                if key not in grouped:
                    grouped[key] = {
                        "Over": None,
                        "Under": None,
                    }

                candidate = {
                    "price": price,
                    "bookmaker": bookmaker_title,
                    "link": best_link(outcome_link, market_link, bookmaker_link),
                }

                current = grouped[key][side]
                if current is None or price > current["price"]:
                    grouped[key][side] = candidate

    local_results = []

    for (market_key, player, point), sides in grouped.items():
        over_data = sides["Over"]
        under_data = sides["Under"]

        if not over_data or not under_data:
            continue

        if over_data["bookmaker"] == under_data["bookmaker"]:
            continue

        over_pct, under_pct, profit_pct, total = calc_split(
            over_data["price"],
            under_data["price"]
        )

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
                "market_key": market_key,
                "market_label": MARKET_LABELS.get(market_key, market_key),
                "over_odds": over_data["price"],
                "under_odds": under_data["price"],
                "over_bookmaker": over_data["bookmaker"],
                "under_bookmaker": under_data["bookmaker"],
                "over_link": over_data["link"],
                "under_link": under_data["link"],
                "over_bet_pct": over_pct,
                "under_bet_pct": under_pct,
                "profit_pct": round(profit_pct, 2),
                "status": status,
            })

    local_results.sort(key=lambda x: x["profit_pct"], reverse=True)

    with lock:
        results.extend(local_results)

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

    results.sort(key=lambda x: x["profit_pct"], reverse=True)

@app.route("/")
def home():
    scan_all()
    return render_template_string(HTML, arbs=results)

if __name__ == "__main__":
    app.run()
