"""
AI秘書 メインアプリケーション
============================
Flaskを使用したWebチャットアプリケーションです。

機能:
- チャット機能（ユーザーとAIの対話）
- MCP経由での記憶読み取り
- 記憶の自動保存
- トークン圧縮（セッションタイムアウト）
- テストモード
- DB保守画面
- 記憶整理機能
"""

from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
import sys
import os
import json
import threading

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# 設定と各モジュールをインポート
from config import (
    SECRET_KEY,
    SESSION_TIMEOUT_SECONDS,
    RESET_TRIGGER_WORDS,
    DEFAULT_TEST_MODE
)
from app.database import (
    init_database,
    get_all_attributes,
    get_all_memories,
    get_all_goals,
    get_all_requests,
    add_attribute,
    add_memory,
    add_goal,
    add_request,
    update_attribute,
    update_memory,
    update_goal,
    update_request,
    delete_attribute,
    delete_memory,
    delete_goal,
    delete_request
)
from app.ollama_client import (
    OllamaClient,
    get_ollama_client,
    DEFAULT_SYSTEM_PROMPT
)
from app.mcp_server import get_mcp_handler
from app.memory_extractor import get_memory_extractor
from app.memory_organizer import get_memory_organizer


# グローバル変数：記憶処理の状態
is_memory_processing = False


# Flaskアプリケーションを作成
app = Flask(
    __name__,
    template_folder=os.path.join(project_root, 'templates'),
    static_folder=os.path.join(project_root, 'static')
)
app.secret_key = SECRET_KEY

# データベースを初期化
init_database()


# ==================================================
# ヘルパー関数
# ==================================================

def should_reset_history(user_input: str, last_input_time: datetime) -> bool:
    """
    履歴をリセットすべきか判定する

    Args:
        user_input: ユーザーの入力
        last_input_time: 最後の入力時刻

    Returns:
        bool: リセットすべき場合True
    """
    # トリガーワードをチェック
    for trigger in RESET_TRIGGER_WORDS:
        if trigger in user_input:
            return True

    # タイムアウトをチェック
    if last_input_time:
        elapsed = (datetime.now() - last_input_time).total_seconds()
        if elapsed >= SESSION_TIMEOUT_SECONDS:
            return True

    return False


def format_history_for_display(history: list) -> list:
    """
    表示用に履歴をフォーマットする

    Args:
        history: 会話履歴

    Returns:
        list: フォーマットされた履歴
    """
    return [
        {
            'role': 'あなた' if msg['role'] == 'user' else 'アシスタント',
            'content': msg['content']
        }
        for msg in history
    ]


# ==================================================
# メインページ（チャット）
# ==================================================

