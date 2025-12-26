"""
構造化LLMクライアント
====================
Instructorフレームワークを使用した2段階応答パターンの実装

2段階応答パターン:
1. 自然言語による思考・推論
2. 構造化データへの変換

これにより、LLMの精度を高めつつ、構造化されたデータを取得できます。
"""

import json
import requests
from typing import TypeVar, Type, Optional, List, Dict, Any
from pydantic import BaseModel
import instructor
import sys
import os

# 設定ファイルをインポート
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import OLLAMA_BASE_URL, OLLAMA_MODEL


T = TypeVar('T', bound=BaseModel)


class StructuredLLMClient:
    """
    構造化LLMクライアント

    Instructorフレームワークを使って、2段階応答パターンで
    LLMから構造化データを取得します。
    """

    def __init__(self, base_url: str = None, model: str = None):
        """
        クライアントを初期化

        Args:
            base_url: OllamaサーバーのURL
            model: モデル名
        """
        self.base_url = base_url or OLLAMA_BASE_URL
        self.model = model or OLLAMA_MODEL

        # テストモード用のログ保存リスト
        self.request_log = []
        self.response_log = []

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        enable_two_stage: bool = True
    ) -> T:
        """
        構造化データを生成する

        Args:
            prompt: ユーザーの入力プロンプト
            response_model: Pydanticモデルクラス
            system_prompt: システムプロンプト
            enable_two_stage: 2段階応答パターンを使用するか

        Returns:
            response_model型のインスタンス
        """
        if enable_two_stage:
            return self._two_stage_generation(prompt, response_model, system_prompt)
        else:
            return self._direct_generation(prompt, response_model, system_prompt)

    def _two_stage_generation(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None
    ) -> T:
        """
        2段階応答パターンで構造化データを生成

        ステップ1: 自然言語で思考・推論
        ステップ2: 構造化データへの変換
        """
        # ステップ1: 自然言語による思考・推論
        stage1_prompt = f"""以下のタスクについて、自然言語で詳しく考えてください。

{prompt}

あなたの思考プロセスを詳しく説明してください。"""

        stage1_response = self._call_ollama(stage1_prompt, system_prompt)

        # ログに記録
        self.request_log.append({
            'stage': 1,
            'prompt': stage1_prompt,
            'system_prompt': system_prompt
        })
        self.response_log.append({
            'stage': 1,
            'response': stage1_response
        })

        # ステップ2: 構造化データへの変換
        stage2_prompt = f"""前のステップでの思考内容:
{stage1_response}

上記の思考内容に基づいて、以下の構造化データ形式で結果を出力してください。

元のタスク:
{prompt}

構造化データのスキーマ:
{response_model.model_json_schema()}

JSON形式で出力してください。"""

        stage2_response = self._call_ollama(stage2_prompt, system_prompt)

        # ログに記録
        self.request_log.append({
            'stage': 2,
            'prompt': stage2_prompt,
            'system_prompt': system_prompt
        })
        self.response_log.append({
            'stage': 2,
            'response': stage2_response
        })

        # JSONをパースして構造化データに変換
        return self._parse_to_model(stage2_response, response_model)

    def _direct_generation(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None
    ) -> T:
        """
        直接的な構造化データ生成（1段階）
        """
        full_prompt = f"""{prompt}

以下の構造化データ形式で結果を出力してください。

構造化データのスキーマ:
{response_model.model_json_schema()}

JSON形式で出力してください。"""

        response = self._call_ollama(full_prompt, system_prompt)

        # ログに記録
        self.request_log.append({
            'stage': 'direct',
            'prompt': full_prompt,
            'system_prompt': system_prompt
        })
        self.response_log.append({
            'stage': 'direct',
            'response': response
        })

        return self._parse_to_model(response, response_model)

    def _call_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Ollama APIを呼び出す

        Args:
            prompt: プロンプト
            system_prompt: システムプロンプト

        Returns:
            LLMからの応答
        """
        messages = []

        if system_prompt:
            messages.append({
                'role': 'system',
                'content': system_prompt
            })

        messages.append({
            'role': 'user',
            'content': prompt
        })

        request_data = {
            'model': self.model,
            'messages': messages,
            'stream': False
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=request_data,
                timeout=120
            )
            response.raise_for_status()
            response_data = response.json()
            return response_data.get('message', {}).get('content', '')
        except Exception as e:
            raise Exception(f"Ollama API呼び出しエラー: {str(e)}")

    def _parse_to_model(self, response: str, model_class: Type[T]) -> T:
        """
        LLMの応答をPydanticモデルに変換

        Args:
            response: LLMの応答
            model_class: Pydanticモデルクラス

        Returns:
            model_classのインスタンス
        """
        # JSONを抽出
        json_str = self._extract_json(response)

        # JSONをパース
        try:
            data = json.loads(json_str)
            return model_class.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            raise ValueError(f"JSONパースエラー: {str(e)}\n応答: {response}")

    def _extract_json(self, text: str) -> str:
        """
        テキストからJSON部分を抽出

        Args:
            text: テキスト

        Returns:
            JSON文字列
        """
        # マークダウンのコードブロックを削除
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0]
        elif '```' in text:
            text = text.split('```')[1].split('```')[0]

        # 正規表現でJSON部分を抽出
        import re
        json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
        if json_match:
            return json_match.group(1)

        return text.strip()

    def check_connection(self) -> bool:
        """
        Ollamaサーバーへの接続を確認
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def clear_logs(self):
        """ログをクリア"""
        self.request_log = []
        self.response_log = []

    def get_logs(self) -> Dict[str, List]:
        """ログを取得"""
        return {
            'requests': self.request_log,
            'responses': self.response_log
        }


# グローバルインスタンス
_structured_client = None


def get_structured_llm_client() -> StructuredLLMClient:
    """
    構造化LLMクライアントのシングルトンインスタンスを取得
    """
    global _structured_client
    if _structured_client is None:
        _structured_client = StructuredLLMClient()
    return _structured_client


# テスト用
if __name__ == '__main__':
    from pydantic import Field

    print("=== 構造化LLMクライアントのテスト ===\n")

    # テスト用のPydanticモデル
    class Person(BaseModel):
        """人物情報"""
        name: str = Field(description="名前")
        age: int = Field(description="年齢")
        occupation: str = Field(description="職業")

    client = StructuredLLMClient()

    if client.check_connection():
        print("✓ Ollamaサーバーに接続できました\n")

        # 2段階応答パターンのテスト
        print("【2段階応答パターンのテスト】")
        prompt = "私は田中太郎です。30歳で、プログラマーをしています。"

        try:
            result = client.generate_structured(
                prompt=f"以下の文から人物情報を抽出してください:\n{prompt}",
                response_model=Person,
                enable_two_stage=True
            )
            print(f"抽出結果: {result.model_dump_json(indent=2, ensure_ascii=False)}")
        except Exception as e:
            print(f"エラー: {e}")
    else:
        print("✗ Ollamaサーバーに接続できません")
