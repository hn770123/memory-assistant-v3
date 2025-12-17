"""
Ollamaクライアントテスト
========================
app/ollama_client.py のユニットテストです。

テストカテゴリ:
1. ユニットテスト: Ollamaが動作していなくても実行可能
2. 統合テスト: Ollamaが動作している環境でのみ実行（@requires_ollama）
"""

import pytest
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.conftest import requires_ollama


class TestOllamaClientUnit:
    """Ollamaクライアントのユニットテスト（Ollama不要）"""

    def test_client_initialization_default(self):
        """デフォルト設定でクライアントを初期化できることを確認"""
        from app.ollama_client import OllamaClient
        import config

        client = OllamaClient()

        assert client.base_url == config.OLLAMA_BASE_URL
        assert client.model == config.OLLAMA_MODEL
        assert client.request_log == []
        assert client.response_log == []

    def test_client_initialization_custom(self):
        """カスタム設定でクライアントを初期化できることを確認"""
        from app.ollama_client import OllamaClient

        client = OllamaClient(
            base_url="http://custom:8080",
            model="custom-model"
        )

        assert client.base_url == "http://custom:8080"
        assert client.model == "custom-model"

    def test_clear_logs(self):
        """ログをクリアできることを確認"""
        from app.ollama_client import OllamaClient

        client = OllamaClient()
        client.request_log = [{"test": "data"}]
        client.response_log = [{"test": "data"}]

        client.clear_logs()

        assert client.request_log == []
        assert client.response_log == []

    def test_get_logs(self):
        """ログを取得できることを確認"""
        from app.ollama_client import OllamaClient

        client = OllamaClient()
        client.request_log = [{"request": "test"}]
        client.response_log = [{"response": "test"}]

        logs = client.get_logs()

        assert logs['requests'] == [{"request": "test"}]
        assert logs['responses'] == [{"response": "test"}]

    def test_default_system_prompt_exists(self):
        """デフォルトシステムプロンプトが定義されていることを確認"""
        from app.ollama_client import DEFAULT_SYSTEM_PROMPT

        assert DEFAULT_SYSTEM_PROMPT is not None
        assert len(DEFAULT_SYSTEM_PROMPT) > 0
        assert "AI秘書" in DEFAULT_SYSTEM_PROMPT

    def test_get_ollama_client_singleton(self):
        """get_ollama_clientがシングルトンを返すことを確認"""
        from app.ollama_client import get_ollama_client

        client1 = get_ollama_client()
        client2 = get_ollama_client()

        assert client1 is client2


class TestOllamaClientConnectionError:
    """接続エラー時の動作テスト"""

    def test_generate_connection_error(self):
        """サーバーに接続できない場合のエラーハンドリングを確認"""
        from app.ollama_client import OllamaClient

        # 存在しないサーバーに接続
        client = OllamaClient(base_url="http://localhost:99999")
        response = client.generate("テスト")

        assert "エラー" in response
        assert len(client.response_log) > 0
        assert 'error' in client.response_log[-1]

    def test_check_connection_failure(self):
        """接続確認が失敗することを確認"""
        from app.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:99999")
        result = client.check_connection()

        assert result is False

    def test_get_available_models_failure(self):
        """モデル取得が失敗した場合に空リストを返すことを確認"""
        from app.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:99999")
        models = client.get_available_models()

        assert models == []


