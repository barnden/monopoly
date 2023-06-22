from random import choices

class Entity:
    def __str__(self):
        return self.eid

    def __hash__(self):
        import uuid
        return uuid.UUID(self.eid).int

class Player(Entity):
    def __init__(self, name, data, balance=0, position=0):
        self.name = name
        self.data = data
        self.balance = balance
        self.position = position
        self.debts = []

    def __repr__(self):
        return f"Player(name={self.name}, balance={self.balance}, position={self.position})"

    def purchase(self, game, amount):
        from .Event import PlayerBalanceUpdated
        # Attempts to debit amount from player's balance
        # If possible, do it and return True
        # Otherwise, return False

        if self.balance < amount:
            return False

        self.balance -= amount
        game += PlayerBalanceUpdated(self, -amount)

        return True

    def credit(self, game, amount):
        # Credits the player's balance
        from .Event import PlayerBalanceUpdated

        self.balance += amount

        if len(self.debts):
            for idx, (creditor, debt) in enumerate(self.debts):
                # If credited amount < debt, deduct amount from debt and return
                if amount < debt:
                    self.debts[idx] = (creditor, debt - amount)

                    if creditor:
                        creditor.balance += amount

                    break

                self.debts[idx] = None

                if creditor:
                    creditor.balance += debt
                amount -= debt

            self.debts = [x for x in self.debts if x]

        game += PlayerBalanceUpdated(self, amount)

    def debit(self, game, creditor, amount):
        from .Event import PlayerBalanceUpdated

        if self.balance < amount:
            # If debit exceeds balance, player owes the difference to the creditor
            # In this case, subsequent credits to the player will go towards paying
            # the debt back to the creditor before the player's balance itself

            if self.balance > 0 and creditor:
                creditor.balance += self.balance

            self.debts.append((creditor, amount - max(0, self.balance)))
        elif creditor:
            creditor.balance += amount

        # Debits whole amount from player's account
        self.balance -= amount

        game += PlayerBalanceUpdated(self, -amount)

def associate(*association):
    def wrapper(cls):
        current = getattr(cls, "association", None)
        _association = association

        if current:
            _association = current + association

        setattr(cls, "association", _association)

        return cls

    return wrapper

@associate("name", "data")
class LootTable(Entity):
    def __init__(self, name, data):
        self.name = name
        self.data = data

    def choice(self):
        card = choices(population=self.data["cards"], weights=self.data["weights"], k=1)[0]

        return card
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name})"

@associate("text", "script")
class Card(Entity):
    def __init__(self, text, script):
        self.text = text
        self.script = script

    def execute(self, game, player):
        context = {"player": player}
        game.execute(self.script, context=context)

        tokens = game.monoscript.tokenize(self.text)
        game.monoscript.bindTokens(tokens, context)
        text = " ".join(tokens)

        return text

    def __repr__(self):
        return f"{self.__class__.__name__}(text={self.text})"

@associate("name", "method", "base", "modifier")
class Industry(Entity):
    def __init__(self, name, method, base, modifier):
        self.name = name
        self.method = method
        self.base = base
        self.modifier = modifier

@associate("label")
class Group(Entity):
    def __init__(self, label):
        self.label = label

class Meta(type):
    @staticmethod
    def get_root(T=None, bases=None):
        if not bases or bases == (Entity,):
            return T

        for t in bases:
            if (base := Meta.get_root(t, t.__bases__)) != None:
                return base

        return None

    def __new__(cls, name, bases, attrs):
        T = Meta.get_root(bases=bases)

        def wrap(fn, base, derived):
            def wrapper(*args, **kwargs):
                base(*args, **kwargs)
                derived(*args, **kwargs)

            setattr(wrapper, "__name__", f"wrapper_{fn}")
            return wrapper

        if T:
            intersect = (set(T.__dict__) & set(attrs)) - set(["__module__", "__init__"])

            for fn in intersect:
                attrs[fn] = wrap(fn, getattr(bases[0], fn, lambda: None), attrs.setdefault(fn, lambda: None))

        return type.__new__(cls, name, bases, attrs)

@associate("label", "events")
class Tile(Entity, metaclass=Meta):
    @staticmethod
    def type_from_string(string):
        match string:
            case "Chest":
                type = ChestTile

            case "Company":
                type = CompanyTile

            case "Property":
                type = PropertyTile

            case _:
                type = Tile

        return type

    def __init__(self, label, events={}):
        self.label = label
        self.events = events

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.label})"

    def on_land(self, game, player):
        if "land" not in self.events:
            return

        game.execute(self.events["land"], context={"player": player})

    def on_pass(self, game, player):
        if "pass" not in self.events:
            return

        game.execute(self.events["pass"], context={"player": player})

@associate("price")
class BuyableTile(Tile):
    def __init__(self, label, price, owner=None, events={}):
        super().__init__(label, events)

        self.price = price
        self.owner = owner

    def buy(self, game, player):
        from .Event import PropertyPurchaseEvent

        # Check if not already owned
        if self.owner:
            return False

        # Check that player has enough money
        if player.balance < self.price:
            return False

        player.balance -= self.price
        self.owner = player

        game.events += PropertyPurchaseEvent(player, self)

        return True

    def on_land(self, game, player):
        # FIXME: Prompt user to buy tile on land

        if not self.owner:
            pass

@associate("table")
class ChestTile(Tile):
    def __init__(self, label, table, events={}):
        super().__init__(label, events)

        self.table = table

    def on_land(self, game, player):
        card = self.table.choice()
        card = game.cards[card]

        text = card.execute(game, player)

        print(f"player {player!r} drew from {self.table!r}, card: {text!r}")


@associate("industry")
class CompanyTile(BuyableTile):
    def __init__(self, label, price, industry, events={}):
        super().__init__(label, price, events=events)
        self.industry = industry

    def on_land(self, game, player):
        # FIXME: Determine logic for company tiles
        pass

@associate("group", "rent")
class PropertyTile(BuyableTile):
    def __init__(self, label, price, group, rent, level=0, events={}):
        super().__init__(label, price, events=events)
        self.group = group
        self.rent = rent
        self.level = level

    def upgrade(self, game, player):
        from .Event import PropertyUpgradeEvent
        # FIXME: Check for monopoly before allowing upgrade

        if self.owner != player:
            return False

        maxLevel = len(self.rent) - 1

        if self.level >= maxLevel:
            return False

        if player.balance < self.price:
            return False

        player.balance -= self.price
        self.level += 1

        game.events += PropertyUpgradeEvent(player, self)

        return True

    def on_land(self, game, player: Player):
        if not self.owner or self.owner == player:
            return

        rent = self.rent[self.level]
        player.debit(game, self.owner, rent)
