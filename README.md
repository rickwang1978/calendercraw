# calendercraw
🏫 中山工商行事曆爬蟲與 Google 日曆極速同步工具

一個專為高雄市私立中山工商設計的行事曆自動擷取、重複比對與多平台同步工具。支援解析學校傳統 ASP 網頁格式、一事件單獨立列、自動清洗亂碼，並透過多線程併行 Batch 技術，實現幾秒內極速同步數百筆行程至 Google 子日曆或 Mac 原生日曆。

✨ 核心特色 (Key Features)

🏫 傳統 ASP 網頁精準解析：自動切換 CP950 / UTF-8 解碼，解決舊式 HTML 無閉合標籤問題，確保「一事件一列」。

🧹 智慧字元清洗：自動剔除 ﹡、* 及解碼殘留亂碼字元，保留乾淨的行程標題與處室分類。

🔍 Google 日曆雙模重複比對：

方案一（離線檔案）：匯入過往的 CSV 或 .ics 檔進行比對，自動標記 ⚠️ 重複 (已存在)。

方案二（Google API 在線比對）：直連 Google Calendar API，分頁抓取指定子日曆行程並進行自動比對。

⚡ 多線程並行 Batch 狂速同步：採用 ThreadPoolExecutor + Google API Batch Request 併發傳輸，300~500 筆行程只需 1~3 秒 寫入完成。

📅 支援指定 Google 子日曆 / Mac 原生日曆：可自由選擇寫入目標日曆，若子日曆不存在將自動為您新建。

📊 多格式自由匯出：支援匯出 Excel CSV (帶 UTF-8 BOM)、Google 日曆 CSV 與 .ics (iCalendar) 檔案。

💻 跨平台支援 (macOS & Windows)：自動偵測作業系統，Mac 上自動啟動 AppleScript 直連原生「日曆.app」。

🖥️ 介面預覽 (UI Preview)

擷取與重複比對

行程資料列表

設定年月與目標 Google 子日曆

標示 🟢 新新增 / ⚠️ 重複 狀態

🛠️ 安裝說明 (Installation)

1. 複製專案 (Clone Repository)

git clone [https://github.com/your-username/csic-calendar-crawler.git](https://github.com/your-username/csic-calendar-crawler.git)
cd csic-calendar-crawler


2. 安裝必要套件 (Dependencies)

pip install requests beautifulsoup4 google-api-python-client google-auth-httplib2 google-auth-oauthlib


🔑 Google Calendar API 設定 (Optional for API Sync)

若要使用 方案二：Google API 線上比對與直連同步 功能，請先設定 OAuth 憑證：

前往 Google Cloud Console 建立新專案。

啟用 Google Calendar API 服務。

在「OAuth 同意畫面」設定測試使用者（填入您的 Google 帳號）。

建立憑證 ➔ 選擇 OAuth 用戶端 ID ➔ 應用程式類型選擇 桌面應用程式 (Desktop App)。

下載 JSON 憑證檔，重命名為 credentials.json，並放置於專案根目錄下。

🚀 執行與打包 (Usage & Packaging)

直接執行 Python 腳本

python csic_calendar_crawler.py


打包為獨立免安裝執行檔 (PyInstaller)

🍎 macOS (.app 打包)

pip install pyinstaller
pyinstaller --noconsole --onefile --windowed --name "中山工商行事曆" csic_calendar_crawler.py


打包完成後，位於 dist/中山工商行事曆.app，將 credentials.json 放在與 .app 同一個資料夾下即可。

🪟 Windows (.exe 打包)

python -m pip install pyinstaller
python -m PyInstaller --noconsole --onefile --name "中山工商行事曆" csic_calendar_crawler.py


產出的 .exe 檔位於 dist/中山工商行事曆.exe。

📂 專案檔案結構 (Project Structure)

.
├── csic_calendar_crawler.py  # 桌面 GUI 應用程式主程式 (Tkinter)
├── credentials.json          # Google OAuth 憑證檔 (需自備)
├── README.md                 # 專案說明文件
└── LICENSE                   # 開源授權條款


📜 授權條款 (License)

本專案採用 MIT License 授權發行。自由使用、修改與分享。