@app.route('/')
def index():
    """
    メインページ（チャット画面）を表示
    """
    # セッションを初期化
    if 'history' not in session:
        session['history'] = []
    if 'test_mode' not in session:
        session['test_mode'] = DEFAULT_TEST_MODE
    if 'last_input_time' not in session:
        session['last_input_time'] = None

    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    """
    チャットAPIエンドポイント

    ユーザーの入力を受け取り、AIの応答を返します。
    """
    # リクエストデータを取得
    data = request.get_json()
    user_input = data.get('message', '').strip()

    if not user_input:
        return jsonify({'error': 'メッセージが空です'}), 400

    # テストモードのログ
    test_logs = [] if session.get('test_mode') else None

    # セッションから履歴を取得
    history = session.get('history', [])
    last_input_time_str = session.get('last_input_time')
    last_input_time = datetime.fromisoformat(last_input_time_str) if last_input_time_str else None

    # 履歴リセットの判定
    history_reset = False
    if should_reset_history(user_input, last_input_time):
        history = []
        history_reset = True
        if test_logs is not None:
            test_logs.append({
                'type': 'session_reset',
                'reason': 'トリガーワードまたはタイムアウト',
                'timestamp': datetime.now().isoformat()
            })

    # MCPでコンテキストを取得
    mcp_handler = get_mcp_handler()
    context = mcp_handler.get_formatted_context()

    if test_logs is not None:
        test_logs.append({
            'type': 'mcp_context',
            'context': context,
            'timestamp': datetime.now().isoformat()
        })

    # Ollamaクライアントを取得
    ollama_client = get_ollama_client()

    if test_logs is not None:
        ollama_client.clear_logs()

    # AIの応答を生成
    ai_response = ollama_client.generate(
        prompt=user_input,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        context=context,
        history=history
    )

    if test_logs is not None:
        test_logs.append({
            'type': 'ollama_request',
            'logs': ollama_client.get_logs(),
            'timestamp': datetime.now().isoformat()
        })

    # 履歴を更新
    history.append({'role': 'user', 'content': user_input})
    history.append({'role': 'assistant', 'content': ai_response})

    # 最後の入力時刻を更新
    session['last_input_time'] = datetime.now().isoformat()
    session['history'] = history

    # 記憶の抽出・保存を非同期で実行（ユーザーが応答を読む間に）
    def extract_and_save():
        global is_memory_processing
        is_memory_processing = True
        try:
            extractor = get_memory_extractor()
            # 直前のAI応答を取得（history[-2]がユーザー入力前のAI応答）
            prev_ai_response = history[-4]['content'] if len(history) >= 4 else ""
            extractor.process_input(user_input, prev_ai_response)
        finally:
            is_memory_processing = False

    # バックグラウンドで記憶抽出を実行
    threading.Thread(target=extract_and_save).start()

    # レスポンスを構築
    response_data = {
        'response': ai_response,
        'history_reset': history_reset
    }

    if test_logs is not None:
        # 記憶抽出のログも追加
        extractor = get_memory_extractor()
        test_logs.append({
            'type': 'memory_extraction',
            'logs': extractor.get_logs()[-3:] if extractor.get_logs() else [],
            'timestamp': datetime.now().isoformat()
        })
        response_data['test_logs'] = test_logs

    return jsonify(response_data)


@app.route('/history', methods=['GET'])
def get_history():
    """
    現在の会話履歴を取得
    """
    history = session.get('history', [])
    return jsonify({
        'history': format_history_for_display(history)
    })


@app.route('/clear_history', methods=['POST'])
def clear_history():
    """
    会話履歴をクリア
    """
    session['history'] = []
    session['last_input_time'] = None
    return jsonify({'success': True})


# ==================================================
# テストモード
# ==================================================

@app.route('/test_mode', methods=['GET', 'POST'])
def test_mode():
    """
    テストモードの状態を取得/切り替え
    """
    if request.method == 'POST':
        data = request.get_json()
        session['test_mode'] = data.get('enabled', False)
        return jsonify({'test_mode': session['test_mode']})
    else:
        return jsonify({'test_mode': session.get('test_mode', DEFAULT_TEST_MODE)})


# ==================================================
# DB保守画面
# ==================================================

@app.route('/admin')
def admin():
    """
    DB保守画面を表示
    """
    return render_template('admin.html')


@app.route('/api/data/<table_name>', methods=['GET'])
def get_data(table_name):
    """
    テーブルデータを取得

    Args:
        table_name: テーブル名（attributes, memories, goals, requests）
    """
    if table_name == 'attributes':
        data = get_all_attributes()
    elif table_name == 'memories':
        data = get_all_memories(active_only=False)
    elif table_name == 'goals':
        data = get_all_goals()
    elif table_name == 'requests':
        data = get_all_requests(active_only=False)
    else:
        return jsonify({'error': '不正なテーブル名'}), 400

    return jsonify({'data': data})


