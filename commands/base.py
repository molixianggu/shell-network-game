from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter, NestedCompleter
from typing import Union

from commands.status import GameStatus, TreeSystem, FileType


async def shell(session, status):
    while True:
        try:
            Command.status = status
            result = await session.prompt_async(
                f"[{status.name}@{status.host} {'/'.join(status.path)}] # ",
                completer=Command.completer,
                complete_while_typing=False
            )

            if not result:
                continue

            if result == "exit":
                break

            cmd = result.split(" ")
            await Command.commands.get(cmd[0], MissCommand)(status).run(cmd)
        except (EOFError, KeyboardInterrupt):
            return


class Command:
    completer = NestedCompleter({}, ignore_case=True)

    status: GameStatus = None

    commands = {}

    name: str = ""
    words: Union[str, dict] = []

    def __init_subclass__(cls, **kwargs):
        if isinstance(cls.words, str):
            cls.completer.options[cls.words] = None
            cls.commands[cls.words] = cls
        elif isinstance(cls.words, dict):
            for k, v in cls.words.items():
                cls.completer.options[k] = v
                cls.commands[k] = cls

    def __init__(self, status: GameStatus):
        self.status = status

    async def run(self, args: list[str]):
        pass


class MissCommand(Command):
    name = "none"
    words = None

    async def run(self, args: list[str]):
        self.status.console.print(f"[red]ERR[/] miss command \"{args[0]}\" .")


class PwdCommand(Command):
    name = "pwd"
    words = "pwd"

    async def run(self, args: list[str]):
        self.status.console.print("/" + "/".join(self.status.path))


class LsCommand(Command):
    name = "ls"
    words = "ls"

    async def run(self, args: list[str]):
        d = sorted(
            self.status.file_sys.find(self.status.path[1:]).sub,
            key=lambda x: (x.type.value, x.name)
        )
        self.status.console.print("     ".join(str(x) for x in d))


class CdCommand(Command):
    class DirCompleter(WordCompleter):

        def get_completions(self, document, complete_event):
            self.words = [".."] + [
                x.name for x in Command.status.file_sys.find(Command.status.path[1:]).sub if x.type == FileType.dir
            ]
            return super().get_completions(document, complete_event)

    name = "cd"
    words = {"cd": DirCompleter([])}

    async def run(self, args: list[str]):
        if len(args) > 2:
            self.status.console.print("[red]ERR[/] args error")
            return

        if len(args) == 1:
            self.status.path = self.status.path[:1]
            return

        result = self.status.path[:]

        path_list = args[1].split("/")

        if args[1].startswith("/"):
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

    async def run(self, args: list[str]):
        if len(args) > 2:
            self.status.console.print("[red]ERR[/] args error")
            return

        cur = self.status.file_sys.find(self.status.path[1:])

        name = args[1]

        if name in cur.index:
            self.status.console.print("[red]ERR[/] directory already exists.")
            return

        cur.add(TreeSystem(name, FileType.dir))


class OpenCommand(Command):
    class FileCompleter(WordCompleter):

        def get_completions(self, document, complete_event):
            self.words = [
                x.name for x in Command.status.file_sys.find(Command.status.path[1:]).sub if x.type != FileType.dir
            ]
            return super().get_completions(document, complete_event)

    name = "open"
    words = {"open": FileCompleter([])}

    async def run(self, args: list[str]):
        p: TreeSystem = self.status.file_sys.find(self.status.path[1:]).index.get(args[1])
        if p is None or p.type == FileType.dir:
            self.status.console.print(f"[red]ERR[/] {args[1]} not can open.")
            return
        self.status.console.print(p.data)


class SshCommand(Command):
    name = "ssh"
    words = "ssh"

    async def run(self, args: list[str]):
        session = PromptSession(f"ssh {args[1]}")
        status = GameStatus("user1", args[1])
        status.file_sys = TreeSystem("root", FileType.dir)
        await shell(session, status)
