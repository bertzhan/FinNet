# -*- coding: utf-8 -*-
"""
SQLite-based 状态管理（替代 JSON 文件）
解决多进程文件锁定问题，提升性能
"""

import os
import json
import sqlite3
import logging
from typing import Dict, List, Optional
from contextlib import contextmanager


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
            logging.debug(f"SQLite 数据库初始化完成: {self.db_path}")

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
                logging.debug("数据库已有数据，跳过 JSON 迁移")
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
                    logging.info(f"✅ 迁移 checkpoint: {len(data)} 条记录")
                except Exception as e:
                    logging.warning(f"迁移 checkpoint 失败: {e}")

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
                    logging.info(f"✅ 迁移 orgid_cache: {len(data)} 条记录")
                except Exception as e:
                    logging.warning(f"迁移 orgid_cache 失败: {e}")

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
                    logging.info(f"✅ 迁移 code_change_cache: {len(data)} 条记录")
                except Exception as e:
                    logging.warning(f"迁移 code_change_cache 失败: {e}")

            conn.commit()

    # ==================== Checkpoint 操作 ====================

    def load_checkpoint(self) -> Dict[str, bool]:
        """加载所有 checkpoint"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, completed FROM checkpoint")
            return {key: bool(completed) for key, completed in cursor.fetchall()}

    def is_completed(self, key: str) -> bool:
        """检查任务是否已完成"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT completed FROM checkpoint WHERE key = ?", (key,))
            result = cursor.fetchone()
            return bool(result[0]) if result else False

    def save_checkpoint(self, key: str):
        """标记任务完成"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO checkpoint (key, completed) VALUES (?, 1)",
                (key,)
            )
            conn.commit()

    # ==================== OrgID 缓存操作 ====================

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

    # ==================== 代码变更缓存操作 ====================

    def load_code_change_cache(self) -> Dict[str, List[str]]:
        """加载所有代码变更缓存"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT orgid, codes FROM code_change_cache")
            return {orgid: json.loads(codes) for orgid, codes in cursor.fetchall()}

    def get_code_changes(self, orgid: str) -> List[str]:
        """获取单个 orgId 的代码变更列表"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT codes FROM code_change_cache WHERE orgid = ?", (orgid,))
            result = cursor.fetchone()
            return json.loads(result[0]) if result else []

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

    # ==================== 统计查询 ====================

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM checkpoint WHERE completed = 1")
            completed_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM orgid_cache")
            orgid_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM code_change_cache")
            code_change_count = cursor.fetchone()[0]

            return {
                "completed_tasks": completed_count,
                "cached_orgids": orgid_count,
                "code_changes": code_change_count
            }

    def clear_all(self):
        """清空所有数据（慎用）"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM checkpoint")
            cursor.execute("DELETE FROM orgid_cache")
            cursor.execute("DELETE FROM code_change_cache")
            conn.commit()
            logging.warning("⚠️  所有数据已清空")


# ==================== 兼容层（无需修改主代码） ====================

class SharedStateSQLite:
    """
    SharedState 的 SQLite 版本
    接口与原 SharedState 完全兼容
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


if __name__ == "__main__":
    # 测试代码
    import tempfile

    logging.basicConfig(level=logging.INFO)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = StateDB(db_path)

        # 测试 checkpoint
        print("Testing checkpoint...")
        db.save_checkpoint("000001-2023-Q1")
        db.save_checkpoint("000001-2023-Q2")
        assert db.is_completed("000001-2023-Q1") is True
        assert db.is_completed("000001-2024-Q1") is False
        print("✅ Checkpoint test passed")

        # 测试 orgId
        print("Testing orgId cache...")
        db.save_orgid("000001", "gssz0000001")
        assert db.get_orgid("000001") == "gssz0000001"
        assert db.get_orgid("000002") is None
        print("✅ OrgID cache test passed")

        # 测试代码变更
        print("Testing code change cache...")
        db.save_code_change("gssz0000001", ["000001", "000002"])
        db.save_code_change("gssz0000001", ["000003"])  # 合并
        changes = db.get_code_changes("gssz0000001")
        assert set(changes) == {"000001", "000002", "000003"}
        print("✅ Code change cache test passed")

        # 测试统计
        stats = db.get_stats()
        print(f"Stats: {stats}")
        assert stats["completed_tasks"] == 2
        assert stats["cached_orgids"] == 1

        print("\n🎉 All tests passed!")
