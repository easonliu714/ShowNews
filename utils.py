import os
import json
import random
import re
import aiohttp
import asyncio
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode

PLATFORMS = [
    "KKTIX", "拓元售票", "OPENTIX", "寬宏", "年代售票", "UDN售票網", "iBon售票"
]

DETAIL_URL_WHITELIST = {
    "KKTIX": re.compile(r"^https?://[a-z0-9-]+\.kktix\.cc/events/[A-Za-z0-9-_]+", re.I),
    "拓元售票": re.compile(r"^https?://(www\.)?tixcraft\.com/activity/detail/[A-Za-z0-9_-]+", re.I),
    "OPENTIX": re.compile(r"^https?://(www\.)?opentix\.life/event/\d+", re.I),
    "寬宏": re.compile(r"^https?://(www\.)?kham\.com\.tw/application/UTK02/UTK0201_\.aspx\?PRODUCT_ID=[A-Z0-9]+", re.I),
    "年代售票": re.compile(r"^https?://(www\.)?ticket\.com\.tw/application/UTK02/UTK0201_\.aspx\?PRODUCT_ID=[A-Z0-9]+", re.I),
    "UDN售票網": re.compile(r"^https?://(www\.)?tickets\.udnfunlife\.com/application/UTK02/UTK0201_\.aspx\?PRODUCT_ID=[A-Z0-9]+", re.I),
    "iBon售票": re.compile(r"^https?://(www\.)?ticket\.ibon\.com\.tw/", re.I),
}

TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
bot = Bot(token=TOKEN) if TOKEN and CHAT_ID else None

