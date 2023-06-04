import json
import re
from random import choice
from functools import reduce
import operator

class Game:
    def __init__(self):
        from Monopoly import ECS, EventDispatcher, Monoscript

        self.ecs = ECS()
        self.events = EventDispatcher()
        self.players = []
        self.monoscript = Monoscript(self)

        self.register_event_handlers()

    def register_event_handlers(self):
        from Monopoly import PlayerMoveEvent

        self.events |= PlayerMoveEvent, [self.on_player_move]

    def on_player_move(self, event):
        print(event)
        pass

    def execute(self, *args, **kwargs):
        self.monoscript.execute(*args, **kwargs)

    def load_from_file(self, file="./board.json"):
        with open(file, "rb") as data:
            board = json.load(data)

        self.load(board)

    def load(self, board):
        from Monopoly import Components, Tile, LootTable, Card, Industry, Group

        ecs = self.ecs

        def process_tile(data):

            if data["type"] == "Chest":
                for table in self.lootTables:
                    name = self.ecs[Components.TEXT][table]

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
            setattr(self, name, [ecs.create_entity(*process(data)) for data in board[name]])

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
    def access(path, obj, default=None):
        if isinstance(path, str):
            path = path.split(".")

        if not isinstance(path, list) or len(path) == 0:
            return default
        path = map(lambda x: x if not x.isnumeric() else int(x), path)
        return reduce(operator.getitem, path, obj)

    def select(self, selectors):
        from Monopoly import Components

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

                if not tid:
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

    def random(self, selectors):
        entities = self.select(selectors)

        if isinstance(entities, list):
            return choice(entities)

        return None

    def distance(self, initial, final):
        # Returns the distance in the forward direction
        m = len(self.tiles)

        initial %= m
        final %= m

        return (m - (final - initial) % m) % (m + 1)

    def distance2(self, initial, final):
        # Returns the shortest distance in either the reverse or forward
        m = len(self.tiles)
        diff = (initial - final) % m

        return min(diff, m - diff)

    def construct(self, eid):
        from Monopoly import Components, Entity

        # Construct an object for an entity from its associated components
        # Used for debugging purposes

        if not eid:
            return None

        mask = self.ecs.entities[eid].mask
        clazz = self.ecs.masks[mask]

        if not clazz:
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