from flask import Flask, render_template_string
import requests
import os
import threading

app = Flask(__name__)

API_KEY = os.environ.get("ODDS_API_KEY")
SPORT = "basketball_nba"
REGIONS = "au"
MARKET = "player_points"

# AU bookmaker keys supported in The Odds API docs
BOOKMAKERS = [
    "sportsbet",
    "pointsbetau",
    "ladbrokes_au",
    "neds",
    # "bet365_au",  # intentionally excluded for NBA player props
]

results = []
lock = threading.Lock()

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>NBA Player Points Arb Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="20">
    <style>
        body { font-family: Arial, sans-serif; background: #111; color: #fff; padding: 16px; }
        h1 { text-align: center; margin-bottom: 20px; }
        .card { background: #1b1b1b; padding: 16px; margin: 12px 0; border-radius: 12px; }
        .profit { color: #00ff99; font-weight: bold; }
        .subtle { color: #aaa; font-size: 12px; }
        .line { margin: 6px 0; }
        .book { color: #7cc4ff; font-weight: bold; }
    </style>
</head>
<body>
    <h1>🏀 NBA Player Points Arbitrage Scanner</h1>

    {% if arbs %}
        {% for arb in arbs %}
            <div class="card">
                <div class="subtle">{{ arb.match }}</div>
                <h3>{{ arb.player }} — {{ arb.line_value }} Points</h3>

                <div class="line">
                    <span class="book">Over</span>:
                    {{ arb.over_odds }} at {{ arb.over_bookmaker }}
                </div>

                <div class="line">
                    <span class="book">Under</span>:
                    {{ arb.under_odds }} at {{ arb.under_bookmaker }}
                </div>

                <div class="line profit">Arb Margin: {{ arb.profit_pct }}%</div>
                <div class="line">Bet split: Over {{ arb.over_bet_pct }}% / Under {{ arb.under_bet_pct }}%</div>
            </div>
        {% endfor %}
    {% else %}
        <div class="card">
            <p>No NBA player points arbs found right now.</p>
        </div>
    {% endif %}
</body>
</html>
"""

def get_events():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": "h2h",
        "bookmakers": ",".join(BOOKMAKERS),
        "oddsFormat": "decimal",
    }
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    return data if isinstance(data, list) else []

def get_event_props(event_id):
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": MARKET,
        "bookmakers": ",".join(BOOKMAKERS),
        "oddsFormat": "decimal",
    }
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    return data if isinstance(data, dict) else {}

def calc_bet_split(over_odds, under_odds):
    inv_over = 1 / over_odds
    inv_under = 1 / under_odds
    total = inv_over + inv_under

    over_pct = round((inv_over / total) * 100, 2)
    under_pct = round((inv_under / total) * 100, 2)
    profit_pct = round((1 - total) * 100, 2)

    return over_pct, under_pct, profit_pct

def process_event(event):
    event_id = event.get("id")
    if not event_id:
        return

    props_data = get_event_props(event_id)
    bookmakers = props_data.get("bookmakers", [])
    match_name = f"{event.get('away_team', 'Away')} vs {event.get('home_team', 'Home')}"

    # Group outcomes by (player, points line)
    grouped = {}

    for bookmaker in bookmakers:
        bookmaker_title = bookmaker.get("title", bookmaker.get("key", "Unknown"))

        for market in bookmaker.get("markets", []):
            if market.get("key") != MARKET:
                continue

            for outcome in market.get("outcomes", []):
                player = outcome.get("description")
                side = outcome.get("name")   # usually Over / Under
                point = outcome.get("point")
                price = outcome.get("price")

                if not player or side not in ("Over", "Under") or point is None or not price:
                    continue

                # Basic sanity filter
                if price < 1.2 or price > 10:
                    continue

                key = (player, point)
                if key not in grouped:
                    grouped[key] = {
                        "Over": None,
                        "Under": None,
                    }

                current = grouped[key][side]
                if current is None or price > current["price"]:
                    grouped[key][side] = {
                        "price": price,
                        "bookmaker": bookmaker_title
                    }

   
