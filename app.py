import uvicorn
from fastapi import FastAPI, Request
import asyncio
from utils import test_crawl_and_notify

app = FastAPI()

@app.get("/")
def read_root():
    return {"status":"ok",
            "usage": "GET /test-crawl 啟動 -test模式活動爬蟲推播(支援臺灣三大熱門平台)，環境變數需設 TG_BOT_TOKEN, TG_CHAT_ID"}

@app.get("/test-crawl")
async def trigger_test_crawler(request: Request):
    # 正式環境請加密/權限保護
    result = await test_crawl_and_notify()
    return result

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(8000), reload=True)
