# AI秘書

ユーザーの属性、記憶、目標、お願いを管理するAIアシスタントアプリケーションです。

## 機能

### チャット機能
- ブラウザ上でAIアシスタントと対話できます
- ユーザーの情報を自動的に記憶し、パーソナライズされた応答を行います
- 「ありがとう」と言うか、5分間操作がないと会話履歴がリセットされます

### 記憶管理
- **ユーザー属性**: 名前、年齢、職業など固定的な情報
- **ユーザー記憶**: 日常の出来事、好み、経験など
- **ユーザー目標**: やりたいこと、達成したい目標
- **アシスタントへのお願い**: 話し方や対応方法の要望

### 記憶の整理・圧縮
- 重複する記憶の統合
- 表現の整形
- 矛盾する情報の解決
- 古い記憶の圧縮（人間の記憶システムを参考）

### テストモード
- Ollamaへのリクエスト内容を表示
- MCPコンテキストの確認
- 記憶抽出のログ表示

### DB管理画面
- 記憶データの参照・追加・編集・削除

## 技術スタック

- **Python**: バックエンド言語
- **Flask**: Webフレームワーク
- **SQLite**: データベース
- **Ollama + llama3.1:8b**: ローカルLLM
- **MCP (Model Context Protocol)**: 記憶の読み取りプロトコル

## セットアップ

### 1. 必要なソフトウェア

- Python 3.10以上
- Ollama（[公式サイト](https://ollama.ai)からインストール）

### 2. Ollamaのセットアップ

```bash
# Ollamaをインストール後、モデルをダウンロード
ollama pull llama3.1:8b

# Ollamaサーバーを起動
ollama serve
```

### 3. Pythonパッケージのインストール

```bash
# プロジェクトディレクトリに移動
cd memory-assistant-v3

# 仮想環境を作成（推奨）
python -m venv venv

# 仮想環境を有効化
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# パッケージをインストール
pip install -r requirements.txt
```

### 4. アプリケーションの起動

```bash
python run.py
```

起動後、ブラウザで http://localhost:5000 にアクセスしてください。

## ファイル構成

```
memory-assistant-v3/
├── app/                      # アプリケーションコード
│   ├── __init__.py          # パッケージ初期化
│   ├── main.py              # Flaskアプリケーション（メイン）
│   ├── database.py          # データベース操作
│   ├── ollama_client.py     # Ollama連携
│   ├── mcp_server.py        # MCPサーバー
│   ├── memory_extractor.py  # 記憶抽出・判定
│   └── memory_organizer.py  # 記憶整理・圧縮
├── mcp_tools/               # MCPツール定義
│   └── memory_tools.py      # メモリ関連ツール
├── static/                  # 静的ファイル
│   ├── css/
│   │   └── style.css        # スタイルシート
│   └── js/
│       ├── main.js          # チャット画面JS
│       └── admin.js         # 管理画面JS
├── templates/               # HTMLテンプレート
│   ├── index.html           # チャット画面
│   └── admin.html           # DB管理画面
├── config.py                # 設定ファイル
├── requirements.txt         # 依存パッケージ
├── run.py                   # 起動スクリプト
└── README.md               # このファイル
```

## 使い方

### 基本的な使い方

1. アプリを起動してブラウザでアクセス
2. チャット欄にメッセージを入力して送信
3. AIアシスタントが応答します
4. 会話の中で自己紹介をすると、自動的に記憶されます

### 記憶される情報の例

- 「私は田中太郎です」→ 名前が記憶される
- 「東京に住んでいます」→ 住所が記憶される
- 「コーヒーが好きです」→ 好みが記憶される
- 「来月までにTOEIC900点を取りたい」→ 目標が記憶される
- 「敬語で話してください」→ お願いが記憶される

### テストモードの使い方

1. 画面右上のトグルスイッチをONにする
2. チャットを行うと、右側にデバッグ情報が表示される
3. MCPコンテキスト、Ollamaへのリクエスト、記憶抽出のログを確認できる

### DB管理画面の使い方

1. 画面右上の「DB管理」ボタンをクリック
2. タブで各データ種類を切り替え
3. データの追加・編集・削除が可能

## 設定

`config.py` で以下の設定を変更できます：

```python
# OllamaサーバーのURL
OLLAMA_BASE_URL = "http://localhost:11434"

# 使用するモデル
OLLAMA_MODEL = "llama3.1:8b"

# セッションタイムアウト（秒）
SESSION_TIMEOUT_SECONDS = 300  # 5分

# 履歴リセットのトリガーワード
RESET_TRIGGER_WORDS = ["ありがとう", "ありがとうございます"]
```

## トラブルシューティング

### Ollamaに接続できない

```
エラー: Ollamaサーバーに接続できません
```

→ Ollamaが起動しているか確認してください：
```bash
ollama serve
```

### モデルが見つからない

→ モデルをダウンロードしてください：
```bash
ollama pull llama3.1:8b
```

### ポートが使用中

→ 別のポートで起動するか、使用中のプロセスを終了してください：
```python
# run.py を編集
app.run(debug=True, host='0.0.0.0', port=5001)  # ポートを変更
```

## ライセンス

このプロジェクトは学習目的で作成されています。
