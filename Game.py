import json
import functools
import operator
from enum import IntEnum

class Components(IntEnum):
    TEXT = 0,
    DATA = 1,
    LIST = 2,
    TYPE = 3,
    PRICE = 4,
    ASSOCIATION = 5

class Entity:
    def __init__(self, id, mask):
        self.id = id
        self.mask = mask

class ECSObject:
    @staticmethod
    def get_association():
        return ()

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

class LootTable(ECSObject):
    @staticmethod
    def get_association():
        return (
            (Components.TEXT, "name"),
            (Components.DATA, "offset"),
        )

class Card(ECSObject):
    @staticmethod
    def get_association():
        return (
            (Components.TEXT, "text"),
            (Components.LIST, "action"),
            (Components.DATA, "weight")
        )

class Industry(ECSObject):
    @staticmethod
    def get_association():
        return (
            (Components.TEXT, "name"),
            (Components.TYPE, "method"),
            (Components.DATA, "base"),
            (Components.LIST, "modifier")
        )

class Group(ECSObject):
    @staticmethod
    def get_association():
        return (
            (Components.TEXT, "label"),
        )

class Tile(ECSObject):
    @staticmethod
    def get_association():
        return (
            (Components.TYPE, "type"),
            (Components.TEXT, "label")
        )
    
    @staticmethod
    def type_from_string(string):
        match string:
            case "Action":
                type = ActionTile

            case "Chest":
                type = ChestTile

            case "Company":
                type = CompanyTile

            case "Property":
                type = PropertyTile

            case "Tax":
                type = TaxTile

            case _:
                type = Tile
        return type

class ActionTile(Tile):
    @staticmethod
    def get_association():
        return (
            *super(ActionTile, ActionTile).get_association(),
            (Components.DATA, "events")
        )

class ChestTile(Tile):
    @staticmethod
    def get_association():
        return (
            *super(ChestTile, ChestTile).get_association(),
            (Components.DATA, "table")
        )

class CompanyTile(Tile):
    @staticmethod
    def get_association():
        return (
            *super(CompanyTile, CompanyTile).get_association(),
            (Components.DATA, "industry")
        )

class PropertyTile(Tile):
    @staticmethod
    def get_association():
        return (
            *super(PropertyTile, PropertyTile).get_association(),
            (Components.DATA, "group"),
            (Components.LIST, "rent"),
            (Components.PRICE, "price")
        )

class TaxTile(Tile):
    @staticmethod
    def get_association():
        return (
            *super(TaxTile, TaxTile).get_association(),
            (Components.DATA, "method"),
            (Components.PRICE, "price")
        )

class ECS:
    def __init__(self):
        self.entities = []
        self.components = {}

    def create_entity(self, data=None, type=None):
        eid = len(self)
        self.entities.append(Entity(eid, 0))

        if data and type:
            self.associate(eid, data, type)

        return eid

    def associate(self, eid, object, type):
        for tid, field in type.get_association():
            self[tid, eid] = object[field]

        self[Components.ASSOCIATION, eid] = type

    def construct(self, eid):
        clazz = self[Components.ASSOCIATION, eid]

        if not clazz:
            raise TypeError(f"Failed to resolve Python type association for entity {eid}.")

        obj = clazz()

        for tid, field in clazz.get_association():
            setattr(obj, field, self[tid, eid])

        return obj

    def assign(self, tid, eid):
        type_mask = 1 << tid
        mask = self.entities[eid].mask

        # Check if entity has already been assigned type
        if type_mask & mask:
            return

        if tid not in self.components:
            # Create component pool if not exists
            self.components[tid] = len(self) * [None]
        elif len(self.components[tid]) < len(self):
            # Extend component poop if necessary
            self.components[tid] += (len(self) - len(self.components[tid])) * [None]

        # Set type bit
        self.entities[eid].mask |= type_mask

    def __getitem__(self, idx):
        if isinstance(idx, int):
            if idx >= len(self):
                return None

            return self.components[idx]

        tid, eid = idx

        if tid not in self.components:
            return None

        if eid >= len(self) or eid < 0:
            return None

        if len(self.components[tid]) < eid:
            return None

        return self.components[tid][eid]

    def __setitem__(self, idx, value):
        if not isinstance(idx, tuple) and len(idx) == 2:
            raise ValueError("Expected type/entity id pair.")

        tid, eid = idx
        if eid >= len(self) or eid < 0:
            raise IndexError("Entity ID out of bounds.")

        self.assign(tid, eid)
        self.components[tid][eid] = value

    def __len__(self):
        return len(self.entities)


class Game:
    def __init__(self):
        self.ecs = ECS()

    def load_from_file(self, file="./board.json"):
        with open(file, "rb") as data:
            board = json.load(data)

        self.load(board)

    def load(self, board):
        ecs = self.ecs

        self.lootTables = []
        self.cards = []
        for data in board["lootTables"]:
            table = ecs.create_entity()
            self.lootTables.append(table)

            cards = data["cards"]
            lootTable = {
                "name": data["name"],
                "offset": {
                    "begin": len(self.cards),
                    "length": len(cards)
                }
            }

            self.ecs.associate(table, lootTable, LootTable)

            for data in cards:
                card = ecs.create_entity()
                self.cards.append(card)

                self.ecs.associate(card, data, Card)

        properties = [
            ("industries", lambda _ : Industry),
            ("groups", lambda _ : Group),
            ("tiles", lambda data : Tile.type_from_string(data["type"]))
        ]

        for prop in properties:
            name, get_type = prop
            setattr(self, name, [ecs.create_entity(data, get_type(data)) for data in board[name]])