@requires_ollama
class TestOllamaClientIntegration:
    """Ollamaクライアントの統合テスト（Ollamaが必要）"""

    def test_check_connection_success(self, ollama_client):
        """Ollamaサーバーへの接続が成功することを確認"""
        result = ollama_client.check_connection()
        assert result is True

    def test_get_available_models_success(self, ollama_client):
        """利用可能なモデルを取得できることを確認"""
        models = ollama_client.get_available_models()

        assert isinstance(models, list)
        # 少なくとも1つのモデルが存在することを確認
        assert len(models) > 0

    def test_generate_simple_response(self, ollama_client):
        """シンプルな応答を生成できることを確認"""
        response = ollama_client.generate("1+1は何ですか？")

        assert response is not None
        assert len(response) > 0
        assert "エラー" not in response

        # ログが記録されていることを確認
        logs = ollama_client.get_logs()
        assert len(logs['requests']) > 0
        assert len(logs['responses']) > 0

    def test_generate_with_system_prompt(self, ollama_client):
        """システムプロンプト付きで応答を生成できることを確認"""
        from app.ollama_client import DEFAULT_SYSTEM_PROMPT

        response = ollama_client.generate(
            "こんにちは",
            system_prompt=DEFAULT_SYSTEM_PROMPT
        )

        assert response is not None
        assert len(response) > 0
        assert "エラー" not in response

    def test_generate_with_context(self, ollama_client):
        """コンテキスト付きで応答を生成できることを確認"""
        context = """
        【ユーザー属性】
        - 名前: テスト太郎
        - 年齢: 30歳
        """

        response = ollama_client.generate(
            "私の名前を教えて",
            context=context
        )

        assert response is not None
        assert len(response) > 0
        assert "エラー" not in response

    def test_generate_with_history(self, ollama_client):
        """会話履歴付きで応答を生成できることを確認"""
        history = [
            {"role": "user", "content": "私の名前は太郎です"},
            {"role": "assistant", "content": "太郎さん、よろしくお願いします。"}
        ]

        response = ollama_client.generate(
            "私の名前を覚えていますか？",
            history=history
        )

        assert response is not None
        assert len(response) > 0
        assert "エラー" not in response

    def test_generate_with_json_format(self, ollama_client):
        """JSON形式で応答を生成できることを確認"""
        response = ollama_client.generate(
            '{"name": "太郎"} というJSONに年齢フィールドを追加して返してください。JSONのみを返してください。',
            format='json'
        )

        assert response is not None
        assert len(response) > 0

    def test_request_log_structure(self, ollama_client):
        """リクエストログの構造が正しいことを確認"""
        ollama_client.generate("テスト")

        logs = ollama_client.get_logs()
        assert len(logs['requests']) > 0

        request = logs['requests'][-1]
        assert 'endpoint' in request
        assert 'data' in request
        assert request['endpoint'] == '/api/chat'
        assert 'model' in request['data']
        assert 'messages' in request['data']

    def test_response_log_structure(self, ollama_client):
        """レスポンスログの構造が正しいことを確認"""
        ollama_client.generate("テスト")

        logs = ollama_client.get_logs()
        assert len(logs['responses']) > 0

        response = logs['responses'][-1]
        # 成功時はmessageキーがあるはず
        assert 'message' in response or 'error' not in response


@requires_ollama
class TestOllamaClientStreaming:
    """ストリーミングモードのテスト（Ollamaが必要）"""

    def test_generate_stream(self, ollama_client):
        """ストリーミングモードで応答を生成できることを確認"""
        chunks = list(ollama_client.generate_stream("こんにちは"))

        assert len(chunks) > 0
        # 全てのチャンクを結合すると応答になる
        full_response = ''.join(chunks)
        assert len(full_response) > 0
        assert "ストリーミングエラー" not in full_response

    def test_generate_stream_logs(self, ollama_client):
        """ストリーミングモードでもログが記録されることを確認"""
        # ストリーミング応答を全て消費
        list(ollama_client.generate_stream("テスト"))

        logs = ollama_client.get_logs()
        assert len(logs['requests']) > 0
        assert logs['requests'][-1].get('stream') is True


@requires_ollama
class TestOllamaClientEndToEnd:
    """エンドツーエンドのテスト（Ollamaが必要）"""

    def test_conversation_flow(self, ollama_client):
        """会話フローが正しく動作することを確認"""
        from app.ollama_client import DEFAULT_SYSTEM_PROMPT

        history = []

        # 最初のメッセージ
        response1 = ollama_client.generate(
            "私は山田花子です。覚えておいてください。",
            system_prompt=DEFAULT_SYSTEM_PROMPT
        )
        assert "エラー" not in response1

        # 履歴を更新
        history.append({"role": "user", "content": "私は山田花子です。覚えておいてください。"})
        history.append({"role": "assistant", "content": response1})

        # 2回目のメッセージ（履歴付き）
        response2 = ollama_client.generate(
            "私の名前は何でしたっけ？",
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            history=history
        )

        assert "エラー" not in response2
        # 名前を覚えていることを期待（厳密なテストではない）
        # LLMの応答は不確定なので、エラーがないことのみ確認

    def test_multiple_requests(self, ollama_client):
        """複数回のリクエストが正しく動作することを確認"""
        for i in range(3):
            response = ollama_client.generate(f"テスト{i}")
            assert "エラー" not in response

        logs = ollama_client.get_logs()
        assert len(logs['requests']) >= 3
        assert len(logs['responses']) >= 3
