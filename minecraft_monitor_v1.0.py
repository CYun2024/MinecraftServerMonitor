import socket
import struct
import json
import time
import re
import sys
import os
import ctypes
import configparser
import threading
import base64
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QMessageBox, 
                            QDialog, QVBoxLayout, QCalendarWidget, QTextEdit, 
                            QLabel, QPushButton, QHBoxLayout, QGroupBox, 
                            QSplitter, QWidget, QSizePolicy, QScrollArea,
                            QComboBox, QCheckBox, QLineEdit, QListWidget, 
                            QListWidgetItem, QAbstractItemView, QGridLayout,
                            QInputDialog, QDialogButtonBox)
from PyQt5.QtGui import QIcon, QTextCharFormat, QColor, QBrush, QFont, QIntValidator, QPixmap
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QObject, QPoint, QRect, QByteArray, QBuffer
import matplotlib
matplotlib.use('Agg')  # 使用Agg后端，不需要GUI
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import matplotlib.font_manager as fm  # 添加字体管理模块
import numpy as np
import pandas as pd
from collections import defaultdict

def get_app_base_path():
    """获取应用程序基目录，支持 PyInstaller 打包和普通运行模式"""
    print('get_app_base_path获取应用程序基目录')
    if getattr(sys, 'frozen', False):
        # 打包后运行：返回可执行文件所在目录
        return os.path.dirname(sys.executable)
    else:
        # 普通 Python 脚本运行：返回脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))

# 配置文件路径 - 使用绝对路径确保可靠性
BASE_DIR = get_app_base_path()
CONFIG_FILE = os.path.join(BASE_DIR, "settings.ini")
ICON_PATH = os.path.join(BASE_DIR, "monitor_icon.ico")
LOG_FILE = os.path.join(BASE_DIR, "server_status.log")  # 日志文件路径

# 默认设置
DEFAULT_SETTINGS = {
    'General': {
        'check_interval': '180',
        'log_file': LOG_FILE,
        'icon_path': ICON_PATH
    },
    'Servers': {
        'servers': '127.0.0.1:25565'
    },
    'Notifications': {
        'show_startup_notification': '1',
        'show_refresh_notification': '1'
    },
    'ServerNotifications': {
        # 格式: 服务器地址: 设置值 (0/1)
        # 例如: '127.0.0.1:25565': '111'  # 分别对应: 上线弹窗, 上线通知, 离线通知
    },
    'Calendar': {
        'show_color': '0'  # 默认不显示颜色
    }
}

# 颜色代码映射
COLOR_MAP = {
    'black': '#000000',
    'dark_blue': '#0000AA',
    'dark_green': '#00AA00',
    'dark_aqua': '#00AAAA',
    'dark_red': '#AA0000',
    'dark_purple': '#AA00AA',
    'gold': '#FFAA00',
    'gray': '#AAAAAA',
    'dark_gray': '#555555',
    'blue': '#5555FF',
    'green': '#55FF55',
    'aqua': '#55FFFF',
    'red': '#FF5555',
    'light_purple': '#FF55FF',
    'yellow': '#FFFF55',
    'white': '#FFFFFF'
}

# 全局锁，用于保护共享资源
config_lock = threading.Lock()

def parse_motd(description):
    """解析 MOTD 信息，保留颜色和样式"""
    print('parse_motd 解析 MOTD 信息')
    # 如果描述是字符串，直接返回
    if isinstance(description, str):
        return description, description
    
    # 如果描述是字典，尝试解析
    if isinstance(description, dict):
        # 如果包含 'extra' 数组
        if 'extra' in description and isinstance(description['extra'], list):
            plain_parts = []
            html_parts = []
            
            for part in description['extra']:
                # 提取文本部分
                if 'text' in part:
                    text = part['text']
                    plain_parts.append(text)
                    
                    # 处理样式
                    style_attrs = []
                    
                    # 处理颜色
                    if 'color' in part:
                        color = part['color']
                        # 如果是命名颜色，转换为十六进制值
                        if color in COLOR_MAP:
                            style_attrs.append(f"color:{COLOR_MAP[color]};")
                        else:
                            # 尝试直接使用，可能是十六进制值
                            style_attrs.append(f"color:{color};")
                    
                    # 处理粗体
                    if part.get('bold', False):
                        style_attrs.append("font-weight:bold;")
                    
                    # 处理斜体
                    if part.get('italic', False):
                        style_attrs.append("font-style:italic;")
                    
                    # 处理下划线
                    if part.get('underlined', False):
                        style_attrs.append("text-decoration:underline;")
                    
                    # 处理删除线
                    if part.get('strikethrough', False):
                        style_attrs.append("text-decoration:line-through;")
                    
                    # 处理模糊效果（随机字符）
                    if part.get('obfuscated', False):
                        # 模糊效果在 HTML 中难以实现，使用特殊样式
                        style_attrs.append("font-family: monospace; letter-spacing: 2px;")
                    
                    # 如果有样式属性，包裹在 span 中
                    if style_attrs:
                        style_str = " ".join(style_attrs)
                        html_parts.append(f'<span style="{style_str}">{text}</span>')
                    else:
                        html_parts.append(text)
            
            plain_motd = "".join(plain_parts)
            html_motd = "".join(html_parts)
            return plain_motd, html_motd
        
        # 如果有 'text' 字段
        elif 'text' in description:
            return description['text'], description['text']
    
    # 默认返回空字符串
    return "No MOTD", "No MOTD"

def base64_to_pixmap(base64_str):
        """将 Base64 字符串转换为 QPixmap"""
        print('base64_to_pixmap 图片编码')
        if not base64_str:
            return None
        
        try:
            # 解码 Base64 字符串
            image_data = base64.b64decode(base64_str)
            
            # 创建 QPixmap
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            
            return pixmap
        except Exception as e:
            print(f"转换图标错误: {str(e)}")
            return None

def load_config():
    """加载配置文件，如果不存在则创建默认配置"""
    print('load_config 加载配置文件')
    with config_lock:
        config = configparser.ConfigParser(delimiters=('='), allow_no_value=True)

        # 确保配置文件目录存在
        config_dir = os.path.dirname(CONFIG_FILE)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(CONFIG_FILE):
            print(f"创建默认配置文件: {CONFIG_FILE}")
            config.read_dict(DEFAULT_SETTINGS)
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
        else:
            config.read(CONFIG_FILE)
        
        # 确保所有必要的设置都存在
        for section, settings in DEFAULT_SETTINGS.items():
            if not config.has_section(section):
                config.add_section(section)
            for key, value in settings.items():
                if not config.has_option(section, key):
                    config.set(section, key, value)

        return config

def save_config(config):
    """保存配置到文件"""
    print('save_config 保存配置文件')
    with config_lock:
        # 确保配置文件目录存在
        config_dir = os.path.dirname(CONFIG_FILE)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)

def parse_server_address(address: str):
    """解析服务器地址格式：host:port 或 host"""
    print('parse_server_address 解析服务器地址')
    default_port = 25565
    if ":" in address:
        parts = address.split(":")
        host = parts[0]
        try:
            port = int(parts[1])
            return host, port
        except ValueError:
            return host, default_port
    else:
        return address, default_port

def is_valid_server_address(address: str):
    """验证服务器地址格式是否正确"""
    print('is_valid_server_address 验证服务器地址')
    try:
        host, port = parse_server_address(address)
        return True
    except:
        return False

def get_server_info(host: str, port: int = 25565, timeout: int = 5) -> dict:
    """
    获取 Minecraft 服务器信息
    返回字典包含: 版本、在线玩家、最大玩家、MOTD、玩家列表等
    """
    print(threading.current_thread().name+'-get_server_info-获取 Minecraft 服务器信息')
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))

            # 发送握手数据包
            handshake = b"\x00"  # 数据包ID (Handshake)
            handshake += _pack_varint(404)  # 协议版本
            handshake += _pack_string(host)
            handshake += struct.pack(">H", port)
            handshake += _pack_varint(1)  # 下一步状态 (Status)
            
            handshake_packet = _pack_varint(len(handshake)) + handshake
            sock.send(handshake_packet)
            
            # 发送状态请求
            status_request = _pack_varint(1) + b"\x00"
            sock.send(status_request)
            
            # 读取响应
            response_length = _unpack_varint(sock)
            response = b""
            while len(response) < response_length:
                response += sock.recv(4096)
            
            # 解析响应
            buffer = response
            packet_id, buffer = _unpack_varint_from_buffer(buffer)
            json_length, buffer = _unpack_varint_from_buffer(buffer)
            json_data = buffer[:json_length]
            server_info = json.loads(json_data.decode("utf-8"))
            print(server_info)
            # 处理玩家列表
            if "players" in server_info and "sample" in server_info["players"]:
                players = [p["name"] for p in server_info["players"]["sample"]]
            else:
                players = []

            # 处理图标（favicon）
            favicon_base64 = None
            if "favicon" in server_info:
                favicon_base64 = server_info["favicon"]
                # 如果包含前缀，去掉前缀
                if favicon_base64.startswith("data:image/png;base64,"):
                    favicon_base64 = favicon_base64[len("data:image/png;base64,"):]

            # 处理 MOTD 格式 - 使用新的解析函数
            plain_motd = "No MOTD"
            html_motd = "No MOTD"
            if "description" in server_info:
                plain_motd, html_motd = parse_motd(server_info["description"])

            return {
                "online": True,
                "host": host,
                "port": port,
                "version": server_info.get("version", {}).get("name", "Unknown"),
                "protocol": server_info.get("version", {}).get("protocol", -1),
                "motd_plain": plain_motd,
                "motd_html": html_motd,
                "players": {
                    "online": server_info.get("players", {}).get("online", 0),
                    "max": server_info.get("players", {}).get("max", 0),
                    "list": players
                },
                "ping": 0,
                "favicon": favicon_base64
            }
            
    except (socket.timeout, ConnectionRefusedError):
        return {"online": False, "host": host, "port": port, "error": "连接失败"}
    except Exception as e:
        return {"online": False, "host": host, "port": port, "error": str(e)}

