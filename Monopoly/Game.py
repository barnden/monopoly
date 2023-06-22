import json
import operator
from random import choice, randint, shuffle
from functools import reduce
from uuid import uuid4

from .Event import *
from .Types import Player
from .Monoscript import Monoscript

@bindlisteners
class Game():
    def __init__(self):
        self.events = EventDispatcher()
        self.monoscript = Monoscript(self)

        self.options = {
            "randomize": True,
            "mortage": True,
            "starting": 2000,
            "evenBuild": True,
            "collectInJail": False,
            "turnsInJail": 3
        }

        self.players = {}
        self.jailed = {}
        self.parked = {}
        self.order = []
        self.entities = {}
        self.trades = {}
        self.turn = 0
        self.active = None

    def create_trade(self, seller: Player, buyer: Player):
        pass

    def jail(self, player):
        from .Monoscript import Selector

        jail = self.select(Selector.parse("Tile[label=Jail]"))[0]
        player.position = self.tiles.index(jail)

        self.jailed[player] = self.options["turnsInJail"]

    def park(self, player, turns=1):
        self.parked[player] = turns

    def advance(self, player, n=0):
        initial = player.position

        player.position = (player.position + n) % len(self.tiles)
        self.events += PlayerMoveEvent(player, initial, player.position)

    def active_player(self):
        return self.players[self.order[self.active]]

    def roll(self, n=2, s=6):
        # Roll n s-sided dice
        dice = [randint(1, s) for _ in range(n)]

        player = self.active_player()
        self.advance(player, sum(dice))

        # if all(x == dice[0] for x in dice):
        #     self.roll(n, s)

        return dice

    def start(self):
        if self.options["randomize"]:
            shuffle(self.order)

        for player in self.players.values():
            self.parked[player] = 0
            self.jailed[player] = 0

        self.active = 0
        self.events += TurnStart(self.active_player())

    def next_turn(self):
        self.events += TurnEnd(self.active_player())

        self.active = (self.active + 1) % len(self.order)
        player = self.active_player()

        if player in self.parked and self.parked[player] > 0:
            self.active = (self.active + 1) % len(self.order)
            self.parked[player] -= 1

            return

        self.events += TurnStart(player)

    @listen(TurnStart)
    def on_turn_start(self, event: TurnStart):
        self.turn += 1

    @listen(PropertyPurchaseEvent)
    def on_purchase(self, event: PropertyPurchaseEvent):
        print(f"{event.tile!r} purchased by {event.player!r}")

    @listen(PlayerMoveEvent)
    def on_move(self, event: PlayerMoveEvent):
        if not event.teleport:
            m = len(self.tiles)
            distance = self.distance(event.initial, event.final)

            # Trigger on pass
            for i in range(1, distance):
                tile = self.tiles[(event.initial + i) % m]
                tile.on_pass(self, event.player)

        tile = self.tiles[event.final]

        print(f"player {event.player!r} landed on {tile!r}")
        tile.on_land(self, event.player)

    def execute(self, *args, **kwargs):
        self.monoscript.execute(*args, **kwargs)

    def load_from_file(self, file: str="./board.json"):
        # Load a board object from JSON
        with open(file, "rb") as data:
            board = json.load(data)

        self.load(board)

    def create_object(self, cls, *args, **kwargs):
        instance = cls(*args, **kwargs)
        eid = str(uuid4())
        setattr(instance, "eid", eid)

        self.entities[eid] = instance

        return instance

    def load(self, board: dict):
        from .Types import LootTable
        # Initialize a game with a board object
        from .Types import Tile, LootTable, Card, Industry, Group
        self.board = board

        def process_tile(data):
            if data["type"] == "Chest":
                table: LootTable
                for table in self.lootTables:
                    if table.name == data["table"]:
                        data["table"] = table

            return data, Tile.type_from_string(data["type"])

        properties = [
            ("lootTables", lambda data: (data, LootTable)),
            ("cards", lambda data: (data, Card)),
            ("industries", lambda data: (data, Industry)),
            ("groups", lambda data: (data, Group)),
            ("tiles", process_tile)
        ]

        def create_object(data, cls):
            return self.create_object(cls, **{attr: data[attr] for attr in cls.association if attr in data})

        for prop in properties:
            field, processor = prop

            setattr(self, field, [create_object(*processor(rawData)) for rawData in board[field]])

        properties = board["properties"]

        count = len(self.tiles)
        dim = properties["dimension"]

        if count != 4 * (dim - 1):
            raise ValueError(f"Incorrect number of tiles {count} for board dimension of {dim}.")

    def add_player(self, name: str, balance=0, position=0, data={}):
        from .Types import Player

        if "jailed" not in data:
            data["jailed"] = False

        if "character" not in data:
            data["character"] = {
                "color": "white"
            }

        player = self.create_object(Player, name, data, balance, position)
        self.players[player.eid] = player
        self.order.append(player.eid)

        return player

    @staticmethod
    def access(path: str | list, obj: dict, default=None):
        if isinstance(path, str):
            path = path.split(".")

        if not isinstance(path, list) or len(path) == 0:
            return default

        path = map(lambda x: x if not x.isnumeric() else int(x), path)
        return reduce(operator.getitem, path, obj)

    def select(self, selectors: dict):
        def predicate(eid):
            entity = self.entities[eid]
            className = entity.__class__.__name__

            if className not in selectors:
                return False

            if not (selector := selectors[className]):
                return True

            for field, relation in selector.items():
                field, *path = field.split('.')
                lhs = getattr(entity, field, None)

                if lhs is None:
                    return False

                if path:
                    lhs = Game.access(path, lhs, lhs)

                op, rhs = relation

                try:
                    lhs = int(lhs)
                    rhs = int(rhs)

                    match op:
                        case "=" | "==":
                            return lhs == rhs
                        case ">=":
                            return lhs >= rhs
                        case "<=":
                            return lhs <= rhs
                        case ">":
                            return lhs > rhs
                        case "<":
                            return lhs < rhs
                        case "!=":
                            return lhs != rhs

                    return False
                except ValueError:
                    match op:
                        case "=" | "==":
                            return lhs == rhs
                        case "!=":
                            return lhs != rhs
                        case _:
                            return False

        entities = [self.entities[eid] for eid in self.entities if predicate(eid)]

        if len(entities):
            return entities

        return None

    def nearest(self, selectors: dict, position: int, forward=True):
        # Get the nearest tile to a given position matching a selector
        # Returns a tuple of (position, eid) where position is the index
        #   of the entity inside the tiles list, and eid is the entity id.
        tiles = self.select(selectors)

        if not tiles:
            return None

        metric = self.distance if forward else self.distance2
        positions = [self.tiles.index(tile) for tile in tiles]
        distances = [metric(position, pos) for pos in positions]

        nearest = positions[distances.index(min(distances))]

        return (nearest, self.tiles[nearest])


    def random(self, selectors: dict):
        # Find all tiles matching the provided selectors, then choose one at random
        entities = self.select(selectors)

        if isinstance(entities, list):
            return choice(entities)

        return None

    def distance(self, initial: int, final: int):
        # Returns the distance in the forward direction
        m = len(self.tiles)

        return (final - initial) % m

    def distance2(self, initial: int, final: int):
        # Returns the shortest distance in either the reverse or forward
        m = len(self.tiles)
        diff = (initial - final) % m

        return min(diff, m - diff)
