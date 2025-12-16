"""
記憶整理・圧縮モジュール
======================
記憶の整理（統合、整形、更新）と圧縮を行います。

人間の記憶システムを参考に:
- 新しい記憶は詳細に保持
- 古い記憶は徐々に圧縮（要約化）
- 同じ内容は統合
- 矛盾する情報は新しい方で更新

処理ステップ:
1. 重複検出: 同じ意味の記憶を検出
2. 統合: 重複する記憶を1つにまとめる
3. 整形: 表現を整える（文法、フォーマット）
4. 矛盾解決: 矛盾する情報を新しい方で更新
5. 圧縮: 古い記憶を要約化

各ステップの進捗はコールバック関数で通知されます。
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional, Any
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.ollama_client import OllamaClient, get_ollama_client
from app.database import (
    get_all_memories,
    get_all_attributes,
    get_all_goals,
    update_memory,
    update_attribute,
    update_goal,
    delete_memory,
    update_compression_level,
    get_connection
)
from config import MEMORY_COMPRESSION_THRESHOLDS


# 重複検出用プロンプト
# 英語プロンプト：性能向上のため英語で指示します
# 日本語訳：
# 以下の記憶リストから、同じ意味や重複している記憶のペアを見つけてください。
# 【記憶リスト】{memories}
# 【出力形式】
# 重複するペアをJSON形式で出力してください。重複がない場合は空の配列を返してください。
DUPLICATE_DETECTION_PROMPT = """Identify pairs of memories that have the same meaning or are duplicates from the list below.

### Memory List
{memories}

### Output Format
Output the duplicate pairs in JSON format. If there are no duplicates, return an empty array.
```json
[
    {{"id1": 1, "id2": 3, "reason": "Both mention exactly the same topic"}},
    {{"id1": 2, "id2": 5, "reason": "Different expression of the same information"}}
]
```
Output **JSON ONLY**. No other text.
"""


# 統合用プロンプト
# 日本語訳：以下の2つの記憶を1つに統合してください。情報が失われないように、両方の重要な情報を含めてください。
MERGE_PROMPT = """Merge the following two memories into one.
Include all important information from both to ensure no information is lost.

### Memory 1
{memory1}

### Memory 2
{memory2}

### Output Format
Output the merged memory in a single Japanese sentence. No JSON.
"""


# 整形用プロンプト
# 日本語訳：以下の記憶の表現を自然な日本語に整えてください。意味は変えずに、読みやすく整形してください。
FORMAT_PROMPT = """Refine the expression of the following memory into natural Japanese.
Make it easier to read without changing the meaning.

### Original Memory
{memory}

### Output Format
Output the refined memory in a single Japanese sentence.
"""


# 圧縮用プロンプト
# 日本語訳：以下の記憶を圧縮してください。重要な情報を保持しながら、より短い表現にしてください。
COMPRESS_PROMPT = """Compress the following memory.
Keep the important information but make the expression shorter.

### Compression Level
{level} (1:Light, 2:Medium, 3:Strong)

### Original Memory
{memory}

### Output Format
Output the compressed memory in Japanese. The higher the compression level, the shorter it should be.
"""


# 矛盾検出用プロンプト
# 日本語訳：以下の属性/目標リストから、矛盾している項目を見つけてください。
CONFLICT_DETECTION_PROMPT = """Identify conflicting items from the following attribute/goal list.

### Item List
{items}

