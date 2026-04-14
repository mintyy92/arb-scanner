from flask import Flask, render_template_string
import requests
import os
import threading

app = Flask(__name__)

API_KEY = os.environ.get("ODDS_API_KEY")

SPORTS = [
    "soccer_epl",
    "basketball_nba",
    "australianrules_afl",
    "rugbyleague_nrl"
]

results = []
lock = threading.Lock()

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Fast Arbitrage Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: Arial; background: #111; color: #fff; padding: 15px; }
        h1 { text-align: center; }
        .card { background:#1e1e1e; padding:15px; margin:10px 0; border-radius:10px; }
        .profit { color:#00ff99; font-weight:bold; }
        .sport { color:#aaa; font-size:12px; }
    </style>
</head>
<body>
    <h1>⚡ Multi-Sport Arbitrage Scanner</h1>

    {% for arb in arbs %}
        <div class="card">
            <div class="sport">{{ arb.sport }}</div>
            <h3>{{ arb.match }}</h3>
            <p>{{ arb.odds }}</p>
            <p class="profit">Profit: {{ arb.profit }}%</p>
        </div>
    {% endfor %}

</body>
</html>
"""

def fetch_sport(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": "au",
        "markets": "h2h"
    }

    try:
        data = requests.get(url, params=params, timeout=5).json()

        if not isinstance(data, list):
            return

        for event in data:
            best_odds = {}

            for bookmaker in event.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        name = outcome["name"]
                        price = outcome["price"]

                        if name not in best_odds or price > best_odds[name]:
                            best_odds[name] = price

            if len(best_odds) == 2:
                odds = list(best_odds.values())

                # Filter bad odds
                if any(o < 1.2 or o > 20 for o in odds):
                    continue

                total = (1 / odds[0]) + (1 / odds[1])

                if total < 0.99:
                    profit = round((1 - total) * 100, 2)

                    # Filter unrealistic profit
                    if profit < 1 or profit > 10:
                        continue

                    with lock:
                        results.append({
                            "sport": sport,
                            "match": f"{event['home_team']} vs {event['away_team']}",
                            "odds": best_odds,
                            "profit": profit
                        })

    except Exception:
        pass

def scan_all():
    global results
    results = []

    threads = []

    for sport in SPORTS:
        t = threading.Thread(target=fetch_sport, args=(sport,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

@app.route("/")
def home():
    scan_all()
    return render_template_string(HTML, arbs=results)

if __name__ == "__main__":
    app.run()
