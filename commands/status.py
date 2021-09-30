from rich.console import Console
from enum import Enum
from typing import Union


class FileType(Enum):
    dir = 'dir'
    img = 'img'
    txt = 'txt'
    exe = 'exe'
    bin = 'bin'
    enc = 'enc'


class NodeType(Enum):
    pass


class TreeSystem:

    def __init__(self, name, ex: Union[FileType, NodeType], data=None):
        self.name = name
        self.sub = []
        self.index = {}
        self.type = ex
        self.data = data

    def add(self, obj: 'TreeSystem'):
        self.sub.append(obj)
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
            tree = tree.index.get(x)
            if tree is None or tree.type != FileType.dir:
                return tree
        return tree

    def __repr__(self):
        return f"[{self.type}:{self.name}]"

    color_map = {
        FileType.dir: "blue",
        FileType.exe: "green",
        FileType.enc: "red",
    }

    def __str__(self):
        return f"[{self.color_map.get(self.type, 'white')}]{self.name}[/]"


root = TreeSystem("root", FileType.dir)
root.add(TreeSystem("lib", FileType.dir)) \
    .add(TreeSystem("v1.sh", FileType.exe, "v1")) \
    .add(TreeSystem("v2.sh", FileType.exe, "v2")) \
    .add(TreeSystem("v3.bin", FileType.bin, "v3"))
root.add(TreeSystem("user.txt", FileType.txt, "文本"))
root.add(TreeSystem("data", FileType.dir)) \
    .add(TreeSystem("img", FileType.dir)) \
    .add(TreeSystem("xxx.png", FileType.img, "xxx)")) \
    .add(TreeSystem("01au3.jpg", FileType.img, "uuu"))


class GameStatus:

    def __init__(self, name="admin", host="127.0.0.1"):
        self.console = Console()
        self.name = name
        self.host = host
        self.path: list[str] = ["root"]
        self.env: dict[str: any] = {}
        self.file_sys = root


if __name__ == '__main__':
    pass
