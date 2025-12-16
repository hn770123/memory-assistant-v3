"""
データベース操作モジュール
========================
SQLiteデータベースの作成、接続、CRUD操作を行います。

テーブル構成:
- user_attributes: ユーザーの属性（名前、年齢、職業など）
- user_memories: ユーザーの記憶（日常的な出来事、情報など）
- user_goals: ユーザーの目標（やりたいこと、達成したいことなど）
- assistant_requests: アシスタントへのお願い（話し方、対応方法など）
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

# 設定ファイルからデータベースパスを取得
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """
    データベース接続を取得する関数

    Returns:
        sqlite3.Connection: データベース接続オブジェクト

    Note:
        row_factory を sqlite3.Row に設定することで、
        カラム名でアクセスできるようになります（例: row['name']）
    """
    # データベースファイルに接続（ファイルがなければ自動作成される）
    conn = sqlite3.connect(DATABASE_PATH)
    # 辞書形式でデータを取得できるように設定
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """
    データベースを初期化する関数

    テーブルが存在しない場合に作成します。
    既存のテーブルは上書きしません（IF NOT EXISTS）。
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ===== user_attributes テーブル =====
    # ユーザーの属性（名前、年齢、職業など固定的な情報）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attribute_name TEXT NOT NULL,          -- 属性名（例: "名前", "年齢"）
            attribute_value TEXT NOT NULL,         -- 属性値（例: "田中太郎", "30歳"）
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 作成日時
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 更新日時
            compression_level INTEGER DEFAULT 0    -- 圧縮レベル（0:なし, 1:軽度, 2:中度, 3:強度）
        )
    ''')

    # ===== user_memories テーブル =====
    # ユーザーの記憶（日常的な出来事、好み、経験など）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_content TEXT NOT NULL,          -- 記憶の内容
            memory_category TEXT DEFAULT 'general', -- カテゴリ（general, preference, event等）
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 最終アクセス日時
            access_count INTEGER DEFAULT 0,        -- アクセス回数（重要度の指標）
            compression_level INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1            -- アクティブフラグ（0:削除済み, 1:有効）
        )
    ''')

    # ===== user_goals テーブル =====
    # ユーザーの目標（達成したいこと、やりたいこと）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_content TEXT NOT NULL,            -- 目標の内容
            goal_status TEXT DEFAULT 'active',     -- 状態（active, completed, cancelled）
            priority INTEGER DEFAULT 5,            -- 優先度（1:最高 ～ 10:最低）
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,                -- 完了日時
            compression_level INTEGER DEFAULT 0
        )
    ''')

    # ===== assistant_requests テーブル =====
    # アシスタントへのお願い（話し方、対応方法など）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assistant_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_content TEXT NOT NULL,         -- お願いの内容
            request_category TEXT DEFAULT 'general', -- カテゴリ（tone, behavior, format等）
            is_active INTEGER DEFAULT 1,           -- 有効フラグ
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 変更をコミット（保存）
    conn.commit()
    conn.close()

    print("データベースの初期化が完了しました")


# ==================================================
# ユーザー属性（user_attributes）の操作関数
# ==================================================

def add_attribute(attribute_name: str, attribute_value: str) -> int:
    """
    ユーザー属性を追加する

    Args:
        attribute_name: 属性名（例: "名前"）
        attribute_value: 属性値（例: "田中太郎"）

    Returns:
        int: 追加されたレコードのID
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 同じ属性名が既に存在するかチェック
    cursor.execute(
        'SELECT id FROM user_attributes WHERE attribute_name = ?',
        (attribute_name,)
    )
    existing = cursor.fetchone()

    if existing:
        # 既存の属性を更新
        cursor.execute('''
            UPDATE user_attributes
            SET attribute_value = ?, updated_at = CURRENT_TIMESTAMP
            WHERE attribute_name = ?
        ''', (attribute_value, attribute_name))
        record_id = existing['id']
    else:
        # 新しい属性を挿入
        cursor.execute('''
            INSERT INTO user_attributes (attribute_name, attribute_value)
            VALUES (?, ?)
        ''', (attribute_name, attribute_value))
        record_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return record_id


def get_all_attributes() -> List[Dict[str, Any]]:
    """
    全てのユーザー属性を取得する

    Returns:
        List[Dict]: 属性のリスト
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM user_attributes ORDER BY updated_at DESC')
    rows = cursor.fetchall()

    conn.close()

    # sqlite3.Row を辞書に変換
    return [dict(row) for row in rows]


def update_attribute(attribute_id: int, attribute_value: str) -> bool:
    """
    ユーザー属性を更新する

    Args:
        attribute_id: 更新する属性のID
        attribute_value: 新しい属性値

    Returns:
        bool: 更新成功時True
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE user_attributes
        SET attribute_value = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (attribute_value, attribute_id))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def delete_attribute(attribute_id: int) -> bool:
    """
    ユーザー属性を削除する

    Args:
        attribute_id: 削除する属性のID

    Returns:
        bool: 削除成功時True
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM user_attributes WHERE id = ?', (attribute_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# ==================================================
# ユーザー記憶（user_memories）の操作関数
# ==================================================

def add_memory(memory_content: str, memory_category: str = 'general') -> int:
    """
    ユーザーの記憶を追加する

    Args:
        memory_content: 記憶の内容
        memory_category: カテゴリ（デフォルト: 'general'）

    Returns:
        int: 追加されたレコードのID
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO user_memories (memory_content, memory_category)
        VALUES (?, ?)
    ''', (memory_content, memory_category))

    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_all_memories(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    全ての記憶を取得する

    Args:
        active_only: Trueの場合、有効な記憶のみ取得

    Returns:
        List[Dict]: 記憶のリスト
    """
    conn = get_connection()
    cursor = conn.cursor()

    if active_only:
        cursor.execute('''
            SELECT * FROM user_memories
            WHERE is_active = 1
            ORDER BY updated_at DESC
        ''')
    else:
        cursor.execute('SELECT * FROM user_memories ORDER BY updated_at DESC')

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_recent_memories(limit: int = 10) -> List[Dict[str, Any]]:
    """
    最近の記憶を取得する

    Args:
        limit: 取得する件数

    Returns:
        List[Dict]: 記憶のリスト
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM user_memories
        WHERE is_active = 1
        ORDER BY updated_at DESC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_memory(memory_id: int, memory_content: str) -> bool:
    """
    記憶を更新する

    Args:
        memory_id: 更新する記憶のID
        memory_content: 新しい内容

    Returns:
        bool: 更新成功時True
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE user_memories
        SET memory_content = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (memory_content, memory_id))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def delete_memory(memory_id: int, hard_delete: bool = False) -> bool:
    """
    記憶を削除する

    Args:
        memory_id: 削除する記憶のID
        hard_delete: Trueの場合、物理削除。Falseの場合、論理削除

    Returns:
        bool: 削除成功時True
    """
    conn = get_connection()
    cursor = conn.cursor()

    if hard_delete:
        # 物理削除（完全に削除）
        cursor.execute('DELETE FROM user_memories WHERE id = ?', (memory_id,))
    else:
        # 論理削除（is_activeを0に設定）
        cursor.execute('''
            UPDATE user_memories
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (memory_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def increment_memory_access(memory_id: int):
    """
    記憶のアクセス回数をインクリメントする

    Args:
        memory_id: 記憶のID
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE user_memories
        SET access_count = access_count + 1,
            last_accessed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (memory_id,))

    conn.commit()
    conn.close()


