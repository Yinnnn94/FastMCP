# FastMCP

FastMCP 是一個提供多個實用工具的 MCP (Model Context Protocol) 伺服器，讓你能透過 AI 助手輕鬆使用以下功能。

## 功能特性

### 1. 🐳 Docker 容器狀態檢查
快速檢查 Docker 容器的運行狀態，監控容器健康度。
- 查看容器詳細資訊
- 實時監控容器狀態
- 快速診斷容器問題

### 2. 📊 資料庫查詢與圖表繪製
連線至資料庫執行查詢，並自動將結果視覺化為圖表。
- 支援多種資料庫連線
- 自動圖表生成
- 數據分析與可視化

### 3. 💬 通用聊天機器人
一般性的 AI 聊天機器人，提供智能對話功能。
- 自然語言對話
- 多輪次對話支援
- 通用知識查詢

### 4. 📅 Outlook 日曆管理
整合 Microsoft Outlook 日曆，提供完整的日曆管理功能。

#### 主要功能：
- **獲取使用者資訊** - 取得當前使用者的基本信息（名稱、Email）
![outlook_get_user_info](https://github.com/Yinnnn94/FastMCP/blob/main/img/outlook/outlook_get_user_info.png)

- **查看日曆事件** - 查詢指定時間範圍內的所有日曆事件
  - 支援自訂時間範圍
  - 包含事件詳情（主題、時間、位置、參與者等）
  - 自動清理事件描述中的特殊字符（換行符、底線等）
  ![outlook_get_calendar](https://github.com/Yinnnn94/FastMCP/blob/main/img/outlook/outlook_get_calendar.png)

- **查詢可用時間** - 查詢多位參與者的共同可用時間
  - 支援多人參與者查詢
  - 可指定位置限制
  - 回傳建議的會議時段及信心指數
  ![outlook_get_free_time](https://github.com/Yinnnn94/FastMCP/blob/main/img/outlook/outlook_get_free_time.png)

- **創建日曆事件** - 快速創建新的日曆事件
  - 設定事件主題、時間、位置
  - 添加多位參與者（自動發送邀請）
  - 添加事件描述
  - 返回事件詳情及 Outlook 連結
  ![outlook_create_event](https://github.com/Yinnnn94/FastMCP/blob/main/img/outlook/outlook_create_event.png)

API 內部自動轉換為 UTC 與 Microsoft Graph 通訊

## 開始使用

安裝所需依賴並運行 FastMCP 伺服器，即可在支援 MCP 的應用中使用這些工具。