RUN_LOG = "run.log"
LOG_FILE = 'Show_News_log.json'

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
]
REQUEST_HEADERS = {
    'User-Agent': random.choice(USER_AGENTS),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

def escape_markdown_v2(text: str) -> str:
    if not isinstance(text, str): text = str(text)
    escape_chars = r'_*[]()~`>#+=|{}.!-'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def append_log_run(msg):
    log_path = Path(RUN_LOG)
    mode = 'a' if log_path.exists() else 'w'
    with log_path.open(mode, encoding='utf-8') as f:
        f.write(f"[{datetime.now()}] {msg}\n")
    print(f"[DEBUG] {msg}")

def load_json_file(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_json_file(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_log():
    return load_json_file(LOG_FILE)

def save_log(log):
    save_json_file(log, LOG_FILE)

def safe_get_text(element, default="詳內文"):
    return element.get_text(strip=True) if element and hasattr(element, 'get_text') and element.get_text(strip=True) else default

def get_event_category_from_title(title):
    if not title: return "其他"
    title_lower = title.lower()
    mapping = {
        "音樂會/演唱會": ["音樂會", "演唱會", "live", "concert", "音樂節"],
        "音樂劇/歌劇": ["音樂劇", "歌劇", "musical", "opera"],
        "戲劇表演": ["戲劇", "舞台劇", "喜劇", "劇場", "劇團"],
        "舞蹈表演": ["舞蹈", "芭蕾"],
        "展覽/博覽": ["展覽", "特展", "藝術展", "美術館"],
        "親子活動": ["親子", "兒童", "寶寶", "家庭"],
        "電影放映": ["電影", "影展"],
        "體育賽事": ["賽事", "馬拉松", "路跑", "球賽"],
        "講座/工作坊": ["講座", "工作坊"],
        "娛樂表演": ["綜藝", "脫口秀", "秀場"],
        "其他": ["旅遊", "美食", "公益"]
    }
    for cat, keys in mapping.items():
        if any(k in title_lower for k in keys): return cat
    return "其他"

async def fetch_platform_events_list(session, platform):
    url_selector_map = {
        "KKTIX": ("https://kktix.com/events", 'a[href*="/events/"]', "KKTIX"),
        "OPENTIX": ("https://www.opentix.life/event", 'a[href*="/event/"]', "OPENTIX"),
        "拓元售票": ("https://tixcraft.com/activity", 'a[href*="/activity/detail/"]', "拓元售票"),
        "寬宏": ("https://kham.com.tw/", 'a[href*="/application/UTK02/UTK0201_"]', "寬宏"),
        "年代售票": ("https://ticket.com.tw/", 'a[href*="/application/UTK02/UTK0201_"]', "年代售票"),
        "UDN售票網": ("https://tickets.udnfunlife.com/", 'a[href*="/application/UTK02/UTK0201_"]', "UDN售票網"),
        "iBon售票": ("https://ticket.ibon.com.tw/", 'a[href^="https://ticket.ibon.com.tw/"]', "iBon售票")
    }
    if platform not in url_selector_map:
        return []
    start_url, selector, plat_name = url_selector_map[platform]
    try:
        async with session.get(start_url, headers=REQUEST_HEADERS, timeout=20) as resp:
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select(selector)
        events = []
        wl = DETAIL_URL_WHITELIST.get(platform)
        seen_urls = set()
        for link in links:
            href = link.get('href','')
            title = safe_get_text(link)
            if not href or not title or len(title)<3: 
                continue
            if not href.startswith("http"):
                if platform=="OPENTIX":
                    href = "https://www.opentix.life" + href
                elif platform=="KKTIX":
                    href = "https://kktix.com" + href
                elif platform=="拓元售票":
                    href = "https://tixcraft.com" + href
                elif platform=="寬宏":
                    href = "https://kham.com.tw" + href
                elif platform=="年代售票":
                    href = "https://ticket.com.tw" + href
                elif platform=="UDN售票網":
                    href = "https://tickets.udnfunlife.com" + href
            if wl and not wl.match(href):
                continue
            if href in seen_urls:
                continue
            events.append({
                "title": title.strip(), "url": href, "platform": plat_name, "type": get_event_category_from_title(title)
            })
            seen_urls.add(href)
        return events
    except Exception as e:
        append_log_run(f"{platform} 列表擷取錯誤: {e}")
        return []

async def extract_event_details_simple(url, platform, session, list_event=None):
    details = {'date': '詳內文', 'location': '詳內文', 'ticket_date': '詳內文', 'description': '', 'title': '詳內文'}
    if list_event and 'title' in list_event:
        details['title'] = list_event['title']
    try:
        async with session.get(url, headers=REQUEST_HEADERS, timeout=20, ssl=False) as resp:
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        title_candidates = [soup.find("title"), soup.find("h1"),
                            soup.find("meta", attrs={"property": "og:title"}),
                            soup.find("meta", attrs={"name": "twitter:title"})]
        for c in title_candidates:
            if c:
                new_title = c.get('content','').strip() if c.name=='meta' else safe_get_text(c)
                if new_title and len(new_title)>5:
                    details['title']=new_title
                    break
        if not details['description']:
            desc_candidates = [
                soup.find("meta", {"property":"og:description"}),
                soup.find("meta", {"name": "description"})
            ]
            for elem in desc_candidates:
                if elem:
                    desc_text = elem.get('content','').strip()
                    if len(desc_text)>150: desc_text=desc_text[:150]+"..."
                    details['description'] = desc_text
                    break
        page_text = soup.get_text(" ", strip=True)
        date_match = re.search(r'(\d{4}[./]\d{1,2}[./]\d{1,2})', page_text)
        if date_match: details['date'] = date_match.group(1).strip()
        loc_match = None

        if platform == "年代售票":
            # 移除多餘字串，年代表演場地可能須用CSS抓取，暫用regex替代，您可進一步微調
            details['title'] = details['title'].replace("年代售票 |", "").strip()
            # 取得較精準地點 (示範用 regex拉取 "演出地點" 欄位附近文字)
            loc_match = re.search(r'演出地點[:：]\s*([^\s，。]+)', page_text)

        elif platform == "UDN售票網":
            details['title'] = details['title'].replace(" | udn售票網", "").strip()
            loc_match = re.search(r'地點[:：]\s*([^\s，。]+)', page_text)

        elif platform == "寬宏":
            # 因寬宏標題全是系統名，改從列表title補足，詳細頁定位示意:
            if list_event and list_event.get('title'):
                details['title'] = list_event['title']
            loc_match = re.search(r'場地[:：]\s*([^\s，。]+)', page_text)

        else:
            loc_match = re.search(r'(?:地點|場地|演出地點)[:：]?\s*([^\s，。]+)', page_text)

        if loc_match:
            details['location'] = loc_match.group(1).strip()

        return details
    except Exception as e:
        append_log_run(f"詳細頁面提取失敗：{url} - {e}")
        return details

async def send_telegram_message_with_retry(event, is_init=False, downgraded=False, max_retries=3):
    if not bot: 
        return False, "Bot not ready"
    for attempt in range(max_retries):
        try:
            header = "🆕 新增活動通知"
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
            lines.append(f"\n📌 [點我查看詳情]({event.get('url','')})")
            msg = "\n".join(lines)
            if len(msg)>4096:
                msg = "\n".join(lines[:6]) + f"\n\n📌 [點我查看詳情]({event.get('url','')})"

            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN_V2)
            # 延遲2秒避免 flood control
            await asyncio.sleep(2)
            return True, None
        except Exception as err:
            append_log_run(f"發送失敗 (第{attempt+1}次)：{event.get('title','(無標題)')} => {err}")
            wait = 5 * (attempt + 1)
            await asyncio.sleep(wait)
    return False, "Send failed"

async def send_platform_summary_message(platform_stats):
    if not bot:
        return
    try:
        lines = ["📊 活動推播統計報告"]
        for plat, stat in platform_stats.items():
            count_new = stat.get('new',0)
            count_sent = stat.get('sent',0)
            lines.append(f"🧾 {plat}: 新活動數 {count_new}，成功推送 {count_sent}")
        lines.append(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        msg = "\n".join(lines)
        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        append_log_run(f"推播統計訊息失敗: {e}")

async def test_crawl_and_notify():
    async with aiohttp.ClientSession() as session:
        platform_stats = {}
        log = load_log()

        for platform in PLATFORMS:
            events = await fetch_platform_events_list(session, platform)
            platform_stats[platform] = {'new':0, 'sent':0}
            if not events:
                append_log_run(f"{platform} 未抓取到新活動")
                continue
            # 去重與過去紀錄比對
            seen_url = set()
            filtered = []
            for e in events:
                if e['url'] not in seen_url:
                    seen_url.add(e['url'])
                    filtered.append(e)
            new_events = [e for e in filtered if e['url'] not in log]

            platform_stats[platform]['new'] = len(new_events)
            count_sent = 0
            for event in new_events[:5]:  # 每平台最多只發5則
                details = await extract_event_details_simple(event['url'], event['platform'], session, list_event=event)
                merged = event.copy()
                merged.update(details)
                ok, err = await send_telegram_message_with_retry(merged, is_init=True)
                if ok:
                    count_sent += 1
                    log[merged['url']] = {'title': merged.get('title', event['title'])}
                    save_log(log)
            platform_stats[platform]['sent'] = count_sent

        # 最後發送平台彙整訊息
        await send_platform_summary_message(platform_stats)

        return {
            "success": True,
            "platform_stats": platform_stats
        }
