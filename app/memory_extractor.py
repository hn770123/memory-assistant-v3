"""
記憶抽出・判定モジュール
======================
ユーザーの入力から記憶すべき情報を抽出・判定します。

設計思想:
- ユーザーの発言のみを記憶対象とする（AIの応答は除外）
- LLMを使って自然言語で記憶を抽出・分類
- 重複や矛盾の検出も行う

抽出対象:
1. ユーザー属性（名前、年齢、職業、趣味など）
2. ユーザーの記憶（日常的な出来事、好み、経験など）
3. ユーザーの目標（やりたいこと、達成したいことなど）
4. アシスタントへのお願い（話し方、対応方法など）
"""

import re
import json
from typing import Dict, List, Optional, Any
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.structured_llm_client import StructuredLLMClient, get_structured_llm_client
from app.extraction_models import ExtractedMemories
from app.database import (
    add_attribute,
    add_memory,
    add_goal,
    add_request,
    get_all_attributes,
    get_all_memories,
    get_all_goals
)


# 記憶抽出用のプロンプト（2段階応答パターン用）
EXTRACTION_PROMPT = """あなたは会話から重要な情報を正確に抽出するAIです。
ユーザーの発言から、保存すべき情報を漏れなく、改変せずに抽出してください。

## ルール
1. ユーザーの発言のみを分析する
2. AIの応答は抽出対象外
3. 推測や仮定は含めない
4. 明確に述べられた情報のみ抽出する

## 分析対象の会話
AI応答: {ai_response}
ユーザー入力: {user_input}

## 抽出カテゴリ
- attributes: ユーザー属性（名前、年齢、職業、住所、趣味など）
- memories: 日常の出来事、経験、好み、知識など
- goals: やりたいこと、達成したいこと、予定など
- requests: アシスタントへのお願い（話し方、振る舞いなど）

## カテゴリ値
- memories: "general", "preference", "event", "knowledge"
- requests: "tone", "behavior", "format", "general"
- priority: 1-10の整数（デフォルト5）

## 注意
- 「私は」「僕は」などの一人称に注目する
- AIが生成した表現は除外する
- 不確かな情報は含めない

ユーザーの発言を分析し、抽出すべき情報を特定してください。
"""


