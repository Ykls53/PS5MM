#!/usr/bin/env python3
"""精确删掉 main.cpp 里所有探针残留，恢复到干净的引擎启动。

用行范围删：从 '// ---- exec 自检验证' 到 'static int probe_exec_self' 结束（第一个 ^}），
再从 main() 里删掉触发文件那一整块作用域。
"""
import sys
from pathlib import Path

M = Path("/home/yk/PS5MM/ps5/app/main.cpp")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    src = M.read_text(encoding="utf-8")

    # 1. 删掉 probe_exec_self 函数（从注释行到函数结束的 ^}）
    start = src.find("// ---- exec 自检验证")
    if start < 0:
        print("no probe fn comment")
        return 0
    fn_end = src.find("\n}\n", src.find("static int probe_exec_self", start))
    if fn_end < 0:
        print("no fn end")
        return 2
    fn_end += 3  # 包含 \n}\n
    block = src[start:fn_end]
    if mode == "--check":
        print("probe fn block chars:", len(block))
        print("preview:", block[:80].replace("\n", " | "))
        return 0
    src = src[:start] + src[fn_end:]

    # 2. 删掉 main() 里的触发文件块（从 "PS5 title 启动时拿不到命令行参数" 到配对的 "}" 作用域结束）
    cm = src.find("    // PS5 title 启动时拿不到命令行参数（测试 --probe-exec 走不通），")
    if cm >= 0:
        # 找到这个作用域的结束：从 "{"/"}" 计数
        brace = src.find("{", cm)
        depth = 0
        end = brace
        for i in range(brace, len(src)):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        # 连同前面的注释一起删
        src = src[:cm] + src[end:]
    M.write_text(src, encoding="utf-8")
    print("cleaned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