def get_ping(host: str, port: int = 25565, timeout: int = 3) -> float:
    """测量服务器实际延迟 (ms)"""
    print('get_ping 测量延迟')
    try:
        start = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.send(b"\xFE\x01")  # Legacy ping packet
            sock.recv(1024)
        return (time.time() - start) * 1000
    except:
        return -1

# VarInt 编码/解码工具函数
def _pack_varint(value: int) -> bytes:
    if value < 0:
        value += (1 << 32)
    out = b""
    while True:
        byte = value & 0x7F
        value >>= 7
        out += struct.pack("B", byte | (0x80 if value > 0 else 0))
        if value == 0:
            break
    return out

def _unpack_varint(sock: socket.socket) -> int:
    data = 0
    for i in range(5):
        byte = sock.recv(1)
        if len(byte) == 0:
            break
        byte = byte[0]
        data |= (byte & 0x7F) << 7 * i
        if not byte & 0x80:
            break
    return data

def _unpack_varint_from_buffer(buffer: bytes) -> (int, bytes):
    data = 0
    count = 0
    for i in range(5):
        if len(buffer) <= i:
            break
        byte = buffer[i]
        data |= (byte & 0x7F) << 7 * i
        count += 1
        if not byte & 0x80:
            break
    return data, buffer[count:]

def _pack_string(string: str) -> bytes:
    data = string.encode("utf-8")
    return _pack_varint(len(data)) + data

def clean_motd(motd: str) -> str:
    """清理MOTD中的格式代码"""
    print('clean_motd 清理MOTD中的格式代码')
    return re.sub(r"§[0-9a-fk-or]", "", motd)

def log_server_status(server_address, start_time: datetime, end_time: datetime, motd_plain: str, start_estimated: bool = False, end_estimated: bool = False):
    """记录服务器状态到日志文件"""
    print('log_server_status 记录日志')
    cleaned_motd = motd_plain.replace('\n', ' ')  # 移除换行符
    # 格式化时间
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    if start_estimated:
        start_str += "*"  # 添加星号表示服务器上线时间早于应用启动时间
    
    if end_time:
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        if end_estimated:
            end_str += "*"  # 添加星号表示服务器下线时间晚于应用退出时间
    else:
        end_str = "无"
    
    # 创建日志条目
    log_entry = f"[{server_address}] [上线] {start_str} ~ {end_str} | MOTD: {cleaned_motd}\n"
    
    # 写入日志文件
    config = load_config()
    log_file = config.get('General', 'log_file', fallback=LOG_FILE)
    
    try:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(log_entry)
    except Exception as e:
        print(f"写入日志文件错误: {str(e)}")

