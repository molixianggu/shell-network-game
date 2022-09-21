import cli

import asyncio

import pyfiglet
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession

from nkgame.commands.base import shell
from nkgame.commands.status import GameStatus


async def interactive_shell():
    """
    带有提示的交互命令行
    """
    session = PromptSession("Shell")
    status = GameStatus()
    status.load()
    localhost = status.hosts.get("localhost")
    localhost.console.print(pyfiglet.figlet_format("NK Game XD"))
    await shell(session, localhost)
    localhost.console.print("Bye.")


async def main():
    with patch_stdout(True):
        await interactive_shell()


if __name__ == "__main__":
    asyncio.run(main())
