from fastmcp import FastMCP
import requests

mcp = FastMCP("Docker-HTTP-Tool")
PROXY_URL = "http://docker-socket-proxy:2375"


@mcp.tool()
def list_containers(
    health: str = None,
    name: str = None,
    status: str = None,

) -> dict:
    """
    列出容器清單，支援多種篩選條件（由 LLM 依使用者問題自行判斷填入）。

    參數：
    - health: 健康狀態篩選，可填 starting | healthy | unhealthy | none
    - name: 依容器名稱篩選（支援部分名稱）
    - status: 執行狀態篩選，可填 created | restarting | running | removing | paused | exited | dead
    """
    import json
    url = f"{PROXY_URL}/v1.43/containers/json"
    filters = {}
    if health:
        filters["health"] = [health]
    if name:
        filters["name"] = [name]
    if status:
        filters["status"] = [status]

    params = {"all": 1}
    if filters:
        params["filters"] = json.dumps(filters)
    try:
        response = requests.get(
            url,
            params=params,
            proxies={"http": None, "https": None},
            timeout=10)
        if response.status_code != 200:
            return {"error": f"無法取得容器清單 (狀態碼: {response.status_code}, 內容: {response.text})"}
        containers = response.json()
        result = [
            {"id": c["Id"][:12], "name": c["Names"][0][1:], "status": c.get("Status", "")}
            for c in containers
        ]
        return {"containers": result, "count": len(result)}
    except requests.exceptions.RequestException as e:
        return {"error": f"連線異常: {str(e)}"}


@mcp.tool()
def fetch_container_logs(container_id: str, description="取得特定container的最後兩百行日誌") -> str:
    """透過 HTTP API 直接抓取容器最後 200 行日誌"""
    # 建議補上版本號 v1.43
    url = f"{PROXY_URL}/v1.43/containers/{container_id}/logs"
    
    # 修改：必須開啟 stdout 或 stderr 至少其中之一
    params = {
        "stdout": True,
        "stderr": True,
        "tail": 200,
        "follow": False # 確保不會進入長連接導致超時
    }
    
    try:
        response = requests.get(
        url, 
        params=params, 
        proxies={"http": None, "https": None}, 
        timeout=10)
        if response.status_code == 200:
            return response.content.decode('utf-8', errors='replace')
        else:
            return f"錯誤：無法取得日誌 (狀態碼: {response.status_code}, 內容: {response.text})"
    except requests.exceptions.RequestException as e:
        return f"連線異常: {str(e)}"
        
if __name__ == "__main__":
    mcp.run(transport="http", port=8003, host = "0.0.0.0")