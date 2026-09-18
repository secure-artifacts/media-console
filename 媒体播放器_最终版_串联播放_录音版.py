import sys
import platform
import random
import json
import ctypes
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from ctypes import wintypes
import vlc

# 彻底封杀底层 C/C++ 库 (FFmpeg) 绕过 Qt 强制输出的刷屏日志
sys.stderr = open(os.devnull, 'w')
os.environ["QT_LOGGING_RULES"] = "*=false"
os.environ["FFMPEG_LOG_LEVEL"] = "quiet"

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QHBoxLayout, QLabel, QFileDialog,
    QSlider, QSpinBox, QStyle, QDialog, QComboBox,
    QListWidget, QListWidgetItem, QMenu, QLineEdit,
    QMessageBox, QScrollArea, QStyledItemDelegate, QToolTip,
    QSizePolicy, QInputDialog, QStyleOptionViewItem,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QCheckBox
)
from PySide6.QtCore import (
    Qt, QTimer, QTime, QSize, QRectF, QPoint, QEvent, QSettings, QUrl, QObject, Signal, QThread
)
from PySide6.QtGui import (
    QDropEvent, QDragEnterEvent, QMouseEvent,
    QIntValidator, QPainter, QColor, QIcon, QHelpEvent,
    QShortcut, QKeySequence, QPixmap, QPen
)
from PySide6.QtMultimedia import (
    QMediaDevices, QAudioInput, QMediaCaptureSession, QMediaRecorder
)

# 尝试导入 Google Drive API 相关依赖
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False

# ==========================================
# 全局主题控制类 与 反差色算法
# ==========================================
class Theme:
    accent = "#89b4fa"

def get_contrast_color(hex_color):
    """根据主色调返回绝对反差色，保证 A-B 区段高亮框极其显眼"""
    mapping = {
        "#89b4fa": "#f9e2af",
        "#a6e3a1": "#cba6f7",
        "#f38ba8": "#94e2d5",
        "#f9e2af": "#89b4fa",
        "#cba6f7": "#a6e3a1",
        "#94e2d5": "#f38ba8",
    }
    return mapping.get(hex_color, "#ffffff")

def resource_path(filename):
    """开发运行与 PyInstaller 打包后都能找到资源文件。"""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / filename)
    try:
        candidates.append(Path(__file__).resolve().parent / filename)
    except Exception:
        pass
    candidates.append(Path.cwd() / filename)
    for path in candidates:
        if path.exists():
            return str(path)
    return str(candidates[0]) if candidates else filename

# ==========================================
# 工具方法：全局时间格式转换
# ==========================================
def format_time_ms(ms):
    total_seconds = max(0, int(ms / 1000))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def ms_to_time_tuple(ms):
    if ms < 0:
        return "", "", ""
    total_s = int(ms / 1000)
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    return str(h), str(m), str(s)

def time_tuple_to_ms(h_str, m_str, s_str):
    h = int(h_str) if h_str and h_str.strip() else 0
    m = int(m_str) if m_str and m_str.strip() else 0
    s = int(s_str) if s_str and s_str.strip() else 0
    return (h * 3600 + m * 60 + s) * 1000

# ==========================================
# 现代暗黑风格 QSS
# ==========================================
def get_qss():
    acc = Theme.accent
    return f"""
    QMainWindow, QDialog {{ background-color: #181825; }}
    QWidget {{ font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }}
    QLabel {{ color: #cdd6f4; font-size: 10pt; font-weight: bold; }}
    QLabel#TimeLabel {{ color: {acc}; font-size: 10pt; padding: 0 5px; }}
    QLabel#CenterTitle {{ color: {acc}; font-size: 14pt; font-weight: 900; }}
    QLabel#VideoPointAlert {{
        color: #f38ba8; font-size: 10pt; font-weight: 900;
        padding: 2px 8px; border-radius: 4px; background-color: #31202a;
    }}
    QPushButton {{
        background-color: #313244; color: #cdd6f4; border: none;
        border-radius: 6px; padding: 6px 10px; font-size: 9pt; font-weight: bold;
    }}
    QPushButton::menu-indicator {{ image: none; width: 0px; padding: 0px; }}
    QPushButton:hover {{ background-color: #45475a; }}
    QPushButton:pressed {{ background-color: #585b70; }}
    QPushButton#PlayButton {{ background-color: {acc}; color: #11111b; border-radius: 20px; }}
    QPushButton#PlayButton:hover {{ background-color: #b4befe; }}
    QPushButton#PlayButton:pressed {{ background-color: #74c7ec; }}
    QSlider::groove:horizontal {{ border-radius: 3px; height: 6px; background: #313244; }}
    QSlider::sub-page:horizontal {{ background: {acc}; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: #ffffff; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }}
    QSlider::handle:horizontal:hover {{ background: #89dceb; }}
    QListWidget, QTreeWidget {{
        background-color: #1e1e2e; color: #cdd6f4; border: 2px dashed #45475a;
        border-radius: 6px; padding: 8px; font-size: 10pt;
    }}
    QTreeWidget::item {{ padding: 6px; }}
    QTreeWidget::item:selected {{ background-color: {acc}; color: #11111b; }}
    QComboBox, QSpinBox {{ background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 4px; }}
    QLineEdit#JumpBox {{
        font-size: 11pt; min-width: 45px; max-width: 55px; min-height: 25px;
        background-color: #1e1e2e; border: 1px solid {acc}; color: #cdd6f4; border-radius: 4px;
    }}
    QLineEdit#PathBox {{ font-size: 9pt; min-height: 25px; background-color: #1e1e2e; border: 1px solid {acc}; color: #cdd6f4; border-radius: 4px; padding: 2px 5px; }}
    QMenu {{ background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; padding: 4px 0px; }}
    QMenu::item {{ padding: 8px 30px; background: transparent; margin: 0px; }}
    QMenu::item:selected {{ background-color: {acc}; color: #11111b; }}
    QCheckBox {{ color: #cdd6f4; font-size: 9pt; spacing: 5px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 3px; border: 1px solid #45475a; background-color: #313244; }}
    QCheckBox::indicator:checked {{ background-color: {acc}; }}
    """

# ==========================================
# Google Drive 异步上传工作线程
# ==========================================
class DriveUploadWorker(QThread):
    finished_signal = Signal(str, bool)

    def __init__(self, filepath, folder_id, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.folder_id = folder_id
        self.scopes = ['https://www.googleapis.com/auth/drive.file']

    def run(self):
        if not HAS_GDRIVE:
            self.finished_signal.emit("未安装 Google Drive API 依赖，请运行:\npip install google-api-python-client google-auth-httplib2 google-auth-oauthlib", False)
            return

        try:
            creds = None
            token_path = resource_path('token.json')
            cred_path = resource_path('credentials.json')

            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, self.scopes)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(cred_path):
                        self.finished_signal.emit(f"找不到 {cred_path} 授权文件！\n请将您的 OAuth 2.0 文件放置在软件同目录下。", False)
                        return
                    flow = InstalledAppFlow.from_client_secrets_file(cred_path, self.scopes)
                    creds = flow.run_local_server(port=0)
                
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

            service = build('drive', 'v3', credentials=creds)
            file_name = os.path.basename(self.filepath)
            
            file_metadata = {'name': file_name}
            if self.folder_id and self.folder_id.strip():
                file_metadata['parents'] = [self.folder_id.strip()]

            media = MediaFileUpload(self.filepath, mimetype='audio/mp4', resumable=True)
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
            self.finished_signal.emit(f"录音文件 [{file_name}] 已成功上传至 Google Drive！\n文件 ID: {file.get('id')}", True)
        except Exception as e:
            self.finished_signal.emit(f"上传 Google Drive 失败:\n{str(e)}", False)

# ==========================================
# 网络流媒体异步探针 (纯净版：仅伪装手机端)
# ==========================================
class YtDlpWorker(QThread):
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.original_url = url
        self.item_to_update = None
        self.fake_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

    def run(self):
        try:
            import yt_dlp
        except ImportError:
            self.error_signal.emit("未检测到 yt-dlp 核心库！\n请在终端运行: pip install -U yt-dlp")
            return

        try:
            ydl_opts = {
                'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[protocol^=http][protocol!*=dash][ext=mp4]/best[protocol^=http]/best[ext=mp4]/best',
                'quiet': True,
                'noplaylist': True,
                'no_warnings': True,
                'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web']}},
                'http_headers': {'User-Agent': self.fake_agent, 'Accept-Language': 'en-US,en;q=0.9'}
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.finished_signal.emit(info)
        except Exception as e:
            self.error_signal.emit(f"无法解析该链接:\n{str(e)}")

