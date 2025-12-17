"""
Ollamaクライアント
=================
Ollama LLMとの通信を行うモジュールです。

Ollamaとは:
    ローカルで実行できるLLM（Large Language Model）サーバーです。
    llama3.1:8bなどのモデルをローカルで動作させることができます。

使用方法:
    client = OllamaClient()
    response = client.generate("こんにちは")
"""

import requests
import json
from typing import Optional, List, Dict, Any, Generator
import sys
import os

# 設定ファイルをインポート
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import OLLAMA_BASE_URL, OLLAMA_MODEL


class OllamaClient:
    """
    Ollama APIクライアント

    Ollama REST APIを使用してLLMと通信します。

    Attributes:
        base_url: OllamaサーバーのベースURL
        model: 使用するモデル名
    """

    def __init__(self, base_url: str = None, model: str = None):
        """
        クライアントを初期化

        Args:
            base_url: OllamaサーバーのURL（デフォルト: config.pyの設定値）
            model: モデル名（デフォルト: config.pyの設定値）
        """
        # 設定ファイルの値をデフォルトとして使用
        self.base_url = base_url or OLLAMA_BASE_URL
        self.model = model or OLLAMA_MODEL

        # テストモード用のログ保存リスト
        self.request_log = []
        self.response_log = []

    def generate(self, prompt: str, system_prompt: str = None,
                 context: str = None, history: List[Dict] = None,
                 stream: bool = False, format: str = None) -> str:
        """
        テキストを生成する

        Args:
            prompt: ユーザーの入力テキスト
            system_prompt: システムプロンプト（AIの振る舞いを定義）
            context: MCP経由で取得したユーザーコンテキスト
            history: 会話履歴のリスト
            stream: ストリーミングモードを使用するか
            format: レスポンスのフォーマット（例: 'json'）

        Returns:
            str: LLMからの応答テキスト
        """
        # メッセージを構築
        messages = []

        # システムプロンプトを追加
        if system_prompt:
            messages.append({
                'role': 'system',
                'content': system_prompt
            })

        # コンテキストをシステムプロンプトに追加
        if context:
            context_message = f"以下はユーザーに関する情報です。この情報を参考に応答してください：\n\n{context}"
            messages.append({
                'role': 'system',
                'content': context_message
            })

        # 会話履歴を追加
        if history:
            messages.extend(history)

        # 現在のユーザー入力を追加
        messages.append({
            'role': 'user',
            'content': prompt
        })

        # リクエストデータを構築
        request_data = {
            'model': self.model,
            'messages': messages,
            'stream': stream
        }
        
        # フォーマット指定があれば追加
        if format:
            request_data['format'] = format

        # テストモード用にリクエストを記録
        self.request_log.append({
            'endpoint': '/api/chat',
            'data': request_data
        })

        try:
            # Ollama APIにリクエストを送信
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                timeout=120  # タイムアウト: 2分
            )

            # エラーチェック
            response.raise_for_status()

            # JSONレスポンスを解析
            response_data = response.json()

            # テストモード用にレスポンスを記録
            self.response_log.append(response_data)

            # メッセージ内容を抽出して返す
            return response_data.get('message', {}).get('content', '')

        except requests.exceptions.ConnectionError:
            error_msg = "Ollamaサーバーに接続できません。Ollamaが起動していることを確認してください。"
            self.response_log.append({'error': error_msg})
            return f"エラー: {error_msg}"

        except requests.exceptions.Timeout:
            error_msg = "Ollamaサーバーからの応答がタイムアウトしました。"
            self.response_log.append({'error': error_msg})
            return f"エラー: {error_msg}"

        except Exception as e:
            error_msg = f"エラーが発生しました: {str(e)}"
            self.response_log.append({'error': error_msg})
            return f"エラー: {error_msg}"

    def generate_stream(self, prompt: str, system_prompt: str = None,
                        context: str = None, history: List[Dict] = None
                        ) -> Generator[str, None, None]:
        """
        ストリーミングモードでテキストを生成する

        Args:
            prompt: ユーザーの入力テキスト
            system_prompt: システムプロンプト
            context: ユーザーコンテキスト
            history: 会話履歴

        Yields:
            str: 生成されたテキストの断片
        """
        # メッセージを構築
        messages = []

        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})

        if context:
            context_message = f"以下はユーザーに関する情報です：\n\n{context}"
            messages.append({'role': 'system', 'content': context_message})

        if history:
            messages.extend(history)

        messages.append({'role': 'user', 'content': prompt})

        # リクエストデータ
        request_data = {
            'model': self.model,
            'messages': messages,
            'stream': True
        }

        self.request_log.append({
            'endpoint': '/api/chat',
            'data': request_data,
            'stream': True
        })

        try:
            # ストリーミングリクエスト
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                stream=True,
                timeout=120
            )

            response.raise_for_status()

            # ストリーミングレスポンスを処理
            full_response = ""
            for line in response.iter_lines():
                if line:
                    # JSONを解析
                    data = json.loads(line)
                    # メッセージ内容を取得
                    content = data.get('message', {}).get('content', '')
                    if content:
                        full_response += content
                        yield content

            # テストモード用にレスポンスを記録
            self.response_log.append({'content': full_response})

        except Exception as e:
            error_msg = f"ストリーミングエラー: {str(e)}"
            self.response_log.append({'error': error_msg})
            yield error_msg

    def check_connection(self) -> bool:
        """
        Ollamaサーバーへの接続を確認する

        Returns:
            bool: 接続成功時True
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get_available_models(self) -> List[str]:
        """
        利用可能なモデル一覧を取得する

        Returns:
            List[str]: モデル名のリスト
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        except Exception:
            return []

    def clear_logs(self):
        """
        テストモード用のログをクリアする
        """
        self.request_log = []
        self.response_log = []

    def get_logs(self) -> Dict[str, List]:
        """
        テストモード用のログを取得する

        Returns:
            Dict: リクエストとレスポンスのログ
        """
        return {
            'requests': self.request_log,
            'responses': self.response_log
        }


