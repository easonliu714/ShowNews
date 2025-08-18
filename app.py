# -*- coding: utf-8 -*-
import asyncio
import aiohttp
import random
import time
import json
import os
import re
import schedule
import argparse
import urllib3
from datetime import datetime
from urllib.parse import urljoin
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import telegram
from telegram.constants import ParseMode

# =========================
# 設定區
# =========================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
]

REQUEST_PARAMS = {'timeout': 20, 'allow_redirects': True}

# 從環境變數讀取配置
TOKEN = os.getenv('TG_BOT_TOKEN')
CHAT_ID = os.getenv('TG_CHAT_ID')

# 檔案路徑
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

LOG_FILE = DATA_DIR / 'Show_News_log.json'
RUN_LOG = DATA_DIR / 'run.log'
FAILED_LOG = DATA_DIR / 'failed_messages.json'
STATS_LOG = DATA_DIR / 'connection_stats.json'

bot = None

# =========================
# 平台上下文
# =========================
class FetchContext:
    def __init__(self):
        self.ua = None
        self.cookies = {}
        self.last_referer = None
        self.consec_auth_fail = 0
        self.warmed = False

platform_contexts = {
    platform: FetchContext()
    for platform in ["拓元售票", "KKTIX", "OPENTIX", "寬宏", "年代售票", "UDN售票網", "iBon售票", "Event Go"]
}

# =========================
# Session設定
# =========================
def create_session():
    session = requests.Session()
    retry = Retry(total=2, read=2, connect=2, backoff_factor=0.6, 
                  status_forcelist=(429, 500, 502, 503, 504, 403, 401))
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.6',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'no-cache',
        'DNT': '1',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none'
    })
    session.verify = True
    return session

session = create_session()

