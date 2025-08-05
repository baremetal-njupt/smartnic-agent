#!/usr/bin/env python3

import sys
import json

# 定义一个字典，用于控制特定命令是否应返回错误
error_commands = {
    "bdev_iscsi_create": False,
    "emulator_virtio_blk_device_create": False,
    "emulator_virtio_blk_device_delete": False,
    "bdev_iscsi_delete": False
}

class FakeCommandError(Exception):
    """模拟命令执行错误的异常类"""
    pass

def fake_execute(command):
    """
    模拟执行RPC命令，根据每个具体命令返回成功或错误消息。
    在错误配置为True时抛出异常。
    """
    print(f"Executing: {' '.join(command)}")

    cmd_key = command[0]  # 假定命令名称总是在第一个参数位置
    if error_commands.get(cmd_key, False):
        raise FakeCommandError(f"{cmd_key} command failed as configured")

    # 根据命令返回模拟的成功信息
    return json.dumps({"status": "success", "message": f"{cmd_key} command executed successfully"})

if __name__ == "__main__":
    try:
        args = sys.argv[1:]
        result = fake_execute(args)
        print(result)
    except FakeCommandError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)  # 以错误状态码退出，表示命令执行失败

