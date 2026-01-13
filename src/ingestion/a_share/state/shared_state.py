# -*- coding: utf-8 -*-
"""
共享状态管理
支持 JSON 和 SQLite 两种实现方式
"""

import os
import json
import sqlite3
import multiprocessing
import logging
from typing import Dict, List, Optional
from contextlib import contextmanager

from ..utils.file_utils import load_json, save_json
from ..utils.code_utils import normalize_code

logger = logging.getLogger(__name__)


class SharedState:
    """
    线程安全的共享状态管理器（JSON模式）
    用于多进程环境下的状态共享
    """
    
    def __init__(
        self,
        checkpoint_file: str,
        orgid_cache_file: str,
        code_change_cache_file: str,
        shared_lock=None
    ):
        """
        Args:
            checkpoint_file: checkpoint JSON文件路径
            orgid_cache_file: orgId缓存JSON文件路径
            code_change_cache_file: 代码变更缓存JSON文件路径
            shared_lock: 共享锁（多进程）或None（单进程）
        """
        self.checkpoint_file = checkpoint_file
        self.orgid_cache_file = orgid_cache_file
        self.code_change_cache_file = code_change_cache_file
        # 使用传入的共享锁（多进程）或创建新锁（单进程）
        self.lock = shared_lock if shared_lock is not None else multiprocessing.Lock()

    def load_checkpoint(self) -> Dict[str, bool]:
        """加载checkpoint"""
        with self.lock:
            return load_json(self.checkpoint_file, {})

    def save_checkpoint(self, key: str):
        """保存checkpoint"""
        with self.lock:
            data = load_json(self.checkpoint_file, {})
            data[key] = True
            save_json(self.checkpoint_file, data)

    def load_orgid_cache(self) -> Dict[str, str]:
        """加载orgId缓存"""
        with self.lock:
            return load_json(self.orgid_cache_file, {})

    def save_orgid(self, code: str, orgid: str):
        """保存orgId"""
        with self.lock:
            data = load_json(self.orgid_cache_file, {})
            data[code] = orgid
            save_json(self.orgid_cache_file, data)

    def get_orgid(self, code: str) -> Optional[str]:
        """获取orgId"""
        with self.lock:
            data = load_json(self.orgid_cache_file, {})
            return data.get(code)
    
    def load_code_change_cache(self) -> Dict[str, List[str]]:
        """加载代码变更缓存"""
        with self.lock:
            return load_json(self.code_change_cache_file, {})
    
    def save_code_change(self, orgid: str, codes: List[str]):
        """
        保存代码变更记录（合并已有记录）
        
        Args:
            orgid: 组织ID
            codes: 代码列表
        """
        with self.lock:
            data = load_json(self.code_change_cache_file, {})
            # 合并新旧代码列表
            existing = data.get(orgid, [])
            for code in codes:
                code_norm = normalize_code(code)
                if code_norm not in existing:
                    existing.append(code_norm)
            data[orgid] = existing
            save_json(self.code_change_cache_file, data)


# ==================== SQLite 实现（高性能版本） ====================

