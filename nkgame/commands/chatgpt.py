import argparse

import os
import openai
from rich.live import Live
from rich.markdown import Markdown

from .base import Command, ArgumentParser


class ChatGPT(Command):
    name = "ChatGPT"
    words = "chatgpt"

    args = ArgumentParser(prog="chatgpt", usage="chatgpt", description="开始一个对话机器人", epilog="")
    args.add_argument("--model", help="使用的模型", default="gpt-3.5-turbo")

    args.add_argument("--key", help="OpenAI API Key", default=os.getenv("OPENAI_API_KEY"))

    def __init__(self, status):
        super().__init__(status)
        self.role = self.name

    async def run(self, args: argparse.Namespace):

        openai.api_key = args.key

        messages = []

        while True:
            try:
                query = self.status.console.input("[green]Query: [/] ")
                if not query or query.lower() == "/q" or query.lower() == "exit":
                    break

                messages.append({"role": "user", "content": query})

                response = openai.ChatCompletion.create(
                    stream=True, model=args.model, messages=messages
                )

                result = ""
                with Live(await self.next_frame(result), refresh_per_second=5) as live:
                    for line in response:
                        if line["choices"][0]["finish_reason"] == "stop":
                            break
                        delta = line["choices"][0]["delta"]
                        if delta.get("role"):
                            self.role = delta["role"]
                        if delta.get("content"):
                            result += delta["content"]
                        live.update(await self.next_frame(result))
            except openai.error.RateLimitError:
                self.status.console.print("Rate limit or maximum monthly limit exceeded", style="bold red")
                messages.pop()
                break

            except (EOFError, KeyboardInterrupt):
                return

            except Exception as e:
                self.status.console.print(f"Unknown error, status code {e}", style="bold red")
                self.status.console.print(e)
                break

    async def next_frame(self, text):
        return Markdown(f"[green]{self.role}: [/] {text}")


name = "chatgpt"

__all__ = [
    "name"
]
