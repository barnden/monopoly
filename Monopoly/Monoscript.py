import re
from collections import ChainMap

class Selector:
    @staticmethod
    def parse(string):
        """
        Game objects can be selected by the syntax:
            Type[attr1=value1, ..., attrN=valueN]
        Objects with the matching type and attribute/value pairs are selected

        Examples:
            "Property" - Matches any property tiles
                         returns:
                         {
                            "Property: None
                         }

            "Property[group=France]" - matches any property tiles belonging to France
                returns:
                {
                    "Property: {
                        "group": "France"
                    }
                }

            "Player[balance>=1500]" - matches any player with at least 1500 credits
        """

        try:
            type = re.match("^.*?(?=\[|$)", string)[0]
        except TypeError:
            raise ValueError("[Selector]: invalid selector type")
        
        try:
            attrs = {}
            queries = re.findall("\[([^!<>=\s]+)\s?([!<>=]+)\s?(.*)\]", string)

            for query in queries:
                attr, *relation = query

                attrs[attr] = relation

        except TypeError:
            attrs = None

        return { type: attrs }

class Monoscript:
    keywords = ["balance", "move", "jail", "random", "log", "transaction", "park"]

    def __init__(self, game):
        from .Game import Game

        self.game: Game = game

    @staticmethod
    def tokenize(string):
        return re.findall("([^\s]+[\[|\(].*?[\)|\]]|\$?[^\s]+|=)", string)

    def balance(self, args, context={}):
        from .Types import Player

        mode, eid, amount = args[1:]

        player: Player
        if isinstance(eid, Player):
            player = eid
        elif eid not in self.game.players:
            raise ValueError(f"[Monoscript]: balance received invalid player eid {eid}")
        else:
            player = self.game.players[eid]

        current = player.balance

        if amount.endswith("%"):
            percent = float(amount[:-1]) / 100.0
            delta = current * percent
        else:
            delta = float(amount)

        if mode == "sub":
            delta *= -1
        elif mode != "add":
            raise ValueError(f"[Monoscript]: move unknown mode {mode!r}")

        player.balance += int(delta)

    def move(self, args, context={}):
        from .Types import Player
        from .Event import PlayerMoveEvent

        eid, mode, *rest = args[1:]

        player: Player
        if isinstance(eid, Player):
            player = eid
        elif eid not in self.game.players:
            raise ValueError(f"[Monoscript]: move invalid player entity id {eid!r}")
        else:
            player = self.game.players[eid]

        instant = False
        if mode == "instant":
            instant = True
            mode = rest.pop(0)

        match mode:
            case "to":
                from .Types import Tile

                if not rest:
                    raise ValueError(f"[Monoscript]: (too few args) expected tile entity id")

                tile = rest[0]

                if isinstance(tile, str):
                    selector = Selector.parse(tile)
                    tile = self.game.select(selector)[0]

                if not isinstance(tile, Tile):
                    raise TypeError(f"[Monoscript]: (invalid type) invalid tile entity {tile!r}")

                initial = player.position
                player.position = self.game.tiles.index(tile)
                self.game.events += PlayerMoveEvent(player, initial, player.position, instant)

            case "near" | "next":
                # Near goes to nearest tile forward or backward, next goes to the nearest forward

                if not rest:
                    raise ValueError(f"[Monoscript]: (too few args) expected tile selector")

                selectors = ChainMap(*[Selector.parse(token) for token in rest])

                forward = (mode == "next")
                tile = self.game.nearest(selectors, player.position, forward)

                if tile:
                    position, _ = tile
                    initial = player.position
                    player.position = position
                    self.game.events += PlayerMoveEvent(player, initial, player.position, instant)

            case _:
                raise ValueError(f"[Monoscript]: move unknown mode {mode!r}")
            
    def park(self, args, context={}):
        from .Types import Player

        eid = args[1]
        player: Player
        if isinstance(eid, Player):
            player = eid
        elif eid not in self.game.players:
            raise ValueError(f"[Monoscript]: move invalid player entity id {eid!r}")
        else:
            player = self.game.players[eid]

        self.game.park(player)

    def jail(self, args, context={}):
        from .Types import Player

        eid = args[1]
        player: Player
        if isinstance(eid, Player):
            player = eid
        elif eid not in self.game.players:
            raise ValueError(f"[Monoscript]: move invalid player entity id {eid!r}")
        else:
            player = self.game.players[eid]

        self.game.jail(player)

    def random(self, args, context={}):
        selectors = {}

        for arg in args[1:]:
            selectors = selectors | Selector.parse(arg)

        return self.game.random(selectors)

    def assign(self, args, context={}):
        varName = args[0]
        rest = args[2:]

        value = " ".join(map(str, rest))
        if rest[0] in Monoscript.keywords:
            value = getattr(self, rest[0])(rest)

        context[varName] = value

        return True

    def bindTokens(self, tokens, context):
        from .Game import Game

        for i, token in enumerate(tokens):
            if not token.startswith('$'):
                continue

            varName = token[1:]
            accessor = None

            if "[" in varName:
                varName, accessor = re.findall("(\w+)\[(.+?)\]", varName)[0]

            if varName in context:
                value = context[varName]
                tokens[i] = value

                if not value or not accessor:
                    continue

                field, *path = accessor.split(".")
                if type(value) == str:
                    value = self.game.entities[value]
                data = getattr(value, field, None)
                data = str(Game.access(path, data, data))

                tokens[i] = data

    def log(self, args, context={}):
        print(" ".join(map(str, args[1:])))

    def execute(self, script, context={}):
        if isinstance(script, list):
            for line in script:
                self.execute(line, context)

            return

        tokens = Monoscript.tokenize(script)
        self.bindTokens(tokens, context)

        handler = getattr(self, tokens[0], self.assign)
        handler(args=tokens, context=context)

        return context