class MemoryExtractor:
    """
    記憶抽出クラス

    ユーザーの入力から記憶すべき情報を抽出し、
    データベースに保存します。

    2段階応答パターン:
    1. 自然言語で情報を分析・抽出
    2. 構造化データに変換
    """

    def __init__(self, structured_client: StructuredLLMClient = None):
        """
        エクストラクターを初期化

        Args:
            structured_client: 構造化LLMクライアント（省略時は自動取得）
        """
        self.client = structured_client or get_structured_llm_client()
        # テストモード用のログ
        self.extraction_log = []

    def extract_memories(self, user_input: str,
                         ai_response: str = "") -> Dict[str, List]:
        """
        ユーザー入力から記憶を抽出する（2段階応答パターン）

        Args:
            user_input: ユーザーの入力テキスト
            ai_response: 直前のAIの応答（除外用）

        Returns:
            Dict: 抽出された記憶情報
                - attributes: 属性リスト
                - memories: 記憶リスト
                - goals: 目標リスト
                - requests: お願いリスト
        """
        # プロンプトを構築
        prompt = EXTRACTION_PROMPT.format(
            ai_response=ai_response if ai_response else "（なし）",
            user_input=user_input
        )

        # テストモード用にログを記録
        self.extraction_log.append({
            'type': 'extraction_request',
            'user_input': user_input,
            'ai_response': ai_response,
            'prompt': prompt
        })

        try:
            # 2段階応答パターンで構造化データを抽出
            extracted_obj = self.client.generate_structured(
                prompt=prompt,
                response_model=ExtractedMemories,
                enable_two_stage=True
            )

            # テストモード用にログを記録
            self.extraction_log.append({
                'type': 'extraction_response',
                'structured_data': extracted_obj.model_dump()
            })

            # Pydanticモデルを辞書形式に変換
            return {
                'attributes': [attr.model_dump() for attr in extracted_obj.attributes],
                'memories': [mem.model_dump() for mem in extracted_obj.memories],
                'goals': [goal.model_dump() for goal in extracted_obj.goals],
                'requests': [req.model_dump() for req in extracted_obj.requests]
            }

        except Exception as e:
            # エラー時は空の結果を返す
            self.extraction_log.append({
                'type': 'extraction_error',
                'error': str(e)
            })
            return {
                'attributes': [],
                'memories': [],
                'goals': [],
                'requests': []
            }

    def _parse_json_response(self, response: str) -> Dict[str, List]:
        """
        LLMの応答からJSONを抽出・解析する

        Args:
            response: LLMの応答テキスト

        Returns:
            Dict: 解析されたJSON（または空の辞書）
        """
        try:
            # 正規表現でJSON部分を抽出
            import re
            json_match = re.search(r'(\{[\s\S]*\})', response)
            if json_match:
                response = json_match.group(1)
            
            # JSONを解析
            data = json.loads(response.strip())

            # 期待される構造を保証
            result = {
                'attributes': data.get('attributes', []),
                'memories': data.get('memories', []),
                'goals': data.get('goals', []),
                'requests': data.get('requests', [])
            }

            return result

        except json.JSONDecodeError:
            # JSON解析失敗時は空の結果
            return {
                'attributes': [],
                'memories': [],
                'goals': [],
                'requests': []
            }

    def save_extracted_memories(self, extracted: Dict[str, List]) -> Dict[str, int]:
        """
        抽出された記憶をデータベースに保存する

        Args:
            extracted: extract_memories()の戻り値

        Returns:
            Dict: 各カテゴリの保存件数
        """
        saved_counts = {
            'attributes': 0,
            'memories': 0,
            'goals': 0,
            'requests': 0
        }

        # 属性を保存
        for attr in extracted.get('attributes', []):
            if 'name' in attr and 'value' in attr:
                add_attribute(attr['name'], attr['value'])
                saved_counts['attributes'] += 1

        # 記憶を保存
        for mem in extracted.get('memories', []):
            if 'content' in mem:
                category = mem.get('category', 'general')
                add_memory(mem['content'], category)
                saved_counts['memories'] += 1

        # 目標を保存
        for goal in extracted.get('goals', []):
            if 'content' in goal:
                priority = goal.get('priority', 5)
                add_goal(goal['content'], priority)
                saved_counts['goals'] += 1

        # お願いを保存
        for req in extracted.get('requests', []):
            if 'content' in req:
                category = req.get('category', 'general')
                add_request(req['content'], category)
                saved_counts['requests'] += 1

        # テストモード用にログを記録
        self.extraction_log.append({
            'type': 'save_result',
            'counts': saved_counts
        })

        return saved_counts

    def process_input(self, user_input: str,
                      ai_response: str = "") -> Dict[str, Any]:
        """
        ユーザー入力を処理し、記憶を抽出・保存する

        これは抽出と保存を一括で行う便利メソッドです。

        Args:
            user_input: ユーザーの入力テキスト
            ai_response: 直前のAIの応答

        Returns:
            Dict: 処理結果
                - extracted: 抽出された記憶
                - saved_counts: 保存件数
        """
        # 記憶を抽出
        extracted = self.extract_memories(user_input, ai_response)

        # 抽出された記憶があれば保存
        saved_counts = self.save_extracted_memories(extracted)

        return {
            'extracted': extracted,
            'saved_counts': saved_counts
        }

    def clear_logs(self):
        """
        テストモード用のログをクリアする
        """
        self.extraction_log = []

    def get_logs(self) -> List[Dict]:
        """
        テストモード用のログを取得する

        Returns:
            List[Dict]: ログエントリのリスト
        """
        return list(self.extraction_log)


# グローバルなエクストラクターインスタンス
_extractor = None


def get_memory_extractor() -> MemoryExtractor:
    """
    メモリエクストラクターのシングルトンインスタンスを取得

    Returns:
        MemoryExtractor: エクストラクターインスタンス
    """
    global _extractor
    if _extractor is None:
        _extractor = MemoryExtractor()
    return _extractor


# テスト用: 直接実行時の動作確認
if __name__ == '__main__':
    print("=== 記憶抽出モジュールのテスト ===\n")

    # テストデータ
    test_cases = [
        {
            'ai_response': 'こんにちは！何かお手伝いできることはありますか？',
            'user_input': '私は田中太郎です。30歳で、東京に住んでいます。'
        },
        {
            'ai_response': '趣味は何ですか？',
            'user_input': '読書と映画鑑賞が好きです。特にSF小説が好きです。'
        },
        {
            'ai_response': '他に何かありますか？',
            'user_input': '来月までにTOEIC900点を取りたいです。あと、敬語で話してください。'
        }
    ]

    extractor = MemoryExtractor()

    for i, test in enumerate(test_cases, 1):
        print(f"\n【テストケース {i}】")
        print(f"AI応答: {test['ai_response']}")
        print(f"ユーザー入力: {test['user_input']}")

        result = extractor.extract_memories(
            test['user_input'],
            test['ai_response']
        )

        print(f"\n抽出結果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