# ==================================================
# ユーザー目標（user_goals）の操作関数
# ==================================================

def add_goal(goal_content: str, priority: int = 5) -> int:
    """
    ユーザーの目標を追加する

    Args:
        goal_content: 目標の内容
        priority: 優先度（1:最高 ～ 10:最低）

    Returns:
        int: 追加されたレコードのID
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO user_goals (goal_content, priority)
        VALUES (?, ?)
    ''', (goal_content, priority))

    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_all_goals(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    全ての目標を取得する

    Args:
        status_filter: 状態フィルタ（'active', 'completed', 'cancelled'）

    Returns:
        List[Dict]: 目標のリスト
    """
    conn = get_connection()
    cursor = conn.cursor()

    if status_filter:
        cursor.execute('''
            SELECT * FROM user_goals
            WHERE goal_status = ?
            ORDER BY priority ASC, updated_at DESC
        ''', (status_filter,))
    else:
        cursor.execute('''
            SELECT * FROM user_goals
            ORDER BY priority ASC, updated_at DESC
        ''')

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_goal(goal_id: int, goal_content: str = None,
                goal_status: str = None, priority: int = None) -> bool:
    """
    目標を更新する

    Args:
        goal_id: 更新する目標のID
        goal_content: 新しい内容（Noneの場合は更新しない）
        goal_status: 新しい状態（Noneの場合は更新しない）
        priority: 新しい優先度（Noneの場合は更新しない）

    Returns:
        bool: 更新成功時True
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 更新するフィールドを動的に構築
    updates = []
    values = []

    if goal_content is not None:
        updates.append('goal_content = ?')
        values.append(goal_content)

    if goal_status is not None:
        updates.append('goal_status = ?')
        values.append(goal_status)
        # 完了状態の場合、完了日時を設定
        if goal_status == 'completed':
            updates.append('completed_at = CURRENT_TIMESTAMP')

    if priority is not None:
        updates.append('priority = ?')
        values.append(priority)

    # 更新日時は常に更新
    updates.append('updated_at = CURRENT_TIMESTAMP')

    # 値にIDを追加
    values.append(goal_id)

    # SQL実行
    cursor.execute(f'''
        UPDATE user_goals
        SET {', '.join(updates)}
        WHERE id = ?
    ''', values)

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def delete_goal(goal_id: int) -> bool:
    """
    目標を削除する

    Args:
        goal_id: 削除する目標のID

    Returns:
        bool: 削除成功時True
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM user_goals WHERE id = ?', (goal_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# ==================================================
# アシスタントへのお願い（assistant_requests）の操作関数
# ==================================================

