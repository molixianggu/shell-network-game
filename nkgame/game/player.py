import rich


class Node:
    pass


class Player:
    max_load_value = 100
    max_memory_value = 128

    def __init__(self):
        self.lv = 0
        self.load_value = self.max_load_value
        self.memory_value = self.max_memory_value
