import sys
import argparse
import asyncio
import json
from pathlib import Path

try:
    import termios
    import tty
except ImportError:
    pass

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit import shortcuts
from prompt_toolkit.styles import Style

from pyvim.editor import Editor
from pyvim.io.base import EditorIO
from pyvim.commands.handler import handle_command

import nkgame
from nkgame.commands.status import HostNode, TreeSystem
from nkgame.pb.game_status_pb2 import FileType
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from nkgame.game.game_base import Game

from .base import Command, ArgumentParser, ShellContinue, ShellBreak


class HelpCommand(Command):
    name = "help"
    words = "help"

    args = ArgumentParser(prog="help", usage="help", description="显示命令使用帮助", epilog="")

    async def run(self, args: argparse.Namespace):
        result = "\n".join(
            f"    {com.name:<10} -- {com.args.description:{chr(12288)}<15}  {com.args.usage}"
            for com in self.commands.values() if com.args is not None
        )

        self.status.console.print(Panel.fit(f'''
命令列表
{result}
        '''))


class ExitCommand(Command):
    name = "exit"
    words = "exit"

    dialog_style = Style.from_dict({
        'dialog': 'bg:#000000',
        'dialog frame.label': 'bg:#ffffff #000000',
        'dialog.body': 'bg:#88ff88 #00ff00',
        'dialog shadow': 'bg:#00aa00',
    })

    async def run(self, args: argparse.Namespace):
        result = await shortcuts.yes_no_dialog(
            title='退出游戏',
            text='确定要退出游戏吗 ?',
            style=self.dialog_style,
        ).run_async()
        if result:
            self.status.game.save()
            raise ShellBreak()


class PwdCommand(Command):
    name = "pwd"
    words = "pwd"

    args = ArgumentParser(prog="pwd", usage="pwd", description="显示当前路径", epilog="")

    async def run(self, args: argparse.Namespace):
        self.status.console.print("/" + "/".join(self.status.path))


class LsCommand(Command):
    name = "ls"
    words = "ls"

    args = ArgumentParser(prog="ls", usage="ls", description="显示目录下内容", epilog="")
    args.add_argument("-l", "--long", help="显示详细信息", action="store_true")

    async def run(self, args: argparse.Namespace):
        values = self.status.file_sys.find(self.status.path[1:]).sub
        data = sorted(values, key=lambda x: (x.type, x.name))
        if not args.long:
            self.status.console.print("     ".join(str(x) for x in data))
            return
        for x in data:
            self.status.console.print(
                f"{x.type:<5}\t{x:<20}{len(x.data) if data else 0:<10}"
                f"{x.readable and 'r' or '-'}{x.writable and 'w' or '-'}{x.executable and 'x' or '-'}"
            )


class CdCommand(Command):
    class DirCompleter(WordCompleter):

        def get_completions(self, document, complete_event):
            self.words = ["~", ".."] + [
                x.name for x in Command.status.file_sys.find(Command.status.path[1:]).sub if x.type == FileType.dir
            ]
            return super().get_completions(document, complete_event)

    name = "cd"
    words = {"cd": DirCompleter([])}

    args = ArgumentParser(prog="cd", usage="cd lib", description="移动到路径", epilog="")
    args.add_argument("path", help="路径", default="")

    async def run(self, args: argparse.Namespace):

        if args.path == "~":
            self.status.path = self.status.path[:1]
            return

        result = self.status.path[:]

        path_list = args.path.strip().split("/")

        if args.path.startswith("/"):
            result = path_list
        else:
            for path in path_list:
                if path == "..":
                    if len(result) <= 1:
                        continue
                    result.pop()
                elif path == ".":
                    pass
                else:
                    result.append(path)
        t = self.status.file_sys.find(result[1:])
        if t is None or t.type != FileType.dir:
            self.status.console.print("[red]ERR[/] directory not found.")
            return
        self.status.path = result


class MkdirCommand(Command):
    name = "mkdir"
    words = "mkdir"

    args = ArgumentParser(prog="mkdir", usage="mkdir xxx", description="创建目录", epilog="")
    args.add_argument("path", help="目录名")

    async def run(self, args: argparse.Namespace):
        cur = self.status.file_sys.find(self.status.path[1:])

        n = args.path

        if n in cur.index:
            self.status.console.print("[red]ERR[/] directory already exists.")
            return

        cur.add(TreeSystem(n, FileType.dir))
        self.status.game.save()


