# ==========================================
# 业务模块: UI Dump, 分析 和 Shizuku
# ==========================================

import os
import time
import sys
import xml.etree.ElementTree as ET
import uiautomator2 as u2
from adb_utils import run_command

def get_script_dir():
    """获取脚本或exe所在目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def dump_ui_xml(device_id, log_callback):
    """执行 uiautomator2 dump"""
    if log_callback: log_callback(f"✅ 选定设备: {device_id}。准备 Dump UI...")

    try:
        if log_callback: log_callback("正在连接 uiautomator2 客户端...")
        u_client = u2.connect(device_id)
        u_client.device_info # 触发连接检查

        if log_callback: log_callback("正在获取当前屏幕的 XML 布局...")
        xml_content = u_client.dump_hierarchy()

        if not xml_content or len(xml_content) < 50:
            if log_callback: log_callback("❌ 失败: XML 内容为空，可能是设备锁屏或服务异常。")
            return

        # 保存文件
        safe_device_id = device_id.replace(":", "_")
        filename = f"ui_dump_{safe_device_id}_{time.strftime('%Y%m%d_%H%M%S')}.xml"
        file_path = os.path.join(get_script_dir(), filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        file_size = os.path.getsize(file_path)
        if log_callback: log_callback(f"🎉 Dump 成功！保存至:\n{file_path} (大小: {file_size} B)")

    except Exception as e:
        if log_callback: 
            log_callback(f"❌ Dump 失败 (设备 {device_id})。")
            log_callback(f"详细错误: {e}")

def analyze_ui_elements(device_id, log_callback):
    """执行 UI 分析"""
    if log_callback: log_callback(f"✅ 选定设备: {device_id}。准备分析...")

    try:
        if log_callback: log_callback("正在连接 uiautomator2 客户端...")
        u_client = u2.connect(device_id)
        
        if log_callback: log_callback("正在获取 XML...")
        xml_content = u_client.dump_hierarchy()

        if not xml_content or len(xml_content) < 50:
            if log_callback: log_callback("❌ 失败: XML 内容无效。")
            return

        if log_callback: log_callback("\n--- XML 元素树结构分析结果 ---")
        root = ET.fromstring(xml_content)

        def print_nodes(node, indent=0):
            node_class = node.get("class", "未知")
            node_text = node.get("text", "")
            node_id = node.get("resource-id", "")
            node_desc = node.get("content-desc", "")
            node_bounds = node.get("bounds", "")

            parts = []
            prefix = "" if indent == 0 else f"{'  ' * indent}* "
            parts.append(f"{prefix}{node_class}")

            if node_text: parts.append(f'文本:"{node_text}"')
            if node_desc: parts.append(f'描述:"{node_desc}"')
            if node_id: parts.append(f"ID:{node_id}")
            parts.append(f"坐标:{node_bounds}")

            if log_callback: log_callback(" | ".join(parts))

            for child in node:
                print_nodes(child, indent + 1)

        print_nodes(root)
        if log_callback: log_callback("\n🎉 UI 元素分析完成！")

    except Exception as e:
        if log_callback: 
            log_callback(f"❌ 分析失败: {e}")

def start_shizuku(device_id, log_callback):
    """启动 Shizuku"""
    if log_callback: log_callback(f"✅ 选定设备: {device_id}。启动 Shizuku...")
    
    script_path = "/storage/emulated/0/Android/data/moe.shizuku.privileged.api/start.sh"
    cmd = f"adb -s {device_id} shell sh {script_path}"
    
    stdout, _ = run_command(cmd, log_callback=None) # 输出我们自己处理
    if stdout and log_callback:
        log_callback("ℹ️ Shizuku 脚本输出:")
        log_callback(stdout)
    
    if log_callback: log_callback("✅ 命令执行完毕，请检查手机状态。")