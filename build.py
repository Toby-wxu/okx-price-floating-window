#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OKX Price 打包脚本：使用 PyInstaller 生成单文件 exe。"""

import shutil
import subprocess
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent
    main_py = project_root / "main.py"
    if not main_py.exists():
        print("错误：未找到 main.py", file=sys.stderr)
        sys.exit(1)

    # 清理旧构建产物
    for name in ("dist", "build"):
        path = project_root / name
        if path.exists():
            shutil.rmtree(path)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name",
        "OKX_Price",
        str(main_py),
    ]
    print("执行命令:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=project_root)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
