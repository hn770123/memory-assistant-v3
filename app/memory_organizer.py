"""
情報整理モジュール
================
ユーザー情報の整理（統合、整形、矛盾解決）と圧縮を行います。

整理対象:
- 属性（attributes）: 名前、年齢、職業などの基本情報
- エピソード（memories）: 日常の出来事、好み、経験など
- 目標（goals）: やりたいこと、達成したいこと
- お願い（requests）: アシスタントへの要望

処理ステップ（逐次実行）:
1. 属性の整理: 重複・矛盾の検出と解決
2. エピソードの整理: 重複統合、整形、圧縮
3. 目標の整理: 重複・矛盾の検出と解決
4. お願いの整理: 重複統合、整形

各ステップの進捗はコールバック関数でリアルタイムに通知されます。
LLMへの負荷を考慮し、全ての処理は逐次実行されます。
"""

import json
from datetime import datetime
from typing import Dict, List, Callable, Optional, Any
from enum import Enum
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.ollama_client import OllamaClient, get_ollama_client
from app.database import (
    get_all_memories,
    get_all_attributes,
    get_all_goals,
    get_all_requests,
    update_memory,
    update_attribute,
    update_goal,
    update_request,
    delete_memory,
    delete_attribute,
    delete_request,
    update_compression_level,
    get_connection
)
from config import MEMORY_COMPRESSION_THRESHOLDS


class DataType(Enum):
    """整理対象のデータタイプ"""
    ATTRIBUTE = "attribute"      # 属性
    EPISODE = "episode"          # エピソード（旧: 記憶）
    GOAL = "goal"                # 目標
    REQUEST = "request"          # お願い


class OrganizeStep(Enum):
    """整理ステップ"""
    ATTRIBUTE = ("属性", 1)
    EPISODE = ("エピソード", 2)
    GOAL = ("目標", 3)
    REQUEST = ("お願い", 4)

    def __init__(self, label: str, order: int):
        self.label = label
        self.order = order

    @property
    def display(self) -> str:
        return f"ステップ {self.order}/4: {self.label}"


# ==================================================
# LLMプロンプト定義（英語で指示、日本語で出力）
# ==================================================

# 重複検出用プロンプト
DUPLICATE_DETECTION_PROMPT = """Identify pairs of items that have the same meaning or are duplicates from the list below.

### Item List
{items}

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
MERGE_PROMPT = """Merge the following two items into one.
Include all important information from both to ensure no information is lost.

### Item 1
{item1}

### Item 2
{item2}

### Output Format
Output the merged content in a single Japanese sentence. No JSON.
"""

# 整形用プロンプト
FORMAT_PROMPT = """Refine the expression of the following text into natural Japanese.
Make it easier to read without changing the meaning.

### Original Text
{text}

### Output Format
Output the refined text in Japanese. Keep it concise.
"""

# 圧縮用プロンプト
COMPRESS_PROMPT = """Compress the following episode.
Keep the important information but make the expression shorter.

### Compression Level
{level} (1:Light, 2:Medium, 3:Strong)

### Original Episode
{content}

