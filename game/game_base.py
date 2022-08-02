import abc
import random

import time
from asyncio import sleep

from typing import Optional

from rich.console import RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel

import msvcrt

from commands.status import HostNode


class Game(metaclass=abc.ABCMeta):
    # 游戏集合
    games: dict[str: type['Game']] = {}

    # 抽象属性

    # 游戏名
    name: str = ""
    # 帧数
    refresh_per = 10

    def __init__(self, status: HostNode):
        self.is_running = True
        self.status = status

    def __init_subclass__(cls, **kwargs):
        if cls.name is not None:
            cls.games[cls.name] = cls

    def close(self):
        self.is_running = False

    async def run(self):
        try:
            with Live(await self.next_frame(b''), refresh_per_second=self.refresh_per) as live:
                while self.is_running:
                    c = msvcrt.getch() if msvcrt.kbhit() else b''
                    st = time.time_ns()
                    live.update(await self.next_frame(c))
                    await sleep(1 / self.refresh_per - ((time.time_ns() - st) / 1e9))
        except BreakGame:
            return
        finally:
            self.close()

    @abc.abstractmethod
    async def next_frame(self, c: bytes) -> Optional[RenderableType]:
        raise NotImplementedError()


class BreakGame(Exception):
    pass


class TetrisGame(Game):
    name = "tetris"

    refresh_per: int = 8

    class State:

        def __init__(self):
            self.score: int = 0
            self.data = [0] * 20
            self.cur_data = [0] * 4
            self.cur_index = 0
            self.cur_horizontal = 0

            self.difficulty = 0.5

            self.game_over = False
            self.game_over_count = 0

            self.pause = False

            self.input_flag = False
            self.input_value = b''
            self.input_count = 0

    def __init__(self, status):
        super().__init__(status)
        self.state = self.State()
        self.generate_tetris()

    async def next_frame(self, c: bytes):
        # 退出
        if c == b'q':
            raise BreakGame()

        # 暂停
        if c == b'z':
            self.state.pause = not self.state.pause

        if self.state.pause:
            return self.draw()

        # 游戏结束的动画
        if self.state.game_over:
            if self.state.game_over_count >= len(self.state.data):
                raise BreakGame()

            self.state.data[self.state.game_over_count] = 0xfffff

            self.state.game_over_count += 1
            return self.draw()

        if c == b'\xe0':
            self.state.input_flag = True
            return self.draw()

        # 处理双位 按键
        if self.state.input_flag:
            c = b'\xe0' + c
            self.state.input_flag = False

        # 处理按键
        if c:
            self.state.input_value = c
            self.action(c)

        # 下落
        self.state.input_count += 1
        if self.state.input_count >= self.refresh_per * self.state.difficulty:
            self.state.input_count = 0
            self.falling()

        if sum(self.state.data[:3]) > 0:
            self.state.game_over = True

        return self.draw()

    def action(self, c):
        if c == b'\xe0K':
            # 左
            # todo 检查是否可以移动
            self.state.cur_data = [x << 1 for x in self.state.cur_data]
            self.state.cur_horizontal += 1
        elif c == b'\xe0M':
            # 右
            self.state.cur_data = [x >> 1 for x in self.state.cur_data]
            self.state.cur_horizontal -= 1
        elif c == b' ':
            # 翻转
            h = self.state.cur_horizontal
            r = [tuple(f'{x >> h if h > 0 else x << -h:04b}') for x in self.state.cur_data]
            v = list(zip(*(reversed(x) for x in r)))
            self.state.cur_data = [
                (lambda x: x << h if h > 0 else x >> -h)(int(''.join(x), 2)) for x in v
            ]
        elif c == b'u':
            # 难度上升
            if 0.2 < self.state.difficulty:
                self.state.difficulty -= 0.1
        elif c == b'n':
            # 难度下降
            if self.state.difficulty < 1:
                self.state.difficulty += 0.1

    def falling(self):
        self.state.cur_index += 1

        bottom = next((i for i, x in enumerate(reversed(self.state.cur_data)) if x > 0), None)

        if (self.state.cur_index + (4 - bottom)) >= len(self.state.data):
            self.ack(bottom)
            self.generate_tetris()
            return

        if any(
                (self.state.data[self.state.cur_index + 1 + i] & x)
                for i, x in enumerate(self.state.cur_data[:4 - bottom])
        ):
            self.ack(bottom)
            self.generate_tetris()
            return

    def ack(self, bottom):
        self.state.data[self.state.cur_index:self.state.cur_index + (4 - bottom)] = [
            self.state.data[self.state.cur_index + i] | x for i, x in
            enumerate(self.state.cur_data[:4 - bottom])
        ]
        # 判断满行时候, 消除
        fs_i = [i for i, x in enumerate(self.state.data) if x == 0xfffff]
        if fs_i:
            for i in fs_i:
                self.state.data.pop(i)
            self.state.data[:0] = [0] * len(fs_i)
            # 加分
            self.state.score += (len(fs_i) * 100 + (len(fs_i) - 1) * 200)

    def draw(self):
        layout = Layout()
        layout.split_row(
            Layout(Panel("\n".join(
                "".join(
                    y == '0' and '□ ' or '■ ' for y in
                    f"{self.draw_line(i, x):020b}"
                )
                for i, x in enumerate(self.state.data)
            ), title="俄罗斯方块"), ratio=2),
            Layout(self.score_box()),
        )
        return layout

    def draw_line(self, i, x):
        r = i - self.state.cur_index
        return x | self.state.cur_data[r] if 0 <= r < 4 else x

    key_name_map = {
        b'\xe0K': '←',
        b'\xe0M': '→',
        b'u': 'Up',
        b'n': 'Down',
        b' ': '翻转',
        b'z': '暂停',
    }

    def score_box(self):
        return Panel(
            f'''
用户\u3000\u3000: {self.status.name}
当前得分: {self.state.score:>08}
当前难度: {int(10 - self.state.difficulty * 10)}
输入按键: {self.key_name_map.get(self.state.input_value, "*")}


←  →  控制 方块移动
空格键 翻转方块
 U    提高难度
 N    降低难度
 Z    暂停游戏

{f'*最终得分: {self.state.score}*' if self.state.game_over and self.state.game_over_count % 3 else '':^20}

{self.state.pause and '暂停中...' or '':^20}

''',
            title="得分"
        )

    def generate_tetris(self):
        """生成方块"""
        self.state.cur_index = 0
        self.state.cur_horizontal = 9
        v = random.choice((
            [0b0000, 0b0110, 0b0110, 0b0000],  # O
            [0b0000, 0b0100, 0b0111, 0b0000],  # L
            [0b0100, 0b0110, 0b0010, 0b0000],  # S
            [0b0000, 0b1111, 0b0000, 0b0000],  # I
            [0b0000, 0b0100, 0b1110, 0b0000],  # T
        ))
        self.state.cur_data = [x << self.state.cur_horizontal for x in v]
