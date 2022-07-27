import argparse
import asyncio
import json
import shlex
import os
import abc

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter, NestedCompleter
from typing import Union

from commands.status import HostNode, TreeSystem
from pb.game_status_pb2 import FileType
from .vim import VFile
from suplemon.main import App as SuplemonApp


class ArgumentParser(argparse.ArgumentParser):

    def exit(self, status=..., message=None):
        if message:
            Command.status.console.print(message)
        raise ShellContinue()


class Command(metaclass=abc.ABCMeta):
    completer = NestedCompleter({}, ignore_case=True)
    status: HostNode = None

    args: argparse.ArgumentParser = None
    commands = {}
    name: str = ""
    words: Union[str, dict] = ""

    def __init_subclass__(cls, **kwargs):
        if isinstance(cls.words, str):
            cls.completer.options[cls.words] = None
            cls.commands[cls.words] = cls
        elif isinstance(cls.words, dict):
            for k, v in cls.words.items():
                cls.completer.options[k] = v
                cls.commands[k] = cls

    def __init__(self, status: HostNode):
        self.status = status

    @abc.abstractmethod
    async def run(self, args: argparse.Namespace):
        raise NotImplementedError()


class MissCommand(Command):
    name = "none"
    words = None

    async def run(self, args: argparse.Namespace):
        self.status.console.print("[red]ERR[/] miss command.")


class ExitCommand(Command):
    name = "exit"
    words = "exit"

    async def run(self, args: argparse.Namespace):
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

    async def run(self, args: argparse.Namespace):
        d = sorted(
            self.status.file_sys.find(self.status.path[1:]).sub,
            key=lambda x: (x.type, x.name)
        )
        self.status.console.print("     ".join(str(x) for x in d))


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

        name = args.path

        if name in cur.index:
            self.status.console.print("[red]ERR[/] directory already exists.")
            return

        cur.add(TreeSystem(name, FileType.dir))
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
        with open(os.path.join("assets", args.name + ".json")) as f:
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
    args.add_argument("file", help="文件名")

    async def run(self, args: argparse.Namespace):
        VFile.status = self.status
        app = SuplemonApp([args.file])

        if app.init():
            modules = app.modules.modules
            modules.get("hostname").hostname = self.status.host

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, app.run)
            self.status.game.save()


class RmCommand(Command):
    name = "rm"
    words = "rm"

    args = ArgumentParser(prog="rm", usage="rm file.txt", description="删除文件", epilog="")
    args.add_argument("file", help="文件名")

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
    args.add_argument("-c", "--create", dest="create", default="")

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
        await shell(session, status)


class ShellContinue(Exception):
    pass


class ShellBreak(Exception):
    pass


async def shell(session, status):
    while True:
        try:
            Command.status = status
            result = await session.prompt_async(
                f"[{status.name}@{status.host} {'/'.join(status.path)}] # ",
                completer=Command.completer,
                complete_while_typing=False
            )

            result = result.strip()

            if not result:
                continue
            try:
                cmd, *args = shlex.split(result)
            except Exception as e:
                status.console.print(f"[red]ERR[/] error: command format error: {e}")
                continue
            c = Command.commands.get(cmd, MissCommand)
            if c.args is None:
                c.args = ArgumentParser()
            try:
                nargs, v = c.args.parse_known_args(args)
                if v:
                    status.console.print(f"[red]ERR[/] args error: [red]{''.join(v)}[/]")
                    continue
                await c(status).run(nargs)
            except ShellContinue:
                continue
            except ShellBreak:
                break
            except Exception as e:
                status.console.print(f"[red]ERR[/] error: {e}")
                import traceback
                traceback.print_exc()
        except (EOFError, KeyboardInterrupt):
            return