class StateDB:
    """
    SQLite-based 状态管理器
    - 自动处理并发访问（无需手动锁）
    - 事务支持（ACID）
    - 索引查询（高性能）
    - 自动从 JSON 迁移
    """

    def __init__(self, db_path: str, json_files: Optional[Dict[str, str]] = None):
        """
        Args:
            db_path: SQLite 数据库文件路径
            json_files: 可选的 JSON 文件映射 {"checkpoint": "path/to/checkpoint.json", ...}
                       用于自动迁移现有数据
        """
        self.db_path = db_path
        self.json_files = json_files or {}
        # 确保数据库文件所在目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()
        self._migrate_from_json()

    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Checkpoint 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checkpoint (
                    key TEXT PRIMARY KEY,
                    completed INTEGER DEFAULT 1,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # OrgID 缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orgid_cache (
                    code TEXT PRIMARY KEY,
                    orgid TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 代码变更缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS code_change_cache (
                    orgid TEXT PRIMARY KEY,
                    codes TEXT NOT NULL,  -- JSON 数组
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoint_key
                ON checkpoint(key)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orgid_code
                ON orgid_cache(code)
            """)

            conn.commit()
            logger.debug(f"SQLite 数据库初始化完成: {self.db_path}")

    @contextmanager
    def _get_conn(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,  # 30秒超时（避免死锁）
            isolation_level="DEFERRED",  # 延迟锁定
            check_same_thread=False  # 允许多线程访问
        )
        # WAL 模式：允许并发读写
        conn.execute("PRAGMA journal_mode=WAL")
        # 启用外键约束
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _migrate_from_json(self):
        """自动从 JSON 文件迁移数据（仅首次）"""
        if not self.json_files:
            return

        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 检查是否已迁移
            cursor.execute("SELECT COUNT(*) FROM checkpoint")
            if cursor.fetchone()[0] > 0:
                logger.debug("数据库已有数据，跳过 JSON 迁移")
                return

            # 迁移 checkpoint
            checkpoint_file = self.json_files.get("checkpoint")
            if checkpoint_file and os.path.exists(checkpoint_file):
                try:
                    with open(checkpoint_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for key, completed in data.items():
                            cursor.execute(
                                "INSERT OR REPLACE INTO checkpoint (key, completed) VALUES (?, ?)",
                                (key, 1 if completed else 0)
                            )
                    logger.info(f"✅ 迁移 checkpoint: {len(data)} 条记录")
                except Exception as e:
                    logger.warning(f"迁移 checkpoint 失败: {e}")

            # 迁移 orgid_cache
            orgid_file = self.json_files.get("orgid_cache")
            if orgid_file and os.path.exists(orgid_file):
                try:
                    with open(orgid_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for code, orgid in data.items():
                            cursor.execute(
                                "INSERT OR REPLACE INTO orgid_cache (code, orgid) VALUES (?, ?)",
                                (code, orgid)
                            )
                    logger.info(f"✅ 迁移 orgid_cache: {len(data)} 条记录")
                except Exception as e:
                    logger.warning(f"迁移 orgid_cache 失败: {e}")

            # 迁移 code_change_cache
            code_change_file = self.json_files.get("code_change_cache")
            if code_change_file and os.path.exists(code_change_file):
                try:
                    with open(code_change_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for orgid, codes in data.items():
                            cursor.execute(
                                "INSERT OR REPLACE INTO code_change_cache (orgid, codes) VALUES (?, ?)",
                                (orgid, json.dumps(codes))
                            )
                    logger.info(f"✅ 迁移 code_change_cache: {len(data)} 条记录")
                except Exception as e:
                    logger.warning(f"迁移 code_change_cache 失败: {e}")

            conn.commit()

    def load_checkpoint(self) -> Dict[str, bool]:
        """加载所有 checkpoint"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, completed FROM checkpoint")
            return {key: bool(completed) for key, completed in cursor.fetchall()}

    def save_checkpoint(self, key: str):
        """标记任务完成"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO checkpoint (key, completed) VALUES (?, 1)",
                (key,)
            )
            conn.commit()

    def load_orgid_cache(self) -> Dict[str, str]:
        """加载所有 orgId 缓存"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code, orgid FROM orgid_cache")
            return {code: orgid for code, orgid in cursor.fetchall()}

    def get_orgid(self, code: str) -> Optional[str]:
        """获取单个 orgId"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT orgid FROM orgid_cache WHERE code = ?", (code,))
            result = cursor.fetchone()
            return result[0] if result else None

    def save_orgid(self, code: str, orgid: str):
        """保存 orgId"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO orgid_cache (code, orgid, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (code, orgid)
            )
            conn.commit()

    def load_code_change_cache(self) -> Dict[str, List[str]]:
        """加载所有代码变更缓存"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT orgid, codes FROM code_change_cache")
            return {orgid: json.loads(codes) for orgid, codes in cursor.fetchall()}

    def save_code_change(self, orgid: str, codes: List[str]):
        """保存代码变更（合并已有记录）"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 获取现有代码
            cursor.execute("SELECT codes FROM code_change_cache WHERE orgid = ?", (orgid,))
            result = cursor.fetchone()
            existing = json.loads(result[0]) if result else []

            # 合并去重
            merged = list(set(existing + codes))

            cursor.execute(
                "INSERT OR REPLACE INTO code_change_cache (orgid, codes, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (orgid, json.dumps(merged))
            )
            conn.commit()


class SharedStateSQLite:
    """
    SharedState 的 SQLite 版本
    接口与原 SharedState 完全兼容，性能更好
    """

    def __init__(self, checkpoint_file: str, orgid_cache_file: str, code_change_cache_file: str, shared_lock=None):
        """
        Args:
            checkpoint_file: JSON checkpoint 文件路径（用于迁移）
            orgid_cache_file: JSON orgid 文件路径（用于迁移）
            code_change_cache_file: JSON code_change 文件路径（用于迁移）
            shared_lock: 忽略（SQLite 不需要手动锁）
        """
        # 将 JSON 文件名转换为 SQLite 数据库名
        base_dir = os.path.dirname(checkpoint_file)
        db_path = os.path.join(base_dir, "cninfo_state.db")

        # 自动迁移 JSON 文件
        json_files = {
            "checkpoint": checkpoint_file,
            "orgid_cache": orgid_cache_file,
            "code_change_cache": code_change_cache_file
        }

        self.db = StateDB(db_path, json_files)
        # shared_lock 参数被忽略（SQLite 不需要）

    def load_checkpoint(self) -> Dict[str, bool]:
        return self.db.load_checkpoint()

    def save_checkpoint(self, key: str):
        self.db.save_checkpoint(key)

    def load_orgid_cache(self) -> Dict[str, str]:
        return self.db.load_orgid_cache()

    def get_orgid(self, code: str) -> Optional[str]:
        return self.db.get_orgid(code)

    def save_orgid(self, code: str, orgid: str):
        self.db.save_orgid(code, orgid)

    def load_code_change_cache(self) -> Dict[str, List[str]]:
        return self.db.load_code_change_cache()

    def save_code_change(self, orgid: str, codes: List[str]):
        self.db.save_code_change(orgid, codes)
