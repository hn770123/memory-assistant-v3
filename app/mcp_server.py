"""
MCPサーバー
==========
Model Context Protocol（MCP）サーバーの実装です。
LLMからの記憶読み取りリクエストを処理します。

使用方法:
    このファイルを直接実行するとMCPサーバーが起動します:
    $ python -m app.mcp_server

注意:
    このアプリケーションではMCPサーバーを別プロセスとして起動するのではなく、
    Flaskアプリケーション内で直接MCPツールを呼び出す方式を採用しています。
    これにより、シンプルな構成で実装できます。
"""

import sys
import os
import json
from typing import Any

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from mcp_tools.memory_tools import (
    get_user_context,
    get_user_attributes_tool,
    get_user_memories_tool,
    get_user_goals_tool,
    get_assistant_requests_tool,
    format_context_for_llm
)


class MCPToolHandler:
    """
    MCPツールハンドラー

    MCPプロトコルに基づいたツール呼び出しを処理します。
    実際のMCPサーバーを使用する代わりに、このクラスを使って
    ツール呼び出しをシミュレートします。

    使用例:
        handler = MCPToolHandler()
        result = handler.call_tool('get_user_context', {})
    """

    def __init__(self):
        """
        ハンドラーを初期化

        利用可能なツールとその説明を定義します。
        """
        # ツール定義（LLMに渡すスキーマ）
        self.tools = {
            'get_user_context': {
                'description': 'ユーザーの全コンテキスト（属性、記憶、目標、お願い）を一括取得します',
                'parameters': {}
            },
            'get_user_attributes': {
                'description': 'ユーザーの属性（名前、年齢、職業など）を取得します',
                'parameters': {}
            },
            'get_user_memories': {
                'description': 'ユーザーの記憶を取得します',
                'parameters': {
                    'limit': {
                        'type': 'integer',
                        'description': '取得する記憶の最大数（デフォルト: 10）',
                        'default': 10
                    },
                    'category': {
                        'type': 'string',
                        'description': 'カテゴリでフィルタリング（オプション）'
                    }
                }
            },
            'get_user_goals': {
                'description': 'ユーザーの目標を取得します',
                'parameters': {
                    'include_completed': {
                        'type': 'boolean',
                        'description': '完了した目標も含めるか（デフォルト: false）',
                        'default': False
                    }
                }
            },
            'get_assistant_requests': {
                'description': 'アシスタントへのお願いを取得します',
                'parameters': {}
            }
        }

        # ツール実装へのマッピング
        self._tool_implementations = {
            'get_user_context': get_user_context,
            'get_user_attributes': get_user_attributes_tool,
            'get_user_memories': get_user_memories_tool,
            'get_user_goals': get_user_goals_tool,
            'get_assistant_requests': get_assistant_requests_tool
        }

    def get_tools_schema(self) -> list:
        """
        利用可能なツールのスキーマを取得

        Returns:
            list: ツールスキーマのリスト（OpenAI Function Calling形式）
        """
        schema_list = []
        for name, info in self.tools.items():
            schema = {
                'type': 'function',
                'function': {
                    'name': name,
                    'description': info['description'],
                    'parameters': {
                        'type': 'object',
                        'properties': info['parameters'],
                        'required': []  # 全てオプショナル
                    }
                }
            }
            schema_list.append(schema)
        return schema_list

    def call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """
        ツールを呼び出す

        Args:
            tool_name: 呼び出すツール名
            arguments: ツールに渡す引数

        Returns:
            dict: ツールの実行結果
                - success: 成功時True
                - result: 実行結果データ
                - error: エラーメッセージ（失敗時）
        """
        if arguments is None:
            arguments = {}

        # ツールの存在確認
        if tool_name not in self._tool_implementations:
            return {
                'success': False,
                'error': f'不明なツール: {tool_name}',
                'result': None
            }

        try:
            # ツールを実行
            tool_func = self._tool_implementations[tool_name]
            result = tool_func(**arguments)

            return {
                'success': True,
                'result': result,
                'error': None
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'result': None
            }

    def get_formatted_context(self) -> str:
        """
        LLM用にフォーマットされたコンテキストを取得

        Returns:
            str: フォーマット済みコンテキスト文字列
        """
        context = get_user_context()
        return format_context_for_llm(context)


# グローバルなMCPハンドラーインスタンス
mcp_handler = MCPToolHandler()


def get_mcp_handler() -> MCPToolHandler:
    """
    MCPハンドラーのインスタンスを取得

    Returns:
        MCPToolHandler: グローバルMCPハンドラー
    """
    return mcp_handler


# テスト用: 直接実行時の動作確認
if __name__ == '__main__':
    print("=== MCPツールハンドラーのテスト ===\n")

    handler = MCPToolHandler()

    # 利用可能なツール一覧を表示
    print("【利用可能なツール】")
    for name, info in handler.tools.items():
        print(f"  - {name}: {info['description']}")

    print("\n【ツール呼び出しテスト】")

    # get_user_context のテスト
    print("\n--- get_user_context ---")
    result = handler.call_tool('get_user_context')
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # フォーマット済みコンテキストのテスト
    print("\n--- フォーマット済みコンテキスト ---")
    print(handler.get_formatted_context())
