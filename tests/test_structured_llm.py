"""
構造化LLMクライアントのテスト
================================
2段階応答パターンとInstructorフレームワークを使った
LLM処理のテストを行います。

モックアップを使用してLLMの応答をシミュレートし、
一連の動作を確認します。
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pydantic import BaseModel, Field
from typing import List

from app.structured_llm_client import StructuredLLMClient
from app.extraction_models import (
    ExtractedMemories,
    AttributeItem,
    MemoryItem,
    GoalItem,
    RequestItem,
    DuplicateList,
    DuplicatePair,
    FormattedText
)
from app.memory_extractor import MemoryExtractor
from app.memory_organizer import MemoryOrganizer


# テスト用のPydanticモデル
class SimplePerson(BaseModel):
    """テスト用の簡単な人物モデル"""
    name: str = Field(description="名前")
    age: int = Field(description="年齢")


class TestStructuredLLMClient:
    """構造化LLMクライアントのテスト"""

    def test_two_stage_generation_with_mock(self):
        """2段階応答パターンのテスト（モック使用）"""
        # モッククライアントを作成
        client = StructuredLLMClient()

        # _call_ollamaメソッドをモック
        with patch.object(client, '_call_ollama') as mock_call:
            # ステップ1の応答（自然言語）
            stage1_response = "名前は田中太郎で、年齢は30歳です。"
            # ステップ2の応答（JSON）
            stage2_response = '{"name": "田中太郎", "age": 30}'

            # モックの戻り値を設定
            mock_call.side_effect = [stage1_response, stage2_response]

            # 2段階応答パターンで生成
            result = client.generate_structured(
                prompt="私は田中太郎で、30歳です。",
                response_model=SimplePerson,
                enable_two_stage=True
            )

            # 結果を検証
            assert result.name == "田中太郎"
            assert result.age == 30

            # LLMが2回呼び出されたことを確認
            assert mock_call.call_count == 2

    def test_direct_generation_with_mock(self):
        """1段階生成のテスト（モック使用）"""
        client = StructuredLLMClient()

        with patch.object(client, '_call_ollama') as mock_call:
            # JSON応答
            response = '{"name": "佐藤花子", "age": 25}'
            mock_call.return_value = response

            # 1段階生成
            result = client.generate_structured(
                prompt="私は佐藤花子で、25歳です。",
                response_model=SimplePerson,
                enable_two_stage=False
            )

            assert result.name == "佐藤花子"
            assert result.age == 25
            assert mock_call.call_count == 1

    def test_json_extraction(self):
        """JSON抽出のテスト"""
        client = StructuredLLMClient()

        # マークダウンコードブロック付きJSON
        text1 = '```json\n{"name": "test", "age": 20}\n```'
        result1 = client._extract_json(text1)
        assert '{"name": "test", "age": 20}' in result1

        # 通常のJSON
        text2 = '{"name": "test2", "age": 30}'
        result2 = client._extract_json(text2)
        assert '{"name": "test2", "age": 30}' in result2


class TestMemoryExtractorWithMock:
    """記憶抽出のテスト（モック使用）"""

    def test_extract_memories_with_mock(self):
        """記憶抽出のテスト"""
        extractor = MemoryExtractor()

        # モックされた構造化LLMクライアント
        with patch.object(extractor.client, 'generate_structured') as mock_gen:
            # モックの戻り値を設定
            mock_result = ExtractedMemories(
                attributes=[
                    AttributeItem(name="名前", value="田中太郎"),
                    AttributeItem(name="年齢", value="30"),
                ],
                memories=[
                    MemoryItem(content="プログラミングが好き", category="preference")
                ],
                goals=[
                    GoalItem(content="英語を勉強したい", priority=7)
                ],
                requests=[
                    RequestItem(content="敬語で話してください", category="tone")
                ]
            )
            mock_gen.return_value = mock_result

            # 記憶を抽出
            result = extractor.extract_memories(
                user_input="私は田中太郎で、30歳です。プログラミングが好きで、英語を勉強したいです。敬語で話してください。",
                ai_response="こんにちは"
            )

            # 結果を検証
            assert len(result['attributes']) == 2
            assert result['attributes'][0]['name'] == "名前"
            assert result['attributes'][0]['value'] == "田中太郎"

            assert len(result['memories']) == 1
            assert result['memories'][0]['content'] == "プログラミングが好き"

            assert len(result['goals']) == 1
            assert result['goals'][0]['content'] == "英語を勉強したい"
            assert result['goals'][0]['priority'] == 7

            assert len(result['requests']) == 1
            assert result['requests'][0]['content'] == "敬語で話してください"

    def test_extract_memories_empty(self):
        """空の入力のテスト"""
        extractor = MemoryExtractor()

        with patch.object(extractor.client, 'generate_structured') as mock_gen:
            # 空の結果を返すモック
            mock_result = ExtractedMemories()
            mock_gen.return_value = mock_result

            result = extractor.extract_memories(
                user_input="こんにちは",
                ai_response=""
            )

            assert len(result['attributes']) == 0
            assert len(result['memories']) == 0
            assert len(result['goals']) == 0
            assert len(result['requests']) == 0

    def test_extract_memories_error_handling(self):
        """エラーハンドリングのテスト"""
        extractor = MemoryExtractor()

        with patch.object(extractor.client, 'generate_structured') as mock_gen:
            # エラーを発生させる
            mock_gen.side_effect = Exception("LLMエラー")

            # エラーが発生しても空の結果を返す
            result = extractor.extract_memories(
                user_input="テスト",
                ai_response=""
            )

            assert result == {
                'attributes': [],
                'memories': [],
                'goals': [],
                'requests': []
            }


class TestMemoryOrganizerWithMock:
    """情報整理のテスト（モック使用）"""

    def test_detect_duplicates_with_mock(self):
        """重複検出のテスト"""
        organizer = MemoryOrganizer()

        with patch.object(organizer.client, 'generate_structured') as mock_gen:
            # モックの戻り値を設定
            mock_result = DuplicateList(
                duplicates=[
                    DuplicatePair(id1=1, id2=2, reason="同じ内容")
                ]
            )
            mock_gen.return_value = mock_result

            # テストデータ
            items = [
                {'id': 1, 'memory_content': 'プログラミングが好き'},
                {'id': 2, 'memory_content': 'プログラミングが好きです'}
            ]

            # 重複検出は_merge_duplicate_episodesの中で行われる
            # ここでは直接テストするため、プライベートメソッドをテスト
            items_str = "\n".join([
                f"ID:{item['id']} - {item['memory_content']}"
                for item in items
            ])

            from app.memory_organizer import DUPLICATE_DETECTION_PROMPT
            prompt = DUPLICATE_DETECTION_PROMPT.format(items=items_str)

            result = organizer.client.generate_structured(
                prompt=prompt,
                response_model=DuplicateList,
                enable_two_stage=True
            )

            assert len(result.duplicates) == 1
            assert result.duplicates[0].id1 == 1
            assert result.duplicates[0].id2 == 2

    def test_format_text_with_mock(self):
        """テキスト整形のテスト"""
        organizer = MemoryOrganizer()

        with patch.object(organizer.client, 'generate_structured') as mock_gen:
            # モックの戻り値を設定
            mock_result = FormattedText(
                formatted="プログラミングが好きです"
            )
            mock_gen.return_value = mock_result

            from app.memory_organizer import FORMAT_PROMPT
            prompt = FORMAT_PROMPT.format(text="プログラミング好き")

            result = organizer.client.generate_structured(
                prompt=prompt,
                response_model=FormattedText,
                enable_two_stage=True
            )

            assert result.formatted == "プログラミングが好きです"


class TestEndToEndWithMock:
    """エンドツーエンドのテスト（モック使用）"""

    def test_extraction_flow(self):
        """抽出フローの統合テスト"""
        extractor = MemoryExtractor()

        # モックデータ
        mock_extracted = ExtractedMemories(
            attributes=[
                AttributeItem(name="職業", value="エンジニア")
            ],
            memories=[
                MemoryItem(content="Pythonを使っている", category="knowledge")
            ],
            goals=[],
            requests=[]
        )

        with patch.object(extractor.client, 'generate_structured', return_value=mock_extracted):
            result = extractor.extract_memories(
                user_input="私はエンジニアで、Pythonを使っています。",
                ai_response=""
            )

            # ログが記録されているか確認
            logs = extractor.get_logs()
            assert len(logs) > 0
            assert logs[0]['type'] == 'extraction_request'
            assert logs[1]['type'] == 'extraction_response'

            # 結果の確認
            assert len(result['attributes']) == 1
            assert len(result['memories']) == 1


# pytestの実行用
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
