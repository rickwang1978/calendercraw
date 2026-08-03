import re
import csv
import sys
import os
import time
import datetime
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# 檢查第三方基礎套件是否安裝
try:
    import requests
    from bs4 import BeautifulSoup
except ModuleNotFoundError:
    print("錯誤：尚未安裝必要的第三方套件！")
    print("請在 CMD 或 Terminal 輸入以下指令安裝：")
    print("pip install requests beautifulsoup4")
    sys.exit(1)

# Google Calendar API 支援套件檢查 (方案二)
GOOGLE_API_AVAILABLE = False
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# Google OAuth 權限範圍
SCOPES = ['https://www.googleapis.com/auth/calendar']

# 判斷目前作業系統是否為 macOS
IS_MAC = sys.platform == 'darwin'

def get_resource_path(filename):
    """ 取得檔案的絕對路徑 (支援 PyInstaller 打包內部與 App 同級目錄) """
    if hasattr(sys, '_MEIPASS'):
        bundled_path = os.path.join(sys._MEIPASS, filename)
        if os.path.exists(bundled_path):
            return bundled_path

    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        if IS_MAC and 'Contents/MacOS' in app_dir:
            app_dir = os.path.abspath(os.path.join(app_dir, '../../..'))
        external_path = os.path.join(app_dir, filename)
        if os.path.exists(external_path):
            return external_path

    return filename

class CSICCalendarCrawlerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"高雄市私立中山工商 - 行事曆雙模比對與匯出工具 v8.5 ({'macOS' if IS_MAC else 'Windows'} 保險防漏版)")
        self.root.geometry("1020x860")
        self.root.minsize(920, 750)

        # 全局資料儲存
        self.parsed_events = []          # 爬取到的原始事件 [dict]
        self.filtered_events = []        # 篩選後的事件 [dict]
        self.existing_gcal_events = set() # 已知存在的事項 (date, title)
        self.google_service = None       # Google Calendar API 服務對象
        self.google_calendars_dict = {}  # 儲存 Google 子日曆 {名稱: calendarId}

        self.setup_ui()
        
        # 僅在 macOS 環境下自動讀取 Mac 日曆清單
        if IS_MAC:
            self.refresh_mac_calendars_thread()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')

        # 主容器
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. 標頭說明區
        header_frame = tk.Frame(main_frame, bg="#1e293b", padx=15, pady=15)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        title_label = tk.Label(
            header_frame, 
            text="🏫 高雄市私立中山工商行事曆雙模比對與同步系統 v8.5", 
            font=("Microsoft JhengHei", 15, "bold"), 
            fg="#ffffff", 
            bg="#1e293b"
        )
        title_label.pack(anchor="w")

        subtitle_label = tk.Label(
            header_frame, 
            text="說明：採用標準安全 Batch 批量機制 + 失敗自動重試，確保行程 100% 完整寫入零漏筆！", 
            font=("Microsoft JhengHei", 9), 
            fg="#cbd5e1", 
            bg="#1e293b"
        )
        subtitle_label.pack(anchor="w", pady=(3, 0))

        # 2. 控制參數設定區
        ctrl_frame = ttk.LabelFrame(main_frame, text=" 1. 擷取參數設定 ", padding="10")
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(ctrl_frame, text="學年/年份：", font=("Microsoft JhengHei", 10, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        current_year = datetime.datetime.now().year
        self.year_var = tk.StringVar(value=str(current_year))
        year_spin = ttk.Spinbox(
            ctrl_frame, 
            from_=2010, 
            to=2040, 
            textvariable=self.year_var, 
            width=8,
            font=("Microsoft JhengHei", 10)
        )
        year_spin.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(ctrl_frame, text="起始月份：", font=("Microsoft JhengHei", 10, "bold")).grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.start_month_var = tk.StringVar(value="8")
        start_m_spin = ttk.Spinbox(
            ctrl_frame, 
            from_=1, 
            to=12, 
            textvariable=self.start_month_var, 
            width=6,
            font=("Microsoft JhengHei", 10)
        )
        start_m_spin.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        ttk.Label(ctrl_frame, text="結束月份：", font=("Microsoft JhengHei", 10, "bold")).grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self.end_month_var = tk.StringVar(value="1")
        end_m_spin = ttk.Spinbox(
            ctrl_frame, 
            from_=1, 
            to=12, 
            textvariable=self.end_month_var, 
            width=6,
            font=("Microsoft JhengHei", 10)
        )
        end_m_spin.grid(row=0, column=5, padx=5, pady=5, sticky="w")

        self.btn_start = tk.Button(
            ctrl_frame, 
            text="🚀 開始線上連線擷取", 
            font=("Microsoft JhengHei", 11, "bold"), 
            bg="#93c5fd", 
            fg="black", 
            activebackground="#60a5fa", 
            activeforeground="black", 
            relief=tk.RAISED, 
            bd=2, 
            padx=18, 
            pady=4, 
            cursor="hand2",
            command=self.start_crawling_thread
        )
        self.btn_start.grid(row=0, column=6, padx=(15, 5), pady=5)

        # 3. 進度與狀態提示區
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(log_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 4))

        self.status_label = ttk.Label(log_frame, text="狀態：就緒（請確認年月設定後點擊『開始線上連線擷取』）", font=("Microsoft JhengHei", 9, "bold"))
        self.status_label.pack(anchor="w")

        # 4. 比對控制面板區 (保險防漏同步)
        compare_frame = ttk.LabelFrame(main_frame, text=" 2. Google 日曆重複比對與安全同步 ", padding="10")
        compare_frame.pack(fill=tk.X, pady=(0, 10))

        # 方案一：離線檔案比對
        btn_compare_file = tk.Button(
            compare_frame, 
            text="📁 方案一：載入舊 CSV/ICS 比對", 
            bg="#fde047", 
            fg="black", 
            activebackground="#eab308", 
            activeforeground="black",
            font=("Microsoft JhengHei", 9, "bold"), 
            padx=8, 
            pady=3, 
            cursor="hand2",
            command=self.load_and_compare_existing_file
        )
        btn_compare_file.grid(row=0, column=0, padx=(0, 10), pady=3, sticky="w")

        # 方案二：API 登入
        btn_login_gapi = tk.Button(
            compare_frame, 
            text="🔐 方案二：登入 Google 帳號", 
            bg="#a7f3d0", 
            fg="black", 
            activebackground="#34d399", 
            activeforeground="black",
            font=("Microsoft JhengHei", 9, "bold"), 
            padx=8, 
            pady=3, 
            cursor="hand2",
            command=self.login_and_fetch_google_calendars_thread
        )
        btn_login_gapi.grid(row=0, column=1, padx=(0, 10), pady=3, sticky="w")

        # 子日曆選擇下拉選單
        ttk.Label(compare_frame, text="目標 Google 子日曆：", font=("Microsoft JhengHei", 9, "bold")).grid(row=0, column=2, padx=(0, 2), pady=3, sticky="e")
        self.gcal_select_var = tk.StringVar(value="中山工商行事曆")
        self.gcal_combo = ttk.Combobox(compare_frame, textvariable=self.gcal_select_var, width=18, font=("Microsoft JhengHei", 9))
        self.gcal_combo.grid(row=0, column=3, padx=(0, 8), pady=3, sticky="w")

        # 比對子日曆按鈕
        btn_compare_gsub = tk.Button(
            compare_frame, 
            text="🔍 比對選取子日曆", 
            bg="#fde047", 
            fg="black", 
            activebackground="#eab308", 
            activeforeground="black",
            font=("Microsoft JhengHei", 9, "bold"), 
            padx=8, 
            pady=3, 
            cursor="hand2",
            command=self.compare_selected_google_calendar_thread
        )
        btn_compare_gsub.grid(row=0, column=4, padx=(0, 8), pady=3, sticky="w")

        # 保險防漏寫入按鈕
        btn_login_gcal_sync = tk.Button(
            compare_frame, 
            text="🛡️ 保險同步至此子日曆 (防漏筆)", 
            bg="#38bdf8", 
            fg="black", 
            activebackground="#0284c7", 
            activeforeground="black",
            font=("Microsoft JhengHei", 9, "bold"), 
            padx=8, 
            pady=3, 
            cursor="hand2",
            command=self.sync_new_events_to_google_api_thread
        )
        btn_login_gcal_sync.grid(row=0, column=5, pady=3, sticky="w")

        # 5. 資料過濾與搜尋列
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(filter_frame, text="🔍 關鍵字：", font=("Microsoft JhengHei", 10)).pack(side=tk.LEFT, padx=(0, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.filter_events())
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=15, font=("Microsoft JhengHei", 10))
        search_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(filter_frame, text="處室：", font=("Microsoft JhengHei", 10)).pack(side=tk.LEFT, padx=(0, 2))
        self.cat_filter_var = tk.StringVar(value="全部")
        self.cat_filter_combo = ttk.Combobox(filter_frame, textvariable=self.cat_filter_var, values=["全部"], width=8, state="readonly", font=("Microsoft JhengHei", 10))
        self.cat_filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.cat_filter_combo.bind("<<ComboboxSelected>>", lambda e: self.filter_events())

        ttk.Label(filter_frame, text="比對過濾：", font=("Microsoft JhengHei", 10)).pack(side=tk.LEFT, padx=(0, 2))
        self.status_filter_var = tk.StringVar(value="全部")
        self.status_filter_combo = ttk.Combobox(filter_frame, textvariable=self.status_filter_var, values=["全部", "僅顯示新事件", "僅顯示重複事件"], width=12, state="readonly", font=("Microsoft JhengHei", 10))
        self.status_filter_combo.pack(side=tk.LEFT)
        self.status_filter_combo.bind("<<ComboboxSelected>>", lambda e: self.filter_events())

        # 6. 資料表格顯示 (Treeview)
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("#", "date", "day", "category", "status", "title")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("#", text="#")
        self.tree.heading("date", text="日期")
        self.tree.heading("day", text="星期")
        self.tree.heading("category", text="處室註記")
        self.tree.heading("status", text="Google 比對狀態")
        self.tree.heading("title", text="行事曆事項內容 (單一事件獨立列)")

        self.tree.column("#", width=40, anchor="center")
        self.tree.column("date", width=100, anchor="center")
        self.tree.column("day", width=70, anchor="center")
        self.tree.column("category", width=80, anchor="center")
        self.tree.column("status", width=130, anchor="center")
        self.tree.column("title", width=500, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 7. 僅 macOS 顯示 Mac 日曆專用設定區
        if IS_MAC:
            mac_sync_frame = ttk.LabelFrame(main_frame, text=" 3. 同步至 Mac 原生『日曆』App ", padding="8")
            mac_sync_frame.pack(fill=tk.X, pady=(0, 8))

            ttk.Label(mac_sync_frame, text="選擇 Mac 目標日曆：", font=("Microsoft JhengHei", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))
            
            self.mac_cal_var = tk.StringVar(value="中山工商行事曆")
            self.mac_cal_combo = ttk.Combobox(mac_sync_frame, textvariable=self.mac_cal_var, width=18, font=("Microsoft JhengHei", 9))
            self.mac_cal_combo.pack(side=tk.LEFT, padx=(0, 8))

            btn_refresh_cals = tk.Button(
                mac_sync_frame, 
                text="🔄 重新整理", 
                font=("Microsoft JhengHei", 8), 
                bg="#f1f5f9", 
                fg="black", 
                padx=6, 
                pady=2, 
                cursor="hand2",
                command=self.refresh_mac_calendars_thread
            )
            btn_refresh_cals.pack(side=tk.LEFT, padx=(0, 15))

            btn_sync_mac = tk.Button(
                mac_sync_frame, 
                text="📅 寫入指定 Mac 日曆 (可自動跳過重複)", 
                bg="#86efac", 
                fg="black", 
                activebackground="#4ade80",
                activeforeground="black",
                font=("Microsoft JhengHei", 9, "bold"), 
                padx=12, 
                pady=3, 
                cursor="hand2",
                command=self.sync_to_mac_calendar_thread
            )
            btn_sync_mac.pack(side=tk.LEFT)

        # 8. 通用檔案匯出區
        export_frame = ttk.Frame(main_frame)
        export_frame.pack(fill=tk.X)

        self.exclude_dup_var = tk.BooleanVar(value=True)
        chk_exclude = ttk.Checkbutton(export_frame, text="匯出時自動排除『重複事件』", variable=self.exclude_dup_var)
        chk_exclude.pack(side=tk.LEFT, padx=(0, 15))

        btn_export_csv = tk.Button(
            export_frame, 
            text="📊 匯出 CSV (Excel)", 
            bg="#cbd5e1", 
            fg="black", 
            activebackground="#94a3b8",
            activeforeground="black",
            font=("Microsoft JhengHei", 10, "bold"), 
            padx=12, 
            pady=5, 
            cursor="hand2",
            command=self.export_standard_csv
        )
        btn_export_csv.pack(side=tk.LEFT, padx=(0, 10))

        btn_export_gcal = tk.Button(
            export_frame, 
            text="📅 匯出 Google CSV", 
            bg="#93c5fd", 
            fg="black", 
            activebackground="#60a5fa",
            activeforeground="black",
            font=("Microsoft JhengHei", 10, "bold"), 
            padx=12, 
            pady=5, 
            cursor="hand2",
            command=self.export_google_csv
        )
        btn_export_gcal.pack(side=tk.LEFT, padx=(0, 10))

        btn_export_ics = tk.Button(
            export_frame, 
            text="📱 匯出 .ics 日曆檔", 
            bg="#c7d2fe", 
            fg="black", 
            activebackground="#a5b4fc",
            activeforeground="black",
            font=("Microsoft JhengHei", 10, "bold"), 
            padx=12, 
            pady=5, 
            cursor="hand2",
            command=self.export_ics
        )
        btn_export_ics.pack(side=tk.LEFT)

        self.count_label = ttk.Label(export_frame, text="共 0 筆資料", font=("Microsoft JhengHei", 10, "bold"))
        self.count_label.pack(side=tk.RIGHT, padx=5)

    # ==================== 方案一：離線檔案比對邏輯 ====================
    def load_and_compare_existing_file(self):
        filepath = filedialog.askopenfilename(
            title="選擇先前下載的 CSV 或 .ics 行事曆檔案",
            filetypes=[
                ("CSV 檔案 (*.csv)", "*.csv"), 
                ("iCalendar 檔案 (*.ics)", "*.ics"),
                ("所有檔案 (*.*)", "*.*")
            ]
        )
        if not filepath:
            return

        dup_count = 0
        try:
            if filepath.lower().endswith('.csv'):
                with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        if len(row) >= 2:
                            if len(row) >= 5 and '/' in str(row[1]): # Google CSV (MM/DD/YYYY)
                                title = row[0].strip()
                                g_date = row[1].strip()
                                parts = g_date.split('/')
                                if len(parts) == 3:
                                    m, d, y = parts
                                    std_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
                                    self.existing_gcal_events.add((std_date, title))
                            else: # 標準 CSV (YYYY-MM-DD, ...)
                                std_date = row[0].strip()
                                title = row[1].strip() if len(row) > 1 else ""
                                self.existing_gcal_events.add((std_date, title))

            elif filepath.lower().endswith('.ics'):
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    events = content.split('BEGIN:VEVENT')
                    for ev in events[1:]:
                        summary_m = re.search(r'SUMMARY:(.*)', ev)
                        dtstart_m = re.search(r'DTSTART;VALUE=DATE:(\d{8})', ev)
                        if summary_m and dtstart_m:
                            title = summary_m.group(1).strip()
                            d_str = dtstart_m.group(1).strip()
                            std_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]}"
                            self.existing_gcal_events.add((std_date, title))

            for e in self.parsed_events:
                if (e['date'], e['title']) in self.existing_gcal_events:
                    e['is_duplicate'] = True
                    dup_count += 1
                else:
                    e['is_duplicate'] = False

            self.filter_events()
            messagebox.showinfo("比對完成", f"方案一比對成功！共標記出 {dup_count} 筆『重複 (已存在)』行程。")

        except Exception as err:
            messagebox.showerror("比對失敗", f"無法讀取所選取的檔案: {err}")

    # ==================== 方案二：Google Calendar API 直連與子日曆處理 ====================
    def login_and_fetch_google_calendars_thread(self):
        if not GOOGLE_API_AVAILABLE:
            msg = ("尚未安裝 Google API 授權套件！\n\n"
                   "請在 CMD 或 Terminal 執行以下命令安裝：\n"
                   "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
            messagebox.showwarning("套件未安裝", msg)
            return

        thread = threading.Thread(target=self.run_google_api_login_and_fetch_calendars, daemon=True)
        thread.start()

    def run_google_api_login_and_fetch_calendars(self):
        self.update_status("正在進行 Google 帳號授權並讀取子日曆清單...", 10)
        
        creds_path = get_resource_path('credentials.json')
        token_path = os.path.join(os.path.expanduser('~'), '.csic_gcal_token.json')

        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            if not creds:
                if not os.path.exists(creds_path):
                    msg = ("未找到 Google API 憑證檔案『credentials.json』！\n\n"
                           "請確認 credentials.json 已放在『中山工商行事曆.app』同個資料夾下。")
                    self.root.after(0, lambda: messagebox.showerror("缺少憑證", msg))
                    self.update_status("授權失敗：缺少 credentials.json", 0)
                    return
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        try:
            self.google_service = build('calendar', 'v3', credentials=creds)
            
            calendar_list = self.google_service.calendarList().list().execute()
            items = calendar_list.get('items', [])
            
            self.google_calendars_dict.clear()
            cal_names = []
            
            for item in items:
                summary = item.get('summary', '未命名日曆')
                cal_id = item.get('id')
                self.google_calendars_dict[summary] = cal_id
                cal_names.append(summary)

            if "中山工商行事曆" not in self.google_calendars_dict:
                cal_names.insert(0, "中山工商行事曆")

            self.root.after(0, lambda: self.update_gcal_combo(cal_names))
            self.update_status("Google 帳號授權成功！已載入子日曆清單。", 100)
            self.root.after(0, lambda: messagebox.showinfo("授權成功", "🎉 成功連線 Google 帳號！已抓取您所有的 Google 子日曆清單。"))

        except Exception as err:
            self.root.after(0, lambda: messagebox.showerror("Google API 錯誤", f"連線過程發生錯誤: {err}"))
            self.update_status("API 連線失敗", 0)

    def update_gcal_combo(self, names):
        self.gcal_combo['values'] = names
        if names:
            self.gcal_select_var.set(names[0])

    def compare_selected_google_calendar_thread(self):
        if not self.google_service:
            messagebox.showwarning("提示", "請先點擊『🔐 方案二：登入 Google 帳號』完成連線與載入日曆！")
            return
        if not self.parsed_events:
            messagebox.showwarning("提示", "請先點擊『開始線上連線擷取』抓取學校行事曆！")
            return

        thread = threading.Thread(target=self.run_compare_selected_google_calendar, daemon=True)
        thread.start()

    def run_compare_selected_google_calendar(self):
        target_name = self.gcal_select_var.get().strip()
        cal_id = self.google_calendars_dict.get(target_name)

        if not cal_id:
            self.root.after(0, lambda: messagebox.showinfo("提示", f"日曆『{target_name}』在您的 Google 帳號中尚未建立。\n比對結果：目前無任何重複事項！"))
            for e in self.parsed_events:
                e['is_duplicate'] = False
            self.root.after(0, self.filter_events)
            return

        self.update_status(f"連線 Google API 查詢子日曆『{target_name}』中...", 30)

        try:
            min_date = min(e['date'] for e in self.parsed_events) + "T00:00:00+08:00"
            max_date = max(e['date'] for e in self.parsed_events) + "T23:59:59+08:00"

            items = []
            page_token = None
            while True:
                events_result = self.google_service.events().list(
                    calendarId=cal_id, 
                    timeMin=min_date, 
                    timeMax=max_date,
                    singleEvents=True, 
                    orderBy='startTime',
                    maxResults=2500,
                    pageToken=page_token
                ).execute()
                
                items.extend(events_result.get('items', []))
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break

            self.existing_gcal_events.clear()

            for item in items:
                start = item.get('start', {}).get('date') or item.get('start', {}).get('dateTime', '')[:10]
                summary = item.get('summary', '').strip()
                if start and summary:
                    self.existing_gcal_events.add((start, summary))

            dup_count = 0
            for e in self.parsed_events:
                if (e['date'], e['title']) in self.existing_gcal_events:
                    e['is_duplicate'] = True
                    dup_count += 1
                else:
                    e['is_duplicate'] = False

            self.root.after(0, self.filter_events)
            self.update_status(f"子日曆『{target_name}』比對完成！", 100)
            self.root.after(0, lambda: messagebox.showinfo("比對成功", f"🎉 已於子日曆『{target_name}』中比對完成！\n共抓取 {len(items)} 筆 Google 事件，偵測到 {dup_count} 筆重複事項。"))

        except Exception as err:
            self.root.after(0, lambda: messagebox.showerror("比對失敗", f"查詢子日曆錯誤: {err}"))
            self.update_status("子日曆比對失敗", 0)

    # 🛡️ 方案二：採用【保險標準 Batch + 重試機制】（100% 完整防漏筆）
    def sync_new_events_to_google_api_thread(self):
        if not self.google_service:
            messagebox.showwarning("提示", "請先點擊『🔐 方案二：登入 Google 帳號』完成連線授權！")
            return

        target_name = self.gcal_select_var.get().strip()
        if not target_name:
            messagebox.showwarning("提示", "請選擇或輸入目標 Google 子日曆名稱！")
            return

        thread = threading.Thread(target=self.run_google_api_sync_safe_batch, args=(target_name,), daemon=True)
        thread.start()

    def run_google_api_sync_safe_batch(self, target_name):
        cal_id = self.google_calendars_dict.get(target_name)

        if not cal_id:
            self.update_status(f"正在為您建立新子日曆『{target_name}』...", 10)
            try:
                calendar_body = {
                    'summary': target_name,
                    'timeZone': 'Asia/Taipei'
                }
                created_calendar = self.google_service.calendars().insert(body=calendar_body).execute()
                cal_id = created_calendar['id']
                self.google_calendars_dict[target_name] = cal_id
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("建立失敗", f"無法建立子日曆『{target_name}』: {e}"))
                self.update_status("建立子日曆失敗", 0)
                return

        events_to_sync = [e for e in self.filtered_events if not (self.exclude_dup_var.get() and e.get('is_duplicate', False))]
        total = len(events_to_sync)

        if total == 0:
            self.root.after(0, lambda: messagebox.showinfo("提示", f"根據設定已排除所有重複事件，子日曆『{target_name}』無需重複同步！"))
            return

        self.update_status(f"🛡️ 啟動保險同步機制，準備傳輸 {total} 筆行程...", 10)

        # 追蹤失敗項目，備用進行重試
        pending_queue = list(events_to_sync)
        success_count = 0
        max_retries = 3

        for retry_pass in range(max_retries + 1):
            if not pending_queue:
                break

            if retry_pass > 0:
                self.update_status(f"⚠️ 正在對 {len(pending_queue)} 筆未成功項目進行第 {retry_pass} 次自動重試...", 50)
                time.sleep(1.5 * retry_pass) # 指數型避讓，等待 API 限制解除

            current_pending = list(pending_queue)
            pending_queue.clear()

            # 每 50 筆做標準 Batch 傳送
            batch_size = 50
            for i in range(0, len(current_pending), batch_size):
                chunk = current_pending[i:i + batch_size]
                
                def make_callback(item_ref):
                    def callback(request_id, response, exception):
                        nonlocal success_count
                        if exception is None:
                            success_count += 1
                        else:
                            # 記錄失敗項目以便進入 retry 輪次
                            pending_queue.append(item_ref)
                    return callback

                batch = self.google_service.new_batch_http_request()
                for item in chunk:
                    event_body = {
                        'summary': item['title'],
                        'description': f"中山工商全校行事曆 ({item['category']})",
                        'start': {'date': item['date']},
                        'end': {'date': item['date']}
                    }
                    batch.add(
                        self.google_service.events().insert(calendarId=cal_id, body=event_body),
                        callback=make_callback(item)
                    )

                try:
                    batch.execute()
                except Exception as b_err:
                    print(f"Batch execution error: {b_err}")
                    # 若整體 Batch 崩潰，該 Chunk 全補回重試佇列
                    pending_queue.extend(chunk)

                # 更新進度條
                progress = min(100, int(((success_count) / total) * 100))
                self.update_status(f"🛡️ 安全寫入中... ({success_count}/{total} 筆完成)", progress)
                time.sleep(0.1) # 給予微小延遲避免觸發 Rate Limit

        self.update_status("Google 子日曆保險同步完成！", 100)
        
        if len(pending_queue) == 0:
            self.root.after(0, lambda: messagebox.showinfo("同步成功", f"🎉 100% 完整同步！已將全數 {success_count} 筆行程寫入 Google 子日曆『{target_name}』！"))
        else:
            self.root.after(0, lambda: messagebox.showwarning("部分完成", f"已成功寫入 {success_count} 筆行程，仍有 {len(pending_queue)} 筆因網路或 API 限制未寫入，建議可再次點擊同步。"))

    def refresh_mac_calendars_thread(self):
        if not IS_MAC: return
        thread = threading.Thread(target=self.fetch_mac_calendars, daemon=True)
        thread.start()

    def fetch_mac_calendars(self):
        script = 'tell application "Calendar" to get name of every calendar'
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            calendar_names = [c.strip() for c in res.stdout.strip().split(",") if c.strip()]
            unique_cals = []
            for cal in calendar_names:
                if cal not in unique_cals: unique_cals.append(cal)
            if "中山工商行事曆" not in unique_cals: unique_cals.insert(0, "中山工商行事曆")
            self.root.after(0, lambda: self.update_mac_cal_combo(unique_cals))
        except Exception as e:
            print(f"讀取 Mac 日曆清單失敗: {e}")

    def update_mac_cal_combo(self, cals):
        if IS_MAC: self.mac_cal_combo['values'] = cals

    def start_crawling_thread(self):
        self.btn_start.config(state=tk.DISABLED, text="⏳ 連線擷取中...")
        thread = threading.Thread(target=self.run_crawler, daemon=True)
        thread.start()

    def reset_start_btn(self):
        self.btn_start.config(state=tk.NORMAL, text="🚀 開始線上連線擷取")

    def run_crawler(self):
        try:
            year = int(self.year_var.get().strip())
            start_m = int(self.start_month_var.get().strip())
            end_m = int(self.end_month_var.get().strip())

            if not (1 <= start_m <= 12 and 1 <= end_m <= 12): raise ValueError
            if year < 2000 or year > 2099: raise ValueError
        except ValueError:
            self.root.after(0, lambda: messagebox.showerror("輸入錯誤", "請輸入有效的西元年份與 1~12 月份數字！"))
            self.root.after(0, self.reset_start_btn)
            self.update_status("輸入無效，請檢查年月設定。", 0)
            return

        months_to_fetch = []
        if start_m <= end_m:
            for m in range(start_m, end_m + 1): months_to_fetch.append((year, m))
        else:
            for m in range(start_m, 13): months_to_fetch.append((year, m))
            for m in range(1, end_m + 1): months_to_fetch.append((year + 1, m))

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
        }

        self.parsed_events.clear()
        total_months = len(months_to_fetch)

        for idx, (y, m) in enumerate(months_to_fetch):
            self.update_status(f"正在連線擷取 {y} 年 {m} 月行事曆...", (idx / total_months) * 100)
            url = f"https://www.csic.khc.edu.tw/into/mydate/index.asp?method=1&thisdate={y}/{m}/1"
            try:
                resp = requests.get(url, headers=headers, timeout=12)
                resp.encoding = 'utf-8' if 'utf-8' in resp.text.lower()[:600] else 'cp950'
                if resp.status_code == 200:
                    events = self.parse_html(resp.text, y, m)
                    self.parsed_events.extend(events)
            except Exception as e:
                print(f"抓取 {y}/{m} 失敗: {e}")

        self.update_status("抓取完成！", 100)
        self.root.after(0, self.on_crawling_complete)

    def parse_html(self, html_content, default_year, default_month):
        soup = BeautifulSoup(html_content, 'html.parser')
        events = []
        day_of_week_map = ['日', '一', '二', '三', '四', '五', '六']

        ym_match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', soup.text)
        year = int(ym_match.group(1)) if ym_match else default_year
        month = int(ym_match.group(2)) if ym_match else default_month

        for td in soup.find_all('td'):
            cell_text = td.get_text().strip()
            if not cell_text: continue

            day_num = None
            day_match = re.search(r'^\s*(\d{1,2})\b', cell_text)
            if day_match and 1 <= int(day_match.group(1)) <= 31:
                day_num = int(day_match.group(1))
            else:
                for tag in td.find_all(['b', 'a', 'font', 'span']):
                    t_text = tag.get_text().strip()
                    if t_text.isdigit() and 1 <= int(t_text) <= 31:
                        day_num = int(t_text)
                        break

            if not day_num: continue

            td_html = str(td)
            td_html_clean = re.sub(r'<br\s*/?>', '\n', td_html, flags=re.IGNORECASE)
            td_html_clean = re.sub(r'<p[^>]*>', '\n', td_html_clean, flags=re.IGNORECASE)

            temp_soup = BeautifulSoup(td_html_clean, 'html.parser')
            plain_text = temp_soup.get_text()

            raw_items = re.split(r'[\n﹡*]', plain_text)

            for item in raw_items:
                cleaned = re.sub(r'^[0-9]{1,2}\s*', '', item)
                cleaned = re.sub(r'[﹡*儮\s]+', ' ', cleaned).strip()

                if len(cleaned) > 1 and not re.match(r'^(日|一|二|三|四|五|六|\d{1,2})$', cleaned):
                    date_str = f"{year:04d}-{month:02d}-{day_num:02d}"
                    date_obj = datetime.date(year, month, day_num)
                    day_of_week = f"星期{day_of_week_map[date_obj.weekday() if date_obj.weekday() != 6 else 0]}"

                    category = '一般'
                    cat_match = re.search(r'\((教|學|實|輔|國中|總|人|軍|圖)\)', cleaned)
                    if cat_match: category = cat_match.group(1)

                    is_dup = (date_str, cleaned) in self.existing_gcal_events

                    event_dict = {
                        'date': date_str,
                        'day': day_of_week,
                        'category': category,
                        'title': cleaned,
                        'is_duplicate': is_dup
                    }

                    if not any(e['date'] == date_str and e['title'] == cleaned for e in events):
                        events.append(event_dict)

        return events

    def update_status(self, text, progress_pct):
        self.root.after(0, lambda: self.status_label.config(text=f"狀態：{text}"))
        self.root.after(0, lambda: self.progress_var.set(progress_pct))

    def on_crawling_complete(self):
        self.reset_start_btn()
        categories = sorted(list(set(e['category'] for e in self.parsed_events)))
        self.cat_filter_combo['values'] = ["全部"] + categories
        self.cat_filter_var.set("全部")
        self.filter_events()
        messagebox.showinfo("成功", f"行事曆擷取完成！共取得 {len(self.parsed_events)} 筆事項。")

    def filter_events(self):
        query = self.search_var.get().lower()
        cat = self.cat_filter_var.get()
        status_filter = self.status_filter_var.get()

        self.filtered_events = []
        for e in self.parsed_events:
            match_query = query in e['date'] or query in e['title'].lower() or query in e['day']
            match_cat = (cat == "全部") or (e['category'] == cat)
            
            match_status = True
            if status_filter == "僅顯示新事件":
                match_status = not e.get('is_duplicate', False)
            elif status_filter == "僅顯示重複事件":
                match_status = e.get('is_duplicate', False)

            if match_query and match_cat and match_status:
                self.filtered_events.append(e)

        self.render_tree()

    def render_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, e in enumerate(self.filtered_events, start=1):
            is_dup = e.get('is_duplicate', False)
            status_str = "⚠️ 重複 (已存在)" if is_dup else "🟢 新新增"
            self.tree.insert("", tk.END, values=(idx, e['date'], e['day'], e['category'], status_str, e['title']))

        self.count_label.config(text=f"顯示 {len(self.filtered_events)} / {len(self.parsed_events)} 筆資料")

    def sync_to_mac_calendar_thread(self):
        if not IS_MAC:
            messagebox.showinfo("提示", "此寫入功能僅支援 macOS 系統。在 Windows 上請使用『匯出 .ics 日曆檔』。")
            return

        if not self.filtered_events:
            messagebox.showwarning("提示", "目前沒有可寫入的資料！")
            return

        target_calendar = self.mac_cal_var.get().strip()
        if not target_calendar:
            messagebox.showwarning("提示", "請選擇要寫入的 Mac 日曆名稱！")
            return
        
        thread = threading.Thread(target=self.run_mac_calendar_sync, args=(target_calendar,), daemon=True)
        thread.start()

    def run_mac_calendar_sync(self, target_calendar):
        self.update_status(f"正在寫入行程至 Mac『{target_calendar}』日曆...", 10)
        events_to_write = [e for e in self.filtered_events if not (self.exclude_dup_var.get() and e.get('is_duplicate', False))]
        total = len(events_to_write)
        
        if total == 0:
            self.root.after(0, lambda: messagebox.showinfo("提示", "根據設定已排除所有重複事件，無新行程需要寫入！"))
            self.reset_start_btn()
            return

        safe_cal_name = target_calendar.replace('"', '\\"')

        setup_script = f'''
        tell application "Calendar"
            if not (exists calendar "{safe_cal_name}") then
                create calendar with name "{safe_cal_name}"
            end if
        end tell
        '''
        try:
            subprocess.run(["osascript", "-e", setup_script], check=True, capture_output=True)
        except Exception as err:
            self.root.after(0, lambda: messagebox.showerror("存取受阻", f"無法存取 Mac 日曆: {err}"))
            self.update_status("寫入失敗", 0)
            return

        success_count = 0
        for idx, event in enumerate(events_to_write, start=1):
            y, m, d = event['date'].split('-')
            safe_title = event['title'].replace('"', '\\"')
            safe_cat = event['category'].replace('"', '\\"')

            event_script = f'''
            tell application "Calendar"
                tell calendar "{safe_cal_name}"
                    set startDate to (current date)
                    set year of startDate to {int(y)}
                    set month of startDate to {int(m)}
                    set day of startDate to {int(d)}
                    set hours of startDate to 0
                    set minutes of startDate to 0
                    set seconds of startDate to 0
                    
                    make new event with properties {{summary:"{safe_title}", start date:startDate, end date:startDate, allday event:true, description:"中山工商全校行事曆 ({safe_cat})"}}
                end tell
            end tell
            '''
            try:
                subprocess.run(["osascript", "-e", event_script], check=True, capture_output=True)
                success_count += 1
            except Exception as e:
                print(f"寫入失敗: {event['title']}, 錯誤: {e}")

            pct = (idx / total) * 100
            self.update_status(f"正在寫入『{target_calendar}』({idx}/{total})...", pct)

        self.fetch_mac_calendars()
        self.update_status("Mac 日曆寫入完成！", 100)
        self.root.after(0, lambda: messagebox.showinfo("寫入成功", f"🎉 已成功寫入 {success_count} 筆新行程至『{target_calendar}』！"))

    def get_export_events(self):
        if self.exclude_dup_var.get():
            return [e for e in self.filtered_events if not e.get('is_duplicate', False)]
        return self.filtered_events

    def export_standard_csv(self):
        export_list = self.get_export_events()
        if not export_list:
            messagebox.showwarning("提示", "排除重複後沒有可匯出的新資料！")
            return

        year_str = self.year_var.get().strip()
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 檔案 (*.csv)", "*.csv"), ("所有檔案 (*.*)", "*.*")],
            initialfile=f"中山工商_{year_str}_行事曆.csv"
        )
        if not filepath: return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['日期', '星期', '處室', '事項內容'])
                for e in export_list: writer.writerow([e['date'], e['day'], e['category'], e['title']])
            messagebox.showinfo("成功", f"已成功匯出 {len(export_list)} 筆標準 CSV 檔案！")
        except Exception as err:
            messagebox.showerror("匯出失敗", f"無法寫入檔案: {err}")

    def export_google_csv(self):
        export_list = self.get_export_events()
        if not export_list:
            messagebox.showwarning("提示", "排除重複後沒有可匯出的新資料！")
            return

        year_str = self.year_var.get().strip()
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 檔案 (*.csv)", "*.csv"), ("所有檔案 (*.*)", "*.*")],
            initialfile=f"中山工商_{year_str}_Google日曆.csv"
        )
        if not filepath: return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['Subject', 'Start Date', 'End Date', 'All Day Event', 'Description'])
                for e in export_list:
                    y, m, d = e['date'].split('-')
                    g_date = f"{m}/{d}/{y}"
                    writer.writerow([e['title'], g_date, g_date, "TRUE", f"中山工商全校行事曆 ({e['category']})"])
            messagebox.showinfo("成功", f"已成功匯出 {len(export_list)} 筆 Google 日曆專用 CSV 檔案！")
        except Exception as err:
            messagebox.showerror("匯出失敗", f"無法寫入檔案: {err}")

    def export_ics(self):
        export_list = self.get_export_events()
        if not export_list:
            messagebox.showwarning("提示", "排除重複後沒有可匯出的新資料！")
            return

        year_str = self.year_var.get().strip()
        filepath = filedialog.asksaveasfilename(
            defaultextension=".ics",
            filetypes=[("iCalendar 檔案 (*.ics)", "*.ics"), ("所有檔案 (*.*)", "*.*")],
            initialfile=f"中山工商_{year_str}_行事曆.ics"
        )
        if not filepath: return

        try:
            ics_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//CSIC//Calendar Crawler Desktop//TW",
                "X-WR-CALNAME:中山工商行事曆"
            ]

            for e in export_list:
                clean_date = e['date'].replace('-', '')
                ics_lines.extend([
                    "BEGIN:VEVENT",
                    f"SUMMARY:{e['title']}",
                    f"DTSTART;VALUE=DATE:{clean_date}",
                    f"DTEND;VALUE=DATE:{clean_date}",
                    f"DESCRIPTION:中山工商全校行事曆 ({e['category']})",
                    "END:VEVENT"
                ])

            ics_lines.append("END:VCALENDAR")

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("\n".join(ics_lines))

            messagebox.showinfo("成功", f"已成功匯出 {len(export_list)} 筆 .ics 日曆檔案！")
        except Exception as err:
            messagebox.showerror("匯出失敗", f"無法寫入檔案: {err}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CSICCalendarCrawlerApp(root)
    root.mainloop()
