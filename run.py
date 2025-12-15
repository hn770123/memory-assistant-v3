"""
AI秘書 起動スクリプト
====================
アプリケーションを起動するためのエントリーポイントです。

使用方法:
    python run.py

または、直接appモジュールを実行:
    python -m app.main

起動後:
    ブラウザで http://localhost:5000 にアクセスしてください
"""

import sys
import os

# プロジェクトルートをパスに追加
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

# メインアプリケーションをインポートして起動
from app.main import app

if __name__ == '__main__':
    # アプリケーションを起動
    # debug=True: エラー時に詳細情報を表示、ファイル変更時に自動リロード
    # host='0.0.0.0': 全てのネットワークインターフェースでリッスン
    # port=5000: ポート番号
    app.run(debug=True, host='0.0.0.0', port=5000)
