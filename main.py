# ==========================================
# 主程序: GUI 入口
# ==========================================

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# 导入拆分的模块
import config
import adb_utils

# ==========================================
# PyInstaller 打包 uiautomator2 资源修复补丁
# ==========================================
import sys
import pathlib
import contextlib

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    import uiautomator2.utils
    _original_with_package_resource = uiautomator2.utils.with_package_resource

    @contextlib.contextmanager
    def _patched_with_package_resource(filename: str):
        meipass = pathlib.Path(sys._MEIPASS)
        file_path = meipass / "uiautomator2" / filename
        if file_path.exists():
            yield file_path
        else:
            with _original_with_package_resource(filename) as f:
                yield f

    uiautomator2.utils.with_package_resource = _patched_with_package_resource
# ==========================================

import ui_actions

class AdbManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ADB 设备管理器 v2.0.1 (Modular)")
        self.root.geometry("1200x750")
        self.root.minsize(800, 450)

        # 线程通信队列
        self.log_queue = queue.Queue()
        self.current_devices = []

        self.create_styles()
        self.create_widgets()

        # 启动自检
        self.check_adb_version()
        # 启动日志监听
        self.root.after(100, self.process_log_queue)

    def create_styles(self):
        c = config.THEME_COLORS
        style = ttk.Style()
        style.theme_use("clam")

        self.root.config(bg=c["BG_MAIN"])
        style.configure("TFrame", background=c["BG_MAIN"])
        
        # LabelFrame
        style.configure("TLabelframe", background=c["BG_FRAME"], foreground=c["FG_LIGHT"], relief="groove", borderwidth=2)
        style.configure("TLabelframe.Label", background=c["BG_FRAME"], foreground=c["FG_LIGHT"], font=("Microsoft YaHei", 11, "bold"))
        
        # Button
        style.configure("TButton", padding=6, relief="flat", background=c["ACCENT"], foreground=c["BUTTON_FG"], font=("Microsoft YaHei", 10, "bold"))
        style.map("TButton", background=[("active", c["ACCENT"]), ("pressed", c["ACCENT"])], relief=[("pressed", "sunken")])
        
        # Label
        style.configure("TLabel", background=c["BG_FRAME"], foreground=c["FG_LIGHT"], font=("Microsoft YaHei", 10))
        
        # Inputs
        style.configure("TEntry", fieldbackground=c["INPUT_BG"], foreground=c["FG_LIGHT"], bordercolor=c["ACCENT"])
        style.map("TCombobox", fieldbackground=[("readonly", c["INPUT_BG"])], selectbackground=[("readonly", c["INPUT_BG"])],
                  selectforeground=[("readonly", c["FG_LIGHT"])], background=[("readonly", c["BG_FRAME"])], foreground=[("readonly", c["FG_LIGHT"])])

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        # --- 顶部按钮区 ---
        auto_frame = ttk.LabelFrame(main_frame, text="设备管理与 UI 调试操作")
        auto_frame.pack(fill=tk.X, pady=(0, 5))
        
        btn_row = ttk.Frame(auto_frame)
        btn_row.pack(fill=tk.X, padx=5, pady=5)

        actions = [
            ("查找并开启无线调试", self.task_find_wireless),
            ("断开所有调试连接", self.task_disconnect_all),
            ("查看所有连接设备", self.task_list_devices),
            ("清除日志", self.clear_log),
            ("💾 Dump UI XML", self.task_dump_ui),
            ("📊 分析 UI 元素", self.task_analyze_ui),
            ("🚀 开启 Shizuku", self.task_start_shizuku)
        ]

        for text, cmd in actions:
            # 注意: 如果是 task_ 开头的，需要用线程包装
            command = (lambda c=cmd: self.start_thread(c)) if cmd != self.clear_log else cmd
            ttk.Button(btn_row, text=text, command=command).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5, pady=5)

        # --- 中部控制区 ---
        ctrl_frame = ttk.LabelFrame(main_frame, text="设备操作与手动连接")
        ctrl_frame.pack(fill=tk.X, pady=(5, 10))
        
        combined_row = ttk.Frame(ctrl_frame)
        combined_row.pack(fill=tk.X, padx=5, pady=5)

        # 设备选择
        dev_frame = ttk.Frame(combined_row)
        dev_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Label(dev_frame, text="选择设备:").pack(side=tk.LEFT, padx=5)
        self.device_combo = ttk.Combobox(dev_frame, state="readonly")
        self.device_combo.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.device_combo.set("等待刷新...")

        # IP 连接
        ip_frame = ttk.Frame(combined_row)
        ip_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(ip_frame, text="手动 IP:").pack(side=tk.LEFT, padx=5)
        self.ip_entry = ttk.Entry(ip_frame, width=20)
        self.ip_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.ip_entry.insert(0, "192.168.1.")

        ttk.Button(ip_frame, text="连接", command=lambda: self.start_thread(self.task_manual_connect)).pack(side=tk.LEFT, padx=5)
        ttk.Button(ip_frame, text="断开", command=lambda: self.start_thread(self.task_manual_disconnect)).pack(side=tk.LEFT, padx=(0, 5))

        # --- 底部日志区 ---
        log_frame = ttk.LabelFrame(main_frame, text="输出日志")
        log_frame.pack(expand=True, fill=tk.BOTH)
        
        c = config.THEME_COLORS
        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, state="disabled", font=("Consolas", 10),
            bg=c["LOG_BG"], fg=c["LOG_FG"], insertbackground="white", selectbackground=c["SELECT_BG"]
        )
        self.log_text.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

    # --- 核心辅助 ---
    def log(self, msg):
        self.log_queue.put(msg)

    def start_thread(self, func):
        threading.Thread(target=func, daemon=True).start()

    def process_log_queue(self):
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                ts = time.strftime("[%H:%M:%S]", time.localtime())
                self.log_text.config(state="normal")
                self.log_text.insert(tk.END, f"{ts} {msg}\n")
                self.log_text.see(tk.END)
                self.log_text.config(state="disabled")
            except queue.Empty:
                pass
        self.root.after(100, self.process_log_queue)
    
    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

    def get_selected_device(self):
        val = self.device_combo.get()
        if not val or "<" in val:
            self.log("❌ 请先选择有效设备")
            self.task_list_devices() # 自动刷新一下
            return None
        return val

    def update_device_list_ui(self, devices):
        """主线程更新UI的回调"""
        self.current_devices = devices
        if devices:
            self.device_combo["values"] = devices
            if self.device_combo.get() not in devices:
                self.device_combo.current(0)
            self.device_combo.config(state="readonly")
            self.log(f"🎉 发现 {len(devices)} 个设备: {', '.join(devices)}")
        else:
            self.device_combo["values"] = ["<无设备>"]
            self.device_combo.set("<无设备>")
            self.device_combo.config(state="disabled")
            self.log("🔍 未发现设备")

    # --- 任务包装 (Tasks) ---
    # 这些方法在子线程运行，负责调用 logic 模块，并在必要时调度 UI 更新

    def task_list_devices(self):
        self.log("\n--- 正在刷新设备列表 ---")
        devices = adb_utils.get_connected_devices(self.log)
        # UI 更新必须回到主线程 (虽然 tkinter 可以在子线程做简单操作，但为了安全建议用 after)
        self.root.after(0, lambda: self.update_device_list_ui(devices))

    def check_adb_version(self):
        self.log("--- 欢迎使用 ADB 管理器 (模块化版) ---")
        self.start_thread(lambda: adb_utils.run_command("adb version", self.log))
        self.start_thread(self.task_list_devices)

    def task_find_wireless(self):
        self.log("\n--- 开始无线调试配对 ---")
        # 先刷新列表确保最新
        self.task_list_devices()
        # 等待列表刷新可能需要一点时间，这里简单直接传当前缓存
        # 更好的做法是在 adb_utils 里重新获取，但这里为了逻辑复用，直接传 self.current_devices
        # 注意：多线程读写 self.current_devices 有轻微风险，但在 GUI 这种低频操作下通常可接受
        time.sleep(0.5) 
        adb_utils.enable_wireless_logic(self.current_devices, self.log)
        self.root.after(2000, self.task_list_devices)

    def task_disconnect_all(self):
        self.log("\n--- 断开所有连接 ---")
        adb_utils.disconnect_all(self.log)
        self.root.after(500, self.task_list_devices)

    def task_manual_connect(self):
        ip = self.ip_entry.get().strip()
        if not ip: return
        self.log(f"\n--- 连接 {ip} ---")
        adb_utils.connect_device_ip(ip, self.log)
        self.root.after(1000, self.task_list_devices)

    def task_manual_disconnect(self):
        ip = self.ip_entry.get().strip()
        if not ip: return
        self.log(f"\n--- 断开 {ip} ---")
        adb_utils.disconnect_device_ip(ip, self.log)
        self.root.after(1000, self.task_list_devices)

    def task_dump_ui(self):
        dev = self.get_selected_device()
        if dev: ui_actions.dump_ui_xml(dev, self.log)

    def task_analyze_ui(self):
        dev = self.get_selected_device()
        if dev: ui_actions.analyze_ui_elements(dev, self.log)

    def task_start_shizuku(self):
        dev = self.get_selected_device()
        if dev: ui_actions.start_shizuku(dev, self.log)

if __name__ == "__main__":
    root = tk.Tk()
    app = AdbManagerApp(root)
    root.mainloop()