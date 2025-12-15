"""
設定ファイル
アプリケーション全体で使用する設定値を定義します
"""

import os

# ===== データベース設定 =====
# SQLiteデータベースファイルのパス
# os.path.dirname(__file__): このファイル（config.py）があるディレクトリを取得
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'ai_secretary.db')

# ===== Ollama設定 =====
# OllamaサーバーのURL（ローカルで実行されるLLMサーバー）
OLLAMA_BASE_URL = "http://localhost:11434"
# 使用するモデル名（設計書で指定されたモデル）
OLLAMA_MODEL = "llama3.1:8b"

# ===== セッション設定 =====
# Flaskセッション用の秘密鍵（本番環境では環境変数から取得することを推奨）
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ===== トークン圧縮設定 =====
# 最後の入力からこの時間（秒）が経過すると履歴をリセット
SESSION_TIMEOUT_SECONDS = 300  # 5分 = 300秒

# 履歴リセットのトリガーワード
RESET_TRIGGER_WORDS = ["ありがとう", "ありがとうございます"]

# ===== テストモード設定 =====
# テストモードのデフォルト状態（True: テストモードON）
DEFAULT_TEST_MODE = False

# ===== 記憶の整理設定 =====
# 記憶が古くなるにつれて圧縮する閾値（日数）
MEMORY_COMPRESSION_THRESHOLDS = {
    'recent': 7,      # 7日以内: 圧縮なし
    'medium': 30,     # 30日以内: 中程度の圧縮
    'old': 90,        # 90日以内: 強い圧縮
    'ancient': 365    # 365日以上: 最大圧縮
}
