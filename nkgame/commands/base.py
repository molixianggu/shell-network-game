import argparse
import abc

try:
    import termios
    import tty
except ImportError:
    # TODO
    pass

from typing import Union, Any

from prompt_toolkit.completion import NestedCompleter

from nkgame.commands.status import HostNode


class ArgumentParser(argparse.ArgumentParser):

    def exit(self, status=..., message=None):
        if message:
            Command.status.console.print(message)
        raise ShellContinue()


class Command(metaclass=abc.ABCMeta):
    completer = NestedCompleter({}, ignore_case=True)
    status: HostNode = None

    args: argparse.ArgumentParser = None
    commands: dict[Any, type['Command']] = {}
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


class ShellContinue(Exception):
    pass


class ShellBreak(Exception):
    pass


class MissCommand(Command):
    name = "none"
    words = None

    async def run(self, args: argparse.Namespace):
        self.status.console.print("[red]ERR[/] miss command.")
