import os

from flask import Flask, Blueprint, render_template, redirect, session

from utils import Config

# Initialize Flask app
cfg = Config()
app = Flask(__name__, static_url_path="/static")
app.secret_key = "25ca83c71412e4cb81691ffe"#os.urandom(12).hex()

print("DEBUG SECRET:", app.secret_key)

games = {}

@app.route("/")
def landing():
    if not session.get("token"):
        session["token"] = os.urandom(12).hex()

    return render_template("landing.html")

@app.route("/game/<game_id>")
def game(game_id):
    if game_id not in games:
        return redirect("/")

    if not session.get("token"):
        session["token"] = os.urandom(12).hex()

    board = games[game_id].board
    groups = { group["label"]: group for group in board["groups"] }

    return render_template("game.html", properties=board["properties"], tiles=board["tiles"], groups=groups)

import api

app.register_blueprint(api.bp, url_prefix="/api/v1")