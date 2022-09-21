
import os
import sys


print("文件安装中, 请稍后...")

if sys.version_info < (3, 7, 0):
    raise Exception("python version low.")

if 'win32' in sys.platform:
    os.system("cls")
    os.system("title +nk-game")
else:
    os.system("clear")