### Output Format
Output the conflicting pairs in JSON format. If there are no conflicts, return an empty array.
```json
[
    {{"id1": 1, "id2": 3, "newer_id": 3, "reason": "Values are contradictory"}}
]
```
In `newer_id`, specify the ID of the newer information (the one that should be kept).
Output **JSON ONLY**. No other text.
"""


class MemoryOrganizer:
    """
    記憶整理クラス

    記憶の整理・圧縮処理を行い、進捗をコールバックで通知します。
    """

    def __init__(self, ollama_client: OllamaClient = None):
        """
        オーガナイザーを初期化

        Args:
            ollama_client: Ollamaクライアント（省略時は自動取得）
        """
        self.client = ollama_client or get_ollama_client()
        # 進捗通知用コールバック
        self.progress_callback: Optional[Callable[[Dict], None]] = None
        # 処理ログ
        self.organization_log = []

    def set_progress_callback(self, callback: Callable[[Dict], None]):
        """
        進捗通知用コールバックを設定

        Args:
            callback: 進捗情報を受け取る関数
                引数は Dict[str, Any] 形式で以下のキーを含む:
                - step: ステップ名
                - status: 'started', 'processing', 'completed'
                - message: 詳細メッセージ
                - data: 追加データ（オプション）
        """
        self.progress_callback = callback

    def _notify_progress(self, step: str, status: str,
                         message: str, data: Any = None):
        """
        進捗を通知する内部メソッド

        Args:
            step: 処理ステップ名
            status: 状態
            message: メッセージ
            data: 追加データ
        """
        progress_info = {
            'step': step,
            'status': status,
            'message': message,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }

        # ログに記録
        self.organization_log.append(progress_info)

        # コールバックがあれば呼び出し
        if self.progress_callback:
            self.progress_callback(progress_info)

    def organize_all(self) -> Dict[str, Any]:
        """
        全ての記憶整理処理を実行

        Returns:
            Dict: 処理結果のサマリー
        """
        self._notify_progress('overall', 'started', '記憶の整理を開始します')

        results = {
            'duplicates_merged': 0,
            'formatted': 0,
            'conflicts_resolved': 0,
            'compressed': 0
        }

        try:
            # ステップ1: 重複検出と統合
            self._notify_progress('duplicate', 'started', '重複記憶の検出を開始')
            merged = self._detect_and_merge_duplicates()
            results['duplicates_merged'] = merged
            self._notify_progress('duplicate', 'completed',
                                  f'{merged}件の重複を統合しました')

            # ステップ2: 整形
            self._notify_progress('format', 'started', '記憶の整形を開始')
            formatted = self._format_memories()
            results['formatted'] = formatted
            self._notify_progress('format', 'completed',
                                  f'{formatted}件の記憶を整形しました')

            # ステップ3: 矛盾解決
            self._notify_progress('conflict', 'started', '矛盾の検出を開始')
            resolved = self._resolve_conflicts()
            results['conflicts_resolved'] = resolved
            self._notify_progress('conflict', 'completed',
                                  f'{resolved}件の矛盾を解決しました')

            # ステップ4: 圧縮
            self._notify_progress('compress', 'started', '古い記憶の圧縮を開始')
            compressed = self._compress_old_memories()
            results['compressed'] = compressed
            self._notify_progress('compress', 'completed',
                                  f'{compressed}件の記憶を圧縮しました')

            self._notify_progress('overall', 'completed',
                                  '記憶の整理が完了しました', results)

        except Exception as e:
            self._notify_progress('overall', 'error',
                                  f'エラーが発生しました: {str(e)}')
            results['error'] = str(e)

        return results

    def _detect_and_merge_duplicates(self) -> int:
        """
        重複する記憶を検出して統合する

        Returns:
            int: 統合された記憶の数
        """
        memories = get_all_memories(active_only=True)

        if len(memories) < 2:
            return 0

        # 記憶リストを文字列に変換
        memory_list_str = "\n".join([
            f"ID:{m['id']} - {m['memory_content']}"
            for m in memories
        ])

        # 重複検出
        prompt = DUPLICATE_DETECTION_PROMPT.format(memories=memory_list_str)
        response = self.client.generate(prompt)

        try:
            # JSONを解析
            duplicates = self._parse_json_response(response)
            if not isinstance(duplicates, list):
                return 0

            merged_count = 0
            processed_ids = set()

            for dup in duplicates:
                id1 = dup.get('id1')
                id2 = dup.get('id2')

                # 既に処理済みならスキップ
                if id1 in processed_ids or id2 in processed_ids:
                    continue

                # 記憶を取得
                mem1 = next((m for m in memories if m['id'] == id1), None)
                mem2 = next((m for m in memories if m['id'] == id2), None)

                if mem1 and mem2:
                    self._notify_progress('duplicate', 'processing',
                                          f'記憶 {id1} と {id2} を統合中...')

                    # 統合
                    merge_prompt = MERGE_PROMPT.format(
                        memory1=mem1['memory_content'],
                        memory2=mem2['memory_content']
                    )
                    merged_content = self.client.generate(merge_prompt).strip()

                    # 新しい内容で更新し、もう一方を削除
                    update_memory(id1, merged_content)
                    delete_memory(id2, hard_delete=False)

                    processed_ids.add(id1)
                    processed_ids.add(id2)
                    merged_count += 1

            return merged_count

        except Exception:
            return 0

    def _format_memories(self) -> int:
        """
        記憶の表現を整形する

        Returns:
            int: 整形された記憶の数
        """
        memories = get_all_memories(active_only=True)
        formatted_count = 0

        for mem in memories[:10]:  # 一度に処理する数を制限
            self._notify_progress('format', 'processing',
                                  f'記憶 {mem["id"]} を整形中...')

            prompt = FORMAT_PROMPT.format(memory=mem['memory_content'])
            formatted = self.client.generate(prompt).strip()

            # 元の内容と異なる場合のみ更新
            if formatted and formatted != mem['memory_content']:
                update_memory(mem['id'], formatted)
                formatted_count += 1

        return formatted_count

    def _resolve_conflicts(self) -> int:
        """
        属性や目標の矛盾を解決する

        Returns:
            int: 解決された矛盾の数
        """
        resolved_count = 0

        # 属性の矛盾を検出
        attributes = get_all_attributes()
        if len(attributes) >= 2:
            resolved_count += self._resolve_item_conflicts(
                attributes, 'attributes', 'attribute_name', 'attribute_value'
            )

        # 目標の矛盾を検出
        goals = get_all_goals()
        if len(goals) >= 2:
            resolved_count += self._resolve_item_conflicts(
                goals, 'goals', 'goal_content', 'goal_status'
            )

        return resolved_count

    def _resolve_item_conflicts(self, items: List[Dict],
                                item_type: str,
                                name_field: str,
                                value_field: str) -> int:
        """
        アイテムの矛盾を解決する内部メソッド

        Args:
            items: アイテムリスト
            item_type: アイテムの種類
            name_field: 名前フィールド名
            value_field: 値フィールド名

        Returns:
            int: 解決された矛盾の数
        """
        # アイテムリストを文字列に変換
        items_str = "\n".join([
            f"ID:{item['id']} - {item.get(name_field, '')}: {item.get(value_field, '')} (更新: {item.get('updated_at', '')})"
            for item in items
        ])

        prompt = CONFLICT_DETECTION_PROMPT.format(items=items_str)
        response = self.client.generate(prompt)

        try:
            conflicts = self._parse_json_response(response)
            if not isinstance(conflicts, list):
                return 0

            resolved_count = 0
            for conflict in conflicts:
                id1 = conflict.get('id1')
                id2 = conflict.get('id2')
                newer_id = conflict.get('newer_id')
                older_id = id1 if newer_id == id2 else id2

                self._notify_progress('conflict', 'processing',
                                      f'{item_type}の矛盾を解決中 (ID:{id1}, {id2})...')

                # 古い方を削除（属性の場合は物理削除、目標の場合は状態変更）
                if item_type == 'attributes':
                    from app.database import delete_attribute
                    delete_attribute(older_id)
                elif item_type == 'goals':
                    update_goal(older_id, goal_status='cancelled')

                resolved_count += 1

            return resolved_count

        except Exception:
            return 0

    def _compress_old_memories(self) -> int:
        """
        古い記憶を圧縮する

        Returns:
            int: 圧縮された記憶の数
        """
        memories = get_all_memories(active_only=True)
        compressed_count = 0
        now = datetime.now()

        for mem in memories:
            # 作成日時から経過日数を計算
            created_at = datetime.fromisoformat(mem['created_at'].replace('Z', '+00:00').replace(' ', 'T'))
            if created_at.tzinfo:
                created_at = created_at.replace(tzinfo=None)
            days_old = (now - created_at).days

            # 現在の圧縮レベル
            current_level = mem.get('compression_level', 0)

            # 経過日数に応じて圧縮レベルを決定
            thresholds = MEMORY_COMPRESSION_THRESHOLDS
            if days_old >= thresholds['ancient'] and current_level < 3:
                target_level = 3
            elif days_old >= thresholds['old'] and current_level < 2:
                target_level = 2
            elif days_old >= thresholds['medium'] and current_level < 1:
                target_level = 1
            else:
                continue  # 圧縮不要

            self._notify_progress('compress', 'processing',
                                  f'記憶 {mem["id"]} を圧縮中 (レベル{target_level})...')

            # 圧縮実行
            prompt = COMPRESS_PROMPT.format(
                level=target_level,
                memory=mem['memory_content']
            )
            compressed = self.client.generate(prompt).strip()

            if compressed and len(compressed) < len(mem['memory_content']):
                update_memory(mem['id'], compressed)
                update_compression_level('user_memories', mem['id'], target_level)
                compressed_count += 1

        return compressed_count

    def _parse_json_response(self, response: str) -> Any:
        """
        LLMの応答からJSONを抽出・解析する

        Args:
            response: LLMの応答テキスト

        Returns:
            Any: 解析されたJSON
        """
        try:
            # マークダウンのコードブロックを削除
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0]
            elif '```' in response:
                response = response.split('```')[1].split('```')[0]

            return json.loads(response.strip())
        except json.JSONDecodeError:
            return []

    def clear_logs(self):
        """
        処理ログをクリアする
        """
        self.organization_log = []

    def get_logs(self) -> List[Dict]:
        """
        処理ログを取得する

        Returns:
            List[Dict]: ログエントリのリスト
        """
        return self.organization_log


# グローバルなオーガナイザーインスタンス
_organizer = None


def get_memory_organizer() -> MemoryOrganizer:
    """
    メモリオーガナイザーのシングルトンインスタンスを取得

    Returns:
        MemoryOrganizer: オーガナイザーインスタンス
    """
    global _organizer
    if _organizer is None:
        _organizer = MemoryOrganizer()
    return _organizer


# テスト用: 直接実行時の動作確認
if __name__ == '__main__':
    print("=== 記憶整理モジュールのテスト ===\n")

    def progress_handler(info: Dict):
        """進捗表示用ハンドラー"""
        print(f"[{info['step']}] {info['status']}: {info['message']}")

    organizer = MemoryOrganizer()
    organizer.set_progress_callback(progress_handler)

    print("記憶整理を実行します...")
    results = organizer.organize_all()

    print("\n【結果サマリー】")
    print(json.dumps(results, ensure_ascii=False, indent=2))