### Output Format
Output the compressed episode in Japanese. The higher the compression level, the shorter it should be.
"""

# 矛盾検出用プロンプト
CONFLICT_DETECTION_PROMPT = """Identify conflicting items from the following list.
Conflicting items have contradictory information about the same topic.

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
    情報整理クラス

    ユーザー情報の整理・圧縮処理を行い、進捗をコールバックで通知します。
    LLMへの負荷を考慮し、全ての処理は逐次実行されます。
    """

    # 処理制限（一度に処理する最大件数）
    MAX_ITEMS_PER_STEP = 20

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
        # 現在のステップ
        self._current_step: Optional[OrganizeStep] = None

    def set_progress_callback(self, callback: Callable[[Dict], None]):
        """
        進捗通知用コールバックを設定

        Args:
            callback: 進捗情報を受け取る関数
                引数は Dict[str, Any] 形式で以下のキーを含む:
                - step: ステップ名（attribute/episode/goal/request/overall）
                - step_display: 表示用ステップ名（例: "ステップ 1/4: 属性"）
                - status: 'started', 'processing', 'completed', 'skipped'
                - message: 詳細メッセージ
                - progress: 進捗情報（current, total）
                - data: 追加データ（オプション）
        """
        self.progress_callback = callback

    def _notify_progress(
        self,
        step: str,
        status: str,
        message: str,
        current: int = 0,
        total: int = 0,
        data: Any = None
    ):
        """
        進捗を通知する内部メソッド

        Args:
            step: 処理ステップ名
            status: 状態（started/processing/completed/skipped/error）
            message: メッセージ
            current: 現在の処理番号
            total: 全体の処理数
            data: 追加データ
        """
        # ステップ表示名を取得
        step_display = ""
        if self._current_step:
            step_display = self._current_step.display

        progress_info = {
            'step': step,
            'step_display': step_display,
            'status': status,
            'message': message,
            'progress': {'current': current, 'total': total} if total > 0 else None,
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
        全ての情報整理処理を実行（逐次処理）

        Returns:
            Dict: 処理結果のサマリー
        """
        self._notify_progress(
            'overall', 'started',
            '📋 情報整理を開始します（属性→エピソード→目標→お願いの順に処理）'
        )

        results = {
            'attributes': {'merged': 0, 'formatted': 0, 'conflicts_resolved': 0},
            'episodes': {'merged': 0, 'formatted': 0, 'compressed': 0},
            'goals': {'merged': 0, 'formatted': 0, 'conflicts_resolved': 0},
            'requests': {'merged': 0, 'formatted': 0}
        }

        try:
            # ステップ1: 属性の整理
            self._current_step = OrganizeStep.ATTRIBUTE
            self._notify_progress(
                'attribute', 'started',
                f'🏷️ {self._current_step.display}の整理を開始'
            )
            results['attributes'] = self._organize_attributes()
            self._notify_progress(
                'attribute', 'completed',
                f'✅ {self._current_step.display}の整理が完了',
                data=results['attributes']
            )

            # ステップ2: エピソードの整理
            self._current_step = OrganizeStep.EPISODE
            self._notify_progress(
                'episode', 'started',
                f'📝 {self._current_step.display}の整理を開始'
            )
            results['episodes'] = self._organize_episodes()
            self._notify_progress(
                'episode', 'completed',
                f'✅ {self._current_step.display}の整理が完了',
                data=results['episodes']
            )

            # ステップ3: 目標の整理
            self._current_step = OrganizeStep.GOAL
            self._notify_progress(
                'goal', 'started',
                f'🎯 {self._current_step.display}の整理を開始'
            )
            results['goals'] = self._organize_goals()
            self._notify_progress(
                'goal', 'completed',
                f'✅ {self._current_step.display}の整理が完了',
                data=results['goals']
            )

            # ステップ4: お願いの整理
            self._current_step = OrganizeStep.REQUEST
            self._notify_progress(
                'request', 'started',
                f'💬 {self._current_step.display}の整理を開始'
            )
            results['requests'] = self._organize_requests()
            self._notify_progress(
                'request', 'completed',
                f'✅ {self._current_step.display}の整理が完了',
                data=results['requests']
            )

            self._current_step = None
            self._notify_progress(
                'overall', 'completed',
                '🎉 全ての情報整理が完了しました',
                data=results
            )

        except Exception as e:
            self._notify_progress(
                'overall', 'error',
                f'❌ エラーが発生しました: {str(e)}'
            )
            results['error'] = str(e)

        return results

    # ==================================================
    # 属性の整理
    # ==================================================

    def _organize_attributes(self) -> Dict[str, int]:
        """
        属性の整理を実行

        Returns:
            Dict: 処理結果
        """
        result = {'merged': 0, 'formatted': 0, 'conflicts_resolved': 0}
        attributes = get_all_attributes()

        if not attributes:
            self._notify_progress(
                'attribute', 'skipped',
                '整理対象の属性がありません'
            )
            return result

        total = len(attributes)
        self._notify_progress(
            'attribute', 'processing',
            f'{total}件の属性を確認中...',
            current=0, total=total
        )

        # 矛盾検出と解決
        if len(attributes) >= 2:
            conflicts = self._detect_conflicts(attributes, 'attribute_name', 'attribute_value')
            result['conflicts_resolved'] = self._resolve_attribute_conflicts(conflicts, attributes)

        # 整形処理
        attributes = get_all_attributes()  # 再取得
        for i, attr in enumerate(attributes[:self.MAX_ITEMS_PER_STEP]):
            self._notify_progress(
                'attribute', 'processing',
                f'属性「{attr["attribute_name"]}」を整形中...',
                current=i + 1, total=min(len(attributes), self.MAX_ITEMS_PER_STEP)
            )
            if self._format_attribute(attr):
                result['formatted'] += 1

        return result

    def _format_attribute(self, attr: Dict) -> bool:
        """属性を整形する"""
        original = f"{attr['attribute_name']}: {attr['attribute_value']}"
        prompt = FORMAT_PROMPT.format(text=original)
        formatted = self.client.generate(prompt).strip()

        # 「名前: 値」形式から値部分を抽出
        if ':' in formatted:
            parts = formatted.split(':', 1)
            if len(parts) == 2:
                formatted_value = parts[1].strip()
            else:
                formatted_value = formatted
        else:
            formatted_value = formatted

        if formatted_value and formatted_value != attr['attribute_value']:
            update_attribute(attr['id'], formatted_value)
            return True
        return False

    def _resolve_attribute_conflicts(
        self,
        conflicts: List[Dict],
        attributes: List[Dict]
    ) -> int:
        """属性の矛盾を解決する"""
        resolved = 0
        processed_ids = set()

        for conflict in conflicts:
            id1, id2 = conflict.get('id1'), conflict.get('id2')
            newer_id = conflict.get('newer_id')

            if id1 in processed_ids or id2 in processed_ids:
                continue

            older_id = id1 if newer_id == id2 else id2
            attr1 = next((a for a in attributes if a['id'] == id1), None)
            attr2 = next((a for a in attributes if a['id'] == id2), None)

            if attr1 and attr2:
                self._notify_progress(
                    'attribute', 'processing',
                    f'属性の矛盾を解決中: 「{attr1["attribute_name"]}」'
                )
                delete_attribute(older_id)
                processed_ids.add(id1)
                processed_ids.add(id2)
                resolved += 1

        return resolved

    # ==================================================
    # エピソード（旧: 記憶）の整理
    # ==================================================

    def _organize_episodes(self) -> Dict[str, int]:
        """
        エピソードの整理を実行

        Returns:
            Dict: 処理結果
        """
        result = {'merged': 0, 'formatted': 0, 'compressed': 0}
        episodes = get_all_memories(active_only=True)

        if not episodes:
            self._notify_progress(
                'episode', 'skipped',
                '整理対象のエピソードがありません'
            )
            return result

        total = len(episodes)
        self._notify_progress(
            'episode', 'processing',
            f'{total}件のエピソードを確認中...',
            current=0, total=total
        )

        # 重複検出と統合
        if len(episodes) >= 2:
            result['merged'] = self._merge_duplicate_episodes(episodes)

        # 整形処理
        episodes = get_all_memories(active_only=True)  # 再取得
        for i, ep in enumerate(episodes[:self.MAX_ITEMS_PER_STEP]):
            self._notify_progress(
                'episode', 'processing',
                f'エピソードを整形中... ({i + 1}/{min(len(episodes), self.MAX_ITEMS_PER_STEP)})',
                current=i + 1, total=min(len(episodes), self.MAX_ITEMS_PER_STEP)
            )
            if self._format_episode(ep):
                result['formatted'] += 1

        # 圧縮処理
        result['compressed'] = self._compress_old_episodes()

        return result

    def _merge_duplicate_episodes(self, episodes: List[Dict]) -> int:
        """重複するエピソードを統合する"""
        # エピソードリストを文字列に変換
        items_str = "\n".join([
            f"ID:{ep['id']} - {ep['memory_content']}"
            for ep in episodes[:self.MAX_ITEMS_PER_STEP]
        ])

        prompt = DUPLICATE_DETECTION_PROMPT.format(items=items_str)
        response = self.client.generate(prompt)

        try:
            duplicates = self._parse_json_response(response)
            if not isinstance(duplicates, list):
                return 0

            merged_count = 0
            processed_ids = set()

            for dup in duplicates:
                id1, id2 = dup.get('id1'), dup.get('id2')

                if id1 in processed_ids or id2 in processed_ids:
                    continue

                ep1 = next((e for e in episodes if e['id'] == id1), None)
                ep2 = next((e for e in episodes if e['id'] == id2), None)

                if ep1 and ep2:
                    self._notify_progress(
                        'episode', 'processing',
                        f'エピソード {id1} と {id2} を統合中...'
                    )

                    merge_prompt = MERGE_PROMPT.format(
                        item1=ep1['memory_content'],
                        item2=ep2['memory_content']
                    )
                    merged_content = self.client.generate(merge_prompt).strip()

                    update_memory(id1, merged_content)
                    delete_memory(id2, hard_delete=False)

                    processed_ids.add(id1)
                    processed_ids.add(id2)
                    merged_count += 1

            return merged_count

        except Exception:
            return 0

    def _format_episode(self, episode: Dict) -> bool:
        """エピソードを整形する"""
        prompt = FORMAT_PROMPT.format(text=episode['memory_content'])
        formatted = self.client.generate(prompt).strip()

        if formatted and formatted != episode['memory_content']:
            update_memory(episode['id'], formatted)
            return True
        return False

    def _compress_old_episodes(self) -> int:
        """古いエピソードを圧縮する"""
        episodes = get_all_memories(active_only=True)
        compressed_count = 0
        now = datetime.now()

        for ep in episodes:
            # 作成日時から経過日数を計算
            created_at = datetime.fromisoformat(
                ep['created_at'].replace('Z', '+00:00').replace(' ', 'T')
            )
            if created_at.tzinfo:
                created_at = created_at.replace(tzinfo=None)
            days_old = (now - created_at).days

            current_level = ep.get('compression_level', 0)
            thresholds = MEMORY_COMPRESSION_THRESHOLDS

            # 圧縮レベルを決定
            if days_old >= thresholds['ancient'] and current_level < 3:
                target_level = 3
            elif days_old >= thresholds['old'] and current_level < 2:
                target_level = 2
            elif days_old >= thresholds['medium'] and current_level < 1:
                target_level = 1
            else:
                continue

            self._notify_progress(
                'episode', 'processing',
                f'エピソード {ep["id"]} を圧縮中（レベル{target_level}）...'
            )

            prompt = COMPRESS_PROMPT.format(
                level=target_level,
                content=ep['memory_content']
            )
            compressed = self.client.generate(prompt).strip()

            if compressed and len(compressed) < len(ep['memory_content']):
                update_memory(ep['id'], compressed)
                update_compression_level('user_memories', ep['id'], target_level)
                compressed_count += 1

        return compressed_count

    # ==================================================
    # 目標の整理
    # ==================================================

    def _organize_goals(self) -> Dict[str, int]:
        """
        目標の整理を実行

        Returns:
            Dict: 処理結果
        """
        result = {'merged': 0, 'formatted': 0, 'conflicts_resolved': 0}
        goals = get_all_goals(status_filter='active')

        if not goals:
            self._notify_progress(
                'goal', 'skipped',
                '整理対象の目標がありません'
            )
            return result

        total = len(goals)
        self._notify_progress(
            'goal', 'processing',
            f'{total}件の目標を確認中...',
            current=0, total=total
        )

        # 矛盾検出と解決
        if len(goals) >= 2:
            conflicts = self._detect_conflicts(goals, 'goal_content', 'goal_status')
            result['conflicts_resolved'] = self._resolve_goal_conflicts(conflicts, goals)

        # 整形処理
        goals = get_all_goals(status_filter='active')  # 再取得
        for i, goal in enumerate(goals[:self.MAX_ITEMS_PER_STEP]):
            self._notify_progress(
                'goal', 'processing',
                f'目標を整形中... ({i + 1}/{min(len(goals), self.MAX_ITEMS_PER_STEP)})',
                current=i + 1, total=min(len(goals), self.MAX_ITEMS_PER_STEP)
            )
            if self._format_goal(goal):
                result['formatted'] += 1

        return result

    def _format_goal(self, goal: Dict) -> bool:
        """目標を整形する"""
        prompt = FORMAT_PROMPT.format(text=goal['goal_content'])
        formatted = self.client.generate(prompt).strip()

        if formatted and formatted != goal['goal_content']:
            update_goal(goal['id'], goal_content=formatted)
            return True
        return False

    def _resolve_goal_conflicts(
        self,
        conflicts: List[Dict],
        goals: List[Dict]
    ) -> int:
        """目標の矛盾を解決する"""
        resolved = 0
        processed_ids = set()

        for conflict in conflicts:
            id1, id2 = conflict.get('id1'), conflict.get('id2')
            newer_id = conflict.get('newer_id')

            if id1 in processed_ids or id2 in processed_ids:
                continue

            older_id = id1 if newer_id == id2 else id2
            goal1 = next((g for g in goals if g['id'] == id1), None)
            goal2 = next((g for g in goals if g['id'] == id2), None)

            if goal1 and goal2:
                self._notify_progress(
                    'goal', 'processing',
                    f'目標の矛盾を解決中...'
                )
                update_goal(older_id, goal_status='cancelled')
                processed_ids.add(id1)
                processed_ids.add(id2)
                resolved += 1

        return resolved

    # ==================================================
    # お願いの整理
    # ==================================================

    def _organize_requests(self) -> Dict[str, int]:
        """
        お願いの整理を実行

        Returns:
            Dict: 処理結果
        """
        result = {'merged': 0, 'formatted': 0}
        requests = get_all_requests(active_only=True)

        if not requests:
            self._notify_progress(
                'request', 'skipped',
                '整理対象のお願いがありません'
            )
            return result

        total = len(requests)
        self._notify_progress(
            'request', 'processing',
            f'{total}件のお願いを確認中...',
            current=0, total=total
        )

        # 重複検出と統合
        if len(requests) >= 2:
            result['merged'] = self._merge_duplicate_requests(requests)

        # 整形処理
        requests = get_all_requests(active_only=True)  # 再取得
        for i, req in enumerate(requests[:self.MAX_ITEMS_PER_STEP]):
            self._notify_progress(
                'request', 'processing',
                f'お願いを整形中... ({i + 1}/{min(len(requests), self.MAX_ITEMS_PER_STEP)})',
                current=i + 1, total=min(len(requests), self.MAX_ITEMS_PER_STEP)
            )
            if self._format_request(req):
                result['formatted'] += 1

        return result

    def _merge_duplicate_requests(self, requests: List[Dict]) -> int:
        """重複するお願いを統合する"""
        items_str = "\n".join([
            f"ID:{req['id']} - {req['request_content']}"
            for req in requests[:self.MAX_ITEMS_PER_STEP]
        ])

        prompt = DUPLICATE_DETECTION_PROMPT.format(items=items_str)
        response = self.client.generate(prompt)

        try:
            duplicates = self._parse_json_response(response)
            if not isinstance(duplicates, list):
                return 0

            merged_count = 0
            processed_ids = set()

            for dup in duplicates:
                id1, id2 = dup.get('id1'), dup.get('id2')

                if id1 in processed_ids or id2 in processed_ids:
                    continue

                req1 = next((r for r in requests if r['id'] == id1), None)
                req2 = next((r for r in requests if r['id'] == id2), None)

                if req1 and req2:
                    self._notify_progress(
                        'request', 'processing',
                        f'お願い {id1} と {id2} を統合中...'
                    )

                    merge_prompt = MERGE_PROMPT.format(
                        item1=req1['request_content'],
                        item2=req2['request_content']
                    )
                    merged_content = self.client.generate(merge_prompt).strip()

                    update_request(id1, merged_content)
                    delete_request(id2)

                    processed_ids.add(id1)
                    processed_ids.add(id2)
                    merged_count += 1

            return merged_count

        except Exception:
            return 0

    def _format_request(self, request: Dict) -> bool:
        """お願いを整形する"""
        prompt = FORMAT_PROMPT.format(text=request['request_content'])
        formatted = self.client.generate(prompt).strip()

        if formatted and formatted != request['request_content']:
            update_request(request['id'], formatted)
            return True
        return False

    # ==================================================
    # 共通ユーティリティ
    # ==================================================

    def _detect_conflicts(
        self,
        items: List[Dict],
        name_field: str,
        value_field: str
    ) -> List[Dict]:
        """矛盾を検出する"""
        items_str = "\n".join([
            f"ID:{item['id']} - {item.get(name_field, '')}: {item.get(value_field, '')} (更新: {item.get('updated_at', '')})"
            for item in items[:self.MAX_ITEMS_PER_STEP]
        ])

        prompt = CONFLICT_DETECTION_PROMPT.format(items=items_str)
        response = self.client.generate(prompt)

        try:
            conflicts = self._parse_json_response(response)
            return conflicts if isinstance(conflicts, list) else []
        except Exception:
            return []

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
        """処理ログをクリアする"""
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
    print("=== 情報整理モジュールのテスト ===\n")

    def progress_handler(info: Dict):
        """進捗表示用ハンドラー"""
        step_display = info.get('step_display', '')
        prefix = f"[{step_display}] " if step_display else f"[{info['step']}] "

        status_icons = {
            'started': '▶️',
            'processing': '⏳',
            'completed': '✅',
            'skipped': '⏭️',
            'error': '❌'
        }
        icon = status_icons.get(info['status'], '•')

        progress_str = ""
        if info.get('progress') and info['progress']['total'] > 0:
            progress_str = f" ({info['progress']['current']}/{info['progress']['total']})"

        print(f"{prefix}{icon} {info['message']}{progress_str}")

    organizer = MemoryOrganizer()
    organizer.set_progress_callback(progress_handler)

    print("情報整理を実行します...\n")
    results = organizer.organize_all()

    print("\n【結果サマリー】")
    print(json.dumps(results, ensure_ascii=False, indent=2))
