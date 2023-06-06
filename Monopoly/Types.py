import Monopoly
from enum import IntEnum
from random import choices
import re

class Components(IntEnum):
    TEXT = 0,
    DATA = 1,
    LIST = 2,
    TYPE = 3,
    OWNER = 5,
    PRICE = 6,
    POSITION = 7,
    BALANCE = 8,
    DEVELOPMENT = 9,
    SCRIPT = 10


@Monopoly.setassociation(
    (Components.TEXT, "name"),
    (Components.DATA, "data")
)
class LootTable:
    @staticmethod
    def choice(game, table):
        data = game[LootTable.data][table]
        card = choices(population=data["cards"], weights=data["weights"], k=1)[0]

        return game.cards[card]

@Monopoly.setassociation(
    (Components.TEXT, "text"),
    (Components.LIST, "script")
)
class Card:
    @staticmethod
    def execute(game, player, card):
        script = game[Card.script][card]

        context = {"player": player}
        game.execute(script, context=context)

        tokens = game.monoscript.tokenize(game[Card.text][card])
        game.monoscript.bindTokens(tokens, context)
        text = " ".join(tokens)

        return text

@Monopoly.setassociation(
    (Components.TEXT, "name"),
    (Components.TYPE, "method"),
    (Components.DATA, "base"),
    (Components.LIST, "modifier")
)
class Industry:
    pass

@Monopoly.setassociation(
    (Components.TEXT, "label")
)
class Group:
    pass

@Monopoly.setassociation(
    (Components.TYPE, "type"),
    (Components.TEXT, "label")
)
class Tile:
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

            case _:
                type = Tile
        return type

    @staticmethod
    def onpass(game, player, tile):
        return

    @staticmethod
    def onland(game, player, tile):
        return

@Monopoly.setassociation(
    (Components.OWNER, "owner"),
    (Components.PRICE, "price")
)
class BuyableTile(Tile):
    @staticmethod
    def buy(game, player, tile):
        # Check if not already owned
        from .Event import PropertyPurchaseEvent

        owner = game[BuyableTile.owner][tile]

        if owner:
            return False

        price = game[BuyableTile.price][tile]["plot"]
        balance = game[Player.balance][player]

        # Check if player's balance is greater than or equal to the price of the plot
        if balance >= price:
            game[Player.balance][player] -= price
            game[BuyableTile.owner][tile] = player

            game.events += PropertyPurchaseEvent(player, tile)

            return True

        return False

@Monopoly.setassociation(
    (Components.SCRIPT, "events")
)
class ActionTile(Tile):
    @staticmethod
    def onpass(game, player, tile):
        events = game[Components.DATA, tile]

        if "pass" not in events:
            return

        for event in events["pass"]:
            pass

    @staticmethod
    def onland(game, player, tile):
        events = game[Components.DATA, tile]

        if "land" not in events:
            return

        for event in events["land"]:
            pass

@Monopoly.setassociation(
    (Components.DATA, "table")
)
class ChestTile(Tile):
    @staticmethod
    def onland(game, player, tile):
        table = game[Components.DATA, tile]
        card = LootTable.draw(game, table)

        print(game.construct(card))

@Monopoly.setassociation(
    (Components.DATA, "industry")
)
class CompanyTile(BuyableTile):
    @staticmethod
    def onland(game, player, tile):
        pass

@Monopoly.setassociation(
    (Components.DATA, "group"),
    (Components.LIST, "rent"),
    (Components.DEVELOPMENT, "level", 0)
)
class PropertyTile(BuyableTile):
    @staticmethod
    def upgrade(game, player, tile):
        if game[PropertyTile.owner][tile] != player:
            return False

        price = game[PropertyTile.price][tile]["house"]
        level = game[PropertyTile.level][tile]
        maxLevel = len(game[PropertyTile.rent][tile]) - 1


        if type(price) == list:
            raise NotImplementedError()

        if level >= maxLevel:
            return False

        balance = game[Player.balance][player]

        if balance >= price:
            game[Components.BALANCE, player] -= price
            game[Components.DEVELOPMENT, tile] += 1

            return True

        return False

@Monopoly.setassociation(
    (Components.TEXT, "name"),
    (Components.DATA, "data"),
    (Components.BALANCE, "balance"),
    (Components.POSITION, "position")
)
class Player:
    @staticmethod
    def move(game, player, position=0, teleport=False):
        from Monopoly import PlayerMoveEvent

        initial = game[Player.position][player]
        final = position % len(game.tiles)

        game[Player.position][player] = final

        game.events += PlayerMoveEvent(player, initial, final, teleport)

    @staticmethod
    def advance(game, player, delta=0, teleport=False):
        position = game[Player.position][player] + delta

        Player.move(game, player, position, teleport)

    @staticmethod
    def update_balance(game, player, balance=0):
        game[Player.balance][player] = balance