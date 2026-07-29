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
    pw=os.getenv("PASSWORD")
    db = os.getenv("INV_DB")
    print(f"資料庫連線參數:{host}:{port} DB:{db}")
    print(f"使用者資訊:{user},{pw}")
    return pymysql.connect(
      host=host,
      port = port,
      user=user,
      password=pw,
      database=db)

@server.tool(name = "get_time", description = "取得現在的時間點")
def get_time():
    """返回目前的 ISO 格式時間。"""
    return {"current_time": datetime.now().isoformat()}

@server.tool(name="query_invoice_results_by_date_range", description="取得對應時間區間發票對帳結果")
def query_invoice_results_by_date_range(start_date: str, end_date: str, result: str = None, invoice_type: str = None):
    """查詢特定月份、發票類型等資料
    start_date: 初始月份
    end_date: 結束月份
    result: 想查詢的對帳結果
    invoice_type: 發票類型
    """
    conn = get_db_connection()
    try:
        # 建議加上 cursorclass，這樣回傳的 rows 才是字典格式，後面的 row[key] 才不會報錯
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. 設定基礎 SQL
            query = """SELECT invoice_number, processed_at, seller_name , invoice_date, `result`, invoice_type FROM n8n_result_with_process_time 
                       WHERE invoice_date >= %s 
                       AND invoice_date <= %s
                       AND is_latest = 1"""
            params = [start_date, end_date]
            # 2. 動態增加 result 過濾條件
            if result is not None and str(result).strip() != "":
                query += " AND result = %s"
                params.append(result)

            if invoice_type is not None and str(invoice_type).strip() != "":
                query += " AND invoice_type = %s"
                params.append(invoice_type)
            print(query, params)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            # 3. 轉換為 DataFrame
            df = pd.DataFrame(rows)
            print(df.head())
            # 4. 日期序列化處理
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].apply(
                        lambda x: x.isoformat() if isinstance(x, (date, datetime)) else x
                    )
           # return {"db_data": df, "counts": len(df)}
            return {"db_data": df.to_dict('records'), "counts": len(df)}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()

@server.tool(name = "get_invoice_results_types", description = "取得發票對帳所有的結果類型")
def get_invoice_results_types():
    """獲取可用的對帳結果類型清單"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT DISTINCT result FROM n8n_result_with_TPE_Time"
            cursor.execute(query)
            rows = cursor.fetchall()
            return rows

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        conn.close()

if __name__ == "__main__":
     server.run(transport="http", port = 8001, host ="0.0.0.0")