class OpenCommand(Command):
    class FileCompleter(WordCompleter):

        def get_completions(self, document, complete_event):
            self.words = [
                x.name for x in Command.status.file_sys.find(Command.status.path[1:]).sub if x.type != FileType.dir
            ]
            return super().get_completions(document, complete_event)

    name = "open"
    words = {"open": FileCompleter([])}

    args = ArgumentParser(prog="open", usage="open xxx.txt", description="打开一个文件", epilog="")
    args.add_argument("file", help="文件路径")

    async def run(self, args: argparse.Namespace):
        p: TreeSystem = self.status.file_sys.find(self.status.path[1:]).index.get(args.file)
        if p is None or p.type == FileType.dir:
            self.status.console.print(f"[red]ERR[/] {args.file} not can open.")
            return

        if p.type == FileType.bin:
            self.status.console.print(json.loads(p.data))
            return
        self.status.console.print(p.data)


class SaveCommand(Command):
    name = "save"
    words = "save"

    async def run(self, args: argparse.Namespace):
        self.status.game.save()


class LoadCommand(Command):
    name = "load"
    words = "load"

    async def run(self, args: argparse.Namespace):
        self.status.game.load()


class PlayCommand(Command):
    name = "play"
    words = {"play": WordCompleter(["awake"])}

    args = ArgumentParser(prog="play", usage="play awake", description="播放动画", epilog="")
    args.add_argument("name", help="动画名称")
    args.add_argument("-t", "--time", dest="time", help="持续时间", default=3, type=int)

    def __init__(self, status: HostNode):
        super().__init__(status)
        self.is_run = True

    async def run(self, args: argparse.Namespace):
        path = Path(nkgame.__file__).parent / 'assets' / f'{args.name}.json'
        with open(path) as f:
            res = json.load(f)
        asyncio.create_task(self.stop(args.time))
        i = 0
        while self.is_run:
            print('\033c' + res[i])
            i += 1
            if i >= len(res):
                await asyncio.sleep(0.5)
                i = 0
            await asyncio.sleep(0.1)
        print("\033c", end="")

    async def stop(self, t):
        await asyncio.sleep(t)
        self.is_run = False


class HostnameCommand(Command):
    name = "hostname"
    words = "hostname"

    args = ArgumentParser(prog="hostname", usage="hostname your_name", description="修改主机名", epilog="")
    args.add_argument("name", help="主机名")

    async def run(self, args: argparse.Namespace):
        if args.name in self.status.game.hosts:
            self.status.console.print("[red]ERR[/] hostname already exists.")
            return
        self.status.host = args.name
        self.status.game.save()


class VimOpenError(Exception):
    def __init__(self, msg):
        self.msg = msg


class VFileIO(EditorIO):
    """
    虚拟文件接口
    """

    def __init__(self, status: HostNode):
        self.status = status

    def can_open_location(self, location):
        return True

    def exists(self, location):
        self.status.console.print("exists", location)
        p: TreeSystem = self.status.file_sys.find(self.status.path[1:]).index.get(location)
        if p is None:
            return False

        self.status.console.print("exists", p)

        if p.type != FileType.txt:
            raise VimOpenError("文件不是文本类型")

        return True

    def read(self, location):
        p: TreeSystem = self.status.file_sys.find(self.status.path[1:]).index.get(location)
        if p is None:
            return "", "utf-8"
        if p.type == FileType.txt:
            return p.data, "utf-8"
        raise VimOpenError("读取文件失败")

    def write(self, location, data, encoding='utf-8'):
        d = self.status.file_sys.find(self.status.path[1:])
        if location in d.index:
            f = d.index.get(location)
            if f.type != FileType.txt:
                raise VimOpenError("文件不是文本类型")
            f.data = data
            f.type = FileType.txt
        else:
            d.add(TreeSystem(location, FileType.txt, data))
        self.status.game.save()


class VimCommand(Command):
    class FileCompleter(WordCompleter):

        def get_completions(self, document, complete_event):
            self.words = [
                x.name for x in Command.status.file_sys.find(Command.status.path[1:]).sub if x.type == FileType.txt
            ]
            return super().get_completions(document, complete_event)

    name = "vim"
    words = {"vim": FileCompleter([])}

    args = ArgumentParser(prog="vim", usage="vim file.txt", description="编辑文件", epilog="")
    args.add_argument("-f", "--file", help="文件名", default=None, required=False)

    async def run(self, args: argparse.Namespace):
        editor = Editor()
        editor.load_initial_files([args.file], in_tab_pages=True)
        editor.io_backends = [VFileIO(self.status)]

        def handle_action(buff):
            """ When enter is pressed in the Vi command line. """
            text = buff.text  # Remember: leave_command_mode resets the buffer.

            # First leave command mode. We want to make sure that the working
            # pane is focussed again before executing the command handlers.
            editor.leave_command_mode(append_to_history=True)

            # Execute command.
            handle_command(editor, text)

        editor.command_buffer.accept_handler = handle_action
        try:
            await editor.application.run_async()
        except VimOpenError as e:
            self.status.console.print(f"[red]ERR[/] open file err: {e.msg}")


