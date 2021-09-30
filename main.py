import asyncio

from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession

from commands.base import shell
from commands.status import GameStatus


async def interactive_shell():
    """
    带有提示的交互命令行
    """
    session = PromptSession("Shell")
    status = GameStatus()
    await shell(session, status)


async def main():
    with patch_stdout(True):
        await interactive_shell()
        print("Bye.")


if __name__ == "__main__":
    asyncio.run(main())