# デフォルトシステムプロンプト（AI秘書用）
DEFAULT_SYSTEM_PROMPT = """あなたは「AI秘書」です。ユーザーの日常をサポートする親しみやすいアシスタントです。

## 行動指針
1. ユーザー情報（属性、記憶、目標、お願い）を活用してパーソナライズした応答をする
2. 丁寧だが堅すぎない自然な日本語で応答する
3. ユーザーの目標達成をサポートする
4. アシスタントへのお願いに従う

## 重要
あなた自身の発言はユーザーの情報ではありません。ユーザーが明示的に述べた内容のみがユーザー情報です。"""


# グローバルなクライアントインスタンス
_client = None


def get_ollama_client() -> OllamaClient:
    """
    Ollamaクライアントのシングルトンインスタンスを取得

    Returns:
        OllamaClient: クライアントインスタンス
    """
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


# テスト用: 直接実行時の動作確認
if __name__ == '__main__':
    print("=== Ollamaクライアントのテスト ===\n")

    client = OllamaClient()

    # 接続確認
    print("【接続確認】")
    if client.check_connection():
        print("✓ Ollamaサーバーに接続できました")

        # 利用可能なモデル一覧
        print("\n【利用可能なモデル】")
        models = client.get_available_models()
        for model in models:
            print(f"  - {model}")

        # 簡単な生成テスト
        print("\n【生成テスト】")
        response = client.generate(
            "こんにちは、自己紹介をしてください",
            system_prompt=DEFAULT_SYSTEM_PROMPT
        )
        print(f"応答: {response}")
    else:
        print("✗ Ollamaサーバーに接続できません")
        print("  Ollamaを起動してください: ollama serve")
