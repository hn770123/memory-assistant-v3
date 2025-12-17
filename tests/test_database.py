"""
データベーステスト
==================
app/database.py のユニットテストです。
テスト用の一時データベースを使用して、各機能をテストします。
"""

import pytest
import sqlite3
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestDatabaseInit:
    """データベース初期化のテスト"""

    def test_init_database_creates_tables(self, test_db):
        """init_database が全てのテーブルを作成することを確認"""
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # テーブル一覧を取得
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        # 4つのテーブルが作成されていることを確認
        assert 'user_attributes' in tables
        assert 'user_memories' in tables
        assert 'user_goals' in tables
        assert 'assistant_requests' in tables


class TestUserAttributes:
    """ユーザー属性（user_attributes）テーブルのテスト"""

    def test_add_attribute(self, test_db):
        """属性を追加できることを確認"""
        from app import database

        record_id = database.add_attribute("名前", "テスト太郎")
        assert record_id > 0

    def test_add_attribute_updates_existing(self, test_db):
        """同じ属性名で追加すると更新されることを確認"""
        from app import database

        id1 = database.add_attribute("年齢", "25歳")
        id2 = database.add_attribute("年齢", "26歳")

        # 同じIDが返される
        assert id1 == id2

        # 値が更新されていることを確認
        attributes = database.get_all_attributes()
        age_attr = next(a for a in attributes if a['attribute_name'] == '年齢')
        assert age_attr['attribute_value'] == '26歳'

    def test_get_all_attributes(self, test_db):
        """全ての属性を取得できることを確認"""
        from app import database

        database.add_attribute("名前", "テスト太郎")
        database.add_attribute("年齢", "30歳")
        database.add_attribute("職業", "エンジニア")

        attributes = database.get_all_attributes()
        assert len(attributes) == 3

    def test_update_attribute(self, test_db):
        """属性を更新できることを確認"""
        from app import database

        record_id = database.add_attribute("趣味", "読書")
        result = database.update_attribute(record_id, "ゲーム")

        assert result is True

        attributes = database.get_all_attributes()
        hobby_attr = next(a for a in attributes if a['attribute_name'] == '趣味')
        assert hobby_attr['attribute_value'] == 'ゲーム'

    def test_delete_attribute(self, test_db):
        """属性を削除できることを確認"""
        from app import database

        record_id = database.add_attribute("削除テスト", "値")
        result = database.delete_attribute(record_id)

        assert result is True

        attributes = database.get_all_attributes()
        assert not any(a['attribute_name'] == '削除テスト' for a in attributes)


class TestUserMemories:
    """ユーザー記憶（user_memories）テーブルのテスト"""

    def test_add_memory(self, test_db):
        """記憶を追加できることを確認"""
        from app import database

        record_id = database.add_memory("テスト記憶", "general")
        assert record_id > 0

    def test_add_memory_with_category(self, test_db):
        """カテゴリ付きで記憶を追加できることを確認"""
        from app import database

        record_id = database.add_memory("好きな食べ物はラーメン", "preference")
        memories = database.get_all_memories()

        memory = next(m for m in memories if m['id'] == record_id)
        assert memory['memory_category'] == 'preference'

    def test_get_all_memories_active_only(self, test_db):
        """アクティブな記憶のみを取得できることを確認"""
        from app import database

        id1 = database.add_memory("アクティブ記憶", "general")
        id2 = database.add_memory("削除予定記憶", "general")
        database.delete_memory(id2)  # 論理削除

        memories = database.get_all_memories(active_only=True)
        assert len(memories) == 1
        assert memories[0]['memory_content'] == "アクティブ記憶"

    def test_get_recent_memories(self, test_db):
        """最近の記憶を取得できることを確認"""
        from app import database

        for i in range(15):
            database.add_memory(f"記憶{i}", "general")

        recent = database.get_recent_memories(limit=5)
        assert len(recent) == 5

    def test_update_memory(self, test_db):
        """記憶を更新できることを確認"""
        from app import database

        record_id = database.add_memory("元の記憶", "general")
        result = database.update_memory(record_id, "更新された記憶")

        assert result is True

        memories = database.get_all_memories()
        memory = next(m for m in memories if m['id'] == record_id)
        assert memory['memory_content'] == "更新された記憶"

    def test_delete_memory_logical(self, test_db):
        """記憶を論理削除できることを確認"""
        from app import database

        record_id = database.add_memory("論理削除テスト", "general")
        result = database.delete_memory(record_id, hard_delete=False)

        assert result is True

        # 論理削除されたのでactive_onlyでは取得できない
        active_memories = database.get_all_memories(active_only=True)
        assert not any(m['id'] == record_id for m in active_memories)

        # 全件取得では取得できる
        all_memories = database.get_all_memories(active_only=False)
        assert any(m['id'] == record_id for m in all_memories)

    def test_delete_memory_hard(self, test_db):
        """記憶を物理削除できることを確認"""
        from app import database

        record_id = database.add_memory("物理削除テスト", "general")
        result = database.delete_memory(record_id, hard_delete=True)

        assert result is True

        # 物理削除されたので全件取得でも取得できない
        all_memories = database.get_all_memories(active_only=False)
        assert not any(m['id'] == record_id for m in all_memories)

    def test_increment_memory_access(self, test_db):
        """記憶のアクセス回数をインクリメントできることを確認"""
        from app import database

        record_id = database.add_memory("アクセステスト", "general")

        # 3回アクセス
        for _ in range(3):
            database.increment_memory_access(record_id)

        memories = database.get_all_memories()
        memory = next(m for m in memories if m['id'] == record_id)
        assert memory['access_count'] == 3


