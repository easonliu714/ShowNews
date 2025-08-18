import os
import sys
import asyncio
import logging
from bs4 import BeautifulSoup
import aiohttp
from telegram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

if not TG_BOT_TOKEN or not TG_CHAT_ID:
    logger.error("Telegram Bot Token or Chat ID environment variables not set!")
    sys.exit(1)

bot = Bot(token=TG_BOT_TOKEN)

async def fetch_html(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None

# 1. KKtix
async def crawl_kktix(session):
    url = "https://kktix.com/events"
    html = await fetch_html(session, url)
    result = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for box in soup.find_all('div', class_="event-list-item-title"):
            a = box.find('a')
            if a:
                title = a.get_text(strip=True)
                link = a['href']
                # KKtix 活動連結未補全，需加上主域名
                if not link.startswith("http"):
                    link = "https://kktix.com" + link
                result.append({"title": title, "url": link})
    logger.info(f"KKtix events: {len(result)}")
    return result

# 2. OpenTix
async def crawl_opentix(session):
    url = "https://www.opentix.life/event-search"
    html = await fetch_html(session, url)
    result = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.find_all("div", class_="event-list-card__info"):
            a = card.find("a")
            if a:
                title = a.get_text(strip=True)
                link = a['href']
                if link and not link.startswith("http"):
                    link = "https://www.opentix.life" + link
                result.append({"title": title, "url": link})
    logger.info(f"OpenTix events: {len(result)}")
    return result

# 3. tixCraft 拓元
async def crawl_tixcraft(session):
    url = "https://tixcraft.com/activity"
    html = await fetch_html(session, url)
    result = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for item in soup.find_all("div", class_="event-item"):
            a = item.find("a")
            if a:
                title = a.get_text(strip=True)
                link = a['href']
                if link and not link.startswith("http"):
                    link = "https://tixcraft.com" + link
                result.append({"title": title, "url": link})
    logger.info(f"tixCraft events: {len(result)}")
    return result

# 4. urbtix (香港城市售票網，台灣有時也取國際演出使用)
async def crawl_urbtix(session):
    url = "https://www.urbtix.hk/event-list"
    html = await fetch_html(session, url)
    result = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for li in soup.find_all("li", class_="event-list__item"):
            a = li.find("a")
            if a:
                title = a.get_text(strip=True)
                link = a['href']
                if link and not link.startswith("http"):
                    link = "https://www.urbtix.hk" + link
                result.append({"title": title, "url": link})
    logger.info(f"Urbtix events: {len(result)}")
    return result

# 5. ACCUPASS
async def crawl_accupass(session):
    url = "https://www.accupass.com/event/"
    html = await fetch_html(session, url)
    result = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.find_all("div", class_="card__body--content"):
            a = card.find("a")
            if a:
                title = a.get_text(strip=True)
                link = a['href']
                if link and not link.startswith("http"):
                    link = "https://www.accupass.com" + link
                result.append({"title": title, "url": link})
    logger.info(f"Accupass events: {len(result)}")
    return result

# 6. TACO (台灣售票網)
async def crawl_taco(session):
    url = "https://taco.com.tw/activity/all"
    html = await fetch_html(session, url)
    result = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        # 假設有 .event-card__title
        for card in soup.find_all("div", class_="event-card__title"):
            a = card.find("a")
            if a:
                title = a.get_text(strip=True)
                link = a['href']
                if link and not link.startswith("http"):
                    link = "https://taco.com.tw" + link
                result.append({"title": title, "url": link})
    logger.info(f"TACO events: {len(result)}")
    return result

# 7. 博客來售票 Kingstone (kingstone.tixcraft.com 旗下)
async def crawl_kingstone(session):
    url = "https://ticket.kingstone.com.tw/activity"
    html = await fetch_html(session, url)
    result = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for item in soup.find_all("div", class_="event-item"):
            a = item.find("a")
            if a:
                title = a.get_text(strip=True)
                link = a['href']
                if link and not link.startswith("http"):
                    link = "https://ticket.kingstone.com.tw" + link
                result.append({"title": title, "url": link})
    logger.info(f"Kingstone events: {len(result)}")
    return result

# ------ 主流程（僅--test模式） ------

async def main_test_mode():
    async with aiohttp.ClientSession() as session:
        tasks = [
            crawl_kktix(session),
            crawl_opentix(session),
            crawl_tixcraft(session),
            crawl_urbtix(session),
            crawl_accupass(session),
            crawl_taco(session),
            crawl_kingstone(session),
        ]
        results = await asyncio.gather(*tasks)

        # 組裝發送訊息
