# ShowNews - 台灣活動資訊爬取與通知系統

自動爬取台灣各大售票平台的活動資訊，並透過Telegram機器人發送通知。

## 功能特色

- 🎫 支援多個售票平台（KKTIX、拓元售票、OPENTIX等）
- 🤖 Telegram機器人自動通知
- ⏰ 定時自動檢查（每日09:00、15:00、21:00）
- 📊 活動分類與統計
- 🔄 重複過濾機制

## 環境變數設定

- `TG_BOT_TOKEN`: Telegram機器人Token
- `TG_CHAT_ID`: Telegram聊天室ID

## 部署方式

### 本地運行
pip install -r requirements.txt
python app.py


### Render部署
1. 連接GitHub Repository
2. 設定環境變數
3. 自動部署

## 授權

MIT License