# =========================
# 統計與日誌
# =========================
def load_json_file(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_json_file(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

load_connection_stats = lambda: load_json_file(STATS_LOG)
save_connection_stats = lambda stats: save_json_file(stats, STATS_LOG)
load_log = lambda: load_json_file(LOG_FILE)
save_log = lambda log: save_json_file(log, LOG_FILE)
load_failed_log = lambda: load_json_file(FAILED_LOG)
save_failed_log = lambda log: save_json_file(log, FAILED_LOG)

def append_log_run(msg):
    log_path = Path(RUN_LOG)
    mode = 'a' if log_path.exists() else 'w'
    with log_path.open(mode, encoding='utf-8') as f:
        f.write(f"[{datetime.now()}] {msg}\n")
    print(f"[DEBUG] {msg}")

# =========================
# 輔助函式
# =========================
def safe_get_text(element, default="詳內文"):
    return element.get_text(strip=True) if element and hasattr(element, 'get_text') and element.get_text(strip=True) else default

def get_event_category_from_title(title):
    if not title:
        return "其他"
    
    title_lower = title.lower()
    category_mapping = {
        "音樂會/演唱會": ["音樂會", "演唱會", "獨奏會", "合唱", "交響", "管樂", "國樂", "弦樂", "鋼琴", "提琴", "巡演", "fan concert", "fancon", "音樂節", "爵士", "演奏", "歌手", "樂團", "tour", "live", "concert", "solo", "recital", "電音派對", "藝人見面會"],
        "音樂劇/歌劇": ["音樂劇", "歌劇", "musical", "opera"],
        "戲劇表演": ["戲劇", "舞台劇", "劇團", "劇場", "喜劇", "公演", "掌中戲", "歌仔戲", "豫劇", "話劇", "相聲", "布袋戲", "京劇", "崑劇", "藝文活動"],
        "舞蹈表演": ["舞蹈", "舞作", "舞團", "芭蕾", "舞劇", "現代舞", "民族舞", "踢踏舞"],
        "展覽/博覽": ["展覽", "特展", "博物館", "美術館", "藝術展", "畫展", "攝影展", "文物展", "科學展", "博覽會", "動漫"],
        "親子活動": ["親子", "兒童", "寶寶", "家庭", "小朋友", "童話", "卡通", "動畫"],
        "電影放映": ["電影", "影展", "數位修復", "放映", "首映", "紀錄片", "動畫電影"],
        "體育賽事": ["棒球", "籃球", "錦標賽", "運動會", "足球", "羽球", "網球", "馬拉松", "路跑", "游泳", "體操", "championship", "遊戲競賽"],
        "講座/工作坊": ["工作坊", "課程", "導讀", "沙龍", "講座", "體驗", "研習", "培訓", "論壇", "研討會", "座談", "workshop", "職場工作術", "資訊科技"],
        "娛樂表演": ["脫口秀", "魔術", "雜技", "馬戲", "特技", "魔幻", "綜藝", "娛樂", "秀場", "表演秀", "社群活動"],
        "其他": ["旅遊", "美食", "公益"]
    }
    
    for category, keywords in category_mapping.items():
        if any(keyword in title_lower for keyword in keywords):
            return category
    return "其他"

# =========================
# 爬取相關函式
# =========================
DETAIL_URL_WHITELIST = {
    "拓元售票": re.compile(r"^https?://(www\.)?tixcraft\.com/activity/detail/[A-Za-z0-9_-]+", re.I),
    "KKTIX": re.compile(r"^https?://[a-z0-9-]+\.kktix\.cc/events/[A-Za-z0-9-_]+", re.I),
    "OPENTIX": re.compile(r"^https?://(www\.)?opentix\.life/event/\d+", re.I),
    "年代售票": re.compile(r"^https?://(www\.)?ticket\.com\.tw/application/UTK02/UTK0201_\.aspx\?PRODUCT_ID=[A-Z0-9]+", re.I),
    "UDN售票網": re.compile(r"^https?://(www\.)?tickets\.udnfunlife\.com/application/UTK02/UTK0201_\.aspx\?PRODUCT_ID=[A-Z0-9]+", re.I),
    "iBon售票": re.compile(r"^https?://(www\.)?ticket\.ibon\.com\.tw/", re.I),
    "寬宏": re.compile(r"^https?://(www\.)?kham\.com\.tw/application/UTK02/UTK0201_\.aspx\?PRODUCT_ID=[A-Z0-9]+", re.I),
    "Event Go": re.compile(r"^https?://eventgo\.bnextmedia\.com\.tw/event/detail[^\s]*$", re.I),
}

def filter_links_for_platform(links, base_url, platform_name):
    events, seen_urls = [], set()
    wl = DETAIL_URL_WHITELIST.get(platform_name)
    
    for link in links:
        href = link.get('href', '')
        title = safe_get_text(link)
        
        if not href or not title or len(title) < 3:
            continue
            
        full_url = urljoin(base_url, href)
        
        # Event Go 專門過濾：只接受 /event/detail 的活動詳頁
        if platform_name == "Event Go":
            if not full_url.startswith("https://eventgo.bnextmedia.com.tw/event/detail"):
                continue
        
        if full_url in seen_urls or (wl and not wl.match(full_url)):
            continue
            
        if platform_name == "UDN售票網":
            title = re.sub(r'\.\.\.moreNT\$\s*[\d,]+\s*~\s*[\d,]+$', '', title).strip()
            title = re.sub(r'&amp;[a-zA-Z0-9#]+;', '', title).strip()
            
        if title.lower() in ['more', '更多', '詳情', '購票']:
            continue
            
        events.append({
            'title': title.strip(),
            'url': full_url,
            'platform': platform_name,
            'type': get_event_category_from_title(title)
        })
        seen_urls.add(full_url)
    
    append_log_run(f"{platform_name} 過濾後剩餘 {len(events)} 個有效連結")
    return events

async def fetch_text(session: aiohttp.ClientSession, url: str, timeout_sec=15):
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1'
    }
    
    async with session.get(url, headers=headers, allow_redirects=True, ssl=False, timeout=timeout_sec) as resp:
        if resp.status != 200:
            raise Exception(f"HTTP {resp.status}")
        text = await resp.text()
        if len(text) < 500:
            raise Exception("內容過短，可能被封鎖")
        return text

# =========================
# Telegram發送
# =========================
def escape_markdown_v2(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*[]()~`>#+=|{}.!-'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

async def send_telegram_message_with_retry(event, is_init=False, downgraded=False, max_retries=1):
    for attempt in range(max_retries):
        try:
            header = "🔄 首輪測試活動" if is_init else "🆕 新增活動通知"
            title = escape_markdown_v2(event.get('title', '詳內文'))
            event_type = escape_markdown_v2(event.get('type', '詳內文'))
            event_date = escape_markdown_v2(event.get('date', '詳內文'))
            event_location = escape_markdown_v2(event.get('location', '詳內文'))
            event_platform = escape_markdown_v2(event.get('platform', '詳內文'))
            
            lines = [
                header,
                f"🎫 {title}",
                f"📍 類型：{event_type}",
                f"📅 日期：{event_date}",
                f"🗺 地點：{event_location}",
                f"🧾 平台：{event_platform}"
            ]
            
            if downgraded:
                lines.append("⚠️ 詳頁資訊受限，請點擊連結查看")
            
            lines.append(f"\n📌 [點我查看詳情]({event.get('url', '')})")
            
            msg = "\n".join(lines)
            
            if len(msg) > 4096:
                append_log_run(f"訊息仍過長，強制截斷: {event.get('title')}")
                msg = "\n".join(lines[:6]) + f"\n\n📌 [點我查看詳情]({event.get('url', '')})"
            
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN_V2)
            return True, None
            
        except Exception as err:
            error_msg = str(err)
            append_log_run(f"發送失敗 (第{attempt+1}次)：{event.get('title','(無標題)')} => {error_msg}")
            
            if "message is too long" in error_msg.lower():
                return False, "Message is too long"
                
            if attempt < max_retries - 1:
                wait_time = 5
                if "Flood control" in error_msg:
                    wait_time = min(60 * (attempt + 1), 300)
                elif any(k in error_msg.lower() for k in ['timeout', 'connect', 'network']):
                    wait_time = 15 * (attempt + 1)
                await asyncio.sleep(wait_time)
    
    return False, str(err)

# =========================
# 簡化的檢查函式
# =========================
async def simple_check():
    """簡化的檢查函式，只抓取KKTIX和拓元售票"""
    append_log_run("開始執行簡化活動檢查")
    
    connector = aiohttp.TCPConnector(ssl=False, limit=10, family=0)
    async with aiohttp.ClientSession(connector=connector) as aio_sess:
        try:
            # 簡化版：只抓取KKTIX
            html = await fetch_text(aio_sess, "https://kktix.com/")
            soup = BeautifulSoup(html, "html.parser")
            links = soup.select('a[href*="/events/"]')
            events = filter_links_for_platform(links, "https://kktix.com/", "KKTIX")
            
            append_log_run(f"發現 {len(events)} 個KKTIX活動")
            
            # 簡單處理：只發送前3個新活動
            log_data = load_log()
            new_events = [e for e in events[:3] if e['url'] not in log_data]
            
            sent_count = 0
            for event in new_events:
                success, error = await send_telegram_message_with_retry(event)
                if success:
                    sent_count += 1
                    log_data[event['url']] = {'title': event['title']}
                    save_log(log_data)
                await asyncio.sleep(2)  # 避免發送太快
            
            append_log_run(f"處理完成：發送 {sent_count} 筆新活動")
            
        except Exception as e:
            append_log_run(f"檢查過程發生錯誤: {e}")

# =========================
# 定時任務
# =========================
async def run_schedule():
    """異步運行定時任務"""
    while True:
        schedule.run_pending()
        await asyncio.sleep(60)  # 每分鐘檢查一次

def setup_schedule():
    """設定定時任務"""
    schedule.every().day.at("09:00").do(lambda: asyncio.create_task(simple_check()))
    schedule.every().day.at("15:00").do(lambda: asyncio.create_task(simple_check()))
    schedule.every().day.at("21:00").do(lambda: asyncio.create_task(simple_check()))
    append_log_run("已設定每日 09:00, 15:00, 21:00 自動檢查")

# =========================
# 主程式
# =========================
async def main():
    global bot
    
    if not TOKEN or not CHAT_ID:
        append_log_run("請設定環境變數 TG_BOT_TOKEN 與 TG_CHAT_ID")
        return
    
    bot = telegram.Bot(token=TOKEN)
    append_log_run("ShowNews 活動爬蟲啟動")
    
    # 設定定時任務
    setup_schedule()
    
    # 執行一次檢查
    await simple_check()
    
    # 在Render上會持續運行
    if os.getenv('RENDER'):
        append_log_run("在Render環境中運行，開始定時任務")
        await run_schedule()
    else:
        append_log_run("本地測試完成")

if __name__ == "__main__":
    asyncio.run(main())
