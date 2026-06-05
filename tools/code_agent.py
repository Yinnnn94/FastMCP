import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import pandas as pd
import uuid
from fastmcp import FastMCP
import os
import dotenv


dotenv.load_dotenv()  # 從 .env 檔案載入環境變數
# Create an MCP server
server = FastMCP("CodeAgent_MCP")

@server.tool(name="execute_plotting_code", description="執行 Python 代碼並產出圖表檔案")
def execute_plotting_code(python_code: str, db_data: list = None):
    font_path = '/app/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    plt.clf() # 清除畫布
    if os.path.exists(font_path):
        try:
            # 1. 直接將字體註冊到全域字體管理器
            fm.fontManager.addfont(font_path)

            # 2. 取得該字體的正確名稱 (例如 'Noto Sans CJK JP')
            prop = fm.FontProperties(fname=font_path)
            font_name = prop.get_name()

            # 3. 設定全域預設字體
            plt.rcParams['font.family'] = font_name
            plt.rcParams['axes.unicode_minus'] = False
            print(f"✅ 字體已註冊並設定為預設: {font_name}")
        except Exception as font_err:
            print(f"❌ 字體載入失敗: {font_err}")

    # 強制將資料庫資料轉換成 DataFrame
    df = pd.DataFrame(db_data) if db_data else pd.DataFrame()
    if not df.empty:
        print(f"✅ 資料已載入 DataFrame，共 {len(df)} 筆資料")

    loc = {}
    try:
        # 執行代碼 (LLM 可使用 df 變數進行資料處理和繪圖)
        exec(python_code, {"plt": plt, "pd": pd, "df": df}, loc)
        filename = f"chart_{uuid.uuid4().hex[:8]}.png"
        file_path = os.path.join('/app/plot_img', filename)
        plt.savefig(file_path)
        print(f"產生的圖片路徑:{file_path}")
        plt.close()

        # 只回傳路徑與狀態，告訴下一個工具去哪裡拿檔案
        return {
            "status": "success",
            "local_file_path": os.path.abspath(file_path),
            "filename": filename,
            "remote_path": f"opwui_img/{filename}",
            "message": "圖表已生成，準備上傳至 TDrive..."
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@server.tool(name = "upload_file_to_tdrive", description = "將檔案上傳到tdrive並分享成連結")
def upload_and_share_to_tdrive(local_file_path, remote_path):
    # --- 1. 設定資訊 ---
    username = os.getenv("TDRIVE_USERNAME")  # 從環境變數讀取
    password = os.getenv("TDRIVE_PW")  # 從環境變數讀取
    domain = os.getenv("TRDIVE_DOMAIN")  # 從環境變數讀取

    # --- 2. 執行 WebDAV 上傳 ---
    upload_url = f"https://{domain}/remote.php/dav/files/{username}/{remote_path}"
    with open(local_file_path, 'rb') as f:
        put_res = requests.put(upload_url, data=f, auth=HTTPBasicAuth(username, password))

    if put_res.status_code not in [201, 204]:
        print(f"上傳失敗: {put_res.status_code}")
        return None

    # --- 3. 呼叫 OCS API 建立公開連結 ---
    share_url = f"https://{domain}/ocs/v2.php/apps/files_sharing/api/v1/shares"
    payload = {
        'path': remote_path,
        'shareType': 3,     # 3 = 公開連結 (Public link)
        'permissions': 1    # 1 = 唯讀 (Read only)
    }
    headers = {
        'OCS-APIRequest': 'true',  # Nextcloud API 必帶 Header
    }

    response = requests.post(
        share_url + "?format=json",
        data=payload,
        auth=HTTPBasicAuth(username, password),
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        # 提取分享連結
        base_share_url = data['ocs']['data']['url']
        # --- 重要：加上 /preview 讓 Open WebUI 直接渲染 ---
        render_url = f"{base_share_url}/preview"
        download_url = f"{base_share_url}/download"
        print(f"成功！渲染連結為: {render_url}")
        return render_url, download_url
    else:
        print(f"分享失敗: {response.status_code}, {response.text}")
        return None

if __name__ == "__main__":
     server.run(transport="http", port = 8002, host ="0.0.0.0")
