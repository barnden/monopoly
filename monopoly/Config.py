import json
import shutil
import operator
from functools import reduce
from pathlib import Path

class Config:
    def __init__(self, cfg_file="./config.json"):
        # Open config file
        cfg_path = Path(cfg_file)
        default_config = Path("./config.default.json")

        try:
            if not cfg_path.exists():
                print("[config] Could not locate 'config.json', attempting to create from defaults.")

                if not default_config.exists():
                    print("[config] ERROR: Could not locate 'config.default.json'.")
                    exit(1)

                print("[config] Copying 'config.default.json' to 'config.json'")

                shutil.copyfile(default_config, cfg_path)

            with open(cfg_file, "rb") as f:
                self.cfg = json.load(f)
                assert self.cfg

        except Exception as e:
            print(e)
            exit(1)

    def get(self, path):
        path_list = path.split("/")
        return reduce(operator.getitem, path_list, self.cfg)

    def get_path(self, path):
        return Path(self.get(path))
