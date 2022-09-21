from pathlib import Path
from rich.console import Console
from enum import Enum
from typing import Union
from nkgame.pb.game_status_pb2 import (
    GameStatus as GameStatusData,
    TreeSystem as TreeSystemData,
    HostNode as HostNodeData,
    FileType
)
import nkgame


class NodeType(Enum):
    pass


class TreeSystem:

    def __init__(self, name, ex: int, data=None):
        self.name = name
        self.sub = []
        self.index: dict[str, TreeSystem] = {}
        self.type = ex
        self.data = data
        self.parent: Union[None, TreeSystem] = None

        self.readable = False
        self.writable = False
        self.executable = False
        self.visible = False

    def add(self, obj: 'TreeSystem'):
        self.sub.append(obj)
        obj.parent = self
        self.index[obj.name] = obj
        if obj.type == FileType.dir:
            return obj
        return self

    def set_data(self, obj):
        self.data = obj
        return self

    def find(self, path):
        tree: TreeSystem = self
        for x in path:
            if x == "..":
                tree = tree.parent
            else:
                tree = tree.index.get(x)
            if tree is None or tree.type != FileType.dir:
                return tree
        return tree

    def to_proto(self):
        return TreeSystemData(
            name=self.name,
            type=self.type,
            data=self.data,
            sub=[x.to_proto() for x in self.sub],
            readable=self.readable,
            writable=self.writable,
            executable=self.executable,
            visible=self.visible
        )

    @classmethod
    def load_proto(cls, pb: TreeSystemData) -> 'TreeSystem':
        tree = cls(pb.name, ex=pb.type, data=pb.data)
        tree.readable = pb.readable
        tree.writable = pb.writable
        tree.executable = pb.executable
        tree.visible = pb.visible
        [tree.add(cls.load_proto(x)) for x in pb.sub]
        return tree

    def __repr__(self):
        return f"[{self.type}:{self.name}]"

    color_map = {
        FileType.dir: ("steel_blue1", 0b10111),
        FileType.exe: ("green", 0b10110),
        FileType.enc: ("red", 0b10010),
        FileType.bin: ("yellow", 0b10110),
    }

    def __str__(self):
        # v = self.readable << 4 | self.writable << 3 | \
        #     self.executable << 2 | self.visible << 1 | \
        #     self.type == FileType.dir
        c, u = self.color_map.get(self.type, ('white', 0))
        # if (v & u) != u:
        #     return f"(x)[red]{self.name}[/]"
        return f"[{c}]{self.name}[/]"


class HostNode:

    def __init__(self, name="admin", host="localhost", file=None, game=None):
        self.console = Console()
        self.name = name
        self.host = host
        self.path: list[str] = ["root"]
        self.env: dict[str: any] = {}
        self.file_sys: TreeSystem = file
        self.game: GameStatus = game


class GameStatus:

    def __init__(self):
        self.hosts: dict[str, HostNode] = {}
        self._path = Path(nkgame.__file__).parent / '001.save'

    def save(self):
        r = GameStatusData(
            name="001",
            nones=[HostNodeData(name=x.name, host=x.host, files=x.file_sys.to_proto()) for x in self.hosts.values()]
        ).SerializeToString()
        
        with open(self._path, "wb") as f:
            f.write(r)

    def load(self):
        r = GameStatusData()
        
        with open(self._path, "rb") as f:
            r.ParseFromString(f.read())
        for node in r.nones:
            n = HostNode(node.name, node.host, file=TreeSystem.load_proto(node.files), game=self)
            self.hosts[node.host] = n


if __name__ == '__main__':
    pass
