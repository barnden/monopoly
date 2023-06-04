import json

def setassociation(*association):
    def wrapper(cls):
        current = getattr(cls, "association", None)
        _association = association

        if current:
            _association = current + association

        setattr(cls, "association", _association)
        setattr(cls, "get_association", staticmethod(lambda: _association))

        mask = 0
        for (component, prop, *_) in _association:
            setattr(cls, prop, component)
            mask |= 1 << component

        setattr(cls, "mask", mask)
        setattr(cls, "__str__", lambda self: self.game.construct(self.eid).toJSON())

        return cls

    return wrapper

class Entity:
    def __init__(self, id, mask):
        self.id = id
        self.mask = mask

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
    
    def __str__(self):
        return self.toJSON()


class ECS:
    def __init__(self):
        self.entities = []
        self.components = {}
        self.classes = {}
        self.masks = {}

    def create_entity(self, data=None, type=None):
        eid = len(self)
        self.entities.append(Entity(eid, 0))

        if data and type:
            self.associate(eid, data, type)

        return eid

    def associate(self, eid, object, type):
        from Monopoly import Components

        if type.__name__ not in self.classes:
            self.classes[type.__name__] = type

        if type.mask not in self.masks:
            self.masks[type.mask] = type
        elif self.masks[type.mask] != type:
            print(f"type association error {type.__name__} {self.masks[type.mask].__name__}")

        for tid, *data in type.get_association():
            if data[0] in object:
                self[tid, eid] = object[data[0]]
            elif len(data) > 1:
                self[tid, eid] = data[1]
            else:
                self.assign(tid, eid)

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