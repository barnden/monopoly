import re
from typing import Any

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
    keywords = ["balance", "move", "trigger", "jail", "random", "log", "transaction"]

    def __init__(self, game):
        self.game = game

    @staticmethod
    def tokenize(string):
        return re.findall("([^\s]+[\[|\(].*?[\)|\]]|\$?[^\s]+|=)", string)

    def balance(self, args, context={}):
        from Monopoly import Player

        mode, eid, amount = args[1:]

        if eid not in self.game.players:
            raise ValueError(f"[Monoscript]: balance invalid player entity id {eid!r}")

        eid = context["player"]
        current = self.game[Player.balance][eid]

        if amount.endswith("%"):
            percent = float(amount[:-1]) / 100.0
            delta = current * percent
        else:
            delta = amount

        delta = int(delta)
        if mode == "sub":
            delta *= -1
        elif mode != "add":
            raise ValueError(f"[Monoscript]: move unknown mode {mode!r}")

        Player.update_balance(self.game, eid, current + delta)

    def move(self, args, context={}):
        from Monopoly import Player, Selector

        eid, mode, *rest = args[1:]

        if eid not in self.game.players:
            raise ValueError(f"[Monoscript]: move invalid player entity id {eid!r}")

        instant = False
        if mode == "instant":
            instant = True
            mode = rest.pop(0)

        match mode:
            case "to":
                if len(rest) == 0:
                    raise ValueError(f"[Monoscript]: (too few args) expected tile entity id")

                tile = rest[0]
                if not isinstance(tile, int):
                    raise TypeError(f"[Monoscript]: (invalid type) invalid tile entity {tile!r}")
                elif tile not in self.game.tiles:
                    raise ValueError(f"[Monoscript]: (invalid tile) entity {tile!r} does not correspond to tile")

                Player.move(self.game, eid, self.game.tiles.index(tile), instant)

            case "near":
                if len(rest) == 0:
                    raise ValueError(f"[Monoscript]: (too few args) expected tile selector")

                selector = Selector.parse(rest[0])
                tiles = self.game.select(selector)

                if len(tiles) == 0:
                    return

                current = self.game[Player.position][eid]
                locations = [self.game.tiles.index(tile) for tile in tiles]
                distances = [self.game.distance2(current, position) for position in locations]
                target = locations[distances.index(min(distances))]

                Player.move(self.game, eid, target, instant)

            case "next":
                if len(rest) == 0:
                    raise ValueError(f"[Monoscript]: (too few args) expected tile selector")

                selector = Selector.parse(rest[0])

            case _:
                raise ValueError(f"[Monoscript]: move unknown mode {mode!r}")

    def trigger(self, args, context={}):
        pass

    def jail(self, args, context={}):
        from Monopoly import Player

        eid = int(args[1])
        if eid not in self.game.players:
            raise ValueError(f"[Monoscript]: (invalid eid) {eid!r} does not represent player")

        self.game[Player.data][eid]["jailed"] = True

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
        from Monopoly import Game

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

                if not accessor:
                    continue

                field, *path = accessor.split(".")
                mask = self.game.ecs.entities[value].mask
                cls = self.game.ecs.masks[mask]
                tid = getattr(cls, field, None)

                data = self.game[tid][value]
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

        handler = self.assign
        if tokens[0] in Monoscript.keywords:
            handler = getattr(self, tokens[0])

        handler(args=tokens, context=context)

        return context