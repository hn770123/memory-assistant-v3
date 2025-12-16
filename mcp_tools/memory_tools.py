"""
MCPメモリツール
==============
MCP経由で記憶を読み取るためのツール定義です。

設計思想:
- コンテキストを最小限にするため、APIは単純に設計
- LLMが正しくパラメータを作成できるよう、明確な名前と説明を使用
- 1つのツールで複数のデータ種類を取得できるよう統合

注意:
- このファイルはMCPサーバーから呼び出されるツール定義です
- 直接実行しないでください
"""

import sys
import os

# 親ディレクトリをパスに追加（database.pyをインポートするため）
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.database import (
    get_all_attributes,
    get_all_memories,
    get_all_goals,
    get_all_requests,
    get_recent_memories
)


def get_user_context() -> dict:
    """
    ユーザーのコンテキスト情報を一括取得する

    この関数は、LLMが応答を生成する際に必要な
    全てのユーザー情報を一度に取得します。

    Returns:
        dict: ユーザーのコンテキスト情報
            - attributes: ユーザーの属性リスト
            - memories: 最近の記憶リスト
            - goals: アクティブな目標リスト
            - requests: アシスタントへのお願いリスト
    """
    return {
        'attributes': get_all_attributes(),
        'memories': get_recent_memories(limit=20),  # 最近の20件に制限
        'goals': get_all_goals(status_filter='active'),
        'requests': get_all_requests(active_only=True)
    }


def get_user_attributes_tool() -> list:
    """
    ユーザーの属性を取得するMCPツール

    Returns:
        list: ユーザー属性のリスト
            各要素は {attribute_name, attribute_value} の形式
    """
    attributes = get_all_attributes()
    # コンテキストを減らすため、必要なフィールドのみ返す
    return [
        {
            'name': attr['attribute_name'],
            'value': attr['attribute_value']
        }
        for attr in attributes
    ]


def get_user_memories_tool(limit: int = 10, category: str = None) -> list:
    """
    ユーザーの記憶を取得するMCPツール

    Args:
        limit: 取得する記憶の最大数（デフォルト: 10）
        category: カテゴリでフィルタリング（オプション）

    Returns:
        list: 記憶のリスト
            各要素は {content, category} の形式
    """
    memories = get_recent_memories(limit=limit)

    # カテゴリでフィルタリング
    if category:
        memories = [m for m in memories if m['memory_category'] == category]

    # コンテキストを減らすため、必要なフィールドのみ返す
    return [
        {
            'content': mem['memory_content'],
            'category': mem['memory_category']
        }
        for mem in memories
    ]


def get_user_goals_tool(include_completed: bool = False) -> list:
    """
    ユーザーの目標を取得するMCPツール

    Args:
        include_completed: 完了した目標も含めるか（デフォルト: False）

    Returns:
        list: 目標のリスト
            各要素は {content, status, priority} の形式
    """
    if include_completed:
        goals = get_all_goals()
    else:
        goals = get_all_goals(status_filter='active')

    # コンテキストを減らすため、必要なフィールドのみ返す
    return [
        {
            'content': goal['goal_content'],
            'status': goal['goal_status'],
            'priority': goal['priority']
        }
        for goal in goals
    ]


def get_assistant_requests_tool() -> list:
    """
    アシスタントへのお願いを取得するMCPツール

    Returns:
        list: お願いのリスト
            各要素は {content, category} の形式
    """
    requests = get_all_requests(active_only=True)

    # コンテキストを減らすため、必要なフィールドのみ返す
    return [
        {
            'content': req['request_content'],
            'category': req['request_category']
        }
        for req in requests
    ]


def format_context_for_llm(context: dict) -> str:
    """
    コンテキストをLLM用の文字列にフォーマットする

    Args:
        context: get_user_context()で取得したコンテキスト

    Returns:
        str: LLMに渡すためのフォーマット済み文字列
    """
    parts = []

    # ユーザー属性
    if context['attributes']:
        parts.append("【ユーザーの属性】")
        for attr in context['attributes']:
            parts.append(f"- {attr['attribute_name']}: {attr['attribute_value']}")
        parts.append("")

    # ユーザーの記憶
    if context['memories']:
        parts.append("【ユーザーの記憶】")
        for mem in context['memories']:
            parts.append(f"- {mem['memory_content']}")
        parts.append("")

    # ユーザーの目標
    if context['goals']:
        parts.append("【ユーザーの目標】")
        for goal in context['goals']:
            priority = goal['priority'] if goal['priority'] is not None else 5
            priority_mark = "★" * (11 - priority)  # 優先度が高いほど★が多い
            parts.append(f"- {goal['goal_content']} {priority_mark}")
        parts.append("")

    # アシスタントへのお願い
    if context['requests']:
        parts.append("【アシスタントへのお願い】")
        for req in context['requests']:
            parts.append(f"- {req['request_content']}")
        parts.append("")

    return "\n".join(parts) if parts else "（保存された情報はありません）"