class RmCommand(Command):
    name = "rm"
    words = "rm"

    args = ArgumentParser(prog="rm", usage="rm file.txt", description="删除文件", epilog="")
    args.add_argument("file", help="文件名")
    args.add_argument("-r", "--recursive", help="递归删除", action="store_true")

    async def run(self, args: argparse.Namespace):
        ps = args.file.split("/")
        if args.file.startswith("/"):
            tree = self.status.file_sys.find(ps)
        else:
            tree = self.status.file_sys.find(self.status.path[1:]).find(ps)
        if tree is None:
            self.status.console.print(f"[red]ERR[/] file {args.file} not exists.")
            return
        if tree.type == FileType.dir:
            if not args.recursive:
                self.status.console.print(f"[red]ERR[/] {args.file} is dir.")
                return
        tree.parent.sub.remove(tree)
        tree.parent.index.pop(tree.name)
        self.status.game.save()


class PyEvalCommand(Command):
    name = "exp"
    words = "exp"

    args = ArgumentParser(prog="exp", usage="exp 1+1", description="简单运算", epilog="")
    args.add_argument("exp", help="表达式")

    args.add_argument("-o", "--out", dest="out", default="", help="输出结果到变量名")
    args.add_argument("-f", "--file", dest="file", default="", help="输出结果到文件名")

    async def run(self, args: argparse.Namespace):
        try:
            result = eval(args.exp, self.status.env)
            self.status.console.print(f'{result}')
        except Exception as e:
            self.status.console.print(f"error: {e}")
            return
        if args.out:
            self.status.env[args.out] = result
        if args.file:
            d = self.status.file_sys.find(self.status.path[1:])
            if args.file in d.index:
                f = d.index.get(args.file)
                f.data = json.dumps(result)
                f.type = FileType.bin
            else:
                d.add(TreeSystem(args.file, FileType.bin, json.dumps(result)))
            self.status.game.save()


class SelectCommand(Command):
    name = "select"
    words = "select"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices = [
            "选项 A",
            "选项 B",
            "选项 C",
        ]
        self.value = 0
        self.input_flag = 0

    async def run(self, args: argparse.Namespace):
        settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

        try:
            with Live(await self.next_frame(''), refresh_per_second=10) as live:
                while True:
                    # c = sys.stdin.read(1) if sys.stdin.readable() else ''
                    c = sys.stdin.read(1)
                    live.update(await self.next_frame(c))
                    # await sleep(0.05)
        except ShellContinue:
            self.status.console.print(f"选择了：[bold red]{self.choices[self.value]}[/] , :heart-emoji:")
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)

    async def next_frame(self, c):
        # 处理双位 按键
        if self.input_flag == 0 and c == '\x1b':
            self.input_flag = 1
        elif self.input_flag == 1 and c == '[':
            self.input_flag = 2
        elif self.input_flag == 2:
            c = '^' + c
            self.input_flag = 0

        if c == '\n':
            raise ShellContinue()
        elif c == '^A':
            self.value -= 1
        elif c == '^B':
            self.value += 1

        self.value = self.value % len(self.choices)

        return Text("\n".join([f"{'>' if i == self.value else ' '} {x}" for i, x in enumerate(self.choices)]))


class SshCommand(Command):
    class HostCompleter(WordCompleter):

        def get_completions(self, document, complete_event):
            self.words = [
                x for x in Command.status.game.hosts.keys()
            ]
            return super().get_completions(document, complete_event)

    name = "ssh"
    words = {"ssh": HostCompleter([])}

    args = ArgumentParser(prog="ssh", usage="ssh 192.168.0.1", description="登录远程节点", epilog="")
    args.add_argument("host", help="远程地址")
    args.add_argument("-c", "--create", dest="create", help="创建节点", action="store_true")

    async def run(self, args: argparse.Namespace):
        if args.host not in self.status.game.hosts and args.create == "":
            self.status.console.print(f"[red]ERR[/] host [steel_blue]{args.host}[/] not exists.")
            return

        if args.create:
            self.status.game.hosts[args.host] = HostNode(
                name=args.create,
                host=args.host,
                file=TreeSystem(name="root", ex=FileType.dir),
                game=self.status.game
            )
        session = PromptSession(f"ssh {args.host}")
        status = self.status.game.hosts.get(args.host)
        if status is None:
            self.status.console.print(f"[red]ERR[/] host [steel_blue]{args.host}[/] not exists.")
            return
        from . import shell
        await shell(session, status)


class GameCommand(Command):
    name = "game"
    words = {"game": WordCompleter(list(Game.games.keys()))}

    args = ArgumentParser(prog="game", usage="game fk", description="选择小游戏", epilog="")
    args.add_argument("name", help="小游戏名")

    async def run(self, args: argparse.Namespace):
        game = Game.games.get(args.name)
        if game is None:
            self.status.console.print(f"[red]ERR[/] game {args.name} not exists.")
            return
        await game(self.status).run()


name = "console"

__all__ = [
    name
]
