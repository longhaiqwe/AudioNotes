import os
import uuid
from typing import Union, Dict, Any
from loguru import logger
import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.data.storage_clients.base import BaseStorageClient
import psycopg2
from psycopg2 import sql

from app.utils import utils

db_name = os.getenv("POSTGRES_DB", "audio_notes")
db_user = os.getenv("POSTGRES_USER", "username")
db_password = os.getenv("POSTGRES_PASSWORD", "password")
db_host = os.getenv("POSTGRES_HOST", "localhost")
db_port = os.getenv("POSTGRES_PORT", "5432")


class LocalStorageClient(BaseStorageClient):
    """将上传文件保存到本地磁盘的存储客户端。"""

    def __init__(self):
        logger.info("LocalStorageClient initialized")

    async def upload_file(
        self,
        object_key: str,
        data: Union[bytes, str],
        mime: str = "application/octet-stream",
        overwrite: bool = True,
        content_disposition: str | None = None,
    ) -> Dict[str, Any]:
        try:
            filename = str(uuid.uuid4())
            extname = os.path.splitext(object_key)[1].lower()
            new_key = filename + extname
            file_path = os.path.join(utils.upload_dir(), new_key)
            with open(file_path, "wb") as f:
                f.write(data if isinstance(data, bytes) else data.encode())
            return {"object_key": new_key, "url": f"/uploads/{new_key}"}
        except Exception as e:
            logger.warning(f"LocalStorageClient.upload_file error: {e}")
            return {}

    async def delete_file(self, object_key: str) -> bool:
        try:
            file_path = os.path.join(utils.upload_dir(), object_key)
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            logger.warning(f"LocalStorageClient.delete_file error: {e}")
            return False

    async def get_read_url(self, object_key: str) -> str:
        return f"/uploads/{object_key}"

    async def close(self) -> None:
        pass


def get_connection_url(driver: str = "asyncpg"):
    return f"postgresql+{driver}://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


# 如果数据库不存在，会自动创建
def __init_db():
    conn = psycopg2.connect(dbname='postgres', user=db_user, password=db_password, host=db_host, port=db_port)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    if not exists:
        conn = psycopg2.connect(dbname='postgres', user=db_user, password=db_password, host=db_host, port=db_port)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        cur.close()
        conn.close()

def __migrate_tables():
    sql = '''
ALTER TABLE steps ADD COLUMN IF NOT EXISTS "command" TEXT;
ALTER TABLE steps ADD COLUMN IF NOT EXISTS "modes" JSONB;
ALTER TABLE steps ADD COLUMN IF NOT EXISTS "defaultOpen" BOOLEAN;
ALTER TABLE steps ADD COLUMN IF NOT EXISTS "autoCollapse" BOOLEAN;
ALTER TABLE steps ADD COLUMN IF NOT EXISTS "icon" TEXT;
ALTER TABLE steps ALTER COLUMN "disableFeedback" SET DEFAULT FALSE;
ALTER TABLE steps ALTER COLUMN "streaming" SET DEFAULT FALSE;

ALTER TABLE elements ADD COLUMN IF NOT EXISTS "props" TEXT;
ALTER TABLE elements ADD COLUMN IF NOT EXISTS "autoPlay" BOOLEAN;
ALTER TABLE elements ADD COLUMN IF NOT EXISTS "playerConfig" JSONB;
    '''
    conn = psycopg2.connect(dbname=db_name, user=db_user, password=db_password, host=db_host, port=db_port)
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()


def __init_tables():
    sql = '''
CREATE TABLE IF NOT EXISTS users (
    "id" UUID PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" JSONB NOT NULL,
    "createdAt" TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    "id" UUID PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" UUID,
    "userIdentifier" TEXT,
    "tags" TEXT[],
    "metadata" JSONB,
    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS steps (
    "id" UUID PRIMARY KEY,
    "name" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "threadId" UUID NOT NULL,
    "parentId" UUID,
    "command" TEXT,
    "modes" JSONB,
    "disableFeedback" BOOLEAN NOT NULL DEFAULT FALSE,
    "streaming" BOOLEAN NOT NULL DEFAULT FALSE,
    "waitForAnswer" BOOLEAN,
    "isError" BOOLEAN,
    "metadata" JSONB,
    "tags" TEXT[],
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" JSONB,
    "showInput" TEXT,
    "defaultOpen" BOOLEAN,
    "autoCollapse" BOOLEAN,
    "language" TEXT,
    "icon" TEXT,
    "indent" INT
);

CREATE TABLE IF NOT EXISTS elements (
    "id" UUID PRIMARY KEY,
    "threadId" UUID,
    "type" TEXT,
    "url" TEXT,
    "chainlitKey" TEXT,
    "name" TEXT NOT NULL,
    "display" TEXT,
    "objectKey" TEXT,
    "size" TEXT,
    "props" TEXT,
    "page" INT,
    "autoPlay" BOOLEAN,
    "playerConfig" JSONB,
    "language" TEXT,
    "forId" UUID,
    "mime" TEXT
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id" UUID PRIMARY KEY,
    "forId" UUID NOT NULL,
    "value" INT NOT NULL,
    "comment" TEXT
);
    '''
    conn = psycopg2.connect(dbname=db_name, user=db_user, password=db_password, host=db_host, port=db_port)
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()


def init():
    __init_db()
    __init_tables()
    __migrate_tables()

    @cl.data_layer
    def _get_data_layer():
        return SQLAlchemyDataLayer(
            conninfo=get_connection_url(),
            storage_provider=LocalStorageClient(),
            show_logger=False,
        )