def add_request(request_content: str, request_category: str = 'general') -> int:
    """
    アシスタントへのお願いを追加する

    Args:
        request_content: お願いの内容
        request_category: カテゴリ（デフォルト: 'general'）

    Returns:
        int: 追加されたレコードのID
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO assistant_requests (request_content, request_category)
        VALUES (?, ?)
    ''', (request_content, request_category))

    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_all_requests(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    全てのお願いを取得する

    Args:
        active_only: Trueの場合、有効なお願いのみ取得

    Returns:
        List[Dict]: お願いのリスト
    """
    conn = get_connection()
    cursor = conn.cursor()

    if active_only:
        cursor.execute('''
            SELECT * FROM assistant_requests
            WHERE is_active = 1
            ORDER BY updated_at DESC
        ''')
    else:
        cursor.execute('SELECT * FROM assistant_requests ORDER BY updated_at DESC')

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_request(request_id: int, request_content: str) -> bool:
    """
    お願いを更新する

    Args:
        request_id: 更新するお願いのID
        request_content: 新しい内容

    Returns:
        bool: 更新成功時True
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE assistant_requests
        SET request_content = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (request_content, request_id))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def delete_request(request_id: int) -> bool:
    """
    お願いを削除する（論理削除）

    Args:
        request_id: 削除するお願いのID

    Returns:
        bool: 削除成功時True
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM assistant_requests WHERE id = ?', (request_id,))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# ==================================================
# 圧縮レベル更新関数
# ==================================================

def update_compression_level(table_name: str, record_id: int,
                             compression_level: int) -> bool:
    """
    レコードの圧縮レベルを更新する

    Args:
        table_name: テーブル名
        record_id: レコードID
        compression_level: 新しい圧縮レベル

    Returns:
        bool: 更新成功時True
    """
    # SQLインジェクション対策: テーブル名をホワイトリストでチェック
    allowed_tables = ['user_attributes', 'user_memories', 'user_goals']
    if table_name not in allowed_tables:
        raise ValueError(f"不正なテーブル名: {table_name}")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f'''
        UPDATE {table_name}
        SET compression_level = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (compression_level, record_id))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# スクリプトとして実行された場合、データベースを初期化
if __name__ == '__main__':
    init_database()