@app.route('/api/data/<table_name>', methods=['POST'])
def add_data(table_name):
    """
    データを追加

    Args:
        table_name: テーブル名
    """
    data = request.get_json()

    if table_name == 'attributes':
        record_id = add_attribute(data['name'], data['value'])
    elif table_name == 'memories':
        record_id = add_memory(data['content'], data.get('category', 'general'))
    elif table_name == 'goals':
        record_id = add_goal(data['content'], data.get('priority', 5))
    elif table_name == 'requests':
        record_id = add_request(data['content'], data.get('category', 'general'))
    else:
        return jsonify({'error': '不正なテーブル名'}), 400

    return jsonify({'success': True, 'id': record_id})


@app.route('/api/data/<table_name>/<int:record_id>', methods=['PUT'])
def update_data(table_name, record_id):
    """
    データを更新

    Args:
        table_name: テーブル名
        record_id: レコードID
    """
    data = request.get_json()

    if table_name == 'attributes':
        success = update_attribute(record_id, data['value'])
    elif table_name == 'memories':
        success = update_memory(record_id, data['content'])
    elif table_name == 'goals':
        success = update_goal(
            record_id,
            goal_content=data.get('content'),
            goal_status=data.get('status'),
            priority=data.get('priority')
        )
    elif table_name == 'requests':
        success = update_request(record_id, data['content'])
    else:
        return jsonify({'error': '不正なテーブル名'}), 400

    return jsonify({'success': success})


@app.route('/api/data/<table_name>/<int:record_id>', methods=['DELETE'])
def remove_data(table_name, record_id):
    """
    データを削除

    Args:
        table_name: テーブル名
        record_id: レコードID
    """
    if table_name == 'attributes':
        success = delete_attribute(record_id)
    elif table_name == 'memories':
        success = delete_memory(record_id, hard_delete=True)
    elif table_name == 'goals':
        success = delete_goal(record_id)
    elif table_name == 'requests':
        success = delete_request(record_id)
    else:
        return jsonify({'error': '不正なテーブル名'}), 400

    return jsonify({'success': success})


# ==================================================
# 記憶整理機能
# ==================================================

@app.route('/organize', methods=['POST'])
def organize_memories():
    """
    記憶の整理・圧縮を実行
    """
    organizer = get_memory_organizer()
    organizer.clear_logs()

    # 処理を実行
    results = organizer.organize_all()

    return jsonify({
        'results': results,
        'logs': organizer.get_logs()
    })


@app.route('/organize/status', methods=['GET'])
def get_organize_status():
    """
    記憶整理の進捗状況を取得
    """
    organizer = get_memory_organizer()
    return jsonify({
        'logs': organizer.get_logs()
    })


# ==================================================
# システム情報
# ==================================================

@app.route('/api/system/status', methods=['GET'])
def system_status():
    """
    システムの状態を取得
    """
    ollama_client = get_ollama_client()

    return jsonify({
        'ollama_connected': ollama_client.check_connection(),
        'available_models': ollama_client.get_available_models(),
        'test_mode': session.get('test_mode', DEFAULT_TEST_MODE),
        'session_timeout': SESSION_TIMEOUT_SECONDS
    })


@app.route('/api/system/processing_status', methods=['GET'])
def get_processing_status():
    """
    記憶処理の実行状態を取得
    """
    global is_memory_processing
    return jsonify({
        'processing': is_memory_processing
    })


# アプリケーションのエントリーポイント
if __name__ == '__main__':
    print("=" * 50)
    print("AI秘書を起動しています...")
    print("=" * 50)

    # Ollama接続確認
    ollama_client = get_ollama_client()
    if ollama_client.check_connection():
        print("✓ Ollamaサーバーに接続しました")
        models = ollama_client.get_available_models()
        print(f"  利用可能なモデル: {', '.join(models)}")
    else:
        print("✗ Ollamaサーバーに接続できません")
        print("  'ollama serve' を実行してOllamaを起動してください")

    print("")
    print("サーバーを起動します...")
    print("ブラウザで http://localhost:5000 にアクセスしてください")
    print("終了するには Ctrl+C を押してください")
    print("")

    # Flaskサーバーを起動
    app.run(debug=True, host='0.0.0.0', port=5000)
