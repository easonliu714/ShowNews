from fastapi import FastAPI
import asyncio
from utils import test_crawl_and_notify

app = FastAPI()

@app.get("/")
async def index():
    return {
        "status": "ok",
        "usage": "GET /test-crawl 啟動測試模式爬蟲推播"
    }

@app.get("/test-crawl")
async def trigger_test_crawler():
    result = await test_crawl_and_notify()
    return result
