import os
from flask import Blueprint, redirect, request, send_from_directory, url_for
from werkzeug.utils import secure_filename
from Monopoly import Game

bp = Blueprint("api", __name__, template_folder="templates")

@bp.route("/", methods=["GET", "POST"])
def default():
    return "Missing endpoint", 400

# @bp.route("/game/board/<board_id>", methods=["GET"])
# def get_board(board_id):
#     board_id = secure_filename(board_id)

#     return send_from_directory("./boards", f"{board_id}.json")


@bp.route("/game/create/<map_name>", methods=["POST"])
def create_board(map_name):
    from app import games

    map_name = secure_filename(map_name)

    game = Game()
    game.load_from_file(f"./boards/{map_name}.json")

    game_id = os.urandom(3).hex()
    games[game_id] = game

    return redirect(url_for("game", game_id=game_id))

@bp.route("/game/<game_id>/player/join", methods=["POST"])
def player_join(game_id):
    from app import games
    from Monopoly import Player

    if game_id not in games:
        # FIXME: Add error redirect for invalid game_id
        return redirect(f"/")
    
    game = games[game_id]
    game_URL = url_for("game", game_id=game_id)

    if "name" not in request.form:
        # FIXME: Add error redirect for missing "name" property in POSTed data
        return redirect(game_URL)

    name = request.form["name"]

    for player in game.players:
        if name == game[Player.name][player]:
            # FIXME: Add error redirect for missing "name" property in POSTed data
            return redirect(game_URL)

    game.add_player(name)

    return redirect(game_URL)

@bp.route("/game/<endpoint>", methods=["POST"])
def game_post(endpoint):
    from app import games

    match endpoint:
        case "player":
            return "Success", 200

    return redirect("/")