# ==========================================
# 独立声道录音控制类
# ==========================================
class AudioRecorder(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = QMediaCaptureSession(self)
        self.audio_input = QAudioInput(self)
        self.recorder = QMediaRecorder(self)
        self.session.setAudioInput(self.audio_input)
        self.session.setRecorder(self.recorder)
        self.is_recording = False
        self.output_filename = ""

    def start_record(self, device_desc=None, filename="record.m4a"):
        devices = QMediaDevices.audioInputs()
        selected_device = QMediaDevices.defaultAudioInput()
        if device_desc:
            for dev in devices:
                if dev.description() == device_desc:
                    selected_device = dev
                    break
        self.audio_input.setDevice(selected_device)
        abs_path = str(Path(filename).absolute())
        self.recorder.setOutputLocation(QUrl.fromLocalFile(abs_path))
        self.recorder.record()
        self.is_recording = True
        self.output_filename = filename
        return True

    def stop_record(self):
        if self.is_recording:
            self.recorder.stop()
            self.is_recording = False

# ==========================================
# 交互组件与对话框
# ==========================================
class TimeInputDialog(QDialog):
    def __init__(self, parent=None, title="设置时间点", duration_ms=-1):
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.setWindowTitle(title)
        self.setStyleSheet(get_qss())
        self.setFixedSize(300, 90)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(2)

        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #f38ba8; font-size: 9pt; font-weight: bold;")
        self.warning_label.setAlignment(Qt.AlignCenter)
        self.warning_label.setFixedHeight(18)
        main_layout.addWidget(self.warning_label)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_box = QLineEdit()
        self.h_box.setObjectName("JumpBox")
        self.h_box.setValidator(QIntValidator(0, 99))
        self.h_box.setAlignment(Qt.AlignCenter)
        self.m_box = QLineEdit()
        self.m_box.setObjectName("JumpBox")
        self.m_box.setValidator(QIntValidator(0, 59))
        self.m_box.setAlignment(Qt.AlignCenter)
        self.s_box = QLineEdit()
        self.s_box.setObjectName("JumpBox")
        self.s_box.setValidator(QIntValidator(0, 59))
        self.s_box.setAlignment(Qt.AlignCenter)

        self.short_duration = (duration_ms >= 0 and duration_ms < 3600 * 1000)
        hour_label = QLabel("时:")
        if self.short_duration:
            self.h_box.setText("0")
            self.h_box.setEnabled(False)
            self.h_box.setToolTip("当前视频不足 1 小时，无需设置小时")
            hour_label.setEnabled(False)

        self.h_box.textChanged.connect(self._check_time)
        self.m_box.textChanged.connect(self._check_time)
        self.s_box.textChanged.connect(self._check_time)

        h_layout.addWidget(self.h_box)
        h_layout.addWidget(hour_label)
        h_layout.addWidget(self.m_box)
        h_layout.addWidget(QLabel("分:"))
        h_layout.addWidget(self.s_box)
        h_layout.addWidget(QLabel("秒"))

        btn = QPushButton("确定")
        btn.setFixedSize(50, 30)
        btn.clicked.connect(self.accept)
        h_layout.addWidget(btn)
        main_layout.addLayout(h_layout)

    def _check_time(self):
        if self.duration_ms < 0: return
        target_ms = self.get_target_ms()
        if target_ms > self.duration_ms:
            self.warning_label.setText(f"⚠ 超出媒体总时长 ({format_time_ms(self.duration_ms)})")
        else:
            self.warning_label.setText("")

    def get_target_ms(self):
        return time_tuple_to_ms(self.h_box.text(), self.m_box.text(), self.s_box.text())

class JumpDialog(TimeInputDialog): pass

# ==========================================
# 闹钟式录音列表管理器
# ==========================================
class EditAlarmDialog(QDialog):
    def __init__(self, parent=None, existing_data=None):
        super().__init__(parent)
        self.setWindowTitle("编辑定时录音")
        self.setStyleSheet(get_qss())
        self.setFixedSize(320, 160)
        layout = QVBoxLayout(self)

        lbl = QLabel("请设置启动时间 (24小时制):")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(30, 0, 30, 0)
        now = datetime.now()
        
        default_h = f"{now.hour:02d}"
        default_m = f"{now.minute:02d}"
        if existing_data:
            parts = existing_data["time"].split(":")
            default_h = f"{int(parts[0]):02d}"
            default_m = f"{int(parts[1]):02d}"

        self.h_box = QLineEdit(default_h)
        self.h_box.setValidator(QIntValidator(0, 23))
        self.h_box.setAlignment(Qt.AlignCenter)
        self.h_box.setObjectName("JumpBox")
        
        self.m_box = QLineEdit(default_m)
        self.m_box.setValidator(QIntValidator(0, 59))
        self.m_box.setAlignment(Qt.AlignCenter)
        self.m_box.setObjectName("JumpBox")
        
        h_layout.addWidget(self.h_box); h_layout.addWidget(QLabel("时"))
        h_layout.addWidget(self.m_box); h_layout.addWidget(QLabel("分"))
        layout.addLayout(h_layout)

        layout.addWidget(QLabel("重复方式 (不选则为仅执行一次):"))
        days_layout = QHBoxLayout()
        days_layout.setSpacing(2)
        self.day_boxes = []
        labels = ["一", "二", "三", "四", "五", "六", "日"]
        existing_days = existing_data.get("days", []) if existing_data else []
        for i, text in enumerate(labels):
            cb = QCheckBox(text)
            if i in existing_days:
                cb.setChecked(True)
            self.day_boxes.append(cb)
            days_layout.addWidget(cb)
        layout.addLayout(days_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("确定保存")
        save_btn.setStyleSheet(f"background-color: {Theme.accent}; color: #11111b;")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_data(self):
        h = int(self.h_box.text() or 0)
        m = int(self.m_box.text() or 0)
        days = [i for i, cb in enumerate(self.day_boxes) if cb.isChecked()]
        return {"time": f"{h:02d}:{m:02d}", "days": days, "active": True}

class AlarmManagerDialog(QDialog):
    def __init__(self, alarms_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("定时录音列表管理")
        self.setStyleSheet(get_qss())
        self.resize(400, 350)
        self.alarms_data = list(alarms_list)
        
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self.refresh_list()
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ 添加定时")
        add_btn.clicked.connect(self.add_alarm)
        del_btn = QPushButton("🗑 删除选中")
        del_btn.setStyleSheet("background-color: #f38ba8; color: #11111b;")
        del_btn.clicked.connect(self.del_alarm)
        ok_btn = QPushButton("确定并应用")
        ok_btn.setStyleSheet(f"background-color: {Theme.accent}; color: #11111b;")
        ok_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        self.list_widget.itemDoubleClicked.connect(self.edit_alarm)

    def format_days(self, days):
        if not days: return "仅一次"
        if len(days) == 7: return "每天"
        wd = ["一", "二", "三", "四", "五", "六", "日"]
        return "周" + ", ".join([wd[d] for d in sorted(days)])

    def refresh_list(self):
        self.list_widget.clear()
        for idx, alarm in enumerate(self.alarms_data):
            item = QListWidgetItem()
            status = "🟢" if alarm.get("active", False) else "⚪"
            days_str = self.format_days(alarm.get("days", []))
            item.setText(f"{status} {alarm['time']} | 重复: {days_str}")
            item.setData(Qt.UserRole, idx)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if alarm.get("active", False) else Qt.Unchecked)
            self.list_widget.addItem(item)
            
        self.list_widget.itemChanged.connect(self.on_item_changed)

    def on_item_changed(self, item):
        idx = item.data(Qt.UserRole)
        is_active = (item.checkState() == Qt.Checked)
        self.alarms_data[idx]["active"] = is_active
        status = "🟢" if is_active else "⚪"
        days_str = self.format_days(self.alarms_data[idx].get("days", []))
        self.list_widget.blockSignals(True)
        item.setText(f"{status} {self.alarms_data[idx]['time']} | 重复: {days_str}")
        self.list_widget.blockSignals(False)

    def add_alarm(self):
        dialog = EditAlarmDialog(self)
        if dialog.exec() == QDialog.Accepted:
            new_data = dialog.get_data()
            new_data["id"] = str(uuid.uuid4())
            self.alarms_data.append(new_data)
            self.list_widget.blockSignals(True)
            self.refresh_list()
            self.list_widget.blockSignals(False)

    def edit_alarm(self, item):
        idx = item.data(Qt.UserRole)
        dialog = EditAlarmDialog(self, self.alarms_data[idx])
        if dialog.exec() == QDialog.Accepted:
            updated_data = dialog.get_data()
            updated_data["id"] = self.alarms_data[idx]["id"]
            self.alarms_data[idx] = updated_data
            self.list_widget.blockSignals(True)
            self.refresh_list()
            self.list_widget.blockSignals(False)

    def del_alarm(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            del self.alarms_data[row]
            self.list_widget.blockSignals(True)
            self.refresh_list()
            self.list_widget.blockSignals(False)

    def get_alarms(self):
        return self.alarms_data

class SegmentDialog(QDialog):
    def __init__(self, duration_ms=-1, current_segments=None, parent=None):
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.setWindowTitle("设置多段播放区段 (A-B段跳跃)")
        self.setStyleSheet(get_qss())
        self.setMinimumSize(680, 260)
        self.resize(680, 300)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 10, 15, 10)
        self.main_layout.setSpacing(8)

        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #f38ba8; font-size: 9pt; font-weight: bold;")
        self.warning_label.setAlignment(Qt.AlignCenter)
        self.warning_label.setFixedHeight(18)
        self.main_layout.addWidget(self.warning_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: #1e1e2e; border-radius: 6px; }")
        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.rows_layout = QVBoxLayout(self.container)
        self.rows_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)

        self.row_widgets = []
        if isinstance(current_segments, dict) and current_segments:
            current_segments = [current_segments]
        elif not current_segments:
            current_segments = []

        if current_segments:
            for seg in current_segments:
                self.add_row(seg.get("start_ms", 0), seg.get("end_ms", -1))
        else:
            self.add_row(0, -1)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ 追加片段")
        add_btn.clicked.connect(lambda: self.add_row(0, -1))
        clear_btn = QPushButton("🗑 清除全部")
        clear_btn.setStyleSheet("background-color: #f38ba8; color: #11111b;")
        clear_btn.clicked.connect(self.clear_all_and_accept)
        ok_btn = QPushButton("确定保存")
        ok_btn.setStyleSheet(f"background-color: {Theme.accent}; color: #11111b;")
        ok_btn.clicked.connect(self.accept)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        self.main_layout.addLayout(btn_layout)

        self.cleared = False
        self._check_time()

    def add_row(self, s_ms, e_ms):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 4, 0, 4)
        lbl = QLabel(f"片段 {len(self.row_widgets)+1}:")
        lbl.setFixedWidth(50)
        row_layout.addWidget(lbl)
        
        sh_str, sm_str, ss_str = ms_to_time_tuple(s_ms) if s_ms > 0 else ("", "", "")
        eh_str, em_str, es_str = ms_to_time_tuple(e_ms) if e_ms > 0 else ("", "", "")
        
        def make_inputs(h_val, m_val, s_val, is_end=False):
            h = QLineEdit(h_val)
            h.setValidator(QIntValidator(0, 99))
            h.setAlignment(Qt.AlignCenter)
            h.setObjectName("JumpBox")
            if is_end and not h_val: h.setPlaceholderText("-")
            m = QLineEdit(m_val)
            m.setValidator(QIntValidator(0, 59))
            m.setAlignment(Qt.AlignCenter)
            m.setObjectName("JumpBox")
            if is_end and not m_val: m.setPlaceholderText("-")
            s = QLineEdit(s_val)
            s.setValidator(QIntValidator(0, 59))
            s.setAlignment(Qt.AlignCenter)
            s.setObjectName("JumpBox")
            if is_end and not s_val: s.setPlaceholderText("-")
            h.textChanged.connect(self._check_time)
            m.textChanged.connect(self._check_time)
            s.textChanged.connect(self._check_time)
            return h, m, s

        row_layout.addWidget(QLabel("从"))
        sh, sm, ss = make_inputs(sh_str, sm_str, ss_str, False)
        row_layout.addWidget(sh); row_layout.addWidget(QLabel("时"))
        row_layout.addWidget(sm); row_layout.addWidget(QLabel("分"))
        row_layout.addWidget(ss); row_layout.addWidget(QLabel("秒"))
        
        row_layout.addWidget(QLabel(" 至 "))
        eh, em, es = make_inputs(eh_str, em_str, es_str, True)
        row_layout.addWidget(eh); row_layout.addWidget(QLabel("时"))
        row_layout.addWidget(em); row_layout.addWidget(QLabel("分"))
        row_layout.addWidget(es); row_layout.addWidget(QLabel("秒"))
        
        del_btn = QPushButton("🗑")
        del_btn.setFixedSize(32, 32)
        del_btn.setStyleSheet("background-color: transparent; color: #f38ba8; font-size: 14pt;")
        del_btn.setToolTip("删除此片段")
        del_btn.clicked.connect(lambda: self.remove_row(row_widget))
        row_layout.addWidget(del_btn)
        
        self.rows_layout.addWidget(row_widget)
        self.row_widgets.append({
            "widget": row_widget, "lbl": lbl,
            "sh": sh, "sm": sm, "ss": ss,
            "eh": eh, "em": em, "es": es
        })
        self._check_time()

    def remove_row(self, widget):
        for r in self.row_widgets:
            if r["widget"] == widget:
                self.row_widgets.remove(r)
                widget.deleteLater()
                break
        for i, r in enumerate(self.row_widgets):
            r["lbl"].setText(f"片段 {i+1}:")
        self._check_time()

    def _check_time(self):
        if self.duration_ms < 0: return
        has_error = False
        for r in self.row_widgets:
            s_ms = time_tuple_to_ms(r['sh'].text(), r['sm'].text(), r['ss'].text())
            e_h, e_m, e_s = r['eh'].text().strip(), r['em'].text().strip(), r['es'].text().strip()
            e_ms = time_tuple_to_ms(e_h, e_m, e_s) if (e_h or e_m or e_s) else -1
            
            if s_ms > self.duration_ms or (e_ms > 0 and e_ms > self.duration_ms):
                self.warning_label.setText(f"⚠ 超出媒体总时长 ({format_time_ms(self.duration_ms)})")
                has_error = True
                break
            elif e_ms > 0 and s_ms >= e_ms:
                self.warning_label.setText("⚠ 结束时间必须大于开始时间")
                has_error = True
                break
        if not has_error:
            self.warning_label.setText("")

    def clear_all_and_accept(self):
        self.cleared = True
        self.accept()

    def get_segments(self):
        if self.cleared: return []
        segs = []
        seg_colors = ["#a6e3a1", "#f9e2af", "#cba6f7", "#89b4fa", "#f38ba8", "#94e2d5"]
        for i, r in enumerate(self.row_widgets):
            s_ms = time_tuple_to_ms(r['sh'].text(), r['sm'].text(), r['ss'].text())
            e_h, e_m, e_s = r['eh'].text().strip(), r['em'].text().strip(), r['es'].text().strip()
            e_ms = time_tuple_to_ms(e_h, e_m, e_s) if (e_h or e_m or e_s) else -1
            if s_ms == 0 and e_ms <= 0: continue
            segs.append({
                "start_ms": s_ms, "end_ms": e_ms,
                "color": seg_colors[i % len(seg_colors)]
            })
        return segs

class ChainTaskWidget(QWidget):
    remove_requested = Signal(QWidget)
    data_changed = Signal()
    
    def __init__(self, playlist, task_data=None, parent=None):
        super().__init__(parent)
        acc = Theme.accent
        self.setStyleSheet(f"""
            QWidget {{ background-color: #1e1e2e; border: 1px solid #45475a; border-radius: 6px; }}
            QLabel {{ border: none; }}
            QLineEdit {{ background-color: #313244; border: 1px solid {acc}; border-radius: 4px; color: #cdd6f4; font-size: 10pt; min-width: 40px; max-width: 50px; min-height: 25px; }}
            QComboBox {{ background-color: #313244; border: 1px solid {acc}; border-radius: 4px; padding: 3px; }}
            QPushButton {{ background-color: #313244; border: 1px solid #45475a; border-radius: 4px; padding: 4px; }}
            QPushButton:hover {{ background-color: #45475a; }}
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        def create_time_group(label_text, default_text="-"):
            group_layout = QHBoxLayout()
            group_layout.addWidget(QLabel(label_text))
            h = QLineEdit()
            h.setValidator(QIntValidator(0, 99))
            h.setAlignment(Qt.AlignCenter)
            h.setPlaceholderText(default_text)
            m = QLineEdit()
            m.setValidator(QIntValidator(0, 59))
            m.setAlignment(Qt.AlignCenter)
            m.setPlaceholderText(default_text)
            s = QLineEdit()
            s.setValidator(QIntValidator(0, 59))
            s.setAlignment(Qt.AlignCenter)
            s.setPlaceholderText(default_text)
            
            # ★★★ 关键修复：用 lambda 吸收 textChanged 自带的 str 参数 ★★★
            h.textChanged.connect(lambda _: self.data_changed.emit())
            m.textChanged.connect(lambda _: self.data_changed.emit())
            s.textChanged.connect(lambda _: self.data_changed.emit())
            
            group_layout.addWidget(h); group_layout.addWidget(QLabel("时"))
            group_layout.addWidget(m); group_layout.addWidget(QLabel("分"))
            group_layout.addWidget(s); group_layout.addWidget(QLabel("秒"))
            group_layout.addStretch()
            return group_layout, h, m, s

        self.trig_layout, self.trig_h, self.trig_m, self.trig_s = create_time_group("触发打断时间:", "")
        main_layout.addLayout(self.trig_layout)
        
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("目标媒体(列表):"))
        self.target_combo = QComboBox()
        self.target_combo.setMaximumWidth(400)
        self.target_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for name, path in playlist:
            self.target_combo.addItem(name, path)
        
        # ★★★ 关键修复：用 lambda 吸收 currentIndexChanged 自带的 int 参数 ★★★
        self.target_combo.currentIndexChanged.connect(lambda _: self.data_changed.emit())
        
        target_layout.addWidget(self.target_combo, 1)
        
        self.gear_btn = QPushButton("⚙")
        self.gear_btn.setFixedSize(30, 30)
        self.gear_btn.setToolTip("高级设置: 指定开始与结束时间")
        self.gear_btn.clicked.connect(self.toggle_advanced)
        target_layout.addWidget(self.gear_btn)
        
        self.del_btn = QPushButton("🗑")
        self.del_btn.setFixedSize(30, 30)
        self.del_btn.setStyleSheet("background-color: #f38ba8; color: #11111b; border: none;")
        self.del_btn.setToolTip("移除此条串联任务")
        self.del_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        target_layout.addWidget(self.del_btn)
        main_layout.addLayout(target_layout)
        
        self.adv_widget = QWidget()
        self.adv_widget.setStyleSheet("border: none;")
        adv_layout = QVBoxLayout(self.adv_widget)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tstart_layout, self.tstart_h, self.tstart_m, self.tstart_s = create_time_group("目标开始时间:", "-")
        self.tstart_layout.addWidget(QLabel("(留空从头播)"))
        adv_layout.addLayout(self.tstart_layout)
        
        self.tend_layout, self.tend_h, self.tend_m, self.tend_s = create_time_group("目标结束时间:", "-")
        self.tend_layout.addWidget(QLabel("(留空播到底)"))
        adv_layout.addLayout(self.tend_layout)
        self.adv_widget.hide()
        main_layout.addWidget(self.adv_widget)
        
        self.res_layout, self.res_h, self.res_m, self.res_s = create_time_group("切回后恢复至:", "")
        main_layout.addLayout(self.res_layout)
        
        if task_data: self.load_data(task_data)
            
    def toggle_advanced(self):
        self.adv_widget.setVisible(not self.adv_widget.isVisible())
        
    def load_data(self, data):
        h, m, s = ms_to_time_tuple(data.get("trigger_ms", 0))
        self.trig_h.setText(h); self.trig_m.setText(m); self.trig_s.setText(s)
        
        target_path = data.get("target_path", "")
        for i in range(self.target_combo.count()):
            if self.target_combo.itemData(i) == target_path:
                self.target_combo.setCurrentIndex(i)
                break
                
        ts = data.get("target_start_ms", 0)
        if ts > 0:
            h, m, s = ms_to_time_tuple(ts)
            self.tstart_h.setText(h); self.tstart_m.setText(m); self.tstart_s.setText(s)
            
        te = data.get("target_end_ms", -1)
        if te > 0:
            h, m, s = ms_to_time_tuple(te)
            self.tend_h.setText(h); self.tend_m.setText(m); self.tend_s.setText(s)
            
        h, m, s = ms_to_time_tuple(data.get("resume_ms", 0))
        self.res_h.setText(h); self.res_m.setText(m); self.res_s.setText(s)
        
    def get_task_data(self):
        trigger_ms = time_tuple_to_ms(self.trig_h.text(), self.trig_m.text(), self.trig_s.text())
        target_start_ms = time_tuple_to_ms(self.tstart_h.text(), self.tstart_m.text(), self.tstart_s.text())
        te_h, te_m, te_s = self.tend_h.text().strip(), self.tend_m.text().strip(), self.tend_s.text().strip()
        target_end_ms = -1 if not te_h and not te_m and not te_s else time_tuple_to_ms(te_h, te_m, te_s)
        resume_ms = time_tuple_to_ms(self.res_h.text(), self.res_m.text(), self.res_s.text())
        
        return {
            "trigger_ms": trigger_ms,
            "target_path": self.target_combo.currentData(),
            "target_start_ms": target_start_ms,
            "target_end_ms": target_end_ms,
            "resume_ms": resume_ms
        }

class ChainTaskDialog(QDialog):
    def __init__(self, playlist, existing_chains, duration_ms=-1, target_durations=None, parent=None):
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.target_durations = target_durations or {}
        self.setWindowTitle("管理串联任务")
        self.setStyleSheet(get_qss())
        self.resize(680, 500)
        self.playlist_data = playlist
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #f38ba8; font-size: 9pt; font-weight: bold;")
        self.warning_label.setAlignment(Qt.AlignCenter)
        self.warning_label.setFixedHeight(18)
        main_layout.addWidget(self.warning_label)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #181825; }")
        self.container = QWidget()
        self.container.setStyleSheet("background-color: #181825;")
        self.tasks_layout = QVBoxLayout(self.container)
        self.tasks_layout.setSpacing(15)
        self.tasks_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)
        
        for chain in existing_chains: self.add_task(chain)
        if not existing_chains: self.add_task()
            
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 添加串联任务")
        btn_add.setMinimumHeight(35)
        btn_add.clicked.connect(lambda: self.add_task())
        btn_confirm = QPushButton("确定保存")
        btn_confirm.setMinimumHeight(35)
        btn_confirm.setStyleSheet(f"background-color: {Theme.accent}; color: #11111b;")
        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_add)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_confirm)
        main_layout.addLayout(btn_layout)
        self._check_time()
        
    def add_task(self, task_data=None):
        widget = ChainTaskWidget(self.playlist_data, task_data, self)
        widget.remove_requested.connect(self.remove_task)
        widget.data_changed.connect(self._check_time)
        self.tasks_layout.addWidget(widget)
        self._check_time()
        
    def remove_task(self, widget):
        self.tasks_layout.removeWidget(widget)
        widget.deleteLater()
        QTimer.singleShot(0, self._check_time)
        
    def _check_time(self):
        has_error = False
        for i in range(self.tasks_layout.count()):
            widget = self.tasks_layout.itemAt(i).widget()
            if isinstance(widget, ChainTaskWidget):
                data = widget.get_task_data()
                if self.duration_ms >= 0:
                    if data["trigger_ms"] > self.duration_ms:
                        self.warning_label.setText(f"⚠ 触发时间超出当前媒体总长 ({format_time_ms(self.duration_ms)})")
                        has_error = True; break
                    if data["resume_ms"] > self.duration_ms:
                        self.warning_label.setText(f"⚠ 恢复时间超出当前媒体总长 ({format_time_ms(self.duration_ms)})")
                        has_error = True; break
                target_path = data["target_path"]
                t_dur = self.target_durations.get(target_path, -1)
                if t_dur >= 0:
                    if data["target_start_ms"] > t_dur:
                        self.warning_label.setText(f"⚠ 目标开始时间超出目标媒体总长 ({format_time_ms(t_dur)})")
                        has_error = True; break
                    if data["target_end_ms"] > 0 and data["target_end_ms"] > t_dur:
                        self.warning_label.setText(f"⚠ 目标结束时间超出目标媒体总长 ({format_time_ms(t_dur)})")
                        has_error = True; break
                if data["target_end_ms"] > 0 and data["target_start_ms"] >= data["target_end_ms"]:
                    self.warning_label.setText("⚠ 目标结束时间必须大于开始时间")
                    has_error = True; break
        if not has_error:
            self.warning_label.setText("")

    def get_all_tasks(self):
        tasks = []
        for i in range(self.tasks_layout.count()):
            widget = self.tasks_layout.itemAt(i).widget()
            if isinstance(widget, ChainTaskWidget):
                data = widget.get_task_data()
                if data["target_path"]: tasks.append(data)
        return tasks

class SavePlaylistDialog(QDialog):
    def __init__(self, db_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("保存到我的固列表")
        self.setStyleSheet(get_qss())
        self.setFixedSize(360, 200)
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.addWidget(QLabel("1. 选择或创建分组 (例如: 西语、中文):"))
        self.folder_combo = QComboBox()
        self.folder_combo.setEditable(True)
        for f in db_data: self.folder_combo.addItem(f["folder_name"])
        if self.folder_combo.count() == 0: self.folder_combo.addItem("默认分组")
        self.folder_combo.setFixedHeight(30)
        layout.addWidget(self.folder_combo)
        layout.addWidget(QLabel("2. 输入此列表名称 (例如: 列表1):"))
        self.name_box = QLineEdit()
        self.name_box.setPlaceholderText("在此输入播放列表的名称")
        self.name_box.setFixedHeight(30)
        self.name_box.setStyleSheet(f"background-color: #1e1e2e; border: 1px solid {Theme.accent}; color: #cdd6f4; border-radius: 4px; padding: 0 5px;")
        layout.addWidget(self.name_box)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("确定保存")
        save_btn.setStyleSheet(f"background-color: {Theme.accent}; color: #11111b;")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_data(self):
        return self.folder_combo.currentText().strip(), self.name_box.text().strip()

class ManagePlaylistsDialog(QDialog):
    def __init__(self, db_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("管理与排序我的列表 (直接拖拽即可排序)")
        self.setStyleSheet(get_qss())
        self.resize(420, 500)
        layout = QVBoxLayout(self)
        tip_label = QLabel("提示: 鼠标按住列表项可上下拖动进行排序\n也可以将列表拖入其他分组中")
        tip_label.setStyleSheet("color: #a6adc8; font-size: 9pt; font-weight: normal;")
        layout.addWidget(tip_label)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)

        for folder in db_data:
            f_item = QTreeWidgetItem(self.tree, [f"📁 {folder['folder_name']}"])
            f_item.setFlags(f_item.flags() | Qt.ItemIsDropEnabled | Qt.ItemIsDragEnabled)
            for pl in folder["playlists"]:
                p_item = QTreeWidgetItem(f_item, [f"🎵 {pl['name']}"])
                p_item.setData(0, Qt.UserRole, pl["items"])
                p_item.setFlags((p_item.flags() & ~Qt.ItemIsDropEnabled) | Qt.ItemIsDragEnabled)

        self.tree.expandAll()
        layout.addWidget(self.tree)
        btn_layout = QHBoxLayout()
        del_btn = QPushButton("🗑 删除选中项")
        del_btn.setStyleSheet("background-color: #f38ba8; color: #11111b;")
        del_btn.clicked.connect(self.delete_selected)
        save_btn = QPushButton("💾 保存排序与修改")
        save_btn.setStyleSheet(f"background-color: {Theme.accent}; color: #11111b;")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def delete_selected(self):
        item = self.tree.currentItem()
        if item:
            parent = item.parent()
            if parent: parent.removeChild(item)
            else:
                index = self.tree.indexOfTopLevelItem(item)
                self.tree.takeTopLevelItem(index)

    def get_new_data(self):
        new_data = []
        for i in range(self.tree.topLevelItemCount()):
            f_item = self.tree.topLevelItem(i)
            if f_item.childCount() > 0:
                folder_name = f_item.text(0).replace("📁 ", "")
                pls = []
                for j in range(f_item.childCount()):
                    p_item = f_item.child(j)
                    pls.append({"name": p_item.text(0).replace("🎵 ", ""), "items": p_item.data(0, Qt.UserRole)})
                new_data.append({"folder_name": folder_name, "playlists": pls})
            else:
                items = f_item.data(0, Qt.UserRole)
                if items is not None:
                    new_data.append({"folder_name": "默认未分类", "playlists": [{"name": f_item.text(0).replace("🎵 ", ""), "items": items}]})
                else:
                    folder_name = f_item.text(0).replace("📁 ", "")
                    new_data.append({"folder_name": folder_name, "playlists": []})
        return new_data

class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_step=10, player=None, current_title="", current_popup_seconds=5, current_chain_popup_seconds=5, current_record_dir="", current_theme_color="#89b4fa", current_default_video_open=True, current_network_auto_play=True, current_auto_upload_drive=False, current_drive_folder_id=""):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(450, 480)
        self.player = player
        self.setStyleSheet(get_qss())

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("主色调 (区分多开):"))
        self.theme_combo = QComboBox()
        themes = [("🔵 冰晶蓝 (Blue)", "#89b4fa"), ("🟢 翡翠绿 (Green)", "#a6e3a1"), ("🔴 珊瑚红 (Red)", "#f38ba8"), ("🟡 星芒黄 (Yellow)", "#f9e2af"), ("🟣 梦幻紫 (Purple)", "#cba6f7"), ("🩵 湖水青 (Teal)", "#94e2d5")]
        for name, hex_val in themes: self.theme_combo.addItem(name, hex_val)
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme_color:
                self.theme_combo.setCurrentIndex(i)
                break
        theme_layout.addWidget(self.theme_combo)
        layout.addLayout(theme_layout)

        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("中央题头:"))
        self.title_box = QLineEdit(current_title)
        self.title_box.setStyleSheet(f"background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 4px;")
        self.title_box.setPlaceholderText("留空不显示")
        title_layout.addWidget(self.title_box)
        layout.addLayout(title_layout)

        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("步长(秒):"))
        self.step_box = QSpinBox()
        self.step_box.setRange(1, 300)
        self.step_box.setValue(int(current_step))
        step_layout.addWidget(self.step_box)
        layout.addLayout(step_layout)

        popup_layout = QHBoxLayout()
        popup_layout.addWidget(QLabel("视频点提前弹出:"))
        self.popup_box = QSpinBox()
        self.popup_box.setRange(0, 300)
        self.popup_box.setValue(int(current_popup_seconds))
        popup_layout.addWidget(self.popup_box); popup_layout.addWidget(QLabel("秒"))
        layout.addLayout(popup_layout)
        
        chain_popup_layout = QHBoxLayout()
        chain_popup_layout.addWidget(QLabel("串联点提前预警:"))
        self.chain_popup_box = QSpinBox()
        self.chain_popup_box.setRange(0, 300)
        self.chain_popup_box.setValue(int(current_chain_popup_seconds))
        chain_popup_layout.addWidget(self.chain_popup_box); chain_popup_layout.addWidget(QLabel("秒"))
        layout.addLayout(chain_popup_layout)

        click_layout = QHBoxLayout()
        click_layout.addWidget(QLabel("播放列表打开方式:"))
        self.click_mode_combo = QComboBox()
        self.click_mode_combo.addItem("单击", "single")
        self.click_mode_combo.addItem("双击", "double")
        self.click_mode_combo.setCurrentIndex(0 if getattr(parent, "playlist_click_mode", "single") == "single" else 1)
        click_layout.addWidget(self.click_mode_combo)
        layout.addLayout(click_layout)

        video_open_layout = QHBoxLayout()
        video_open_layout.addWidget(QLabel("默认播放时开启视频窗口:"))
        self.video_open_combo = QComboBox()
        self.video_open_combo.addItem("开启", True)
        self.video_open_combo.addItem("关闭 (仅播音频)", False)
        self.video_open_combo.setCurrentIndex(0 if current_default_video_open else 1)
        video_open_layout.addWidget(self.video_open_combo)
        layout.addLayout(video_open_layout)

        net_play_layout = QHBoxLayout()
        net_play_layout.addWidget(QLabel("网络资源加载后行为:"))
        self.net_play_combo = QComboBox()
        self.net_play_combo.addItem("加载后立即播放", True)
        self.net_play_combo.addItem("仅添加到列表末尾 (排队)", False)
        self.net_play_combo.setCurrentIndex(0 if current_network_auto_play else 1)
        net_play_layout.addWidget(self.net_play_combo)
        layout.addLayout(net_play_layout)

        record_dir_layout = QHBoxLayout()
        record_dir_layout.addWidget(QLabel("录音保存目录:"))
        self.record_dir_box = QLineEdit(current_record_dir)
        self.record_dir_box.setStyleSheet(f"background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 4px;")
        record_dir_layout.addWidget(self.record_dir_box)
        browse_rec_btn = QPushButton("浏览")
        browse_rec_btn.clicked.connect(self._browse_rec_dir)
        record_dir_layout.addWidget(browse_rec_btn)
        layout.addLayout(record_dir_layout)

        drive_upload_layout = QHBoxLayout()
        drive_upload_layout.addWidget(QLabel("录音后自动上传网盘:"))
        self.drive_upload_combo = QComboBox()
        self.drive_upload_combo.addItem("开启 (本地+网盘双备份)", True)
        self.drive_upload_combo.addItem("关闭 (仅保存在本地)", False)
        self.drive_upload_combo.setCurrentIndex(0 if current_auto_upload_drive else 1)
        drive_upload_layout.addWidget(self.drive_upload_combo)
        layout.addLayout(drive_upload_layout)

        drive_folder_layout = QHBoxLayout()
        drive_folder_layout.addWidget(QLabel("网盘目标文件夹 ID:"))
        self.drive_folder_box = QLineEdit(current_drive_folder_id)
        self.drive_folder_box.setStyleSheet(f"background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 4px;")
        self.drive_folder_box.setPlaceholderText("留空则默认上传至网盘根目录")
        drive_folder_layout.addWidget(self.drive_folder_box)
        layout.addLayout(drive_folder_layout)

        btn = QPushButton("确定")
        btn.clicked.connect(self.accept)
        layout.addStretch()
        layout.addWidget(btn)

    def _browse_rec_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择录音保存目录", self.record_dir_box.text())
        if d: self.record_dir_box.setText(d)

# ==========================================
# 播放列表底层画笔渲染器
# ==========================================
class PlaylistItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = ["#f38ba8", "#f9e2af", "#a6e3a1", "#89dceb", "#cba6f7", "#fab387", "#94e2d5"]

    def paint(self, painter, option, index):
        list_widget = self.parent()
        if not list_widget: return

        my_path = index.data(Qt.UserRole)
        my_item = list_widget.item(index.row())
        if not my_item: return super().paint(painter, option, index)

        dots = []
        chain_index = 0
        for row in range(list_widget.count()):
            item = list_widget.item(row)
            chains = item.data(DragDropListWidget.CHAIN_ROLE) or []
            for c in chains:
                color_hex = self.colors[chain_index % len(self.colors)]
                chain_index += 1
                if item == my_item: dots.append(color_hex)
                elif c.get("target_path") == my_path: dots.append(color_hex)
                
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect
        
        if option.state & QStyle.State_Selected:
            painter.setBrush(QColor(Theme.accent))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 4, 4)
            text_color = QColor("#11111b")
        else:
            text_color = QColor("#cdd6f4")
            
        painter.setPen(text_color)
        fm = option.fontMetrics
        
        dur_x = rect.right() - 180
        dur_width = 80
        dur_rect = QRectF(dur_x, rect.top(), dur_width, rect.height())
        
        segments = my_item.data(DragDropListWidget.SEGMENT_ROLE) or []
        if isinstance(segments, dict): segments = [segments] if segments else []
        seg_w = 6
        seg_spacing = 4
        total_seg_w = len(segments) * (seg_w + seg_spacing) if segments else 0
        
        seg_start_x = dur_x - total_seg_w - 10
        
        if segments:
            seg_x = seg_start_x
            for seg in segments:
                c_hex = seg.get('color', '#a6e3a1')
                painter.setBrush(QColor(c_hex))
                painter.setPen(Qt.NoPen)
                capsule_h = 16
                capsule_y = rect.center().y() - capsule_h / 2
                painter.drawRoundedRect(QRectF(seg_x, capsule_y, seg_w, capsule_h), 3, 3)
                seg_x += (seg_w + seg_spacing)
        
        margin_left = 10
        name_x = rect.left() + margin_left
        name_w_max = seg_start_x - name_x - 10
        name = index.data(Qt.DisplayRole) or "" 
        elided_name = fm.elidedText(name, Qt.ElideRight, max(30, int(name_w_max)))
        name_rect = QRectF(name_x, rect.top(), max(30, int(name_w_max)), rect.height())
        
        painter.setPen(text_color)
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_name)
        
        duration_str = index.data(Qt.UserRole + 3)
        duration_text = f"[{duration_str}]" if duration_str else ""
        if duration_text:
            painter.drawText(dur_rect, Qt.AlignLeft | Qt.AlignVCenter, duration_text)
        
        dot_x_start = rect.right() - 25
        if dots:
            dot_y = rect.center().y()
            for color_hex in reversed(dots):
                painter.setBrush(QColor(color_hex))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPoint(int(dot_x_start), int(dot_y)), 5, 5)
                dot_x_start -= 16

        painter.restore()

    def helpEvent(self, event, view, option, index):
        if event.type() == QEvent.ToolTip:
            list_widget = self.parent()
            if not list_widget: return super().helpEvent(event, view, option, index)

            my_item = list_widget.item(index.row())
            if not my_item: return super().helpEvent(event, view, option, index)

            my_path = index.data(Qt.UserRole)
            segments = my_item.data(DragDropListWidget.SEGMENT_ROLE) or []
            if isinstance(segments, dict): segments = [segments] if segments else []
                
            rect = option.rect
            x_pos = event.pos().x()
            
            dur_x = rect.right() - 180
            seg_w = 6
            seg_spacing = 4
            total_seg_w = len(segments) * (seg_w + seg_spacing) if segments else 0
            seg_start_x = dur_x - total_seg_w - 10

            if segments and seg_start_x <= x_pos <= seg_start_x + total_seg_w:
                index_seg = int((x_pos - seg_start_x) / (seg_w + seg_spacing))
                if 0 <= index_seg < len(segments):
                    seg = segments[index_seg]
                    s_txt = format_time_ms(seg.get('start_ms', 0))
                    e_txt = format_time_ms(seg.get('end_ms', -1)) if seg.get('end_ms', -1) > 0 else "末尾"
                    QToolTip.showText(event.globalPos(), f"片段 {index_seg+1}: {s_txt} - {e_txt}", view)
                    return True
            
            dots_info = []
            chain_index = 0
            for row in range(list_widget.count()):
                item = list_widget.item(row)
                chains = item.data(DragDropListWidget.CHAIN_ROLE) or []
                for c in chains:
                    chain_index += 1
                    if item == my_item:
                        target_name = Path(c.get('target_path', '')).name
                        time_str = format_time_ms(c.get('trigger_ms', 0))
                        dots_info.append(f"[{chain_index}] 主控 ➡️ {target_name} ({time_str} 触发)")
                    elif c.get("target_path") == my_path:
                        src_name = item.data(Qt.DisplayRole)
                        time_str = format_time_ms(c.get('trigger_ms', 0))
                        dots_info.append(f"[{chain_index}] 被控 ⬅️ 来自 {src_name} ({time_str} 触发)")

            if dots_info and x_pos >= dur_x + 80:
                QToolTip.showText(event.globalPos(), "\n".join(dots_info), view)
                return True
            
            if x_pos < seg_start_x:
                full_name = index.data(Qt.DisplayRole)
                if full_name:
                    QToolTip.showText(event.globalPos(), full_name, view)
                    return True
                    
        return super().helpEvent(event, view, option, index)

class WaveSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self.setMouseTracking(True)
        self.wave_data = []
        self.video_points = []
        self.chain_points_data = []
        self.segments = []
        self.bg_pixmap = None
        self.fg_pixmap = None
        self.generate_wave_for_media(None)

    def generate_wave_for_media(self, seed_path):
        if seed_path: random.seed(seed_path)
        else: random.seed("default_media_console_seed")
            
        data = []
        target = 0.5
        for i in range(150):
            if i % 12 == 0: target = random.uniform(0.1, 1.0)
            val = target + random.uniform(-0.15, 0.15)
            data.append(max(0.1, min(1.0, val)))

        random.seed()
        self.wave_data = data
        self._render_pixmaps()
        self.update()

    def set_segments(self, segments):
        self.segments = segments
        self.update()

    def set_video_points(self, points):
        self.video_points = sorted(set(int(x) for x in points if x >= 0))
        self.update()
        
    def set_chain_points(self, chains):
        self.chain_points_data = []
        colors = ["#f38ba8", "#f9e2af", "#a6e3a1", "#89dceb", "#cba6f7", "#fab387", "#94e2d5"]
        for i, x in enumerate(chains):
            trigger_ms = int(x["trigger_ms"])
            if trigger_ms >= 0:
                self.chain_points_data.append({"ms": trigger_ms, "color": colors[i % len(colors)]})
        self.update()

    def mouseMoveEvent(self, event):
        w = self.width()
        media_length = getattr(self, "media_length_seconds", 0)
        
        if w > 0 and media_length > 0:
            hover_time_ms = (event.position().x() / w) * (media_length * 1000)
            tolerance_ms = (media_length * 1000) * (5 / w)
            tooltip_text = ""
            
            for pt in self.video_points:
                if abs(pt - hover_time_ms) <= tolerance_ms:
                    tooltip_text = f"视频点: {format_time_ms(pt)}"
                    break
                    
            if not tooltip_text:
                for pt_data in self.chain_points_data:
                    if abs(pt_data["ms"] - hover_time_ms) <= tolerance_ms:
                        tooltip_text = f"串联任务: {format_time_ms(pt_data['ms'])}"
                        break
                        
            if not tooltip_text and hasattr(self, 'segments') and self.segments:
                for i, seg in enumerate(self.segments):
                    s_ms = seg.get('start_ms', 0)
                    e_ms = seg.get('end_ms', -1)
                    if e_ms <= 0: e_ms = media_length * 1000
                    if s_ms <= hover_time_ms <= e_ms:
                        tooltip_text = f"片段 {i+1}: {format_time_ms(s_ms)} - {format_time_ms(e_ms)}"
                        break
                        
            if tooltip_text: self.setToolTip(tooltip_text)
            else: self.setToolTip("")

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            val = self.minimum() + (self.maximum() - self.minimum()) * event.position().x() / max(1, self.width())
            self.setValue(int(val))
            self.sliderMoved.emit(self.value())
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_pixmaps()

    def _render_pixmaps(self):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0: return

        self.bg_pixmap = QPixmap(w, h); self.bg_pixmap.fill(Qt.transparent)
        self.fg_pixmap = QPixmap(w, h); self.fg_pixmap.fill(Qt.transparent)

        painter_bg = QPainter(self.bg_pixmap); painter_bg.setRenderHint(QPainter.Antialiasing)
        painter_fg = QPainter(self.fg_pixmap); painter_fg.setRenderHint(QPainter.Antialiasing)

        base_h = 3; base_y = h - base_h
        painter_bg.setBrush(QColor("#45475a")); painter_bg.setPen(Qt.NoPen)
        painter_bg.drawRoundedRect(QRectF(0, base_y, w, base_h), 1.5, 1.5)
        painter_fg.setBrush(QColor(Theme.accent)); painter_fg.setPen(Qt.NoPen)
        painter_fg.drawRoundedRect(QRectF(0, base_y, w, base_h), 1.5, 1.5)

        if not self.wave_data:
            painter_bg.end(); painter_fg.end(); return

        bar_count = len(self.wave_data)
        bar_width = w / max(1, bar_count)

        painter_bg.setBrush(QColor("#45475a")); painter_fg.setBrush(QColor(Theme.accent))
        for i, amp in enumerate(self.wave_data):
            x = i * bar_width
            bar_h = (h - base_h) * amp * 0.9
            y = base_y - bar_h
            rect = QRectF(x, y, max(0.5, bar_width - 1.2), bar_h)
            painter_bg.drawRoundedRect(rect, 1, 1); painter_fg.drawRoundedRect(rect, 1, 1)

        painter_bg.end(); painter_fg.end()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        w = self.width(); h = self.height()
        if w <= 0 or h <= 0 or not self.bg_pixmap or not self.fg_pixmap: return

        progress_ratio = self.value() / max(1, self.maximum())
        split_x = int(w * progress_ratio)

        painter.drawPixmap(0, 0, self.bg_pixmap)
        if split_x > 0:
            painter.setClipRect(0, 0, split_x, h)
            painter.drawPixmap(0, 0, self.fg_pixmap)
            painter.setClipping(False)

        media_length_ms = getattr(self, "media_length_seconds", 0) * 1000
        if media_length_ms > 0 and hasattr(self, 'segments') and self.segments:
            for seg in self.segments:
                s_ratio = max(0, seg.get("start_ms", 0)) / media_length_ms
                e_ms = seg.get("end_ms", -1)
                e_ratio = min(media_length_ms, e_ms) / media_length_ms if e_ms > 0 else 1.0
                x1 = int(s_ratio * w); x2 = int(e_ratio * w)
                if x2 > x1:
                    orig_color = seg.get("color", "#a6e3a1")
                    
                    pen = QPen(QColor(orig_color))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    
                    fill_color = QColor(orig_color)
                    fill_color.setAlpha(60) 
                    painter.setBrush(fill_color)
                    
                    painter.drawRect(x1, 1, x2 - x1, h - 2)

        if self.maximum() > self.minimum():
            painter.setBrush(QColor("#f38ba8"))
            for point_ms in self.video_points:
                ratio = point_ms / 1000.0 / max(0.001, getattr(self, "media_length_seconds", 0))
                if not (0 <= ratio <= 1): continue
                x = ratio * w
                painter.setPen(QColor("#f38ba8"))
                painter.drawLine(int(x), 2, int(x), h - 1)
                painter.setBrush(QColor("#f38ba8")); painter.setPen(Qt.NoPen)
                painter.drawPolygon([QPoint(int(x), 0), QPoint(int(x - 4), 5), QPoint(int(x + 4), 5)])
                
            for pt_data in self.chain_points_data:
                point_ms = pt_data["ms"]; c_hex = pt_data["color"]
                ratio = point_ms / 1000.0 / max(0.001, getattr(self, "media_length_seconds", 0))
                if not (0 <= ratio <= 1): continue
                x = ratio * w
                painter.setPen(QColor(c_hex))
                painter.drawLine(int(x), 2, int(x), h - 1)
                painter.setBrush(QColor(c_hex)); painter.setPen(Qt.NoPen)
                painter.drawPolygon([QPoint(int(x), 0), QPoint(int(x - 4), 5), QPoint(int(x + 4), 5)])


class VolumeBar(QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Vertical, parent)
        self.setRange(0, 100); self.setValue(100); self.setFixedSize(24, 102)
        self.setCursor(Qt.PointingHandCursor); self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        w = self.width(); h = self.height(); track_w = 10
        x = (w - track_w) / 2; top = 6; bottom = h - 6
        track_h = max(1, bottom - top)

        painter.setPen(Qt.NoPen); painter.setBrush(QColor("#11111b"))
        painter.drawRoundedRect(QRectF(x, top, track_w, track_h), 5, 5)

        ratio = max(0.0, min(1.0, self.value() / 100.0))
        fill_h = track_h * ratio
        if fill_h > 0:
            painter.setBrush(QColor(Theme.accent))
            painter.drawRoundedRect(QRectF(x, bottom - fill_h, track_w, fill_h), 5, 5)

        handle_y = bottom - track_h * ratio
        handle_y = max(top, min(bottom, handle_y))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(x - 3, handle_y - 6, track_w + 6, 12))


class VolumePopup(QWidget):
    def __init__(self, owner):
        super().__init__(None)
        self.owner = owner
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(28, 108); self.setMouseTracking(True)

        self.slider = VolumeBar(self)
        self.slider.move(2, 3)
        self.slider.valueChanged.connect(owner._slider_value_changed)
        self.slider.installEventFilter(self)
        self.setStyleSheet("QWidget { background: #313244; border: 1px solid #45475a; border-radius: 5px; }")

    def enterEvent(self, event):
        self.owner._keep_volume_popup(); super().enterEvent(event)
    def leaveEvent(self, event):
        self.owner._schedule_hide_volume_popup(); super().leaveEvent(event)
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter: self.owner._keep_volume_popup()
        elif event.type() == QEvent.Leave: self.owner._schedule_hide_volume_popup()
        return super().eventFilter(obj, event)


class VolumeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_muted = False; self.previous_volume = 100
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True); self.hide_timer.setInterval(250)
        self.hide_timer.timeout.connect(self._hide_popup)
        self.setFixedSize(32, 32); self.setMouseTracking(True)

        self.button = QPushButton("🔊", self)
        self.button.setFixedSize(32, 32); self.button.setToolTip("点击静音 / 取消静音")
        self.button.move(0, 0); self.button.setMouseTracking(True)
        self.popup = VolumePopup(self)
        self.button.installEventFilter(self); self.installEventFilter(self)
        self.button.clicked.connect(self.toggle_mute)

    def _show_popup(self):
        self.hide_timer.stop()
        pos = self.button.mapToGlobal(QPoint(0, 0))
        x = pos.x() - (self.popup.width() - self.button.width()) // 2
        y = pos.y() - self.popup.height() - 4
        self.popup.move(x, y); self.popup.show(); self.popup.raise_()

    def _keep_volume_popup(self):
        self.hide_timer.stop()
        if not self.popup.isVisible(): self._show_popup()

    def _schedule_hide_volume_popup(self): self.hide_timer.start()

    def _hide_popup(self):
        if self.button.underMouse() or self.popup.underMouse(): return
        self.popup.hide()

    def enterEvent(self, event):
        self._show_popup(); super().enterEvent(event)
    def leaveEvent(self, event):
        self._schedule_hide_volume_popup(); super().leaveEvent(event)
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter: self._show_popup()
        elif event.type() == QEvent.Leave: self._schedule_hide_volume_popup()
        return super().eventFilter(obj, event)

    def slider_value(self): return self.popup.slider.value()

    def _update_volume_state(self, value):
        value = max(0, min(100, int(value)))
        if value > 0:
            self.previous_volume = value; self.is_muted = False; self.button.setText("🔊")
        else:
            self.is_muted = True; self.button.setText("🔇")
        return value

    def _slider_value_changed(self, value):
        self._update_volume_state(value)

    def toggle_mute(self):
        if self.is_muted: self.set_volume(self.previous_volume or 100)
        else:
            self.previous_volume = self.slider_value() or 100
            self.set_volume(0)

    def set_volume(self, value):
        value = self._update_volume_state(value)
        if self.popup.slider.value() != value:
            self.popup.slider.setValue(value)

class DragDropListWidget(QListWidget):
    VIDEO_POINTS_ROLE = Qt.UserRole + 1
    CHAIN_ROLE = Qt.UserRole + 2
    HEADERS_ROLE = Qt.UserRole + 4
    AUDIO_URL_ROLE = Qt.UserRole + 5
    SEGMENT_ROLE = Qt.UserRole + 6
    ORIGINAL_URL_ROLE = Qt.UserRole + 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setItemDelegate(PlaylistItemDelegate(self))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.video_point_add_callback = None
        self.chain_add_callback = None
        self.item_removed_callback = None
        self.playlist_cleared_callback = None
        self.playlist_changed_callback = None
        self.segment_set_callback = None
        self.duration_fetcher_callback = None
        self.reload_network_callback = None

    def get_points(self, item):
        if not item: return []
        points = item.data(self.VIDEO_POINTS_ROLE)
        if not points: return []
        return sorted(set(int(x) for x in points))

    def set_points(self, item, points):
        if item:
            clean_points = sorted(set(int(x) for x in points if x >= 0))
            item.setData(self.VIDEO_POINTS_ROLE, clean_points)
            if self.playlist_changed_callback: self.playlist_changed_callback()

    def get_chains(self, item):
        if not item: return []
        chains = item.data(self.CHAIN_ROLE)
        if not chains: return []
        return chains

    def set_chains(self, item, chains):
        if item:
            item.setData(self.CHAIN_ROLE, chains)
            if self.playlist_changed_callback: self.playlist_changed_callback()

    def find_item_by_path(self, path):
        if not path: return None
        for row in range(self.count()):
            item = self.item(row)
            if item and item.data(Qt.UserRole) == path: return item
        return None

    def clear(self):
        super().clear()
        if self.playlist_cleared_callback: self.playlist_cleared_callback()

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)

        if item:
            menu.setMinimumWidth(320)
            points = self.get_points(item)

            add_action = menu.addAction("➕ 增加视频点")
            if points:
                view_menu = menu.addMenu(f"📍 视频点（{len(points)}个）")
                view_menu.setMinimumWidth(250)
                for point in points:
                    action = view_menu.addAction(f"▶ {format_time_ms(point)}")
                    action.setData(point)
                view_menu.addSeparator()
                delete_menu = view_menu.addMenu("删除视频点")
                delete_menu.setMinimumWidth(230)
                for point in points:
                    action = delete_menu.addAction(f"删除 {format_time_ms(point)}")
                    action.setData(("delete_one", point))
                delete_all_action = delete_menu.addAction("清理全部视频点")
                delete_all_action.setData(("delete_all", None))
            else:
                empty_action = menu.addAction("📍 视频点：暂无")
                empty_action.setEnabled(False)

            menu.addSeparator()
            chain_manage_action = menu.addAction("🔗 设置/管理串联任务")
            menu.addSeparator()
            segment_action = menu.addAction("✂️ 设置多段播放区段")
            
            original_url = item.data(self.ORIGINAL_URL_ROLE)
            is_network = str(item.data(Qt.UserRole)).startswith("http")
            
            copy_action = None
            reload_action = None
            if original_url or is_network:
                menu.addSeparator()
                copy_action = menu.addAction("🔗 复制网络源链接")
                reload_action = menu.addAction("🔄 重新解析/刷新该流媒体")

            menu.addSeparator()
            remove_item_action = menu.addAction("❌ 移除该媒体")
            clear_item_points = menu.addAction("🗑 清理此视频全部视频点")
            clear_item_points.setEnabled(bool(points))
            menu.addSeparator()
            clear_playlist = menu.addAction("🗑 清理当前列表")

            action = menu.exec(self.mapToGlobal(pos))

            if action == add_action:
                if self.video_point_add_callback: self.video_point_add_callback(item)
            elif action == chain_manage_action:
                if self.chain_add_callback: self.chain_add_callback(item)
            elif action == segment_action:
                if self.segment_set_callback: self.segment_set_callback(item)
            elif copy_action and action == copy_action:
                url_to_copy = original_url or item.data(Qt.UserRole)
                QApplication.clipboard().setText(url_to_copy)
            elif reload_action and action == reload_action:
                if self.reload_network_callback: self.reload_network_callback(item)
            elif action == remove_item_action:
                if self.item_removed_callback: self.item_removed_callback(item)
                else:
                    row = self.row(item)
                    self.takeItem(row)
            elif action == clear_item_points:
                self.set_points(item, [])
                self.itemChanged.emit(item)
            elif action == clear_playlist:
                self.clear()
            elif action:
                data = action.data()
                if isinstance(data, tuple):
                    command, point = data
                    if command == "delete_one":
                        points = self.get_points(item)
                        if point in points:
                            points.remove(point)
                            self.set_points(item, points)
                    elif command == "delete_all":
                        self.set_points(item, [])
        else:
            clear_action = menu.addAction("🗑 清理当前列表")
            action = menu.exec(self.mapToGlobal(pos))
            if action == clear_action: self.clear()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.source() == self: event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.source() == self: event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.source() == self:
            super().dropEvent(event)
            if self.playlist_changed_callback: self.playlist_changed_callback()
            return

        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path:
                    name = Path(file_path).name
                    item = QListWidgetItem()
                    item.setData(Qt.DisplayRole, name)
                    item.setData(Qt.UserRole, file_path)
                    if self.duration_fetcher_callback:
                        dur = self.duration_fetcher_callback(file_path)
                        item.setData(Qt.UserRole + 3, format_time_ms(dur) if dur > 0 else "")
                    else:
                        item.setData(Qt.UserRole + 3, "")
                    item.setData(self.VIDEO_POINTS_ROLE, [])
                    item.setData(self.CHAIN_ROLE, [])
                    item.setData(self.SEGMENT_ROLE, [])
                    item.setData(self.ORIGINAL_URL_ROLE, "")
                    self.addItem(item)
            event.acceptProposedAction()
            if self.playlist_changed_callback: self.playlist_changed_callback()
        else:
            super().dropEvent(event)

class VideoWindow(QWidget):
    def __init__(self):
        super().__init__()
        icon_path = resource_path("iii.png")
        if Path(icon_path).exists(): self.setWindowIcon(QIcon(icon_path))
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowTitle("Pure_Video_Screen")
        self.resize(800, 450)
        self.setStyleSheet("background-color: #000000;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.video_frame = QWidget(self)
        main_layout.addWidget(self.video_frame)

class ClickableLabel(QLabel):
    def __init__(self, text="00:00:00"):
        super().__init__(text)
        self.click_callback = None

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self.click_callback:
            self.click_callback()

def set_windows_audio_session_name(display_name):
    if platform.system() != "Windows": return False
    try:
        if not display_name: display_name = "媒体控制台"
        ole32 = ctypes.OleDLL("ole32")
        ole32.CoInitialize(None)

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

        def guid(text):
            import uuid
            u = uuid.UUID(text)
            return GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))

        CLSID_MMDEVICE = guid("BCDE0395-E52F-467C-8E3D-C4579291692E")
        IID_IMMDEVICE_ENUM = guid("A95664D2-9614-4F35-A746-DE8DB63617E6")
        IID_IAUDIO_SESSION_MANAGER2 = guid("77AA99A0-1BD6-484F-8BC7-2C8C2A56F3D5")
        IID_IAUDIO_SESSION_CONTROL2 = guid("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D")
        CLSCTX_ALL = 23; E_RENDER = 0; E_CONSOLE = 0
        pid = ctypes.windll.kernel32.GetCurrentProcessId()

        def call_method(obj, index, restype, argtypes, *args):
            vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            fn_ptr = vtbl[index]
            fn = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(fn_ptr)
            return fn(obj, *args)

        ole32.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        ole32.CoCreateInstance.restype = wintypes.HRESULT

        enum_ptr = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(ctypes.byref(CLSID_MMDEVICE), None, CLSCTX_ALL, ctypes.byref(IID_IMMDEVICE_ENUM), ctypes.byref(enum_ptr))
        if hr < 0 or not enum_ptr: ole32.CoUninitialize(); return False

        device_ptr = ctypes.c_void_p()
        hr = call_method(enum_ptr, 4, wintypes.HRESULT, [ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)], E_RENDER, E_CONSOLE, ctypes.byref(device_ptr))
        if hr < 0 or not device_ptr: call_method(enum_ptr, 2, ctypes.c_ulong, []); ole32.CoUninitialize(); return False

        session_mgr = ctypes.c_void_p()
        hr = call_method(device_ptr, 3, wintypes.HRESULT, [ctypes.POINTER(GUID), ctypes.c_ulong, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(IID_IAUDIO_SESSION_MANAGER2), CLSCTX_ALL, None, ctypes.byref(session_mgr))
        if hr < 0 or not session_mgr: call_method(device_ptr, 2, ctypes.c_ulong, []); call_method(enum_ptr, 2, ctypes.c_ulong, []); ole32.CoUninitialize(); return False

        session_enum = ctypes.c_void_p()
        hr = call_method(session_mgr, 5, wintypes.HRESULT, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(session_enum))
        if hr < 0 or not session_enum:
            call_method(session_mgr, 2, ctypes.c_ulong, []); call_method(device_ptr, 2, ctypes.c_ulong, []); call_method(enum_ptr, 2, ctypes.c_ulong, []); ole32.CoUninitialize(); return False

        count = ctypes.c_int(0)
        hr = call_method(session_enum, 3, wintypes.HRESULT, [ctypes.POINTER(ctypes.c_int)], ctypes.byref(count))
        if hr < 0:
            call_method(session_enum, 2, ctypes.c_ulong, []); call_method(session_mgr, 2, ctypes.c_ulong, []); call_method(device_ptr, 2, ctypes.c_ulong, []); call_method(enum_ptr, 2, ctypes.c_ulong, []); ole32.CoUninitialize(); return False

        renamed = False
        for i in range(count.value):
            ctrl = ctypes.c_void_p()
            hr = call_method(session_enum, 4, wintypes.HRESULT, [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)], i, ctypes.byref(ctrl))
            if hr < 0 or not ctrl: continue

            ctrl2 = ctypes.c_void_p()
            iid_ptr = ctypes.byref(IID_IAUDIO_SESSION_CONTROL2)
            hr = call_method(ctrl, 0, wintypes.HRESULT, [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)], iid_ptr, ctypes.byref(ctrl2))
            if hr >= 0 and ctrl2:
                session_pid = ctypes.c_uint32(0)
                hr_pid = call_method(ctrl2, 14, wintypes.HRESULT, [ctypes.POINTER(ctypes.c_uint32)], ctypes.byref(session_pid))
                if hr_pid >= 0 and session_pid.value == pid:
                    call_method(ctrl2, 5, wintypes.HRESULT, [ctypes.c_wchar_p, ctypes.c_void_p], display_name, None)
                    renamed = True
                    call_method(ctrl2, 2, ctypes.c_ulong, []); call_method(ctrl, 2, ctypes.c_ulong, [])
                    break
                call_method(ctrl2, 2, ctypes.c_ulong, [])
            call_method(ctrl, 2, ctypes.c_ulong, [])

        call_method(session_enum, 2, ctypes.c_ulong, []); call_method(session_mgr, 2, ctypes.c_ulong, []); call_method(device_ptr, 2, ctypes.c_ulong, []); call_method(enum_ptr, 2, ctypes.c_ulong, [])
        ole32.CoUninitialize()
        return renamed
    except Exception:
        try: ctypes.OleDLL("ole32").CoUninitialize()
        except: pass
        return False

# ==========================================
# 主控制台
# ==========================================
class ControlWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.app_icon_path = resource_path("iii.png")
        if Path(self.app_icon_path).exists():
            icon = QIcon(self.app_icon_path)
            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)

        self.setAcceptDrops(True)
        self.custom_title = ""
        self.default_title = "媒体控制台"
        self.setWindowTitle(self.default_title)

        self.collapsed_height = 165
        self.expanded_height = 360
        self.setMinimumWidth(680); self.setMaximumWidth(680)
        self.setMinimumHeight(self.collapsed_height); self.setMaximumHeight(self.collapsed_height)

        self.vlc_instance = vlc.Instance("--avcodec-hw=none", "--quiet")
        self.player = self.vlc_instance.media_player_new()

        self.video_window = None
        self.current_media_path = None
        self.current_list_item = None
        self.saved_video_size = QSize(800, 450)

        self.is_paused = False
        self.skip_step_seconds = 10
        self.time_format_mode = 0
        self.video_popup_seconds = 5
        self.chain_popup_seconds = 5
        self.playlist_click_mode = "single"
        self.default_video_open = True
        self.network_auto_play = True
        
        self.audio_recorder = AudioRecorder(self)
        self.record_save_dir = str(Path.cwd() / "Recordings")
        self.auto_upload_drive = False
        self.drive_folder_id = ""
        self.playlist_db_path = str(Path.cwd() / "Playlists" / "my_playlists_db.json")

        self.triggered_video_points = set()
        self.chain_stack = []
        self.triggered_chain_tasks = set()
        self.current_chain_end_ms = -1
        self.last_player_time_ms = -1
        self._cached_events = []
        self.auto_skip_paths = set()
        self.alarms_list = []

        config_path = str(Path.cwd() / "MediaConsoleConfig.ini")
        self.app_settings = QSettings(config_path, QSettings.IniFormat)
        self._loading_settings = True

        Theme.accent = self.app_settings.value("settings/theme_color", "#89b4fa", str)

        self.dummy_video_widget = QWidget()
        self.dummy_video_widget.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.Tool)
        self.dummy_video_widget.setGeometry(-5000, -5000, 1, 1)
        self.dummy_video_widget.show()

        self.bind_vlc_to_dummy()
        self.setStyleSheet(get_qss())
        self.setup_ui()
        self.load_persistent_settings()
        self._loading_settings = False
        self.update_audio_session_name()

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)
        
        self.record_timer = QTimer(self)
        self.record_timer.setInterval(1000)
        self.record_timer.timeout.connect(self._update_record_status)
        self.record_timer.start()

    def read_playlist_db(self):
        p = Path(self.playlist_db_path)
        if p.exists():
            try:
                with open(p, 'r', encoding='utf-8') as f: return json.load(f)
            except: pass
        return []

    def write_playlist_db(self, data):
        p = Path(self.playlist_db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

    def update_audio_session_name(self):
        name = self.custom_title or self.default_title or "媒体控制台"
        QApplication.setApplicationName(name)
        QApplication.setApplicationDisplayName(name)
        
        try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(name)
        except: pass
        
        try:
            if hasattr(self.vlc_instance, 'set_app_id'): self.vlc_instance.set_app_id(name, "", "")
        except: pass
        
        for t in [100, 500, 1000, 2000, 4000, 6000, 8000, 10000]:
            QTimer.singleShot(t, lambda: set_windows_audio_session_name(name))

    def setup_ui(self):
        central_widget = QWidget()
        central_widget.setAcceptDrops(True)
        self.setCentralWidget(central_widget)

        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.top_container = QWidget()
        self.top_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        top_layout = QVBoxLayout(self.top_container)
        top_layout.setSpacing(8)
        top_layout.setContentsMargins(15, 10, 15, 10)

        title_row = QHBoxLayout()
        left_side = QWidget(); left_side.setFixedSize(150, 25)
        title_row.addWidget(left_side)
        
        self.center_title_label = QLabel(self.custom_title)
        self.center_title_label.setObjectName("CenterTitle")
        self.center_title_label.setAlignment(Qt.AlignCenter)
        self.center_title_label.setFixedHeight(25)
        title_row.addWidget(self.center_title_label, 1)
        
        right_side = QWidget(); right_side.setFixedSize(150, 25)
        right_layout = QHBoxLayout(right_side); right_layout.setContentsMargins(0, 0, 0, 0); right_layout.addStretch()
        self.recording_status_label = QLabel("")
        self.recording_status_label.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 10pt;")
        self.recording_status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right_layout.addWidget(self.recording_status_label)
        title_row.addWidget(right_side)
        top_layout.addLayout(title_row)

        self.media_name_label = QLabel("暂未播放媒体")
        self.media_name_label.setStyleSheet("color: #a6adc8; font-size: 9pt; font-weight: normal;")
        self.media_name_label.setAlignment(Qt.AlignLeft)
        top_layout.addWidget(self.media_name_label)

        self.video_point_alert = QLabel("", self.top_container)
        self.video_point_alert.setObjectName("VideoPointAlert")
        self.video_point_alert.setAlignment(Qt.AlignCenter)
        self.video_point_alert.setFixedHeight(24)
        self.video_point_alert.hide()
        self.position_video_point_alert()

        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(5)
        self.slider = WaveSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderMoved.connect(self.set_position)
        progress_layout.addWidget(self.slider)

        self.time_label = ClickableLabel("00:00:00 / 00:00:00")
        self.time_label.setObjectName("TimeLabel")
        self.time_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.time_label.setFixedSize(160, 35)
        self.time_label.click_callback = self.toggle_time_format
        progress_layout.addWidget(self.time_label)
        top_layout.addLayout(progress_layout)

        controls_layout = QHBoxLayout()
        self.toggle_win_btn = QPushButton(" 视频窗口")
        self.toggle_win_btn.setIcon(self.style().standardIcon(QStyle.SP_DesktopIcon))
        
        self.load_file_btn = QPushButton(" 载入文件")
        self.load_file_btn.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.load_menu = QMenu(self)
        self.load_file_btn.setMenu(self.load_menu)
        self.load_menu.aboutToShow.connect(self.populate_load_menu)

        self.locate_btn = QPushButton()
        self.locate_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.locate_btn.setFixedSize(30, 30)
        self.locate_btn.setToolTip("定位并高亮当前正在播放的条目")
        self.locate_btn.clicked.connect(self.locate_current_item)

        controls_layout.addWidget(self.toggle_win_btn)
        controls_layout.addWidget(self.load_file_btn)
        controls_layout.addWidget(self.locate_btn)
        controls_layout.addStretch(1)

        self.rewind_btn = QPushButton()
        self.rewind_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.rewind_btn.setFixedSize(36, 36)
        self.play_btn = QPushButton()
        self.play_btn.setObjectName("PlayButton")
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.setFixedSize(40, 40)
        self.forward_btn = QPushButton()
        self.forward_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.forward_btn.setFixedSize(36, 36)

        controls_layout.addWidget(self.rewind_btn)
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.forward_btn)
        controls_layout.addStretch(1)

        self.jump_btn = QPushButton("跳转到")
        self.volume_widget = VolumeWidget()
        
        self.record_btn = QPushButton("🔴")
        self.record_btn.setFixedSize(30, 30)
        self.record_btn.setToolTip("左键: 一键开始/停止录音\n右键: 管理定时录音列表")
        self.record_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.record_btn.customContextMenuRequested.connect(self.show_record_menu)
        
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(30, 30)
        self.playlist_toggle_btn = QPushButton("⇊")
        self.playlist_toggle_btn.setFixedSize(30, 30)

        controls_layout.addWidget(self.jump_btn)
        controls_layout.addWidget(self.volume_widget)
        controls_layout.addWidget(self.record_btn)
        controls_layout.addWidget(self.settings_btn)
        controls_layout.addWidget(self.playlist_toggle_btn)
        top_layout.addLayout(controls_layout)

        self.main_layout.addWidget(self.top_container, 0, Qt.AlignTop)

        self.playlist_widget = QWidget()
        self.playlist_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        playlist_layout = QVBoxLayout(self.playlist_widget)
        playlist_layout.setContentsMargins(15, 0, 15, 10)

        self.list_widget = DragDropListWidget()
        self.list_widget.video_point_add_callback = self.add_video_point_for_item
        self.list_widget.chain_add_callback = self.add_chain_task_for_item
        self.list_widget.item_removed_callback = self.remove_item_from_list
        self.list_widget.playlist_cleared_callback = self.on_playlist_cleared
        self.list_widget.playlist_changed_callback = self.save_persistent_settings
        self.list_widget.segment_set_callback = self.set_segment_for_item
        self.list_widget.duration_fetcher_callback = self.get_media_duration_sync
        self.list_widget.reload_network_callback = self.reload_network_item

        playlist_layout.addWidget(self.list_widget)
        self.playlist_widget.hide()
        self.main_layout.addWidget(self.playlist_widget, 1)

        self.play_btn.clicked.connect(self.play_pause)
        self.rewind_btn.clicked.connect(self.skip_backward)
        self.forward_btn.clicked.connect(self.skip_forward)
        self.toggle_win_btn.clicked.connect(self.toggle_video_window)
        self.jump_btn.clicked.connect(self.open_jump_dialog)
        self.volume_widget.popup.slider.valueChanged.connect(self.change_volume)
        self.record_btn.clicked.connect(self.toggle_record)
        self.settings_btn.clicked.connect(self.open_settings)
        self.playlist_toggle_btn.clicked.connect(self.toggle_playlist)
        self.list_widget.itemClicked.connect(self.handle_list_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self.handle_list_item_double_clicked)
        
        self.shortcut_left = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.shortcut_left.activated.connect(self.skip_backward)
        self.shortcut_right = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.shortcut_right.activated.connect(self.skip_forward)
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_space.activated.connect(self.play_pause)

    def show_record_menu(self, pos):
        menu = QMenu(self)
        act_manage = menu.addAction("⏰ 定时录音列表管理")
        action = menu.exec(self.record_btn.mapToGlobal(pos))
        if action == act_manage:
            dialog = AlarmManagerDialog(self.alarms_list, self)
            if dialog.exec() == QDialog.Accepted:
                self.alarms_list = dialog.get_alarms()
                self.save_persistent_settings()

    def get_next_alarm_info(self):
        now = datetime.now()
        next_time = None
        next_alarm_id = None

        for alarm in self.alarms_list:
            if not alarm.get("active", False):
                continue
            
            parts = alarm["time"].split(":")
            h, m = int(parts[0]), int(parts[1])
            days = alarm.get("days", [])

            target = None
            for i in range(8):
                cand_date = now + timedelta(days=i)
                cand = cand_date.replace(hour=h, minute=m, second=0, microsecond=0)
                
                if days and cand.weekday() not in days:
                    continue
                    
                if cand < now.replace(second=0, microsecond=0):
                    continue
                    
                if cand.date() == now.date() and cand.hour == now.hour and cand.minute == now.minute:
                    last_triggered = alarm.get("last_triggered")
                    if last_triggered:
                        try:
                            last_t = datetime.fromisoformat(last_triggered)
                            if last_t.date() == cand.date() and last_t.hour == cand.hour and last_t.minute == cand.minute:
                                continue
                        except: pass
                            
                target = cand
                break
                
            if target:
                if not next_time or target < next_time:
                    next_time = target
                    next_alarm_id = alarm.get("id")

        return next_time, next_alarm_id

    def locate_current_item(self):
        if hasattr(self, 'current_list_item') and self.current_list_item:
            self.list_widget.setCurrentItem(self.current_list_item)
            self.list_widget.scrollToItem(self.current_list_item)

    def _add_media_item(self, name, path, dur_ms, points=None, chains=None, headers=None, audio_url="", segments=None, original_url=""):
        item = QListWidgetItem()
        item.setData(Qt.DisplayRole, name)
        item.setData(Qt.UserRole, path)
        item.setData(Qt.UserRole + 3, format_time_ms(dur_ms) if dur_ms > 0 else "")
        item.setData(DragDropListWidget.VIDEO_POINTS_ROLE, points or [])
        item.setData(DragDropListWidget.CHAIN_ROLE, chains or [])
        item.setData(DragDropListWidget.HEADERS_ROLE, headers or {})
        item.setData(DragDropListWidget.AUDIO_URL_ROLE, audio_url)
        item.setData(DragDropListWidget.SEGMENT_ROLE, segments or [])
        item.setData(DragDropListWidget.ORIGINAL_URL_ROLE, original_url)
        self.list_widget.addItem(item)
        return item

    def _stop_and_clear_state(self):
        try:
            self.timer.stop()
            self.player.stop()
        except: pass
        self.current_media_path = None
        self.current_list_item = None
        self.triggered_video_points.clear()
        self.chain_stack.clear()
        self.triggered_chain_tasks.clear()
        self.current_chain_end_ms = -1
        self._cached_events = []
        self.auto_skip_paths.clear()
        
        self.hide_video_point_alert()
        self.slider.set_segments([])
        self.slider.set_video_points([])
        self.slider.set_chain_points([])
        self.slider.generate_wave_for_media(None)
        
        self.media_name_label.setText("暂未播放媒体")
        self.media_name_label.setStyleSheet("color: #a6adc8; font-size: 9pt; font-weight: normal;")
        self.time_label.setText("00:00:00 / 00:00:00")
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def _handle_missing_media(self, item):
        display_name = item.data(Qt.DisplayRole) if item else "未知媒体"
        self.media_name_label.setText(f"❌ 找不到媒体: {display_name}")
        self.media_name_label.setStyleSheet("color: #f38ba8; font-size: 9pt; font-weight: bold;")
        self.player.stop()
        self.timer.stop()
        self.is_paused = True
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.current_media_path = None

    def _create_vlc_media(self, path, item, is_network):
        media = self.vlc_instance.media_new(path)
        if is_network:
            headers = item.data(DragDropListWidget.HEADERS_ROLE) if item else {}
            audio_url = item.data(DragDropListWidget.AUDIO_URL_ROLE) if item else ""
            headers = headers or {}
            ua = headers.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
            media.add_option(f":http-user-agent={ua}")
            if headers.get('Cookie'): media.add_option(f":http-cookie={headers['Cookie']}")
            if headers.get('Referer'): media.add_option(f":http-referrer={headers['Referer']}")
            if audio_url: media.add_option(f":input-slave={audio_url}")
            media.add_option(":network-caching=1500")
            media.add_option(":http-reconnect=true")
        return media

    def position_video_point_alert(self):
        if hasattr(self, "video_point_alert"):
            self.video_point_alert.setGeometry(15, 12, 235, 24)
        
    def populate_load_menu(self):
        self.load_menu.clear()
        act_new_file = self.load_menu.addAction("📽️ 载入新媒体文件")
        act_new_file.triggered.connect(self.load_files_to_list)
        act_new_folder = self.load_menu.addAction("📁 载入视频文件夹")
        act_new_folder.triggered.connect(self.load_folder_to_list)
        self.load_menu.addSeparator()
        act_new_net = self.load_menu.addAction("🌐 载入网络媒体 (YouTube等)")
        act_new_net.triggered.connect(self.load_network_stream)
        self.load_menu.addSeparator()

        db = self.read_playlist_db()
        if db:
            my_list_menu = self.load_menu.addMenu("🗂️ 我的固定列表")
            for folder in db:
                f_menu = my_list_menu.addMenu(f"📂 {folder['folder_name']}")
                for pl in folder['playlists']:
                    act = f_menu.addAction(f"🎵 {pl['name']}")
                    act.triggered.connect(lambda checked=False, items=pl['items']: self.load_fixed_playlist_items(items))
        else:
            act = self.load_menu.addAction("🗂️ 暂无固定列表")
            act.setEnabled(False)

        self.load_menu.addSeparator()
        act_save = self.load_menu.addAction("💾 将当前播放条目保存为列表")
        act_save.triggered.connect(self.save_current_as_fixed_playlist)
        act_manage = self.load_menu.addAction("⚙️ 排序与管理我的列表")
        act_manage.triggered.connect(self.manage_fixed_playlists)
        
        self.load_menu.addSeparator()
        act_export = self.load_menu.addAction("📤 导出固定列表配置")
        act_export.triggered.connect(self.export_playlists)
        act_import = self.load_menu.addAction("📥 导入固定列表配置")
        act_import.triggered.connect(self.import_playlists)

    def load_network_stream(self):
        try: import yt_dlp
        except ImportError:
            QMessageBox.warning(self, "缺少核心依赖", "未检测到解析库！\n\n请在终端运行:\npip install -U yt-dlp")
            return

        url, ok = QInputDialog.getText(self, "载入网络流媒体", "请输入支持的视频链接 (如 YouTube URL):")
        if ok and url.strip():
            url = url.strip()
            self.loading_dialog = QDialog(self)
            self.loading_dialog.setWindowTitle("网络探针")
            self.loading_dialog.setFixedSize(280, 100)
            self.loading_dialog.setWindowModality(Qt.ApplicationModal)
            self.loading_dialog.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
            self.loading_dialog.setStyleSheet(get_qss())
            layout = QVBoxLayout(self.loading_dialog)
            layout.addWidget(QLabel("正在穿透解析真实视频流，请稍候...", alignment=Qt.AlignCenter))
            
            self.yt_worker = YtDlpWorker(url)
            self.yt_worker.original_url = url
            self.yt_worker.finished_signal.connect(self._on_yt_finished)
            self.yt_worker.error_signal.connect(self._on_yt_error)
            self.yt_worker.start()
            self.loading_dialog.exec()

    def reload_network_item(self, item):
        url = item.data(DragDropListWidget.ORIGINAL_URL_ROLE)
        if not url: url = item.data(Qt.UserRole)
        
        self.loading_dialog = QDialog(self)
        self.loading_dialog.setWindowTitle("重新加载")
        self.loading_dialog.setFixedSize(280, 100)
        self.loading_dialog.setStyleSheet(get_qss())
        layout = QVBoxLayout(self.loading_dialog)
        layout.addWidget(QLabel("正在重新解析视频流，请稍候...", alignment=Qt.AlignCenter))
        
        self.yt_worker = YtDlpWorker(url)
        self.yt_worker.original_url = url
        self.yt_worker.item_to_update = item
        self.yt_worker.finished_signal.connect(self._on_yt_finished)
        self.yt_worker.error_signal.connect(self._on_yt_error)
        self.yt_worker.start()
        self.loading_dialog.exec()

    def _on_yt_finished(self, info):
        if hasattr(self, 'loading_dialog') and self.loading_dialog: self.loading_dialog.close()

        formats = info.get('requested_formats')
        if formats and len(formats) >= 2:
            stream_url = formats[0].get('url')
            audio_url = formats[1].get('url')
            headers = formats[0].get('http_headers', {})
        else:
            stream_url = info.get('url')
            audio_url = ""
            headers = info.get('http_headers', {})

        title = info.get('title', 'Unknown Network Stream')
        duration_sec = info.get('duration', -1)

        item_to_update = getattr(self.yt_worker, 'item_to_update', None)
        original_url = getattr(self.yt_worker, 'original_url', self.yt_worker.url)

        if not stream_url:
            QMessageBox.warning(self, "解析失败", "未能获取到真实的流媒体直连地址。")
            return

        if item_to_update:
            item_to_update.setData(Qt.UserRole, stream_url)
            item_to_update.setData(DragDropListWidget.HEADERS_ROLE, headers)
            item_to_update.setData(DragDropListWidget.AUDIO_URL_ROLE, audio_url)
            item_to_update.setData(DragDropListWidget.ORIGINAL_URL_ROLE, original_url)
            if self.current_list_item == item_to_update:
                self.play_media(stream_url, item_to_update)
            QMessageBox.information(self, "刷新成功", "该网络流媒体已重新解析并更新。")
            self.save_persistent_settings()
        else:
            dur_ms = int(duration_sec * 1000) if duration_sec and duration_sec > 0 else -1
            item = self._add_media_item(f"🌐 {title}", stream_url, dur_ms, headers=headers, audio_url=audio_url, original_url=original_url)

            if not self.playlist_widget.isVisible(): self.toggle_playlist()
            self.save_persistent_settings()
            
            if getattr(self, "network_auto_play", True):
                self.list_widget.setCurrentItem(item)
                self.handle_list_click(item, is_manual=True)

    def _on_yt_error(self, err_msg):
        if hasattr(self, 'loading_dialog') and self.loading_dialog: self.loading_dialog.close()
        QMessageBox.warning(self, "解析失败", f"无法解析该链接:\n\n{err_msg}")

    def load_fixed_playlist_items(self, items):
        self.list_widget.clear()
        for entry in items:
            path = entry.get("path")
            if not path: continue
            is_network = str(path).startswith("http://") or str(path).startswith("https://")
            saved_name = entry.get("name")
            name = saved_name if saved_name else ("🌐 Network Stream" if is_network else Path(path).name)
            dur = -1 if is_network else self.get_media_duration_sync(path)
            
            self._add_media_item(
                name, path, dur,
                points=sorted(set(int(x) for x in entry.get("points", []) if int(x) >= 0)),
                chains=entry.get("chains", []),
                headers=entry.get("headers", {}),
                audio_url=entry.get("audio_url", ""),
                segments=entry.get("segment", []),
                original_url=entry.get("original_url", "")
            )
        if not self.playlist_widget.isVisible(): self.toggle_playlist()
        self.save_persistent_settings()

    def save_current_as_fixed_playlist(self):
        if self.list_widget.count() == 0:
            QMessageBox.warning(self, "提示", "当前播放列表为空，没有可以保存的内容！")
            return
        db = self.read_playlist_db()
        dialog = SavePlaylistDialog(db, self)
        
        if dialog.exec() == QDialog.Accepted:
            folder_name, pl_name = dialog.get_data()
            if not folder_name or not pl_name:
                QMessageBox.warning(self, "错误", "文件夹和列表名不能为空！")
                return

            items = []
            for row in range(self.list_widget.count()):
                item = self.list_widget.item(row)
                items.append({
                    "name": item.data(Qt.DisplayRole),
                    "path": item.data(Qt.UserRole),
                    "points": self.list_widget.get_points(item),
                    "chains": self.list_widget.get_chains(item),
                    "headers": item.data(DragDropListWidget.HEADERS_ROLE) or {},
                    "audio_url": item.data(DragDropListWidget.AUDIO_URL_ROLE) or "",
                    "segment": item.data(DragDropListWidget.SEGMENT_ROLE) or [],
                    "original_url": item.data(DragDropListWidget.ORIGINAL_URL_ROLE) or ""
                })

            folder_obj = next((f for f in db if f["folder_name"] == folder_name), None)
            if not folder_obj:
                folder_obj = {"folder_name": folder_name, "playlists": []}
                db.append(folder_obj)

            pl_obj = next((p for p in folder_obj["playlists"] if p["name"] == pl_name), None)
            if pl_obj: pl_obj["items"] = items
            else: folder_obj["playlists"].append({"name": pl_name, "items": items})

            self.write_playlist_db(db)
            QMessageBox.information(self, "保存成功", "列表已成功保存至内部数据库！")

    def manage_fixed_playlists(self):
        db = self.read_playlist_db()
        if not db:
            QMessageBox.information(self, "提示", "您还没有保存任何固定列表。")
            return
        dialog = ManagePlaylistsDialog(db, self)
        if dialog.exec() == QDialog.Accepted:
            new_db = dialog.get_new_data()
            new_db = [f for f in new_db if f["playlists"]]
            self.write_playlist_db(new_db)

    def export_playlists(self):
        db = self.read_playlist_db()
        if not db:
            QMessageBox.warning(self, "提示", "当前没有任何固定列表可以导出。")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出列表配置", "MediaPlaylists.json", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(db, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "导出成功", f"列表配置已成功导出至:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出过程中发生错误:\n{str(e)}")

    def import_playlists(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入列表配置", "", "JSON Files (*.json)")
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                new_db = json.load(f)
            
            if not isinstance(new_db, list):
                raise ValueError("无效的配置文件格式")

            reply = QMessageBox.question(
                self, "导入模式", 
                "你想覆盖现有的固定列表吗？\n\n[Yes/是] 清空现有列表并完全替换\n[No/否] 追加合并到现有的固定列表中",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes
            )
            
            if reply == QMessageBox.Cancel:
                return
            
            current_db = self.read_playlist_db()
            if reply == QMessageBox.Yes:
                self.write_playlist_db(new_db)
            elif reply == QMessageBox.No:
                for new_folder in new_db:
                    existing_folder = next((f for f in current_db if f["folder_name"] == new_folder["folder_name"]), None)
                    if existing_folder:
                        existing_folder["playlists"].extend(new_folder["playlists"])
                    else:
                        current_db.append(new_folder)
                self.write_playlist_db(current_db)

            QMessageBox.information(self, "导入成功", "固定列表配置已成功导入！")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"读取配置文件时发生错误，格式可能不正确:\n{str(e)}")

    def toggle_time_format(self):
        self.time_format_mode = (self.time_format_mode + 1) % 2
        self._last_text_update_ms = -2000
        
        if self.player.get_media():
            current_ms = self.player.get_time()
            length_ms = self.player.get_length()
            if current_ms >= 0 and length_ms > 0:
                cur_str = QTime(0, 0, 0).addMSecs(current_ms).toString("hh:mm:ss")
                len_str = QTime(0, 0, 0).addMSecs(length_ms).toString("hh:mm:ss")
                if self.time_format_mode == 0: self.time_label.setText(f"{cur_str} / {len_str}")
                else:
                    remain_ms = max(0, length_ms - current_ms)
                    rem_str = QTime(0, 0, 0).addMSecs(remain_ms).toString("hh:mm:ss")
                    self.time_label.setText(f"已播: {cur_str}\n剩余: {rem_str}")
        self.update_ui()

    def save_persistent_settings(self):
        try:
            st = self.app_settings
            st.setValue("settings/custom_title", self.custom_title)
            st.setValue("settings/skip_step_seconds", self.skip_step_seconds)
            st.setValue("settings/video_popup_seconds", self.video_popup_seconds)
            st.setValue("settings/chain_popup_seconds", getattr(self, "chain_popup_seconds", 5))
            st.setValue("settings/playlist_click_mode", self.playlist_click_mode)
            st.setValue("settings/default_video_open", self.default_video_open)
            st.setValue("settings/network_auto_play", getattr(self, "network_auto_play", True))
            st.setValue("settings/time_format_mode", self.time_format_mode)
            st.setValue("settings/volume", self.volume_widget.slider_value())
            st.setValue("settings/muted", self.volume_widget.is_muted)
            st.setValue("settings/theme_color", Theme.accent)
            st.setValue("settings/record_save_dir", self.record_save_dir)
            st.setValue("settings/auto_upload_drive", getattr(self, "auto_upload_drive", False))
            st.setValue("settings/drive_folder_id", getattr(self, "drive_folder_id", ""))
            st.setValue("settings/alarms_list", json.dumps(getattr(self, "alarms_list", [])))
            st.setValue("window/control_geometry", self.saveGeometry())

            if self.saved_video_size.isValid():
                st.setValue("window/video_width", self.saved_video_size.width())
                st.setValue("window/video_height", self.saved_video_size.height())

            playlist_data = []
            for row in range(self.list_widget.count()):
                item = self.list_widget.item(row)
                if not item: continue
                playlist_data.append({
                    "name": item.data(Qt.DisplayRole),
                    "path": item.data(Qt.UserRole),
                    "points": self.list_widget.get_points(item),
                    "chains": self.list_widget.get_chains(item),
                    "headers": item.data(DragDropListWidget.HEADERS_ROLE) or {},
                    "audio_url": item.data(DragDropListWidget.AUDIO_URL_ROLE) or "",
                    "segment": item.data(DragDropListWidget.SEGMENT_ROLE) or [],
                    "original_url": item.data(DragDropListWidget.ORIGINAL_URL_ROLE) or ""
                })
            st.setValue("playlist/data", json.dumps(playlist_data, ensure_ascii=False))
            st.sync()
        except: pass

    def load_persistent_settings(self):
        st = self.app_settings
        self.skip_step_seconds = int(st.value("settings/skip_step_seconds", 10))
        self.video_popup_seconds = int(st.value("settings/video_popup_seconds", 5))
        self.chain_popup_seconds = int(st.value("settings/chain_popup_seconds", 5))
        self.playlist_click_mode = st.value("settings/playlist_click_mode", "single", str)
        self.default_video_open = str(st.value("settings/default_video_open", "true")).lower() == "true"
        self.network_auto_play = str(st.value("settings/network_auto_play", "true")).lower() == "true"
        self.time_format_mode = int(st.value("settings/time_format_mode", 0))

        self.saved_video_size = QSize(int(st.value("window/video_width", 800)), int(st.value("window/video_height", 450)))
        geometry = st.value("window/control_geometry", None)
        if geometry:
            try: self.restoreGeometry(geometry)
            except: pass

        self.custom_title = st.value("settings/custom_title", "", str)
        if self.custom_title:
            self.center_title_label.setText(self.custom_title)
            self.setWindowTitle(f"{self.custom_title} - {self.default_title}")
        else:
            self.center_title_label.setText("")

        volume = int(st.value("settings/volume", 100))
        muted = str(st.value("settings/muted", "false")).lower() in ("1", "true", "yes")
        if muted: self.volume_widget.set_volume(0)
        else: self.volume_widget.set_volume(volume)
            
        self.record_save_dir = st.value("settings/record_save_dir", str(Path.cwd() / "Recordings"), str)
        self.auto_upload_drive = str(st.value("settings/auto_upload_drive", "false")).lower() == "true"
        self.drive_folder_id = st.value("settings/drive_folder_id", "", str)

        alarms_raw = st.value("settings/alarms_list", "[]", str)
        try:
            self.alarms_list = json.loads(alarms_raw)
        except:
            self.alarms_list = []

        raw = st.value("playlist/data", "", str)
        if raw:
            try:
                playlist_data = json.loads(raw)
                for entry in playlist_data:
                    path = entry.get("path")
                    if not path: continue
                    is_network = str(path).startswith("http://") or str(path).startswith("https://")
                    saved_name = entry.get("name")
                    name = saved_name if saved_name else ("🌐 Network Stream" if is_network else Path(path).name)
                    dur = -1 if is_network else self.get_media_duration_sync(path)
                    
                    self._add_media_item(
                        name, path, dur,
                        points=sorted(set(int(x) for x in entry.get("points", []) if int(x) >= 0)),
                        chains=entry.get("chains", []),
                        headers=entry.get("headers", {}),
                        audio_url=entry.get("audio_url", ""),
                        segments=entry.get("segment", []),
                        original_url=entry.get("original_url", "")
                    )
            except: pass

    def on_playlist_cleared(self):
        self._stop_and_clear_state()
        self.save_persistent_settings()
        
    def remove_item_from_list(self, item):
        if item == self.current_list_item:
            self._stop_and_clear_state()
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
        self.save_persistent_settings()

    def load_files_to_list(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择音视频文件", "", "所有文件 (*)")
        if files:
            for file_path in files:
                self._add_media_item(Path(file_path).name, file_path, self.get_media_duration_sync(file_path))
            if not self.playlist_widget.isVisible(): self.toggle_playlist()
            self.save_persistent_settings()
            
    def load_folder_to_list(self):
        d = QFileDialog.getExistingDirectory(self, "选择媒体文件夹")
        if not d: return
        valid_exts = {".mp3", ".mp4", ".m4a", ".wav", ".avi", ".mkv", ".flac", ".aac"}
        files = [f for f in Path(d).iterdir() if f.is_file() and f.suffix.lower() in valid_exts]
        if not files:
            QMessageBox.information(self, "提示", "所选文件夹中没有支持的音视频文件。")
            return
        for file_path_obj in files:
            self._add_media_item(file_path_obj.name, str(file_path_obj), self.get_media_duration_sync(str(file_path_obj)))
        if not self.playlist_widget.isVisible(): self.toggle_playlist()
        self.save_persistent_settings()

    def handle_list_item_clicked(self, item):
        if self.playlist_click_mode == "single": self.handle_list_click(item, is_manual=True)

    def handle_list_item_double_clicked(self, item):
        if self.playlist_click_mode == "double": self.handle_list_click(item, is_manual=True)

    def handle_list_click(self, item, is_manual=False):
        if is_manual: self.auto_skip_paths.clear()
        path = item.data(Qt.UserRole)
        if path: self.play_media(path, item)

    def set_segment_for_item(self, item):
        path = item.data(Qt.UserRole)
        dur = self.get_media_duration_ms(path)
        current_segments = item.data(DragDropListWidget.SEGMENT_ROLE) or []
        dialog = SegmentDialog(duration_ms=dur, current_segments=current_segments, parent=self)
        if dialog.exec() == QDialog.Accepted:
            segs = dialog.get_segments()
            item.setData(DragDropListWidget.SEGMENT_ROLE, segs)
            self.save_persistent_settings()
            if self.current_media_path and item.data(Qt.UserRole) == self.current_media_path:
                self.slider.set_segments(segs)
                if segs:
                    self.active_segments = sorted(segs, key=lambda x: x.get('start_ms', 0))
                    self.current_seg_index = 0
                    start_ms = self.active_segments[0].get('start_ms', 0)
                    self.player.set_time(start_ms)
                else:
                    self.active_segments = []
                    self.current_seg_index = -1
            self.list_widget.viewport().update()

    def add_video_point_for_item(self, item):
        path = item.data(Qt.UserRole) if item else None
        duration_ms = self.get_media_duration_ms(path) if path else -1
        dialog = TimeInputDialog(self, "增加视频点", duration_ms=duration_ms)
        if dialog.exec() != QDialog.Accepted: return

        target_ms = dialog.get_target_ms()
        points = self.list_widget.get_points(item)
        if target_ms not in points: points.append(target_ms)
        self.list_widget.set_points(item, points)

        if self.current_media_path and item.data(Qt.UserRole) == self.current_media_path and self.player.get_media():
            self.refresh_video_points()
        self.save_persistent_settings()

    def add_chain_task_for_item(self, item):
        playlist = []
        target_durations = {}

        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            display_name = it.data(Qt.DisplayRole)
            path = it.data(Qt.UserRole)
            playlist.append((display_name, path))
            
            # 优先用更准确的时长
            dur_ms = self.get_media_duration_ms(path)
            if dur_ms <= 0:
                # 再尝试从列表缓存的字符串解析
                dur_str = it.data(Qt.UserRole + 3)
                if dur_str:
                    parts = dur_str.split(":")
                    if len(parts) == 3:
                        dur_ms = time_tuple_to_ms(parts[0], parts[1], parts[2])
                    elif len(parts) == 2:
                        dur_ms = time_tuple_to_ms("0", parts[0], parts[1])
            target_durations[path] = dur_ms
            
        if not playlist:
            QMessageBox.warning(self, "无可用文件", "当前播放列表为空，请先载入媒体文件。")
            return

        existing_chains = self.list_widget.get_chains(item)
        current_path = item.data(Qt.UserRole)
        
        # 当前这条媒体的时长（优先实时获取）
        duration_ms = self.get_media_duration_ms(current_path)
        if duration_ms <= 0:
            duration_ms = target_durations.get(current_path, -1)

        dialog = ChainTaskDialog(
            playlist=playlist,
            existing_chains=existing_chains,
            duration_ms=duration_ms,
            target_durations=target_durations,
            parent=self
        )
        if dialog.exec() != QDialog.Accepted:
            return

        new_tasks = dialog.get_all_tasks()
        self.list_widget.set_chains(item, new_tasks)
        if self.current_media_path and item.data(Qt.UserRole) == self.current_media_path and self.player.get_media():
            self.refresh_video_points()
        self.save_persistent_settings()

    def refresh_video_points(self):
        if not self.current_media_path:
            self.slider.set_video_points([]); self.slider.set_chain_points([]); self._cached_events = []
            return

        current_item = self.list_widget.find_item_by_path(self.current_media_path)
        if not current_item:
            self.slider.set_video_points([]); self.slider.set_chain_points([]); self._cached_events = []
            return

        points = self.list_widget.get_points(current_item)
        chains = self.list_widget.get_chains(current_item)
        
        self._cached_events = []
        for pt in points: self._cached_events.append({'time': pt, 'type': 'video', 'target': None})
        for ch in chains: self._cached_events.append({'time': ch["trigger_ms"], 'type': 'chain', 'target': ch["target_path"]})
        self._cached_events.sort(key=lambda x: x['time'])

        length_ms = self.player.get_length()
        self.slider.media_length_seconds = length_ms / 1000.0 if length_ms > 0 else 0
        self.slider.set_video_points(points); self.slider.set_chain_points(chains)

    def get_current_video_points(self):
        if not self.current_media_path: return []
        item = self.list_widget.find_item_by_path(self.current_media_path)
        if not item:
            self.current_list_item = None
            return []
        self.current_list_item = item
        return self.list_widget.get_points(item)

    def play_media(self, path, item=None, is_chain=False, chain_start_ms=0, chain_end_ms=-1):
        is_network = str(path).startswith("http://") or str(path).startswith("https://")
        
        if not path or (not is_network and not Path(path).exists()):
            self._handle_missing_media(item)
            return

        display_name = item.data(Qt.DisplayRole) if item else (path if is_network else Path(path).name)
        self.media_name_label.setStyleSheet("color: #a6adc8; font-size: 9pt; font-weight: normal;")
        self.media_name_label.setText(f"当前播放: {display_name}")

        self.current_media_path = path
        self.current_list_item = item
        
        segments = item.data(DragDropListWidget.SEGMENT_ROLE) if item else []
        if isinstance(segments, dict): segments = [segments] if segments else []
            
        self.active_segments = []
        self.current_seg_index = -1
        self.current_chain_end_ms = -1
        
        if is_chain and (chain_start_ms > 0 or chain_end_ms > 0):
            self.active_segments = [{'start_ms': chain_start_ms, 'end_ms': chain_end_ms, 'color': get_contrast_color(Theme.accent)}]
            self.current_seg_index = 0
        elif not is_chain and segments:
            self.active_segments = sorted(segments, key=lambda x: x.get('start_ms', 0))
            self.current_seg_index = 0

        if self.current_list_item: self.list_widget.setCurrentItem(self.current_list_item)
        else: self.list_widget.clearSelection()

        if not is_chain:
            self.chain_stack.clear()
            self.triggered_chain_tasks.clear()

        self.triggered_video_points.clear()
        self.last_player_time_ms = -1

        if is_network:
            if self.default_video_open and not self.video_window: self.open_video_window()
            elif not self.default_video_open and not self.video_window: self.bind_vlc_to_dummy()
        else:
            ext = Path(path).suffix.lower()
            if ext in [".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".webm"]:
                if self.default_video_open and not self.video_window: self.open_video_window()
                elif not self.default_video_open and not self.video_window: self.bind_vlc_to_dummy()
            else:
                if not self.video_window: self.bind_vlc_to_dummy()

        media = self._create_vlc_media(path, item, is_network)
        self.player.set_media(media)
        self.player.play()

        self.timer.start()
        self.is_paused = False
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        self.player.audio_set_volume(self.volume_widget.slider_value())
        self.update_audio_session_name()

        self.slider.generate_wave_for_media(path)
        self.slider.set_segments(self.active_segments)
        self.slider.media_length_seconds = 0
        self.slider.set_video_points([])
        self.slider.set_chain_points([])
        
        if self.active_segments and self.current_seg_index >= 0:
            start_ms = self.active_segments[0].get('start_ms', 0)
            if start_ms > 0: QTimer.singleShot(400, lambda: self.player.set_time(start_ms))

        QTimer.singleShot(300, self.refresh_video_points)

    def return_from_chain(self, chain_info):
        self.current_chain_end_ms = -1
        self.active_segments = []
        self.current_seg_index = -1
        
        path = chain_info["original_path"]
        item = chain_info["original_item"]
        resume_ms = chain_info["resume_ms"]
        is_network = str(path).startswith("http://") or str(path).startswith("https://")

        if not path or (not is_network and not Path(path).exists()):
            self._handle_missing_media(item)
            return

        self.current_media_path = path
        self.current_list_item = item
        self.triggered_video_points.clear()

        display_name = item.data(Qt.DisplayRole) if item else (path if is_network else Path(path).name)
        self.media_name_label.setStyleSheet("color: #a6adc8; font-size: 9pt; font-weight: normal;")
        self.media_name_label.setText(f"当前播放: {display_name}")

        if self.current_list_item: self.list_widget.setCurrentItem(self.current_list_item)
        self.triggered_chain_tasks.clear()

        if item:
            chains = self.list_widget.get_chains(item)
            for i, task in enumerate(chains):
                if task["trigger_ms"] <= resume_ms: self.triggered_chain_tasks.add(f"{path}_{i}")

        media = self._create_vlc_media(path, item, is_network)
        self.player.set_media(media)
        self.player.play()

        QTimer.singleShot(400, lambda: self.player.set_time(resume_ms))
        
        self.timer.start()
        self.is_paused = False
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        
        self.slider.generate_wave_for_media(path)
        self.slider.set_segments([])
        QTimer.singleShot(300, self.refresh_video_points)

    def play_pause(self):
        if not self.player.get_media():
            return

        if self.is_paused:
            # 检查是否已经播到结尾（或处于 Ended/Stopped 状态）
            length = self.player.get_length()
            current = self.player.get_time()
            state = self.player.get_state()

            # 如果已经结束或位置在结尾附近，主动从头开始
            if (state in (vlc.State.Ended, vlc.State.Stopped) or
                (length > 0 and current >= length - 800)):
                self.player.set_time(0)
                self.last_player_time_ms = -1
                self.triggered_video_points.clear()
                # 如果有多段播放，也重置到第一段
                if hasattr(self, 'active_segments') and self.active_segments:
                    self.current_seg_index = 0
                    start_ms = self.active_segments[0].get('start_ms', 0)
                    if start_ms > 0:
                        self.player.set_time(start_ms)

            self.player.play()
            self.is_paused = False
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))

            # 关键：必须重新启动 UI 更新定时器
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.player.pause()
            self.is_paused = True
            self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def skip_forward(self):
        if self.player.get_media(): self.player.set_time(self.player.get_time() + self.skip_step_seconds * 1000)

    def skip_backward(self):
        if self.player.get_media(): self.player.set_time(max(0, self.player.get_time() - self.skip_step_seconds * 1000))

    def set_position(self, position):
        if self.player.get_media():
            target_ms = int(position / 1000.0 * max(0, self.player.get_length()))
            self.player.set_time(target_ms)
            self.last_player_time_ms = target_ms

    def get_media_duration_ms(self, path=None):
        try:
            current_path = getattr(self, "current_media_path", None)
            if path is None or path == current_path:
                duration = self.player.get_length()
                if duration and duration > 0: return int(duration)
                media = self.player.get_media()
                if media:
                    media.parse()
                    duration = media.get_duration()
                    if duration and duration > 0: return int(duration)
                return -1
            return self.get_media_duration_sync(path)
        except Exception: return -1
            
    def get_media_duration_sync(self, path):
        try:
            media = self.vlc_instance.media_new(path)
            media.parse()
            duration = media.get_duration()
            media.release()
            return int(duration) if duration and duration > 0 else -1
        except Exception: return -1

    def open_jump_dialog(self):
        if not self.player.get_media(): return
        duration_ms = self.get_media_duration_ms()
        dialog = JumpDialog(self, "跳转至...", duration_ms=duration_ms)
        if dialog.exec() == QDialog.Accepted:
            target_ms = dialog.get_target_ms()
            self.player.set_time(target_ms)
            self.last_player_time_ms = target_ms

    def change_volume(self, value):
        if self.player:
            self.player.audio_set_volume(value)
            if value == 0: self.player.audio_set_mute(True)
            else: self.player.audio_set_mute(False)
        if not getattr(self, "_loading_settings", False):
            self.save_persistent_settings()

    def toggle_record(self):
        if self.audio_recorder.is_recording:
            self.audio_recorder.stop_record()
            self.record_btn.setText("🔴")
            self.record_btn.setStyleSheet("")
            
            elapsed = 0
            if hasattr(self, 'recording_start_time') and self.recording_start_time:
                elapsed = int((datetime.now() - self.recording_start_time).total_seconds())

            self.recording_start_time = None
            m = elapsed // 60
            s = elapsed % 60
            duration_str = f"总时长：{m}分{s}秒"

            old_file = Path(self.audio_recorder.output_filename)
            new_file = old_file.with_name(f"{old_file.stem}_{duration_str}{old_file.suffix}")

            def finish_and_rename():
                final_path = old_file
                try:
                    if old_file.exists():
                        os.rename(old_file, new_file)
                        final_path = new_file
                except Exception:
                    pass

                if getattr(self, "auto_upload_drive", False):
                    self.recording_status_label.setText("☁️ 正在异步上传网盘...")
                    self.recording_status_label.setStyleSheet("color: #89b4fa; font-weight: bold; font-size: 10pt;")
                    self.recording_status_label.show()
                    
                    self.upload_worker = DriveUploadWorker(str(final_path), getattr(self, "drive_folder_id", ""))
                    self.upload_worker.finished_signal.connect(self._on_upload_finished)
                    self.upload_worker.start()
                    QMessageBox.information(self, "本地录音完成", f"已保存到本地:\n{final_path}\n\n正在后台静默上传至 Google Drive，请勿立即关闭软件。")
                else:
                    self.recording_status_label.setText("")
                    QMessageBox.information(self, "录音完成", f"已保存到:\n{final_path}")

            QTimer.singleShot(500, finish_and_rename)
        else:
            save_dir = self.record_save_dir
            if not save_dir or not Path(save_dir).exists():
                save_dir = str(Path.cwd() / "Recordings")
                Path(save_dir).mkdir(parents=True, exist_ok=True)
                
            timestamp = datetime.now().strftime("%Y-%m-%d(%H_%M_%S)")
            title_str = f"【{self.custom_title}】" if self.custom_title else "【未命名通道】"
            filename = str(Path(save_dir) / f"{title_str}_{timestamp}.m4a")

            success = self.audio_recorder.start_record(None, filename)
            if success:
                self.record_btn.setText("⏹")
                self.record_btn.setStyleSheet("background-color: #f38ba8; color: #11111b; border-radius: 6px;")
                self.recording_start_time = datetime.now()
                self.recording_status_label.setText("🔴 录音启动中...")
                self.recording_status_label.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 10pt;")
                self.recording_status_label.show()
            else:
                QMessageBox.warning(self, "录音失败", "无法打开音频通道，请检查设备是否正常工作。")

    def _on_upload_finished(self, msg, success):
        self.recording_status_label.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 10pt;")
        if success:
            QMessageBox.information(self, "网盘上传成功", msg)
        else:
            QMessageBox.warning(self, "网盘上传失败", msg)

    def _update_record_status(self):
        now = datetime.now()
        
        for alarm in self.alarms_list:
            if not alarm.get("active", False):
                continue
            parts = alarm["time"].split(":")
            h, m = int(parts[0]), int(parts[1])
            days = alarm.get("days", [])
            
            if now.hour == h and now.minute == m:
                if days and now.weekday() not in days:
                    continue
                last_triggered = alarm.get("last_triggered")
                if last_triggered:
                    try:
                        last_t = datetime.fromisoformat(last_triggered)
                        if last_t.date() == now.date() and last_t.hour == h and last_t.minute == m:
                            continue
                    except: pass
                
                alarm["last_triggered"] = now.isoformat()
                if not days:
                    alarm["active"] = False
                self.save_persistent_settings()
                
                if not self.audio_recorder.is_recording:
                    self.toggle_record()

        if self.audio_recorder.is_recording:
            try:
                is_even = (int(now.timestamp() * 2) % 2 == 0)
                blink = "🔴" if is_even else "⭕"
                if hasattr(self, 'recording_start_time') and self.recording_start_time:
                    elapsed = int((now - self.recording_start_time).total_seconds())
                    em = elapsed // 60
                    es = elapsed % 60
                    time_str = f"{em:02d}:{es:02d}"
                else:
                    time_str = "00:00"
                self.recording_status_label.setText(f"{blink} REC {time_str}")
                self.recording_status_label.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 10pt;")
                self.recording_status_label.show()
            except: pass

        elif getattr(self, "auto_upload_drive", False) and hasattr(self, 'upload_worker') and self.upload_worker.isRunning():
            self.recording_status_label.show()

        else:
            next_time, _ = self.get_next_alarm_info()
            if next_time:
                rem = int((next_time - now).total_seconds())
                if rem <= 300: 
                    rm = rem // 60
                    rs = rem % 60
                    self.recording_status_label.setText(f"⏳ 即将录音: {rm:02d}:{rs:02d}")
                    self.recording_status_label.setStyleSheet("color: #f9e2af; font-weight: bold; font-size: 10pt;")
                    self.recording_status_label.show()
                else:
                    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                    wd_str = weekdays[next_time.weekday()]
                    time_str = next_time.strftime("%H:%M")
                    self.recording_status_label.setText(f"⏰ 预定: {wd_str} {time_str}")
                    self.recording_status_label.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 10pt;")
                    self.recording_status_label.show()
            else:
                self.recording_status_label.hide()

    def open_settings(self):
        try:
            dialog = SettingsDialog(
                self, int(self.skip_step_seconds), self.player, str(self.custom_title),
                int(self.video_popup_seconds), int(getattr(self, "chain_popup_seconds", 5)),
                str(getattr(self, "record_save_dir", "")), str(Theme.accent), bool(self.default_video_open),
                bool(getattr(self, "network_auto_play", True)),
                bool(getattr(self, "auto_upload_drive", False)), str(getattr(self, "drive_folder_id", ""))
            )

            if dialog.exec() == QDialog.Accepted:
                Theme.accent = dialog.theme_combo.currentData()
                self.setStyleSheet(get_qss())
                self.slider._render_pixmaps(); self.slider.update()
                self.list_widget.viewport().update()

                self.skip_step_seconds = dialog.step_box.value()
                self.video_popup_seconds = dialog.popup_box.value()
                self.chain_popup_seconds = dialog.chain_popup_box.value()
                self.playlist_click_mode = dialog.click_mode_combo.currentData()
                self.default_video_open = dialog.video_open_combo.currentData()
                self.network_auto_play = dialog.net_play_combo.currentData()
                self.custom_title = dialog.title_box.text()

                if self.custom_title:
                    self.center_title_label.setText(self.custom_title)
                    self.setWindowTitle(f"{self.custom_title} - {self.default_title}")
                else:
                    self.center_title_label.setText("")
                    self.setWindowTitle(self.default_title)

                self.record_save_dir = dialog.record_dir_box.text()
                
                self.auto_upload_drive = dialog.drive_upload_combo.currentData()
                self.drive_folder_id = dialog.drive_folder_box.text().strip()

                self.save_persistent_settings()
                self.update_audio_session_name()
        except Exception as e:
            QMessageBox.critical(self, "设置打开失败", f"无法打开设置界面，内部错误信息：\n{str(e)}")

    def bind_vlc_to_window(self):
        if not self.video_window: return
        self._apply_win_id(int(self.video_window.video_frame.winId()))

    def bind_vlc_to_dummy(self):
        self._apply_win_id(int(self.dummy_video_widget.winId()))

    def _apply_win_id(self, win_id):
        system_os = platform.system()
        if system_os == "Windows": self.player.set_hwnd(win_id)
        elif system_os == "Darwin": self.player.set_nsobject(win_id)
        else: self.player.set_xwindow(win_id)

        if self.player.get_media():
            v_track = self.player.video_get_track()
            if v_track >= 0:
                self.player.video_set_track(-1)
                def re_enable(): self.player.video_set_track(v_track)
                QTimer.singleShot(50, re_enable)

    def calculate_video_position_above_control(self):
        video_w = self.saved_video_size.width() if self.saved_video_size.isValid() else 800
        video_h = self.saved_video_size.height() if self.saved_video_size.isValid() else 450
        control_frame = self.frameGeometry()
        x = control_frame.center().x() - video_w // 2
        y = control_frame.top() - video_h - 2
        return x, y, video_w, video_h

    def place_video_above_control(self):
        if not self.video_window or not self.video_window.isVisible(): return
        x, y, w, h = self.calculate_video_position_above_control()
        self.video_window.setGeometry(x, y, w, h)

    def sync_position_with_video(self): self.place_video_above_control()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_video_point_alert()
        if self.video_window and self.video_window.isVisible():
            QTimer.singleShot(0, self.place_video_above_control)

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.video_window and self.video_window.isVisible():
            self.place_video_above_control()

    def open_video_window(self):
        if self.video_window: return
        self.video_window = VideoWindow()
        if self.saved_video_size.isValid(): self.video_window.resize(self.saved_video_size)
        self.video_window.show()
        self.bind_vlc_to_window()
        self.save_persistent_settings()
        QTimer.singleShot(0, self.place_video_above_control)

    def close_video_window(self):
        if not self.video_window: return
        self.saved_video_size = self.video_window.size()
        self.bind_vlc_to_dummy()
        self.video_window.close(); self.video_window.deleteLater(); self.video_window = None
        self.save_persistent_settings()

    def toggle_video_window(self):
        if self.video_window: self.close_video_window()
        else: self.open_video_window()

    def toggle_playlist(self):
        if self.playlist_widget.isVisible():
            self.playlist_widget.hide()
            self.setMinimumHeight(self.collapsed_height); self.setMaximumHeight(self.collapsed_height)
            self.resize(680, self.collapsed_height)
            self.playlist_toggle_btn.setText("⇊")
        else:
            self.playlist_widget.show()
            self.setMinimumHeight(self.collapsed_height + 120); self.setMaximumHeight(16777215)
            self.resize(680, self.expanded_height)
            self.playlist_toggle_btn.setText("⇈")

    def check_video_points(self, current_ms):
        if not self.current_media_path or not hasattr(self, "_cached_events"):
            self.hide_video_point_alert()
            return

        popup_ms = self.video_popup_seconds * 1000
        chain_popup_ms = getattr(self, "chain_popup_seconds", 5) * 1000
        upcoming = None

        for ev in self._cached_events:
            rem = ev['time'] - current_ms
            if rem < -1000: continue
            if ev['type'] == 'video' and 0 <= rem <= popup_ms:
                upcoming = ev; break
            elif ev['type'] == 'chain' and 0 <= rem <= chain_popup_ms:
                upcoming = ev; break

        if upcoming:
            target_ms = upcoming['time']; event_type = upcoming['type']; target_path = upcoming['target']
            self.show_video_point_alert(target_ms, event_type, target_path)

            if event_type == "video":
                if (current_ms >= target_ms - popup_ms and target_ms not in self.triggered_video_points):
                    self.triggered_video_points.add(target_ms)
                    if not self.video_window: self.open_video_window()
        else:
            self.hide_video_point_alert()

        for pt in list(self.triggered_video_points):
            if current_ms < pt - 1000: self.triggered_video_points.remove(pt)

    def show_video_point_alert(self, point_ms, event_type, target_path=None):
        point_text = format_time_ms(point_ms)
        if event_type == "chain":
            self.video_point_alert.setStyleSheet("color: #f9e2af; font-size: 10pt; font-weight: 900; padding: 2px 8px; border-radius: 4px; background-color: #332b21;")
            self.video_point_alert.setText(f"⚠ 准备打断  {point_text}  · 串联点")
            if target_path:
                is_network = target_path.startswith("http://") or target_path.startswith("https://")
                if is_network:
                    if not self.video_window: self.open_video_window()
                else:
                    ext = Path(target_path).suffix.lower()
                    if ext in [".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv"]:
                        if not self.video_window: self.open_video_window()
        else:
            self.video_point_alert.setStyleSheet("color: #f38ba8; font-size: 10pt; font-weight: 900; padding: 2px 8px; border-radius: 4px; background-color: #31202a;")
            self.video_point_alert.setText(f"⚠ 准备共享  {point_text}  · 视频点")

        self.video_point_alert.show()

        if not hasattr(self, "_alert_blink_counter"):
            self._alert_blink_counter = 0; self._alert_blink_state = False

        self._alert_blink_counter += 1
        if self._alert_blink_counter >= 5:
            self._alert_blink_state = not self._alert_blink_state
            self.video_point_alert.setVisible(self._alert_blink_state)
            self._alert_blink_counter = 0

    def hide_video_point_alert(self): self.video_point_alert.hide()

    def update_ui(self):
        if not self.player.get_media(): return

        state = self.player.get_state()
        current_ms = self.player.get_time()

        is_segment_end = False
        if hasattr(self, 'active_segments') and self.active_segments and 0 <= self.current_seg_index < len(self.active_segments):
            curr_seg = self.active_segments[self.current_seg_index]
            end_ms = curr_seg.get('end_ms', -1)
            
            if state == vlc.State.Ended or (end_ms > 0 and current_ms >= end_ms):
                self.current_seg_index += 1
                if self.current_seg_index < len(self.active_segments):
                    next_start = self.active_segments[self.current_seg_index].get('start_ms', 0)
                    self.player.set_time(next_start); self.last_player_time_ms = next_start
                    return
                else: is_segment_end = True

        is_end_of_chain = getattr(self, "current_chain_end_ms", -1) > 0 and current_ms >= self.current_chain_end_ms

        if state == vlc.State.Ended or is_end_of_chain or is_segment_end:
            if self.chain_stack:
                self.return_from_chain(self.chain_stack.pop())
                return

            if state == vlc.State.Ended or is_end_of_chain or is_segment_end:
                current_row = self.list_widget.currentRow()
                next_row = current_row + 1
                while next_row < self.list_widget.count():
                    next_item = self.list_widget.item(next_row)
                    if next_item.data(Qt.UserRole) in self.auto_skip_paths: next_row += 1
                    else:
                        self.list_widget.setCurrentRow(next_row)
                        self.handle_list_click(next_item, is_manual=False)
                        return
                        
                self.player.stop()
                self.timer.stop()
                self.is_paused = True
                self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
                self.current_chain_end_ms = -1
                self.current_seg_index = -1
                return

        time_diff = current_ms - self.last_player_time_ms
        is_normal_playback = -1000 <= time_diff <= 5000

        if self.current_list_item and is_normal_playback and self.last_player_time_ms >= 0:
            chains = self.list_widget.get_chains(self.current_list_item)
            for i, task in enumerate(chains):
                trigger_ms = task["trigger_ms"]
                task_id = f"{self.current_media_path}_{i}"
                
                if (self.last_player_time_ms < trigger_ms <= current_ms) or (trigger_ms <= current_ms <= trigger_ms + 3000):
                    if task_id not in self.triggered_chain_tasks:
                        self.triggered_chain_tasks.add(task_id)
                        self.auto_skip_paths.add(task["target_path"])
                        self.chain_stack.append({
                            "original_path": self.current_media_path,
                            "original_item": self.current_list_item,
                            "resume_ms": task["resume_ms"]
                        })
                        self.player.stop()
                        target_item = self.list_widget.find_item_by_path(task["target_path"])
                        self.play_media(
                            task["target_path"], item=target_item, is_chain=True,
                            chain_start_ms=task.get("target_start_ms", 0),
                            chain_end_ms=task.get("target_end_ms", -1)
                        )
                        return

        length_ms = self.player.get_length()
        if current_ms < 0 or length_ms < 0: return

        if length_ms > 0: 
            self.slider.media_length_seconds = length_ms / 1000.0
            if self.current_list_item and not self.current_list_item.data(Qt.UserRole + 3):
                self.current_list_item.setData(Qt.UserRole + 3, format_time_ms(length_ms))
                self.list_widget.viewport().update()
                self.save_persistent_settings()

        if not self.slider.isSliderDown(): self.slider.setValue(int(self.player.get_position() * 1000))

        time_diff_text = current_ms - getattr(self, "_last_text_update_ms", -2000)
        
        if abs(time_diff_text) >= 1000 or current_ms < 1000 or state == vlc.State.Ended:
            self._last_text_update_ms = current_ms
            cur_str = QTime(0, 0, 0).addMSecs(current_ms).toString("hh:mm:ss")
            len_str = QTime(0, 0, 0).addMSecs(length_ms).toString("hh:mm:ss")

            if self.time_format_mode == 0: self.time_label.setText(f"{cur_str} / {len_str}")
            else:
                remain_ms = max(0, length_ms - current_ms)
                rem_str = QTime(0, 0, 0).addMSecs(remain_ms).toString("hh:mm:ss")
                self.time_label.setText(f"已播: {cur_str}\n剩余: {rem_str}")

        self.check_video_points(current_ms)
        self.last_player_time_ms = current_ms

    def closeEvent(self, event):
        if self.audio_recorder.is_recording:
            reply = QMessageBox.question(self, "正在录音", "当前正在录音中，是否关闭软件？\n(确认关闭将自动切断并保存录音)", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes: self.audio_recorder.stop_record()
            else: event.ignore(); return

        try:
            self.save_persistent_settings()
            self.timer.stop()
            if self.video_window:
                self.saved_video_size = self.video_window.size()
                self.bind_vlc_to_dummy()
                self.video_window.close(); self.video_window.deleteLater(); self.video_window = None
        except: pass
        event.accept()

# ==========================================
# 主程序
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    control_win = ControlWindow()
    control_win.show()
    def restore_runtime_state(): control_win.position_video_point_alert()
    QTimer.singleShot(120, restore_runtime_state)
    sys.exit(app.exec())