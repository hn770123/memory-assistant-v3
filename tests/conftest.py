"""
Pytest設定ファイル
==================
テスト用のフィクスチャと設定を定義します。
"""

import pytest
import sqlite3
import tempfile
import os
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config


@pytest.fixture
def test_db_path():
    """
    テスト用の一時データベースパスを提供するフィクスチャ

    テスト終了後に自動的にファイルを削除します。
    """
    # 一時ファイルを作成
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    yield path

    # テスト後にファイルを削除
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def test_db(test_db_path, monkeypatch):
    """
    テスト用データベースをセットアップするフィクスチャ

    config.DATABASE_PATHをテスト用のパスに置き換えます。
    """
    # DATABASE_PATHをテスト用に置き換え
    monkeypatch.setattr(config, 'DATABASE_PATH', test_db_path)

    # appモジュールを再インポートする必要があるため、キャッシュをクリア
    for module_name in list(sys.modules.keys()):
        if module_name.startswith('app.'):
            del sys.modules[module_name]

    # データベースモジュールをインポートして初期化
    from app import database

    # database.pyでインポートされたDATABASE_PATHもパッチ
    monkeypatch.setattr(database, 'DATABASE_PATH', test_db_path)

    database.init_database()

    yield test_db_path

    # テスト後のクリーンアップ
    for module_name in list(sys.modules.keys()):
        if module_name.startswith('app.'):
            del sys.modules[module_name]


@pytest.fixture
def ollama_client():
    """
    テスト用のOllamaClientインスタンスを提供するフィクスチャ
    """
    from app.ollama_client import OllamaClient
    client = OllamaClient()
    client.clear_logs()
    return client


def is_ollama_available():
    """
    Ollamaサーバーが利用可能かチェックする
    """
    try:
        import requests
        response = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


# Ollamaが利用可能かどうかを示すマーカー
requires_ollama = pytest.mark.skipif(
    not is_ollama_available(),
    reason="Ollamaサーバーが利用できません"
)
