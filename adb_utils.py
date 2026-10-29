# ==========================================
# 工具模块: 处理 ADB 基础连接和命令
# ==========================================

import subprocess
import re
import time
import threading

def run_command(command, log_callback=None):
    """
    执行系统命令并返回输出。
    
    :param command: 要执行的命令字符串
    :param log_callback: 用于输出日志的回调函数 (func(str))
    :return: (stdout, stderr)
    """
    try:
        if log_callback:
            log_callback(f"▶️ 执行命令: {command}")
            
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            startupinfo=startupinfo,
        )
        stdout, stderr = process.communicate()

        if process.returncode != 0 and stderr:
            if log_callback:
                log_callback(f"❌ 命令执行出错:\n{stderr.strip()}")
            return None, stderr

        if log_callback and stdout.strip():
            # 简化日志，某些频繁输出不显示全部内容
            pass 
            
        return stdout.strip(), None
        
    except FileNotFoundError:
        msg = "错误: 'adb' 命令未找到。请确保ADB已安装并配置环境变量。"
        if log_callback:
            log_callback(msg)
        return None, msg
    except Exception as e:
        msg = f"发生未知错误: {e}"
        if log_callback:
            log_callback(msg)
        return None, msg

def get_connected_devices(log_callback=None):
    """获取当前连接的设备列表"""
    stdout, _ = run_command("adb devices", log_callback)
    devices = []
    if stdout:
        output_lines = stdout.splitlines()
        devices = [
            line.split("\t")[0]
            for line in output_lines[1:]
            if "\tdevice" in line
        ]
    return devices

def disconnect_all(log_callback=None):
    """断开所有连接"""
    run_command("adb disconnect", log_callback)

def connect_device_ip(ip, log_callback=None):
    """手动连接 IP"""
    if ":" not in ip:
        ip = f"{ip}:5555"
    run_command(f"adb connect {ip}", log_callback)

def disconnect_device_ip(ip, log_callback=None):
    """手动断开 IP"""
    if ":" not in ip:
        ip = f"{ip}:5555"
    run_command(f"adb disconnect {ip}", log_callback)

def enable_wireless_logic(current_devices, log_callback=None):
    """
    核心逻辑: 查找 USB 设备并开启无线调试
    注意：此函数通常在线程中运行，因为它包含 sleep 等待
    """
    if not current_devices:
        if log_callback: log_callback("未找到任何ADB设备。")
        return

    # 过滤出 USB 设备 (非 IP 格式)
    usb_devices = [
        dev for dev in current_devices
        if not re.match(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+", dev)
    ]

    if not usb_devices:
        if log_callback: log_callback("没有找到通过USB连接的设备。请先用USB连接手机。")
        return

    for device_id in usb_devices:
        if log_callback: log_callback(f"\n处理设备: {device_id}")

        # 1. 获取 IP
        ip_cmd = f"adb -s {device_id} shell ip addr show wlan0"
        ip_output, ip_err = run_command(ip_cmd, log_callback=None) # 内部不再重复打印
        
        if ip_err or not ip_output:
            if log_callback: log_callback(f"无法获取 {device_id} 的IP地址。")
            continue

        ip_match = re.search(r"inet (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/", ip_output)
        if not ip_match:
            if log_callback: log_callback(f"在 {device_id} 上未找到wlan0的IP地址。请检查WiFi连接。")
            continue

        ip_address = ip_match.group(1)
        if log_callback: log_callback(f"设备 {device_id} 的IP地址是: {ip_address}")

        # 2. 开启 5555 端口
        run_command(f"adb -s {device_id} tcpip 5555", log_callback)

        # 3. 连接
        # 稍微等待一下让端口生效
        time.sleep(1)
        run_command(f"adb connect {ip_address}:5555", log_callback)