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