def remove_last_incomplete_log_entry(server_address, start_time: datetime, start_estimated: bool = False):
    """删除最后一条不完整的日志记录（结束时间为'无'的记录）"""
    print('remove_last_incomplete_log_entry 删除最后一条不完整的日志记录（这TM有Bug）')
    config = load_config()
    log_file = config.get('General', 'log_file', fallback=LOG_FILE)
    
    try:
        # 如果日志文件不存在，直接返回
        if not os.path.exists(log_file):
            return
            
        # 读取所有日志行
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # 如果没有日志行，直接返回
        if not lines:
            return
            
        # 构建要查找的上线记录特征
        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        if start_estimated:
            start_str += "*"
        prefix = f"[{server_address}] [上线] {start_str} ~ 无 | MOTD:"
        
        # 从后向前查找匹配的行
        last_index = -1
        for i in range(len(lines)-1, -1, -1):
            if lines[i].startswith(prefix):
                last_index = i
                break
                
        # 如果找到匹配的行，删除它
        if last_index != -1:
            del lines[last_index]
            
            # 重新写入日志文件
            with open(log_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
    except Exception as e:
        print(f"删除日志记录错误: {str(e)}")

class CenterDialog(QDialog):
    """居中显示的对话框基类"""
    def showEvent(self, event):
        print('showEvent 显示')
        super().showEvent(event)
        self.center_on_screen()
        
    def center_on_screen(self):
        """将窗口居中显示在屏幕上"""
        print('center_on_screen 将窗口居中显示在屏幕上')
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move(int((screen.width() - size.width()) / 2),
                 int((screen.height() - size.height()) / 2))

class CalendarWindow(CenterDialog):
    """服务器日历可视化窗口"""
    
    def __init__(self, parent=None):
        print('CalendarWindow__init__ 服务器日历可视化窗口')
        super().__init__(parent)
        self.setWindowTitle("服务器日历")
        self.setGeometry(100, 100, 900, 600)
        self.setWindowIcon(QIcon(load_config().get('General', 'icon_path', fallback=ICON_PATH)))
        
        # 主布局
        main_layout = QVBoxLayout()
        
        # 创建顶部信息栏
        info_layout = QHBoxLayout()
        self.date_label = QLabel("选择日期查看服务器状态历史")
        info_layout.addWidget(self.date_label)
        
        # 添加刷新按钮
        self.refresh_button = QPushButton("刷新数据")
        self.refresh_button.clicked.connect(self.load_log_data)
        info_layout.addWidget(self.refresh_button)
        
        # 添加当天总时长标签
        self.daily_total_label = QLabel("当天总时长: 0小时0分钟")
        info_layout.addWidget(self.daily_total_label)
        
        # 添加统计信息标签
        self.stats_label = QLabel("")
        info_layout.addStretch()
        info_layout.addWidget(self.stats_label)
        
        main_layout.addLayout(info_layout)
        
        # 添加可视化控制栏
        viz_control_layout = QHBoxLayout()
        
        # 添加服务器选择框
        viz_control_layout.addWidget(QLabel("选择服务器:"))
        self.server_combo = QComboBox()
        self.server_combo.addItem("所有服务器")  # 默认选项
        self.server_combo.currentIndexChanged.connect(self.update_calendar_colors)  # 服务器改变时更新颜色
        viz_control_layout.addWidget(self.server_combo)
        
        # 添加可视化类型选择
        viz_control_layout.addWidget(QLabel("可视化类型:"))
        self.viz_type_combo = QComboBox()
        self.viz_type_combo.addItems(["每日时长", "每周时长", "每月时长", "按MOTD分类统计"])
        viz_control_layout.addWidget(self.viz_type_combo)
        
        # 添加时间范围选择
        viz_control_layout.addWidget(QLabel("时间范围:"))
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["最近7天", "最近30天", "全部数据"])
        viz_control_layout.addWidget(self.time_range_combo)
        
        # 添加生成按钮
        self.generate_viz_button = QPushButton("生成可视化")
        self.generate_viz_button.clicked.connect(self.generate_visualization)
        viz_control_layout.addWidget(self.generate_viz_button)
        
        # 添加复选框用于显示MOTD分类
        self.show_motd_checkbox = QCheckBox("显示MOTD详情")
        self.show_motd_checkbox.setChecked(True)
        viz_control_layout.addWidget(self.show_motd_checkbox)
        
        viz_control_layout.addStretch()
        
        main_layout.addLayout(viz_control_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 日历区域
        calendar_widget = QWidget()
        calendar_layout = QVBoxLayout(calendar_widget)
        calendar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setMinimumDate(datetime.now().date() - timedelta(days=365))
        self.calendar.setMaximumDate(datetime.now().date() + timedelta(days=30))
        self.calendar.clicked.connect(self.date_selected)
        
        # 添加日历说明
        legend_group = QGroupBox("图例说明")
        legend_layout = QVBoxLayout()
        
        # 修改为"显示颜色"复选框
        self.show_color_checkbox = QCheckBox("显示颜色") 
        # 从配置加载初始状态
        config = load_config()
        show_color = config.getboolean('Calendar', 'show_color', fallback=False)
        self.show_color_checkbox.setChecked(show_color)
        
        self.show_color_checkbox.stateChanged.connect(self.update_calendar_colors)
        self.show_color_checkbox.stateChanged.connect(self.save_show_color_setting)  # 保存配置的连接
        
        legend_layout.addWidget(self.show_color_checkbox)
        
        # 创建颜色说明
        color_info = [
            ("在线  0~4h", QColor(204,255,153)),
            ("在线  4~6h", QColor(255,255,0)),
            ("在线  6~8h", QColor(255,127,14)),
            ("在线  > 8h", QColor(255,69,0))
        ]
        
        for text, color in color_info:
            hbox = QHBoxLayout()
            color_label = QLabel()
            color_label.setFixedSize(20, 20)
            color_label.setStyleSheet(f"background-color: {color.name()}; border: 1px solid gray;")
            hbox.addWidget(color_label)
            hbox.addWidget(QLabel(text))
            hbox.addStretch()
            legend_layout.addLayout(hbox)
        
        legend_group.setLayout(legend_layout)
        
        calendar_layout.addWidget(self.calendar)
        calendar_layout.addWidget(legend_group)
        
        # 日志详情区域
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        
        detail_group = QGroupBox("服务器状态详情")
        detail_group_layout = QVBoxLayout()
        
        # 添加滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 10))
        
        scroll_area.setWidget(self.log_display)
        detail_group_layout.addWidget(scroll_area)
        detail_group.setLayout(detail_group_layout)
        
        detail_layout.addWidget(detail_group)
        
        # 添加到分割器
        splitter.addWidget(calendar_widget)
        splitter.addWidget(detail_widget)
        splitter.setSizes([300, 600])
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
        
        # 加载日志数据
        self.log_data = {}
        self.server_list = set()  # 存储所有服务器地址
        self.load_log_data()
        
        # 应用初始样式
        self.update_calendar_colors()
        
        # 默认选择今天
        self.calendar.setSelectedDate(datetime.now().date())
        self.date_selected()
        
    def save_show_color_setting(self):
        """保存'显示颜色'设置到配置文件"""
        print('save_show_color_setting 保存显示颜色设置到配置文件')
        config = load_config()
        
        # 确保Calendar部分存在
        if not config.has_section('Calendar'):
            config.add_section('Calendar')
        
        # 保存当前状态
        config.set('Calendar', 'show_color', 
                  '1' if self.show_color_checkbox.isChecked() else '0')
        
        save_config(config)

    def load_log_data(self):
        """加载并解析日志文件数据"""
        print('load_log_data 加载并解析日志文件数据')
        self.log_data = {}
        total_days = 0
        total_sessions = 0
        self.server_list = set()  # 重置服务器列表
        
        config = load_config()
        log_file = config.get('General', 'log_file', fallback=LOG_FILE)
        
        try:
            if not os.path.exists(log_file):
                self.log_display.setText("日志文件不存在")
                return
            
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 解析日志行
                    try:
                        # 示例: [127.0.0.1:25565] [上线] 2024-06-28 10:30:00 - 2024-06-28 12:45:00 | MOTD: Welcome to the server
                        if line.startswith("[") and "] [上线]" in line:
                            # 提取服务器地址
                            server_address_end = line.index("] [上线]")
                            server_address = line[1:server_address_end]
                            self.server_list.add(server_address)  # 添加到服务器列表
                            
                            parts = line[server_address_end + len("] [上线] "):].split("|")
                            time_part = parts[0].strip()
                            motd_part = parts[1].replace("MOTD:", "").strip() if len(parts) > 1 else "无MOTD"
                            
                            # 处理时间范围
                            time_range = time_part.split("~")
                            start_str = time_range[0].strip()
                            end_str = time_range[1].strip() if len(time_range) > 1 else ""
                            
                            # 解析时间
                            start_estimated = start_str.endswith("*")
                            end_estimated = end_str.endswith("*")
                            
                            start_str = start_str.rstrip("*").strip()
                            end_str = end_str.rstrip("*").strip()
                            
                            try:
                                start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                            except:
                                continue
                            
                            if end_str == "无":
                                end_time = None
                            else:
                                try:
                                    end_time = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                                except:
                                    end_time = None
                            
                            # 添加到日期索引
                            session = {
                                "server": server_address,
                                "start": start_time,
                                "end": end_time,
                                "motd": motd_part,
                                "start_estimated": start_estimated,
                                "end_estimated": end_estimated,
                                "duration": (end_time - start_time).total_seconds() if end_time else 0
                            }
                            
                            # 按日期分组
                            current_date = start_time.date()
                            while end_time is None or current_date <= end_time.date():
                                if current_date not in self.log_data:
                                    self.log_data[current_date] = []
                                
                                self.log_data[current_date].append(session)
                                current_date += timedelta(days=1)
                                
                                # 如果到达结束日期或没有结束时间（只处理一天）
                                if end_time is None or current_date > end_time.date():
                                    break
                            
                            total_sessions += 1
                    
                    except Exception as e:
                        print(f"解析日志行错误: {line}\n错误: {str(e)}")
            
            # 更新服务器选择框
            self.server_combo.clear()
            self.server_combo.addItem("所有服务器")  # 默认选项
            for server in sorted(self.server_list):
                self.server_combo.addItem(server)
            
            # 统计信息
            total_days = len(self.log_data)
            self.stats_label.setText(f"总天数: {total_days} | 总会话: {total_sessions} | 服务器数: {len(self.server_list)}")
            
        except Exception as e:
            self.log_display.setText(f"读取日志文件错误: {str(e)}")
        
        # 更新日历颜色
        self.update_calendar_colors()
    
    def update_calendar_colors(self):
        """根据日志数据更新日历颜色"""
        print('update_calendar_colors 根据日志数据更新日历颜色')
        # 获取是否显示颜色
        show_color = self.show_color_checkbox.isChecked()  # 修改这里
        
        # 重置所有日期格式为白色
        for date in self.log_data.keys():
            fmt = QTextCharFormat()
            fmt.setBackground(QBrush(Qt.white))  # 默认白色
            self.calendar.setDateTextFormat(date, fmt)
        
        # 如果不显示颜色，直接返回
        if not show_color:  # 修改这里
            return
        
        # 获取选择的服务器
        selected_server = self.server_combo.currentText()
        
        # 检查是否按服务器显示颜色
        by_server = (selected_server != "所有服务器")
        
        for date in self.log_data.keys():
            fmt = QTextCharFormat()
            
            # 获取当天的所有会话
            sessions = self.log_data[date]
            
            # 计算当天的在线时间比例
            total_seconds = 24 * 60 * 60
            online_seconds = 0
            has_data = False  # 标记当天是否有数据
            
            for session in sessions:
                # 如果按服务器显示颜色，只统计所选服务器的会话
                if by_server and session["server"] != selected_server:
                    continue
                    
                start_time = session["start"]
                end_time = session["end"] or datetime.now()
                
                # 计算当天开始和结束时间
                day_start = datetime.combine(date, datetime.min.time())
                day_end = datetime.combine(date, datetime.max.time())
                
                # 计算会话在当天的部分
                session_start = max(start_time, day_start)
                session_end = min(end_time, day_end) if end_time else day_end
                
                # 计算在线秒数
                online_seconds += (session_end - session_start).total_seconds()
                has_data = True  # 标记有数据
            
            # 如果没有数据且按服务器显示，保持白色
            if by_server and not has_data:
                continue
            
            # 计算在线比例
            online_ratio = online_seconds / total_seconds
            
            # 设置颜色
            if online_ratio < 0.166:  # 在线 < 4h
                fmt.setBackground(QBrush(QColor(204,255,153)))  # 绿色
            elif online_ratio <  0.25: # 在线 4h ~ 6h
                fmt.setBackground(QBrush(QColor(255,255,0)))  # 黄色
            elif online_ratio <  0.333: # 在线 6h ~ 8h
                fmt.setBackground(QBrush(QColor(255,127,14)))  # 橙色
            else:  # 在线 > 8h
                fmt.setBackground(QBrush(QColor(255,69,0)))  # 红色
            
            self.calendar.setDateTextFormat(date, fmt)
    
    def date_selected(self):
        """当选择日期时显示详细信息"""
        print('date_selected 选择日期 显示详细信息')
        selected_date = self.calendar.selectedDate().toPyDate()
        self.date_label.setText(f"选择的日期: {selected_date.strftime('%Y-%m-%d')}")
        
        # 获取选择的服务器
        selected_server = self.server_combo.currentText()

        # 检查是否按服务器显示（即是否选择了特定服务器）
        by_server = (selected_server != "所有服务器")  # 修改这里
        
        # 计算并显示当天总时长
        total_seconds = 0
        if selected_date in self.log_data:
            sessions = self.log_data[selected_date]
            for session in sessions:
                # 如果按服务器显示，只统计所选服务器的会话
                if by_server and selected_server != "所有服务器" and session["server"] != selected_server:
                    continue
                    
                start_time = session["start"]
                end_time = session["end"] or datetime.now()
                
                # 计算当天开始和结束时间
                day_start = datetime.combine(selected_date, datetime.min.time())
                day_end = datetime.combine(selected_date, datetime.max.time())
                
                # 计算会话在当天的部分
                session_start = max(start_time, day_start)
                session_end = min(end_time, day_end) if end_time else day_end
                
                # 计算在线秒数
                total_seconds += (session_end - session_start).total_seconds()
        
        # 转换为小时和分钟
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        self.daily_total_label.setText(f"当天总时长: {hours}小时{minutes}分钟")
        
        if selected_date in self.log_data:
            sessions = self.log_data[selected_date]
            
            # 生成显示文本
            display_text = f"<h2>服务器状态 - {selected_date.strftime('%Y-%m-%d')}</h2>"
            
            # 如果按服务器显示，添加服务器信息
            if by_server and selected_server != "所有服务器":
                display_text += f"<p>服务器: <b>{selected_server}</b></p>"
                
            # 统计该日期显示的会话数
            displayed_sessions = 0
            for session in sessions:
                if by_server and selected_server != "所有服务器" and session["server"] != selected_server:
                    continue
                displayed_sessions += 1
                    
            display_text += f"<p>共 {displayed_sessions} 个在线会话 | 总时长: {hours}小时{minutes}分钟</p>"
            
            # 添加每个会话的详情
            session_count = 0
            for session in sessions:
                # 如果按服务器显示，只显示所选服务器的会话
                if by_server and selected_server != "所有服务器" and session["server"] != selected_server:
                    continue
                    
                session_count += 1
                display_text += "<hr>"
                display_text += f"<h3>会话 {session_count}</h3>"
                display_text += f"<p><b>服务器:</b> {session['server']}</p>"
                
                start_time = session["start"]
                end_time = session["end"]
                
                # 计算在线时长
                if end_time:
                    duration = end_time - start_time
                    hours, remainder = divmod(duration.total_seconds(), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    duration_str = f"{int(hours)}小时 {int(minutes)}分钟"
                else:
                    duration_str = "仍在运行中"
                
                # 格式化时间
                start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                if session["start_estimated"]:
                    start_str += " *"
                
                end_str = end_time.strftime("%Y-%m-%d %H:%M:%S") if end_time else "无"
                if session["end_estimated"] and end_time:
                    end_str += " *"
                
                display_text += f"<p><b>上线时间:</b> {start_str}</p>"
                display_text += f"<p><b>下线时间:</b> {end_str}</p>"
                display_text += f"<p><b>持续时间:</b> {duration_str}</p>"
                display_text += f"<p><b>MOTD:</b> {session['motd']}</p>"
            
            if session_count == 0:
                display_text += "<p>该日期没有符合条件的记录</p>"
            
            self.log_display.setHtml(display_text)
        else:
            self.log_display.setText(f"{selected_date.strftime('%Y-%m-%d')} 无服务器状态记录")

    def generate_visualization(self):
        """在新窗口中生成服务器启动时间可视化图表"""
        print('generate_visualization 生成可视化')
        # 创建可视化窗口 - 增加窗口尺寸
        viz_dialog = CenterDialog(self)
        viz_dialog.setWindowTitle("服务器运行时间可视化")
        viz_dialog.setGeometry(100, 50, 1200, 800)  # 增加窗口尺寸
        
        # 使用垂直布局
        layout = QVBoxLayout(viz_dialog)
        
        # 创建matplotlib图形 - 增加图形尺寸
        figure = Figure(figsize=(12, 8), dpi=100)  # 增加图形尺寸
        canvas = FigureCanvas(figure)
        
        # 创建滚动区域以适应大图表
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(canvas)
        layout.addWidget(scroll_area)
        
        # 设置支持中文的字体 - 更可靠的方法
        font_path = None
        # 尝试查找常见的中文字体
        possible_fonts = [
            'SimHei', 'Microsoft YaHei', 'KaiTi', 'SimSun',  # Windows
            'STHeiti', 'STKaiti', 'Songti SC', 'Heiti SC',    # MacOS
            'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei',       # Linux
            'Noto Sans CJK SC', 'Source Han Sans SC'           # 跨平台
        ]
        
        # 查找系统中可用的字体
        for font_name in possible_fonts:
            try:
                font_path = fm.findfont(font_name)
                if font_path:
                    # 设置字体
                    font_prop = fm.FontProperties(fname=font_path, size=12)  # 增加字体大小
                    matplotlib.rcParams['font.family'] = font_prop.get_name()
                    matplotlib.rcParams['axes.unicode_minus'] = False
                    matplotlib.rcParams['font.size'] = 12  # 全局字体大小
                    matplotlib.rcParams['axes.titlesize'] = 16  # 标题字体大小
                    matplotlib.rcParams['axes.labelsize'] = 14  # 轴标签字体大小
                    matplotlib.rcParams['xtick.labelsize'] = 12  # X轴刻度字体大小
                    matplotlib.rcParams['ytick.labelsize'] = 12  # Y轴刻度字体大小
                    break
            except:
                continue
        
        # 如果找不到中文字体，使用默认字体并警告
        if not font_path:
            print("警告: 未找到中文字体，图表中的中文可能显示为方块")
            # 设置默认字体大小
            matplotlib.rcParams['font.size'] = 12
            matplotlib.rcParams['axes.titlesize'] = 16
            matplotlib.rcParams['axes.labelsize'] = 14
            matplotlib.rcParams['xtick.labelsize'] = 12
            matplotlib.rcParams['ytick.labelsize'] = 12
        
        ax = figure.add_subplot(111)
        
        # 获取可视化类型和时间范围
        viz_type = self.viz_type_combo.currentText()
        time_range = self.time_range_combo.currentText()
        show_motd = self.show_motd_checkbox.isChecked()
        selected_server = self.server_combo.currentText()
        by_server = (selected_server != "所有服务器")  # 修改这里
        
        # 确定时间范围
        end_date = datetime.now().date()
        if time_range == "最近7天":
            start_date = end_date - timedelta(days=7)
        elif time_range == "最近30天":
            start_date = end_date - timedelta(days=30)
        else:  # 全部数据
            if self.log_data:
                start_date = min(self.log_data.keys())
            else:
                start_date = end_date - timedelta(days=30)
        
        # 准备数据
        dates = []
        durations = []
        motd_data = defaultdict(list)
        
        current_date = start_date
        while current_date <= end_date:
            if current_date in self.log_data:
                total_seconds = 0
                for session in self.log_data[current_date]:
                    # 如果按服务器显示，只统计所选服务器的会话
                    if by_server and selected_server != "所有服务器" and session["server"] != selected_server:
                        continue
                        
                    start_time = session["start"]
                    end_time = session["end"] or datetime.now()
                    
                    # 计算当天开始和结束时间
                    day_start = datetime.combine(current_date, datetime.min.time())
                    day_end = datetime.combine(current_date, datetime.max.time())
                    
                    # 计算会话在当天的部分
                    session_start = max(start_time, day_start)
                    session_end = min(end_time, day_end) if end_time else day_end
                    
                    # 计算在线秒数
                    duration_seconds = (session_end - session_start).total_seconds()
                    total_seconds += duration_seconds
                    
                    # 按MOTD分组
                    motd = session['motd']
                    if show_motd:
                        motd_data[motd].append((current_date, duration_seconds))
                
                dates.append(current_date)
                durations.append(total_seconds / 3600)  # 转换为小时
            current_date += timedelta(days=1)
        
        if not dates:
            # 直接使用英文显示避免字体问题
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=15)
            canvas.draw()
            
            # 添加关闭按钮
            close_button = QPushButton("关闭")
            close_button.clicked.connect(viz_dialog.accept)
            layout.addWidget(close_button)
            
            viz_dialog.exec_()
            return
        
        # 根据可视化类型生成图表
        if viz_type == "每日时长":
            # 绘制每日时长柱状图
            ax.bar(dates, durations, color='skyblue', width=0.8)
            
            # 设置标题和标签 - 使用更大的字体
            title = '每日服务器在线时长'
            if by_server and selected_server != "所有服务器":
                title += f" - {selected_server}"
            ax.set_title(title, fontsize=18)
            ax.set_xlabel('日期', fontsize=16)
            ax.set_ylabel('时长 (小时)', fontsize=16)
            
            # 设置日期格式
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            figure.autofmt_xdate(rotation=30)  # 旋转日期标签避免重叠
            
            # 添加数据标签 - 使用更大的字体
            for i, v in enumerate(durations):
                if v > 0:
                    ax.text(dates[i], v + 0.1, f"{v:.1f}", 
                            ha='center', va='bottom', fontsize=12)
        
        elif viz_type == "每周时长":
            # 按周分组数据
            weekly_data = defaultdict(float)
            for date, duration in zip(dates, durations):
                year, week, _ = date.isocalendar()
                weekly_data[f"{year}-W{week:02d}"] += duration
            
            # 准备绘图数据
            weeks = sorted(weekly_data.keys())
            week_durations = [weekly_data[week] for week in weeks]
            
            # 绘制每周时长柱状图
            ax.bar(weeks, week_durations, color='lightgreen', width=0.6)
            
            # 设置标题和标签 - 使用更大的字体
            title = '每周服务器在线时长'
            if by_server and selected_server != "所有服务器":
                title += f" - {selected_server}"
            ax.set_title(title, fontsize=18)
            ax.set_xlabel('周', fontsize=16)
            ax.set_ylabel('时长 (小时)', fontsize=16)
            
            # 添加数据标签 - 使用更大的字体
            for i, v in enumerate(week_durations):
                if v > 0:
                    ax.text(i, v + 0.1, f"{v:.1f}", 
                            ha='center', va='bottom', fontsize=12)
        
        elif viz_type == "每月时长":
            # 按月分组数据
            monthly_data = defaultdict(float)
            for date, duration in zip(dates, durations):
                month_key = date.strftime("%Y-%m")
                monthly_data[month_key] += duration
            
            # 准备绘图数据
            months = sorted(monthly_data.keys())
            month_durations = [monthly_data[month] for month in months]
            
            # 绘制每月时长柱状图
            ax.bar(months, month_durations, color='salmon', width=0.6)
            
            # 设置标题和标签 - 使用更大的字体
            title = '每月服务器在线时长'
            if by_server and selected_server != "所有服务器":
                title += f" - {selected_server}"
            ax.set_title(title, fontsize=18)
            ax.set_xlabel('月份', fontsize=16)
            ax.set_ylabel('时长 (小时)', fontsize=16)
            
            # 添加数据标签 - 使用更大的字体
            for i, v in enumerate(month_durations):
                if v > 0:
                    ax.text(i, v + 0.1, f"{v:.1f}", 
                            ha='center', va='bottom', fontsize=12)
        
        elif viz_type == "按MOTD分类统计":
            if not motd_data:
                # 使用英文显示避免字体问题
                ax.text(0.5, 0.5, "No MOTD data available", ha='center', va='center', fontsize=15)
                canvas.draw()
                
                # 添加关闭按钮
                close_button = QPushButton("关闭")
                close_button.clicked.connect(viz_dialog.accept)
                layout.addWidget(close_button)
                
                viz_dialog.exec_()
                return
            
            # 准备MOTD数据
            motd_names = []
            motd_durations = []
            
            for motd, data in motd_data.items():
                total_duration = sum(duration for _, duration in data) / 3600  # 转换为小时
                motd_names.append(motd[:20] + "..." if len(motd) > 20 else motd)
                motd_durations.append(total_duration)
            
            # 排序按时长降序
            sorted_indices = np.argsort(motd_durations)[::-1]
            sorted_names = [motd_names[i] for i in sorted_indices]
            sorted_durations = [motd_durations[i] for i in sorted_indices]
            
            # 如果MOTD太多，只显示前10个，其余合并为"其他"
            max_items = 10
            if len(sorted_durations) > max_items:
                other_duration = sum(sorted_durations[max_items:])
                sorted_durations = sorted_durations[:max_items]
                sorted_names = sorted_names[:max_items]
                
                # 添加"其他"类别
                sorted_durations.append(other_duration)
                sorted_names.append("其他")
            
            # 绘制饼图 - 使用更大的字体
            title = '按MOTD分类的服务器在线时长'
            if by_server and selected_server != "所有服务器":
                title += f" - {selected_server}"
            ax.set_title(title, fontsize=18)
            ax.pie(sorted_durations, labels=sorted_names, autopct='%1.1f%%', 
                  startangle=90, textprops={'fontsize': 14})  # 增加字体大小
            ax.axis('equal')  # 确保饼图是圆的
        
        # 设置网格
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.clicked.connect(viz_dialog.accept)
        layout.addWidget(close_button)
        
        # 调整布局并显示窗口
        viz_dialog.setLayout(layout)
        
        # 绘制图表并显示窗口
        canvas.draw()
        viz_dialog.exec_()

class ServerListItem(QWidget):
    """自定义服务器列表项，包含通知设置"""
    removed = pyqtSignal(str)# 添加移除信号

    def __init__(self, server_address, parent=None):
        print('ServerListItem__init__ 自定义服务器列表项')
        super().__init__(parent)
        self.server_address = server_address
        
        layout = QGridLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 服务器地址标签 - 使用省略号处理长地址
        self.address_label = QLabel(server_address)
        self.address_label.setToolTip(server_address)  # 悬停时显示完整地址
        self.address_label.setFixedWidth(200)  # 固定宽度确保对齐
        self.address_label.setStyleSheet("QLabel { qproperty-alignment: 'AlignVCenter | AlignLeft; }")
        layout.addWidget(self.address_label, 0, 0)
        
        # 通知设置复选框 - 使用网格布局确保对齐
        self.popup_check = QCheckBox("上线弹窗")
        self.popup_check.setToolTip("服务器上线时显示弹窗通知")
        layout.addWidget(self.popup_check, 0, 1)
        
        self.online_check = QCheckBox("上线通知")
        self.online_check.setToolTip("服务器上线时显示托盘通知")
        layout.addWidget(self.online_check, 0, 2)
        
        self.offline_check = QCheckBox("离线通知")
        self.offline_check.setToolTip("服务器离线时显示通知")
        layout.addWidget(self.offline_check, 0, 3)

        # 添加"忽略MOTD变化"复选框
        self.ignore_motd_check = QCheckBox("忽略MOTD变化")
        self.ignore_motd_check.setToolTip("针对动态MOTD")
        layout.addWidget(self.ignore_motd_check, 0, 4)
        
        # 移除按钮
        self.remove_button = QPushButton("移除")
        self.remove_button.setFixedWidth(80)
        self.remove_button.clicked.connect(self.remove_self)
        layout.addWidget(self.remove_button, 0, 5)

        # 设置列比例，确保对齐
        layout.setColumnStretch(0, 3)  # 服务器地址列
        layout.setColumnStretch(1, 2)  # 上线弹窗
        layout.setColumnStretch(2, 2)  # 上线通知
        layout.setColumnStretch(3, 2)  # 离线通知
        layout.setColumnStretch(4, 2)  # 忽略MOTD变化
        layout.setColumnStretch(5, 1)  # 移除按钮
        
        self.setLayout(layout)
    
    def get_notification_settings(self):
        """获取通知设置"""
        print('get_notification_settings 获取通知设置')
        return (
            int(self.popup_check.isChecked()),
            int(self.online_check.isChecked()),
            int(self.offline_check.isChecked()),
            int(self.ignore_motd_check.isChecked())  # 添加忽略MOTD设置
        )
    
    def remove_self(self):
        """移除自身"""
        print('remove_self 服务器移除')
        self.removed.emit(self.server_address)  # 发出移除信号
        self.deleteLater()

class ServerCheckerThread(QThread):
    """后台线程用于检查服务器状态"""
    status_changed = pyqtSignal(dict, str)  # 服务器状态和消息
    
    def __init__(self, server_address):
        print('ServerCheckerThread__init__ 后台线程-检查服务器状态')
        super().__init__()
        self.server_address = server_address
        self.host, self.port = parse_server_address(server_address)
        self.last_status = None
        self.running = True
        self.last_online_status = None  # 记录上一次的在线状态
        self.current_session_start = None  # 当前上线会话的开始时间
        self.current_session_motd = None  # 当前上线会话的MOTD
        self.last_motd = None  # 上一次的MOTD
        self.initial_check = True  # 标记是否为初始检查
        self.force_check = False  # 强制检查标志
        self.start_estimated = False  # 记录当前会话的开始时间是否是估计的
        self.ignore_motd = False  # 是否忽略MOTD变化
    
    def run(self):
        """线程主循环"""
        print(threading.current_thread().name+'-run-线程主循环')
        config = load_config()
        check_interval = int(config.get('General', 'check_interval', fallback=180))
        settings_str=config.get('ServerNotifications', self.server_address, fallback='1110')
        settings = [bool(int(x)) for x in settings_str] if settings_str else [True, True, True, False]
        self.ignore_motd=settings[3]
        
        # 初始状态检测
        info = get_server_info(self.host, self.port)
        if info.get("online", False):
            info["ping"] = get_ping(self.host, self.port)

        # 处理初始状态
        if info["online"]:
            # 应用启动时服务器在线，记录上线时间为当前时间
            self.current_session_start = datetime.now()
            self.current_session_motd = info["motd_plain"]
            self.last_motd = info["motd_plain"]
            self.last_online_status = True
            self.start_estimated = True  # 标记为估计的上线时间
            # 记录日志，标记开始时间为估计值
            log_server_status(
                self.server_address,
                self.current_session_start,
                None,
                self.current_session_motd,
                start_estimated=True
            )
        else:
            # 应用启动时服务器离线，不记录
            self.last_online_status = False
            self.start_estimated = False
        
        # 标记初始检查完成
        self.initial_check = False

        while self.running:
            # 获取服务器信息
            info = get_server_info(self.host, self.port)
            
            # 测量延迟
            if info.get("online", False):
                info["ping"] = get_ping(self.host, self.port)
            
            # 检测状态变化
            current_online = info["online"]

            # 状态变化处理
            if self.last_online_status is None or self.last_online_status != current_online:
                if current_online:
                    # 服务器上线
                    self.current_session_start = datetime.now()
                    self.current_session_motd = info["motd_plain"]
                    self.last_motd = info["motd_plain"]
                    self.start_estimated = False  # 正常检测到的上线
                    
                    # 记录日志
                    log_server_status(
                        self.server_address,
                        self.current_session_start,
                        None,
                        self.current_session_motd
                    )
                else:
                    # 服务器下线
                    if self.current_session_start:
                        # 删除之前的不完整记录
                        remove_last_incomplete_log_entry(
                            self.server_address,
                            self.current_session_start,
                            self.start_estimated
                        )
                        
                        # 记录完整日志，保留开始时间的估计标记
                        log_server_status(
                            self.server_address,
                            self.current_session_start,
                            datetime.now(),
                            self.current_session_motd,
                            start_estimated=self.start_estimated
                        )
                        self.current_session_start = None
                        self.current_session_motd = None
                        self.last_motd = None
                        self.start_estimated = False
                
                # 更新状态
                self.last_online_status = current_online
            elif current_online and self.last_online_status:
                # 状态保持在线，但MOTD发生变化 - 服务器重启
                current_motd = info["motd_plain"]
                if self.last_motd and self.last_motd != current_motd and not self.ignore_motd:
                    # 删除之前的不完整记录
                    if self.current_session_start:
                        remove_last_incomplete_log_entry(
                            self.server_address,
                            self.current_session_start,
                            self.start_estimated
                        )
                    
                    # 记录服务器下线（重启）
                    log_server_status(
                        self.server_address,
                        self.current_session_start,
                        datetime.now(),
                        self.last_motd,
                        start_estimated=self.start_estimated
                    )
                    
                    # 记录服务器上线（重启后）
                    self.current_session_start = datetime.now()
                    self.current_session_motd = current_motd
                    self.last_motd = current_motd
                    self.start_estimated = False  # 新的会话是正常检测到的
                    
                    # 记录上线事件
                    log_server_status(
                        self.server_address,
                        self.current_session_start,
                        None,
                        self.current_session_motd
                    )
                else:
                    # 更新最后MOTD
                    self.last_motd = current_motd

            # 生成状态消息
            timestamp = datetime.now().strftime("%H:%M:%S")
            status_msg = f"[{timestamp}] [{self.server_address}] 服务器状态: "
            
            if info["online"]:
                cleaned_motd = info["motd_plain"]
                status_msg += f"✅ 在线 | 延迟: {info['ping']:.2f} ms | 玩家: {info['players']['online']}/{info['players']['max']}"
                
                # 如果服务器状态从离线变为在线，发送通知
                if self.last_status is None or not self.last_status["online"]:
                    self.status_changed.emit(info, "online")
            else:
                status_msg += f"❌ 离线 - {info.get('error', '未知错误')}"
                self.status_changed.emit(info, "offline")
            
            # 更新最后状态
            self.last_status = info
            self.status_changed.emit(info, status_msg)
            
            # 等待指定间隔或直到强制检查
            for i in range(check_interval):
                if not self.running:
                    return
                if self.force_check:
                    self.force_check = False
                    break
                time.sleep(1)
    
    def request_force_check(self):
        """请求立即执行一次服务器检查"""
        print('request_force_check 请求立即执行一次服务器检查')
        self.force_check = True
    
    def stop(self):
        """停止线程"""
        print('stop 停止线程')
        self.running = False
        
        # 如果服务器在线时退出，记录下线时间为当前时间（带星号）
        if self.current_session_start:
            # 删除之前的不完整记录
            remove_last_incomplete_log_entry(
                self.server_address,
                self.current_session_start,
                self.start_estimated
            )
            
            # 记录完整日志，保留开始时间的估计标记
            log_server_status(
                self.server_address,
                self.current_session_start,
                datetime.now(),
                self.current_session_motd,
                start_estimated=self.start_estimated,
                end_estimated=True
            )

class SettingsDialog(CenterDialog):
    """设置对话框（添加按服务器通知设置）"""
    
    def __init__(self, parent=None):
        print('SettingsDialog__init__ 设置')
        super().__init__(parent)
        self.setWindowTitle("服务器监控设置(部分设置重启生效)")
        self.setGeometry(200, 200, 900, 600)  # 增加宽度和高度以容纳更多内容
        self.setWindowIcon(QIcon(load_config().get('General', 'icon_path', fallback=ICON_PATH)))
        
        # 主布局
        layout = QVBoxLayout()
        
        # 常规设置组
        general_group = QGroupBox("常规设置")
        general_layout = QGridLayout()
        
        # 检查间隔设置
        general_layout.addWidget(QLabel("检查间隔 (秒):"), 0, 0)
        self.interval_edit = QLineEdit()
        self.interval_edit.setValidator(QIntValidator(10, 86400, self))  # 10秒到1天
        general_layout.addWidget(self.interval_edit, 0, 1)
        
        # 日志文件设置
        general_layout.addWidget(QLabel("日志文件路径:"), 1, 0)
        self.log_file_edit = QLineEdit()
        general_layout.addWidget(self.log_file_edit, 1, 1)
        
        # 图标路径设置
        general_layout.addWidget(QLabel("托盘图标路径:"), 2, 0)
        self.icon_path_edit = QLineEdit()
        general_layout.addWidget(self.icon_path_edit, 2, 1)
        
        general_group.setLayout(general_layout)
        layout.addWidget(general_group)
        
        # 全局通知设置组
        global_notification_group = QGroupBox("全局通知设置")
        global_notification_layout = QVBoxLayout()

        self.startup_notify_check = QCheckBox("显示启动通知")
        global_notification_layout.addWidget(self.startup_notify_check)
        
        self.global_refresh_notify_check = QCheckBox("显示刷新提示")
        self.global_refresh_notify_check.setToolTip("为所有服务器启用刷新提示")
        global_notification_layout.addWidget(self.global_refresh_notify_check)

        self.global_setting_notify_check = QCheckBox("设置保存提示")
        global_notification_layout.addWidget(self.global_setting_notify_check)
        
        global_notification_group.setLayout(global_notification_layout)
        layout.addWidget(global_notification_group)
        
        # 服务器设置组 - 增加高度比例
        servers_group = QGroupBox("服务器列表")
        servers_layout = QVBoxLayout()
        
        # 添加服务器按钮
        self.add_button = QPushButton("添加服务器")
        self.add_button.clicked.connect(self.add_server)
        servers_layout.addWidget(self.add_button)
        
        # 服务器列表标题 - 使用网格布局确保对齐
        title_widget = QWidget()
        title_layout = QGridLayout(title_widget)
        title_layout.setContentsMargins(5, 5, 5, 5)

        
        # 设置列比例，确保对齐
        title_layout.setColumnStretch(0, 3)  # 服务器地址列
        title_layout.setColumnStretch(1, 2)  # 上线弹窗
        title_layout.setColumnStretch(2, 2)  # 上线通知
        title_layout.setColumnStretch(3, 2)  # 离线通知
        title_layout.setColumnStretch(4, 2)  # 忽略MOTD变化
        title_layout.setColumnStretch(5, 1)  # 操作按钮
        
        servers_layout.addWidget(title_widget)
        
        # 服务器列表滚动区域 - 增加高度
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        
        scroll_area.setWidget(scroll_content)
        scroll_area.setMinimumHeight(250)  # 增加滚动区域高度
        servers_layout.addWidget(scroll_area)
        
        servers_group.setLayout(servers_layout)
        layout.addWidget(servers_group, 1)  # 增加高度比例
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # 存储服务器列表项的字典
        self.server_items = {}
        
        # 加载当前设置
        self.load_settings()

        self.removed_servers = set() # 添加这个集合来跟踪被移除的服务器
    
    def load_settings(self):
        """加载当前设置"""
        print('load_settings 加载当前设置')
        config = load_config()
        
        # 常规设置
        self.interval_edit.setText(config.get('General', 'check_interval', fallback='180'))
        self.log_file_edit.setText(config.get('General', 'log_file', fallback=LOG_FILE))
        self.icon_path_edit.setText(config.get('General', 'icon_path', fallback=ICON_PATH))
        
        # 全局通知设置
        self.startup_notify_check.setChecked(config.getboolean('Notifications', 'show_startup_notification', fallback=True))
        self.global_refresh_notify_check.setChecked(config.getboolean('Notifications', 'show_refresh_notification', fallback=True))
        self.global_setting_notify_check.setChecked(config.getboolean('Notifications', 'show_setting_notification', fallback=True))
        
        # 清空滚动区域
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 加载服务器列表和通知设置
        servers = config.get('Servers', 'servers', fallback='127.0.0.1:25565').split('\n')
    
        # 打印所有服务器通知设置以进行调试
        print("ServerNotifications 部分的所有设置:")
        if config.has_section('ServerNotifications'):
            for server_key in config.options('ServerNotifications'):
                print(f"  {server_key}:{config.get('ServerNotifications', server_key)}")
        
        for server in servers:
            server = server.strip()
            if server and is_valid_server_address(server):
                print(f"处理服务器: {server}")
                
                # 尝试不同的键格式
                keys_to_try = [
                    server,  # 原始格式
                    server.replace(' ', ''),  # 移除空格
                ]
                found = False
                settings_str = ""
                
                # 尝试不同的键格式
                for key in keys_to_try:
                    if config.has_option('ServerNotifications', key):
                        settings_str = config.get('ServerNotifications', key)
                        print(f"  找到设置 ({key}): {settings_str}")
                        found = True
                        break
                
                if not found:
                    print(f"  未找到 {server} 的设置，使用默认值 '0000'")
                    settings_str = "0000"
                
                # 确保设置值是4位数字
                if len(settings_str) < 4:
                    # 不足3位时用0填充
                    settings_str = settings_str.ljust(4, '0')
                    print(f"  设置值不足4位，填充为: {settings_str}")
                else:
                    # 只取前4位
                    settings_str = settings_str[:4]
                
                # 转换为整数列表
                try:
                    settings = [int(x) for x in settings_str]
                    print(f"  转换后的设置: {settings}")
                except ValueError:
                    print(f"  转换失败，使用默认值 [0, 0, 0, 0]")
                    settings = [0, 0, 0, 0]

                # 创建列表项
                item = ServerListItem(server)
                item.popup_check.setChecked(settings[0] == 1)
                item.online_check.setChecked(settings[1] == 1)
                item.offline_check.setChecked(settings[2] == 1)
                item.ignore_motd_check.setChecked(settings[3] == 1)  # 忽略MOTD设置

                item.removed.connect(self.handle_server_removed)
                self.scroll_layout.addWidget(item)
                self.server_items[server] = item

                self.removed_servers = set()  # 每次加载设置时重置
    
    def save_settings(self):
        """保存设置到配置文件"""
        print('save_settings 保存设置')
        config = load_config()
        
        # 常规设置
        config.set('General', 'check_interval', self.interval_edit.text())
        config.set('General', 'log_file', self.log_file_edit.text())
        config.set('General', 'icon_path', self.icon_path_edit.text())
        
        # 全局通知设置
        config.set('Notifications', 'show_startup_notification', 
                  '1' if self.startup_notify_check.isChecked() else '0')
        config.set('Notifications', 'show_refresh_notification', 
                  '1' if self.global_refresh_notify_check.isChecked() else '0')
        config.set('Notifications', 'show_setting_notification', 
                  '1' if self.global_setting_notify_check.isChecked() else '0')
        
        # 保存服务器列表
        servers = []
    
        # 确保 ServerNotifications 部分存在
        if not config.has_section('ServerNotifications'):
            config.add_section('ServerNotifications')
        
        # 打印当前要保存的设置
        print("保存服务器通知设置:")

        for server in self.removed_servers:
            if config.has_option('ServerNotifications', server):
                config.remove_option('ServerNotifications', server)
                print(f"  已移除服务器设置: {server}")
        
        for server, item in list(self.server_items.items()):
            # 检查项是否仍然有效
            if item and item.parent():
                settings = item.get_notification_settings()
                settings_str = ''.join(map(str, settings))
                
                # 使用原始服务器地址作为键
                config.set('ServerNotifications', server, settings_str)
                servers.append(server)
                print(f"  保存服务器设置: {server} -> {settings_str}")
            else:
                # 如果项无效，从字典中移除
                del self.server_items[server]
        
        config.set('Servers', 'servers', "\n".join(servers))
        
        save_config(config)
        
        # 保存后打印配置文件内容以验证
        print("配置文件内容:")
        with open(CONFIG_FILE, 'r') as f:
            print(f.read())
        
        return config
    
    def add_server(self):
        """添加新服务器"""
        print('add_server 添加新服务器')
        server, ok = QInputDialog.getText(
            self, 
            "添加服务器", 
            "输入服务器地址 (格式: host:port):",
            text="127.0.0.1:25565"
        )
        if ok and server:
            if ":" not in server:
                server += ":25565"
            if is_valid_server_address(server):
                # 检查是否已存在
                if server in self.server_items:
                    QMessageBox.warning(self, "服务器已存在", "该服务器已在列表中")
                    return
                
                # 创建新服务器项
                item = ServerListItem(server)
                # 默认启用所有通知
                item.popup_check.setChecked(True)
                item.online_check.setChecked(True)
                item.offline_check.setChecked(True)
                item.ignore_motd_check.setChecked(False)

                item.removed.connect(self.handle_server_removed)
                self.scroll_layout.addWidget(item)
                self.server_items[server] = item
            else:
                QMessageBox.warning(self, "无效地址", "请输入有效的服务器地址 (格式: host:port)")
    
    def accept(self):
        """保存设置并关闭对话框"""
        print('accept 保存设置并关闭对话框')
        try:
            # 验证输入
            try:
                interval = int(self.interval_edit.text())
                if interval < 10:
                    raise ValueError("检查间隔不能小于10秒")
            except ValueError:
                QMessageBox.warning(self, "无效值", "请输入有效的检查间隔（大于10的整数）")
                return
                
            # 确保至少有一个服务器
            if not self.server_items:
                QMessageBox.warning(self, "无服务器", "请至少添加一个服务器")
                return
                
            # 保存设置
            self.save_settings()
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置时出错: {str(e)}")
            
    def handle_server_removed(self, server_address):
        """处理服务器项移除信号"""
        print('handle_server_removed 处理服务器项移除信号')
        if server_address in self.server_items:
            del self.server_items[server_address]  # 从字典中移除
            self.removed_servers.add(server_address)  # 添加到被移除集合

class MinecraftServerMonitor(QApplication):
    """Minecraft服务器监控托盘应用"""
    
    def __init__(self, args):
        print('MinecraftServerMonitor__init__ Minecraft服务器监控托盘应用')
        super().__init__(args)
        self.setQuitOnLastWindowClosed(False)
        self.config = load_config()
        
        # 设置托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        self.update_tray_icon()
        
        # 创建托盘菜单
        self.menu = QMenu()
        
        # 添加菜单项
        self.status_menu = self.menu.addMenu("服务器状态")
        self.menu.addSeparator()
        
        # 添加立即刷新按钮
        self.refresh_action = self.menu.addAction("全部刷新")
        self.refresh_action.triggered.connect(self.force_refresh_all)
        
        self.view_info_action = self.menu.addAction("查看所有服务器状态")
        self.view_info_action.triggered.connect(self.show_all_server_info)
        
        self.view_log_action = self.menu.addAction("查看日志")
        self.view_log_action.triggered.connect(self.show_log)
        
        # 添加服务器日历菜单项
        self.calendar_action = self.menu.addAction("服务器日历")
        self.calendar_action.triggered.connect(self.show_calendar)
        
        # 添加设置菜单项
        self.settings_action = self.menu.addAction("设置")
        self.settings_action.triggered.connect(self.show_settings)
        
        self.menu.addSeparator()
        self.quit_action = self.menu.addAction("退出")
        self.quit_action.triggered.connect(self.quit_app)
        
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        
        # 设置服务器检查器
        self.server_checkers = []
        self.server_statuses = {}
        
        # 加载服务器列表
        servers = self.config.get('Servers', 'servers', fallback='127.0.0.1:25565').split('\n')
        for server in servers:
            if server.strip() and is_valid_server_address(server.strip()):
                self.add_server_checker(server.strip())
        
        # 显示启动通知（如果启用）
        if self.config.getboolean('Notifications', 'show_startup_notification', fallback=True):
            self.tray_icon.showMessage(
                "服务器监控已启动",
                f"开始监控 {len(self.server_checkers)} 个服务器",
                QSystemTrayIcon.Information,
                3000
            )
    
    def add_server_checker(self, server_address):
        """添加一个新的服务器检查器"""
        print('add_server_checker 添加一个新的服务器检查器')
        # 获取该服务器的通知设置
        config = load_config()
        settings_str = config.get('ServerNotifications', server_address, fallback='0000')
        
        # 确保设置值是4位数字
        if len(settings_str) < 4:
            settings_str = settings_str.ljust(4, '0')
        
        checker = ServerCheckerThread(server_address)
        checker.status_changed.connect(self.update_status)
        checker.start()
        self.server_checkers.append(checker)
        
        # 初始化状态
        self.server_statuses[server_address] = {
            'status': "初始化中...",
            'info': None
        }
        
        # 更新状态菜单
        self.update_status_menu()
    
    def remove_server_checker(self, server_address):
        """移除一个服务器检查器"""
        print('remove_server_checker 移除一个服务器检查器')
        for checker in self.server_checkers[:]:
            if checker.server_address == server_address:
                checker.stop()
                checker.wait(2000)  # 等待2秒让线程结束
                self.server_checkers.remove(checker)
                if server_address in self.server_statuses:
                    del self.server_statuses[server_address]
                break
        
        # 更新状态菜单
        self.update_status_menu()
    
    def update_status_menu(self):
        """更新状态菜单"""
        print('update_status_menu 更新状态菜单')
        self.status_menu.clear()
        
        # 添加每个服务器的状态
        for server_address, status_info in self.server_statuses.items():
            action = self.status_menu.addAction(f"{server_address}: {status_info['status']}")
            action.setEnabled(False)
        
        # 添加分隔符
        self.status_menu.addSeparator()
        
        # 添加查看所有服务器详细信息的选项
        view_all_action = self.status_menu.addAction("查看所有服务器状态")
        view_all_action.triggered.connect(self.show_all_server_info)
    
    def update_tray_icon(self):
        """更新托盘图标"""
        print('update_tray_icon 更新托盘图标')
        icon_path = self.config.get('General', 'icon_path', fallback=ICON_PATH)
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            print(f"警告: 图标文件 {icon_path} 不存在，使用默认图标")
            # 创建一个简单的默认图标
            self.tray_icon.setIcon(self.style().standardIcon(QApplication.style().SP_ComputerIcon))
    
    def force_refresh_all(self):
        """立即刷新所有服务器状态"""
        print('force_refresh_all 立即刷新')
        for checker in self.server_checkers:
            checker.request_force_check()
        
        # 显示刷新提示（如果启用）
        if self.config.getboolean('Notifications', 'show_refresh_notification', fallback=True):
            self.tray_icon.showMessage(
                "刷新请求已发送",
                "正在立即检查所有服务器状态...",
                QSystemTrayIcon.Information,
                2000
            )
    
    def show_settings(self):
        """显示设置对话框"""
        print('show_settings 显示设置对话框')
        try:
            settings_dialog = SettingsDialog()
            if settings_dialog.exec_() == QDialog.Accepted:
                # 保存设置
                new_config = settings_dialog.save_settings()
                
                # 更新托盘图标
                self.update_tray_icon()
                
                # 重新加载服务器列表
                new_servers = set()
                for server in new_config.get('Servers', 'servers').split('\n'):
                    if server.strip() and is_valid_server_address(server.strip()):
                        new_servers.add(server.strip())
                
                current_servers = set(self.server_statuses.keys())
                
                # 添加新服务器
                for server in new_servers - current_servers:
                    self.add_server_checker(server)
                
                # 移除不再存在的服务器
                for server in current_servers - new_servers:
                    self.remove_server_checker(server)
                
                # 更新状态
                if new_config.getboolean('Notifications', 'show_setting_notification', fallback=True):
                    self.tray_icon.showMessage(
                        "设置已保存",
                        "服务器监控设置已更新",
                        QSystemTrayIcon.Information,
                        2000
                    )
        except Exception as e:
            QMessageBox.critical(None, "设置错误", f"打开设置对话框时出错: {str(e)}")
    
    def show_calendar(self):
        """显示服务器日历窗口"""
        print('show_calendar 显示服务器日历窗口')
        try:
            self.calendar_window = CalendarWindow()
            self.calendar_window.exec_()
        except Exception as e:
            QMessageBox.critical(None, "错误", f"无法打开日历窗口: {str(e)}")
    
    def update_status(self, info, message):
        """更新服务器状态"""
        print('update_status')
        server_address = f"{info['host']}:{info['port']}"
        
        # 更新状态
        self.server_statuses[server_address] = {
            'status': message,
            'info': info
        }

        # 获取该服务器的通知设置
        config = load_config()
        settings_str = config.get('ServerNotifications', server_address, fallback='1110')
        settings = [bool(int(x)) for x in settings_str] if settings_str else [True, True, True, False]
        popup_enabled, online_enabled, offline_enabled, ignore = settings
        
        # 更新状态菜单
        self.update_status_menu()
        
        # 更新托盘工具提示
        online_count = sum(1 for s in self.server_statuses.values() if s['info'] and s['info']['online'])
        total_count = len(self.server_statuses)
        
        self.tray_icon.setToolTip(
            f"Minecraft服务器监控\n"
            f"监控服务器数: {total_count}\n"
            f"在线服务器: {online_count}\n"
            f"上次检查: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        # 如果服务器在线，显示通知
        if message == "online":
            # 系统托盘通知
            if online_enabled:
                self.tray_icon.showMessage(
                    "服务器在线通知",
                    f"{server_address} 服务器已上线!",
                    QSystemTrayIcon.Information,
                    5000  # 显示5秒
                )
            
            # Windows消息弹窗
            if popup_enabled:
                QMessageBox.information(
                    None,
                    "服务器在线通知",
                    f"{server_address} 服务器已上线!\n\n"
                    f"版本: {info['version']}\n"
                    f"玩家: {info['players']['online']}/{info['players']['max']}\n"
                    f"延迟: {info['ping']:.0f}ms",
                    QMessageBox.Ok
                )
        # 如果服务器离线，显示通知
        elif message == "offline":
            if offline_enabled:
                self.tray_icon.showMessage(
                    "服务器离线通知",
                    f"{server_address} 服务器已离线!",
                    QSystemTrayIcon.Information,
                    5000  # 显示5秒
                )
    
    def show_all_server_info(self):
        """显示所有服务器详细信息"""
        print('show_all_server_info 显示所有服务器详细信息')
        # 创建自定义对话框显示信息
        info_dialog = CenterDialog()
        info_dialog.setWindowTitle("所有服务器状态")
        info_dialog.setGeometry(100, 100, 900, 700)

        info_dialog.setStyleSheet("background-color: #333333; color: white;")
        
        layout = QVBoxLayout()
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background-color: #333333; border: none;")  # 设置滚动区域背景

        # 创建内容容器
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #333333;")  # 设置内容背景
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignTop)
        
        # 添加标题
        title_label = QLabel("<h2 style='color: white;'>服务器状态概览</h2>")
        content_layout.addWidget(title_label)
        
        # 获取所有服务器地址
        server_addresses = list(self.server_statuses.keys())
        
        # 遍历所有服务器状态
        for idx, server_address in enumerate(server_addresses):
            status_info = self.server_statuses[server_address]
            info = status_info['info']
            if not info:
                # 初始化中...
                status_label = QLabel(f"<b style='color: white;'>{server_address}</b>: 初始化中...")
                content_layout.addWidget(status_label)
                continue

            # 创建服务器信息组框
            server_group = QGroupBox(server_address)
            # 设置服务器信息区域的背景为灰色
            server_group.setStyleSheet("""
                QGroupBox {
                    background-color: #333333;
                    color: white;
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 1ex;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top center;
                    padding: 0 5px;
                    background-color: #333333;
                    color: white;
                }
            """)
            server_layout = QVBoxLayout()
            
            # 添加状态行
            if not info["online"]:
                status_label = QLabel(f"❌ 离线<br>错误: {info.get('error', '未知错误')}")
                server_layout.addWidget(status_label)
            else:
                # 在线状态 - 添加图标和详细信息
                hbox = QHBoxLayout()

                # 左侧：图标
                icon_label = QLabel()
                icon_label.setFixedSize(64, 64)  # 固定图标大小
                icon_label.setAlignment(Qt.AlignCenter)
                icon_label.setStyleSheet("background-color: #444444;")  # 图标背景稍亮

                # 如果有图标数据，显示图标
                if "favicon" in info and info["favicon"]:
                    pixmap = base64_to_pixmap(info["favicon"])
                    if pixmap and not pixmap.isNull():
                        # 缩放图标以适应标签
                        pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        icon_label.setPixmap(pixmap)
                    else:
                        # 没有有效图标时显示占位符
                        icon_label.setText("<span style='color: white;'>无图标</span>")

                else:
                    # 没有图标数据时显示占位符
                    icon_label.setText("<span style='color: white;'>无图标</span>")

                hbox.addWidget(icon_label)

                # 右侧：详细信息
                details = QTextEdit()  # 使用QTextEdit以支持内部滚动和富文本
                details.setReadOnly(True)
                details.setStyleSheet("""
                    QTextEdit {
                        background-color: #333333;
                        color: white;  /* 默认文字颜色为白色 */
                        border: none;
                    }
                """)
                
                motd_html = info.get("motd_html", "No MOTD")
                motd_html = motd_html.replace('\n', '<br>')

                player_list = ""
                if "players" in info and "list" in info["players"]:
                    players = info["players"]["list"]
                    player_list = "<br>".join([f"  - <span style='color: white;'>{p}</span>" for p in players[:10]])
                    if len(players) > 10:
                        player_list += f"<br>  <span style='color: white;'>... 和 {len(players) - 10} 其他玩家</span>"
                    
                # 所有文本使用白色，除了MOTD保持原有颜色
                details.setHtml(
                    f"<span style='color: white;'><b>状态:</b> ✅ 在线</span><br>"
                    f"<span style='color: white;'><b>延迟:</b> {info['ping']:.2f} ms</span><br>"
                    f"<span style='color: white;'><b>版本:</b> {info['version']} (协议: {info['protocol']})</span><br>"
                    f"<b>MOTD:</b><br>{motd_html}<br>"
                    f"<span style='color: white;'><b>玩家:</b> {info['players']['online']}/{info['players']['max']}</span><br>"
                    f"<span style='color: white;'><b>在线玩家:</b></span><br>{player_list if player_list else '<span style=\'color: white;\'>无信息</span>'}"
                )
                
                # 设置合适的固定高度
                details.setFixedHeight(220)
                details.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                
                hbox.addWidget(details, 1)
                server_layout.addLayout(hbox)

            server_group.setLayout(server_layout)
            content_layout.addWidget(server_group)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        # 添加关闭按钮
        close_button = QPushButton("关闭")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: 1px solid #777777;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        close_button.clicked.connect(info_dialog.accept)
        layout.addWidget(close_button)

        info_dialog.setLayout(layout)
        info_dialog.exec_()

    def show_log(self):
        """显示日志内容"""
        print('show_log 显示日志内容')
        try:
            log_file = self.config.get('General', 'log_file', fallback=LOG_FILE)
            
            if not os.path.exists(log_file):
                QMessageBox.information(None, "日志文件", "日志文件不存在")
                return
                
            with open(log_file, "r", encoding="utf-8") as log_file:
                log_content = log_file.read()
                
            # 创建自定义对话框显示日志
            log_dialog = CenterDialog()
            log_dialog.setWindowTitle("服务器状态日志")
            log_dialog.setGeometry(100, 100, 800, 600)
            
            layout = QVBoxLayout()
            
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            
            content = QTextEdit()
            content.setReadOnly(True)
            content.setPlainText(log_content)
            content.setFont(QFont("Consolas", 10))
            
            scroll_area.setWidget(content)
            layout.addWidget(scroll_area)
            
            close_button = QPushButton("关闭")
            close_button.clicked.connect(log_dialog.accept)
            layout.addWidget(close_button)
            
            log_dialog.setLayout(layout)
            log_dialog.exec_()
        except Exception as e:
            QMessageBox.critical(None, "错误", f"无法读取日志文件: {str(e)}")
    
    def quit_app(self):
        """退出应用程序"""
        print('quit_app 退出应用程序')
        for checker in self.server_checkers:
            checker.stop()
            checker.wait(2000)  # 等待2秒让线程结束
        self.quit()

def hide_console_window():
    """隐藏控制台窗口（仅Windows）"""
    print('hide_console_window 隐藏控制台窗口')
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        hWnd = kernel32.GetConsoleWindow()
        if hWnd:
            user32.ShowWindow(hWnd, 0)  # 0 = SW_HIDE

if __name__ == "__main__":
    # 如果是Windows系统，隐藏控制台窗口
    hide_console_window()
    
    # 创建应用程序实例
    app = MinecraftServerMonitor(sys.argv)
    
    # 运行应用程序
    sys.exit(app.exec_())
