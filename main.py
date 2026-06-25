#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OKX 价格悬浮窗启动入口。"""

import tkinter as tk

from app import FloatingWindow
from constants import DEFAULT_INST_IDS


def main():
    root = tk.Tk()
    FloatingWindow(root, DEFAULT_INST_IDS)
    root.mainloop()


if __name__ == "__main__":
    main()
