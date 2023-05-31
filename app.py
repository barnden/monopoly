import os
import json

from pathlib import Path
from functools import partial
from flask import Flask, render_template

from monopoly import Config

cfg = Config()

# Initialize Flask app
app = Flask(__name__, static_url_path="/static")
app.secret_key = os.urandom(12).hex()

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/game")
def game():
    return render_template("game.html")