class TestUserGoals:
    """ユーザー目標（user_goals）テーブルのテスト"""

    def test_add_goal(self, test_db):
        """目標を追加できることを確認"""
        from app import database

        record_id = database.add_goal("テスト目標", priority=3)
        assert record_id > 0

    def test_get_all_goals(self, test_db):
        """全ての目標を取得できることを確認"""
        from app import database

        database.add_goal("目標1", priority=5)
        database.add_goal("目標2", priority=3)
        database.add_goal("目標3", priority=1)

        goals = database.get_all_goals()
        assert len(goals) == 3

        # 優先度順にソートされていることを確認（低い値が優先）
        assert goals[0]['priority'] <= goals[1]['priority']

    def test_get_all_goals_with_filter(self, test_db):
        """状態フィルタ付きで目標を取得できることを確認"""
        from app import database

        id1 = database.add_goal("進行中目標", priority=5)
        id2 = database.add_goal("完了目標", priority=3)
        database.update_goal(id2, goal_status='completed')

        active_goals = database.get_all_goals(status_filter='active')
        assert len(active_goals) == 1
        assert active_goals[0]['goal_content'] == "進行中目標"

        completed_goals = database.get_all_goals(status_filter='completed')
        assert len(completed_goals) == 1
        assert completed_goals[0]['goal_content'] == "完了目標"

    def test_update_goal(self, test_db):
        """目標を更新できることを確認"""
        from app import database

        record_id = database.add_goal("元の目標", priority=5)
        result = database.update_goal(
            record_id,
            goal_content="更新された目標",
            priority=1
        )

        assert result is True

        goals = database.get_all_goals()
        goal = next(g for g in goals if g['id'] == record_id)
        assert goal['goal_content'] == "更新された目標"
        assert goal['priority'] == 1

    def test_update_goal_status_to_completed(self, test_db):
        """目標を完了状態に更新するとcompleted_atが設定されることを確認"""
        from app import database

        record_id = database.add_goal("完了テスト目標")
        database.update_goal(record_id, goal_status='completed')

        goals = database.get_all_goals(status_filter='completed')
        goal = next(g for g in goals if g['id'] == record_id)

        assert goal['goal_status'] == 'completed'
        assert goal['completed_at'] is not None

    def test_delete_goal(self, test_db):
        """目標を削除できることを確認"""
        from app import database

        record_id = database.add_goal("削除テスト目標")
        result = database.delete_goal(record_id)

        assert result is True

        goals = database.get_all_goals()
        assert not any(g['id'] == record_id for g in goals)


class TestAssistantRequests:
    """アシスタントへのお願い（assistant_requests）テーブルのテスト"""

    def test_add_request(self, test_db):
        """お願いを追加できることを確認"""
        from app import database

        record_id = database.add_request("丁寧に話してください", "tone")
        assert record_id > 0

    def test_get_all_requests(self, test_db):
        """全てのお願いを取得できることを確認"""
        from app import database

        database.add_request("丁寧に話してください", "tone")
        database.add_request("短く答えてください", "format")

        requests = database.get_all_requests()
        assert len(requests) == 2

    def test_get_all_requests_active_only(self, test_db):
        """アクティブなお願いのみを取得できることを確認"""
        from app import database

        id1 = database.add_request("アクティブなお願い", "general")
        id2 = database.add_request("削除予定のお願い", "general")
        database.delete_request(id2)

        requests = database.get_all_requests(active_only=True)
        # delete_requestは物理削除なので1件のみ
        assert len(requests) == 1

    def test_update_request(self, test_db):
        """お願いを更新できることを確認"""
        from app import database

        record_id = database.add_request("元のお願い", "general")
        result = database.update_request(record_id, "更新されたお願い")

        assert result is True

        requests = database.get_all_requests()
        request = next(r for r in requests if r['id'] == record_id)
        assert request['request_content'] == "更新されたお願い"

    def test_delete_request(self, test_db):
        """お願いを削除できることを確認"""
        from app import database

        record_id = database.add_request("削除テストお願い", "general")
        result = database.delete_request(record_id)

        assert result is True

        requests = database.get_all_requests()
        assert not any(r['id'] == record_id for r in requests)


class TestCompressionLevel:
    """圧縮レベル更新のテスト"""

    def test_update_compression_level_for_attribute(self, test_db):
        """属性の圧縮レベルを更新できることを確認"""
        from app import database

        record_id = database.add_attribute("テスト属性", "値")
        result = database.update_compression_level(
            'user_attributes', record_id, 2
        )

        assert result is True

        attributes = database.get_all_attributes()
        attr = next(a for a in attributes if a['id'] == record_id)
        assert attr['compression_level'] == 2

    def test_update_compression_level_for_memory(self, test_db):
        """記憶の圧縮レベルを更新できることを確認"""
        from app import database

        record_id = database.add_memory("テスト記憶", "general")
        result = database.update_compression_level(
            'user_memories', record_id, 3
        )

        assert result is True

        memories = database.get_all_memories()
        memory = next(m for m in memories if m['id'] == record_id)
        assert memory['compression_level'] == 3

    def test_update_compression_level_invalid_table(self, test_db):
        """不正なテーブル名でエラーが発生することを確認"""
        from app import database

        with pytest.raises(ValueError) as exc_info:
            database.update_compression_level('invalid_table', 1, 1)

        assert "不正なテーブル名" in str(exc_info.value)
