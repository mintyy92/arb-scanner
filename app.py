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
    <title>AU Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="20">
    <style>
        body { font-family: Arial; background: #111; color: #fff; padding: 16px; }
        .card { background:#1e1e1e; padding:15px; margin:10px 0; border-radius:10px; }
        .profit { color:#00ff99; font-weight:bold; }
        .near { color:#ffd54f; font-weight:bold; }
        .value { color:#7cc4ff; font-weight:bold; }
        .subtle { color:#aaa; font-size:12px; }
    </style>
</head>
<body>
    <h1>🇦🇺 AU Markets Scanner</h1>

    {% if rows %}
        {% for row in rows %}
            <div class="card">
                <div class="subtle">{{ row.sport }} — {{ row.match }}</div>
                <h3>{{ row.market }}</h3>

                <p><b>Best odds:</b> {{ row.best_odds }} ({{ row.book }})</p>
                <p>{{ row.other }}</p>

                {% if row.status == "ARB" %}
                    <p class="profit">ARB: {{ row.profit }}%</p>
                {% elif row.status == "NEAR" %}
                    <p class="near">Near Arb: {{ row.profit }}%</p>
                {% else %}
                    <p class="value">Edge: {{ row.profit }}%</p>
                {% endif %}
            </div>
        {% endfor %}
    {% else %}
        <p>No AU market data found right now.</p>
    {% endif %}
</body>
</html>
"""

def get_odds(sport):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": ",".join(MARKETS),
        "oddsFormat": "decimal",
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        return data if isinstance(data, list) else []
    except:
        return []

def calc_profit(o1, o2):
    total = (1/o1) + (1/o2)
    return round((1-total)*100, 2), total

def process_sport(sport, label):
    data = get_odds(sport)

    local = []

    for event in data:
        match = f"{event.get('home_team')} vs {event.get('away_team')}"

        markets = {}

        for book in event.get("bookmakers", []):
            book_name = book.get("title")

            for m in book.get("markets", []):
                key = m.get("key")

                if key not in MARKETS:
                    continue

                for o in m.get("outcomes", []):
                    name = o.get("name")
                    price = o.get("price")
                    point = o.get("point")

                    if not name or not price:
                        continue

                    mkey = (key, name, point)

                    if mkey not in markets:
                        markets[mkey] = []

                    markets[mkey].append((price, book_name))

        # BEST PRICE
        for k, offers in markets.items():
            offers.sort(reverse=True)
            best = offers[0]

            prices = [o[0] for o in offers]
            avg = sum(prices)/len(prices)
            edge = round(((best[0]/avg)-1)*100, 2)

            others = ", ".join([f"{b} {p}" for p,b in offers[1:]])

            local.append({
                "sport": label,
                "match": match,
                "market": f"{k[0]} - {k[1]} {k[2] if k[2] else ''}",
                "best_odds": best[0],
                "book": best[1],
                "other": others,
                "profit": edge,
                "status": "BEST"
            })

        # ARB (simple h2h)
        h2h = [k for k in markets if k[0]=="h2h"]

        if len(h2h) == 2:
            o1 = sorted(markets[h2h[0]], reverse=True)[0]
            o2 = sorted(markets[h2h[1]], reverse=True)[0]

            profit, total = calc_profit(o1[0], o2[0])

            if total < 1:
                status = "ARB"
            elif total < 1.02:
                status = "NEAR"
            else:
                status = None

            if status:
                local.append({
                    "sport": label,
                    "match": match,
                    "market": "H2H ARB",
                    "best_odds": o1[0],
                    "book": o1[1],
                    "other": f"{o2[1]} {o2[0]}",
                    "profit": profit,
                    "status": status
                })

    with lock:
        results.extend(local)

def scan():
    global results
    results = []

    threads = []

    for s, label in SPORTS:
        t = threading.Thread(target=process_sport, args=(s, label))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

@app.route("/")
def home():
    scan()
    return render_template_string(HTML, rows=results)

if __name__ == "__main__":
    app.run()
