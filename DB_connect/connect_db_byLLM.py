from datetime import date, datetime
from fastmcp import FastMCP
import pandas as pd
import pymysql
import os
import dotenv

server = FastMCP("Invoice_OCR_Project")
dotenv.load_dotenv(dotenv_path=".env", override=True)

def get_db_connection():
    """建立 Doris / MySQL 資料庫連線"""
    host = os.getenv("HOST")
    port = int(os.getenv("PORT"))
    user = os.getenv("USER")
    pw = os.getenv("PASSWORD")
    db = os.getenv("INV_DB")
    print(f"資料庫連線參數:{host}:{port} DB:{db}")
    return pymysql.connect(host=host, port=port, user=user, password=pw, database=db)


@server.tool(name="get_time", description="取得現在的時間點")
def get_time():
    return {"current_time": datetime.now().isoformat()}


@server.tool(
    name="get_db_schema",
    description=(
        "取得資料庫 schema 與欄位說明。"
        "在撰寫 SQL 查詢前請先呼叫此工具，確認可用欄位與值的格式。"
    )
)
def get_db_schema():
    return {
        "table": "table",
        "note": "查詢時務必加上 WHERE is_latest = 1 以只取最新對帳結果",
        "columns": {
            "col1": "發票號碼",
            "col2": "發票日期，格式 YYYY-MM-DD，可用 >= / <= 做區間查詢",
            "col3": "賣方公司名稱，模糊比對用 LIKE '%keyword%'",
            "col4": "對帳結果，常見值: '相符', '不符', '待確認'",
            "col5": "發票類型，例如: '原物料', '消費性'",
            "col6": "OCR 處理時間，格式 DATETIME",
            "col7": "是否為最新版本，查詢時固定加 WHERE is_latest = 1",
        },
        "example_sql": (
            "SELECT col4, col5, COUNT(*) AS cnt "
            "FROM table "
            "WHERE col2 >= '2025-01-01' AND col2 <= '2025-03-31' "
            "AND col7 = 1 "
            "GROUP BY col4, col5"
        )
    }

BLOCKED_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE", "REPLACE"]

@server.tool(
    name="execute_readonly_query",
    description=(
        "執行唯讀 SQL SELECT 查詢並回傳結果。"
        "請先呼叫 get_db_schema 確認欄位後再使用此工具。"
        "只允許 SELECT 語句，禁止任何寫入或結構變更操作。"
    )
)
def execute_readonly_query(sql: str):
    normalized = sql.strip().upper()
    if not normalized.startswith("SELECT"):
        return {"error": "只允許 SELECT 查詢"}
    for keyword in BLOCKED_KEYWORDS:
        if keyword in normalized:
            return {"error": f"不允許包含 {keyword}"}

    print(f"執行 SQL: {sql}")
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            df = pd.DataFrame(rows)
            if df.empty:
                return {"db_data": [], "counts": 0}
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].apply(
                        lambda x: x.isoformat() if isinstance(x, (date, datetime)) else x
                    )
            return {"db_data": df.to_dict('records'), "counts": len(df)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


if __name__ == "__main__":
    server.run(transport="http", port=8002, host="0.0.0.0")
