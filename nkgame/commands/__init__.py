import shlex

from .base import Command, ArgumentParser, MissCommand, ShellContinue, ShellBreak

from .console import name as _
from .chatgpt import name as _


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
