"""
記憶抽出用のPydanticモデル
==========================
Instructorフレームワークで使用する構造化データモデル
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class AttributeItem(BaseModel):
    """属性アイテム"""
    name: str = Field(description="属性名（例: 名前、年齢、職業、住所、趣味など）")
    value: str = Field(description="属性値")


class MemoryItem(BaseModel):
    """記憶アイテム"""
    content: str = Field(description="記憶の内容")
    category: str = Field(
        description="記憶のカテゴリ（general/preference/event/knowledge）",
        default="general"
    )


class GoalItem(BaseModel):
    """目標アイテム"""
    content: str = Field(description="目標の内容")
    priority: int = Field(
        description="優先度（1-10、デフォルト5）",
        default=5,
        ge=1,
        le=10
    )


class RequestItem(BaseModel):
    """お願いアイテム"""
    content: str = Field(description="お願いの内容")
    category: str = Field(
        description="お願いのカテゴリ（tone/behavior/format/general）",
        default="general"
    )


class ExtractedMemories(BaseModel):
    """抽出された記憶情報"""
    attributes: List[AttributeItem] = Field(
        description="ユーザー属性のリスト（名前、年齢、職業、住所、趣味など）",
        default_factory=list
    )
    memories: List[MemoryItem] = Field(
        description="日常の出来事、経験、好み、知識などのリスト",
        default_factory=list
    )
    goals: List[GoalItem] = Field(
        description="やりたいこと、達成したいこと、予定などのリスト",
        default_factory=list
    )
    requests: List[RequestItem] = Field(
        description="アシスタントへのお願い（話し方、振る舞いなど）のリスト",
        default_factory=list
    )


# memory_organizer用のモデル

class DuplicatePair(BaseModel):
    """重複ペア"""
    id1: int = Field(description="1つ目のアイテムのID")
    id2: int = Field(description="2つ目のアイテムのID")
    reason: str = Field(description="重複している理由")


class DuplicateList(BaseModel):
    """重複リスト"""
    duplicates: List[DuplicatePair] = Field(
        description="重複しているアイテムのペアのリスト",
        default_factory=list
    )


class ConflictPair(BaseModel):
    """矛盾ペア"""
    id1: int = Field(description="1つ目のアイテムのID")
    id2: int = Field(description="2つ目のアイテムのID")
    newer_id: int = Field(description="新しい情報（残すべきもの）のID")
    reason: str = Field(description="矛盾している理由")


class ConflictList(BaseModel):
    """矛盾リスト"""
    conflicts: List[ConflictPair] = Field(
        description="矛盾しているアイテムのペアのリスト",
        default_factory=list
    )


class FormattedText(BaseModel):
    """整形されたテキスト"""
    formatted: str = Field(description="整形されたテキスト")


class MergedContent(BaseModel):
    """統合されたコンテンツ"""
    merged: str = Field(description="統合されたコンテンツ")


class CompressedContent(BaseModel):
    """圧縮されたコンテンツ"""
    compressed: str = Field(description="圧縮されたコンテンツ")
