from fastmcp import FastMCP
import requests
import mysql.connector
import os
import dotenv
from minio import Minio
import datetime

dotenv.load_dotenv(dotenv_path=".env", override=True)

server = FastMCP("cso_eITS")

RAGFLOW_HOST = os.getenv("RAGFLOW_HOST")
RAGFLOW_PORT = os.getenv("RAGFLOW_PORT")
RAGFLOW_API = os.getenv("RAGFLOW_API")
RAGFLOW_DATASET_ID = os.getenv("RAGFLOW_DATASET_ID")

MINIO_URL= os.getenv("MINIO_URL")
MINIO_ACCESS_KEY= os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY= os.getenv("MINIO_SECRET_KEY")

DB_CONFIG = {
    "host": os.getenv("HOST", "localhost"),
    "port": int(os.getenv("PORT", 3306)),
    "user": os.getenv("USER", "root"),
    "password": os.getenv("PASSWORD", ""),
    "database": os.getenv("EITS_DB", "eits"),
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


@server.tool(name="get_time", description="Get the current time in ISO format")
def get_time():
    """Return current time in ISO format."""
    from datetime import datetime
    now = datetime.now()
    return {"current_time": now.isoformat()}



def _ragflow_get_doc_ids(dataset_id: str) -> list[str]:
    RAGFLOW_BASE_URL=f'{RAGFLOW_HOST}:{RAGFLOW_PORT}'
    url = f'{RAGFLOW_BASE_URL}/api/v1/datasets/{dataset_id}/documents?page=1&page_size=100000'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {RAGFLOW_API}'}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []
    result = response.json()
    return [doc['id'] for doc in result['data'].get('docs', [])]

_RAGFLOW_DOC_IDS: list[str] = _ragflow_get_doc_ids(RAGFLOW_DATASET_ID)


def _minio_presigned_url(doc_name: str) -> str:

    client = Minio(MINIO_URL, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY)
    return client.presigned_get_object(
        RAGFLOW_DATASET_ID,
        doc_name,
        expires=datetime.timedelta(minutes=15),
        extra_query_params={
            "response-content-disposition": "inline",
            "response-content-type": "text/plain;charset=utf-8",
        }
    )

@server.tool(
    name="retrieve_from_ragflow",
    description="從 RAGFLOW 知識庫搜尋相關文件片段，並回傳每份來源文件的 MinIO 預覽 URL（15分鐘有效）"
)
def retrieve_from_ragflow(query: str) -> dict:
    """
    Args:
        query: 要查詢的問題或關鍵字
    """
    doc_ids = _RAGFLOW_DOC_IDS
    if not doc_ids:
        return {"error": "無法取得文件清單"}

    RAGFLOW_BASE_URL = f'{RAGFLOW_HOST}:{RAGFLOW_PORT}'
    url = f'{RAGFLOW_BASE_URL}/api/v1/retrieval'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {RAGFLOW_API}'}
    data = {
        "question": query,
        "dataset_ids": [RAGFLOW_DATASET_ID],
        "document_ids": doc_ids,
        "similarity_threshold": 0.2,
        "keyword": True,
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 200:
        return {"error": f"RAGFlow error {response.status_code}: {response.text}"}

    chunks = response.json()['data'].get('chunks', [])

    seen = set()
    doc_urls = []
    for c in chunks:
        did = c["document_id"]
        if did not in seen:
            seen.add(did)
            try:
                doc_urls.append({c['document_keyword']: did, "url": _minio_presigned_url(did)})
            except Exception as e:
                doc_urls.append({"document_id": did, "url": f"MinIO Error: {e}"})

    return {
        "chunk_count": len(chunks),
        "chunks": [{"content": c["content"], "document_id": c["document_id"]} for c in chunks],
        "doc_urls": doc_urls,
    }
    
@server.tool(
    name="find_tickets_by_date",
    description="利用指定年月區間查詢 tickets 摘要，start_month / end_month 格式為 YYYY/MM"
)
def find_tickets_by_date(
    start_month: str,
    end_month: str,
) -> dict:
    """
    Args:
        start_month: 起始年月，格式 YYYY/MM，例如 '2026/01'
        end_month:   結束年月，格式 YYYY/MM，例如 '2026/04'
    """
    sql = """
        SELECT TICKET_NO, SUMMARY_CONTENT
        FROM eITS_DB
        WHERE year_month BETWEEN %s AND %s
        ORDER BY year_month DESC
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (start_month, end_month))
        rows = cursor.fetchall()
        return {
            "count": len(rows),
            "filters": {"start_month": start_month, "end_month": end_month},
            "tickets": rows,
        }
    finally:
        cursor.close()
        conn.close()


@server.tool(
    name="find_tickets_by_ticket_no",
    description="利用指定得tickets號碼查詢原始文件"
)

def find_tickets_by_ticket_no(
    ticket_id: str,
) -> dict:
    """
    Args:
        ticket_id:  Ticket 的唯一識別碼，提供時查單筆或多筆資料
    """
    sql = """
        SELECT SUMMARY_CONTENT
        FROM eITS_DB
        WHERE TICKET_NO = %s
        ORDER BY year_month DESC
    """

    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (ticket_id,))
        rows = cursor.fetchall()
        return {
            "count": len(rows),
            "filters": {
                "ticket_id": ticket_id
            },
            "tickets": rows,
        }
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    server.run(transport="http", port=8003, host = "0.0.0.0")