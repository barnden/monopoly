import json
import re
from random import choice
from functools import reduce
import operator
import random

from .ECS import ECS
from .Event import PlayerMoveEvent, PropertyPurchaseEvent, EventDispatcher, bindlisteners, listen
from .Monoscript import Monoscript

@bindlisteners
class Game(object):
    def __init__(self):
        self.ecs = ECS()
        self.events = EventDispatcher()
        self.monoscript = Monoscript(self)
        self.players = []
        self.stats = {}
        self.activePlayer = None

    def shuffle(self):
        random.shuffle(self.players)

    def roll(self, n=2, s=6):
        return (random.randint(1, s) for _ in range(n))

    @listen(PropertyPurchaseEvent)
    def on_purchase(self, event: PropertyPurchaseEvent):
        from .Types import BuyableTile, Player

        tile = self[BuyableTile.label][event.tile]
        player = self[Player.name][event.player]
        print(f"{tile} purchased by {player}")

    @listen(PlayerMoveEvent)
    def on_player_move(self, event: PlayerMoveEvent):
        from .Types import ActionTile, Tile, Player

        if not event.teleport:
            m = len(self.tiles)
            distance = self.distance(event.initial, event.final)

            # Trigger "pass" event
            for i in range(1, distance):
                tile = self.tiles[(event.initial + i) % m]

                if ActionTile.mask == self.ecs.entities[tile].mask:
                    script = self[ActionTile.events][tile]

                    if "pass" in script:
                        self.execute(script["pass"], context={"player": event.player})

        tile = self.tiles[event.final]
        if ActionTile.mask == self.ecs.entities[tile].mask:
            script = self[ActionTile.events][tile]

            if "land" in script:
                self.execute(script["land"], context={"player": event.player})

        print(f"player {self[Player.name][event.player]} landed on {self[Tile.label][tile]}")

    def execute(self, *args, **kwargs):
        self.monoscript.execute(*args, **kwargs)

    def load_from_file(self, file: str="./board.json"):
        # Load a board object from JSON
        with open(file, "rb") as data:
            board = json.load(data)

        self.load(board)

    def load(self, board):
        # Initialize a game with a board object
        from Monopoly import Components, Tile, LootTable, Card, Industry, Group

        def process_tile(data):
            if data["type"] == "Chest":
                for table in self.lootTables:
                    name = self[Components.TEXT][table]

                    if name == data["table"]:
                        data["table"] = table
                        break

            return data, Tile.type_from_string(data["type"])

        properties = [
            ("lootTables", lambda data: (data, LootTable)),
            ("cards", lambda data: (data, Card)),
            ("industries", lambda data: (data, Industry)),
            ("groups", lambda data: (data, Group)),
            ("tiles", process_tile)
        ]

        for prop in properties:
            name, process = prop
            setattr(self, name, [self.ecs.create_entity(*process(data)) for data in board[name]])

        properties = board["properties"]

        count = len(self.tiles)
        dim = properties["dimension"]

        if count != 4 * (dim - 1):
            raise ValueError(f"Incorrect number of tiles {count} for board dimension of {dim}.")

    def add_player(self, name, balance=0, position=0, data={}):
        from Monopoly import Player

        if "jailed" not in data:
            data["jailed"] = False

        if "character" not in data:
            data["character"] = {
                "color": "white"
            }

        player_data = {
            "name": name,
            "data": data,
            "position": position,
            "balance": balance
        }

        eid = self.ecs.create_entity(player_data, Player)
        self.players.append(eid)

        return eid

    @staticmethod
    def access(path: str | list, obj, default=None):
        if isinstance(path, str):
            path = path.split(".")

        if not isinstance(path, list) or len(path) == 0:
            return default

        path = map(lambda x: x if not x.isnumeric() else int(x), path)
        return reduce(operator.getitem, path, obj)

    def select(self, selectors):
        if not self.ecs.classes.keys() & selectors.keys():
            return None

        def predicate(obj):
            className = self.ecs.masks[self.ecs.entities[obj].mask].__name__

            if className not in selectors:
                return False

            cls = self.ecs.classes[className]
            selector = selectors[className]

            if not selector:
                return True

            for field, relation in selector.items():
                tid, *path = field.split('.')
                tid = getattr(cls, tid, None)

                if tid is None:
                    return False

                lhs = self[tid][obj]
                lhs = Game.access(path, lhs, lhs)

                op, rhs = relation

                match op:
                    case "=":
                        return lhs == rhs
                    case ">=":
                        return int(lhs) >= int(rhs)
                    case "<=":
                        return int(lhs) <= int(rhs)
                    case ">":
                        return int(lhs) > int(rhs)
                    case "<":
                        return int(lhs) < int(rhs)
                    case "!=":
                        return lhs != rhs

        entities = [entity.id for entity in self.ecs.entities if predicate(entity.id)]

        if len(entities):
            return entities

        return None
    
    def nearest(self, selectors, position, forward=True):
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


    def random(self, selectors):
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

    def construct(self, eid: int):
        from Monopoly import Entity

        # Construct an object for an entity from its associated components
        # Used for debugging purposes

        if eid is None:
            return None

        mask = self.ecs.entities[eid].mask
        clazz = self.ecs.masks[mask]

        if clazz is None:
            raise TypeError(f"Failed to resolve Python type association for entity {eid}.")

        obj = Entity(eid, self.ecs.entities[eid].mask)

        for tid, *data in clazz.get_association():
            field = data[0]
            setattr(obj, field, self[tid, eid])

        return obj

    def __getitem__(self, idx):
        return self.ecs[idx]

    def __setitem__(self, idx, value):
        self.ecs[idx] = value