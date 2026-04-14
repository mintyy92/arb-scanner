from flask import Flask, render_template_string
import requests
import os

app = Flask(__name__)

API_KEY = os.environ.get("ODDS_API_KEY")
SPORT = "basketball_nba"
REGIONS = "us"

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

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>NBA Props Debug</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: Arial, sans-serif; background: #111; color: #fff; padding: 16px; margin: 0; }
        .card { background: #1b1b1b; padding: 16px; margin: 12px 0; border-radius: 12px; border: 1px solid #2a2a2a; }
        .line { margin: 6px 0; }
    </style>
</head>
<body>
    <div class="card">
        <div class="line">Events found: {{ summary.events_count }}</div>
        <div class="line">Events with prop bookmakers: {{ summary.events_with_props }}</div>
        <div class="line">Raw offers found: {{ summary.offers_count }}</div>
    </div>
</body>
</html>
"""

def get_events():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events"
    params = {
        "apiKey": API_KEY,
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

@app.route("/")
def home():
    events = get_events()
    events_with_props = 0
    total_offers = 0

    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue

        props_data = get_event_props(event_id)
        bookmakers = props_data.get("bookmakers", [])

        if bookmakers:
            events_with_props += 1

        for bookmaker in bookmakers:
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    if outcome.get("price") is not None:
                        total_offers += 1

    summary = {
        "events_count": len(events),
        "events_with_props": events_with_props,
        "offers_count": total_offers,
    }

    return render_template_string(HTML, summary=summary)

if __name__ == "__main__":
    app.run()
