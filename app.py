from flask import Flask, render_template_string
import requests
import os

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

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>NBA Props Debug</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="30">
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
            margin-bottom: 8px;
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
        .good {
            color: #00ff99;
        }
        .warn {
            color: #ffd54f;
        }
        .offer {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #2a2a2a;
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
    <h1>🏀 NBA Props Debug</h1>

    <div class="card">
        <div class="title">Summary</div>
        <div class="line">Events found: {{ summary.events_count }}</div>
        <div class="line">Events with prop bookmakers: {{ summary.events_with_props }}</div>
        <div class="line">Raw offers found: {{ summary.offers_count }}</div>
    </div>

    {% if events %}
        {% for event in events %}
            <div class="card">
                <div class="subtle">{{ event.match }}</div>
                <div class="title">Bookmakers with props: {{ event.bookmaker_count }}</div>

                {% if event.offers %}
                    {% for offer in event.offers %}
                        <div class="offer">
                            <div class="line"><span class="good">{{ offer.player }}</span></div>
                            <div class="line">{{ offer.market_label }} — {{ offer.side }} {{ offer.point }}</div>
                            <div class="line">{{ offer.bookmaker }}: {{ offer.price }}</div>
                            {% if offer.link %}
                                <div class="line"><a href="{{ offer.link }}" target="_blank">Open</a></div>
                            {% endif %}
                        </div>
                    {% endfor %}
                {% else %}
                    <div class="line warn">No raw offers found for this event.</div>
                {% endif %}
            </div>
        {% endfor %}
    {% else %}
        <div class="empty">No NBA events found.</div>
    {% endif %}
</body>
</html>
"""

def best_link(outcome_link, market_link, bookmaker_link):
    return outcome_link or market_link or bookmaker_link or None

def get_events():
    # Broad discovery: do NOT filter by AU bookmakers here
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"
    params = {
        "apiKey": API_KEY,
        "regions": "us",       # broad discovery so we actually get NBA events
        "markets": "h2h",
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

@app.route("/")
def home():
    events = get_events()
    debug_events = []
    total_offers = 0
    events_with_props = 0

    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue

        props_data = get_event_props(event_id)
        bookmakers = props_data.get("bookmakers", [])
        match_name = f"{event.get('away_team', 'Away')} vs {event.get('home_team', 'Home')}"

        offers = []

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

                    offers.append({
                        "player": player,
                        "market_label": MARKET_LABELS.get(market_key, market_key),
                        "side": side,
                        "point": point,
                        "price": price,
                        "bookmaker": bookmaker_title,
                        "link": best_link(outcome_link, market_link, bookmaker_link),
                    })

        if bookmakers:
            events_with_props += 1

        total_offers += len(offers)

        debug_events.append({
            "match": match_name,
            "bookmaker_count": len(bookmakers),
            "offers": offers[:50],
        })

    summary = {
        "events_count": len(events),
        "events_with_props": events_with_props,
        "offers_count": total_offers,
    }

    return render_template_string(HTML, summary=summary, events=debug_events)

if __name__ == "__main__":
    app.run()
