/**
 * AI秘書 メインJavaScript
 * ======================
 * チャット画面の動作を制御します。
 *
 * 機能:
 * - メッセージの送受信
 * - 履歴の管理
 * - テストモードの切り替え
 * - 情報整理の実行（属性/エピソード/目標/お願い）
 */

// ===== DOM要素の取得 =====
// getElementById: IDを指定して要素を取得する関数
const messagesContainer = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const clearBtn = document.getElementById('clear-btn');
const organizeBtn = document.getElementById('organize-btn');
const testModeToggle = document.getElementById('test-mode-toggle');
const testPanel = document.getElementById('test-panel');
const testLog = document.getElementById('test-log');
const clearTestLogBtn = document.getElementById('clear-test-log');
const organizeModal = document.getElementById('organize-modal');
const organizeProgress = document.getElementById('organize-progress');
const closeModalBtn = document.getElementById('close-modal-btn');
const memoryIndicator = document.getElementById('memory-indicator');


// ===== 初期化処理 =====
// DOMContentLoaded: HTMLの読み込みが完了したら実行される
document.addEventListener('DOMContentLoaded', () => {
    // テストモードの状態を取得
    loadTestModeState();

    // テキストエリアの自動リサイズを設定
    setupTextareaAutoResize();

    // イベントリスナーを設定
    setupEventListeners();
});


/**
 * テキストエリアの自動リサイズを設定する
 * 入力に合わせて高さが自動調整されます
 */
function setupTextareaAutoResize() {
    messageInput.addEventListener('input', () => {
        // 高さをリセット
        messageInput.style.height = 'auto';
        // スクロール高さに合わせる（最大150px）
        messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
    });
}


/**
 * イベントリスナーを設定する
 */
function setupEventListeners() {
    // 送信ボタンクリック
    sendBtn.addEventListener('click', sendMessage);

    // Enterキーで送信（Shift+Enterは改行）
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // デフォルトの改行を防ぐ
            sendMessage();
        }
    });

    // 履歴クリアボタン
    clearBtn.addEventListener('click', clearHistory);

    // 記憶整理ボタン
    organizeBtn.addEventListener('click', organizeMemories);

    // テストモード切り替え
    testModeToggle.addEventListener('change', toggleTestMode);

    // テストログクリア
    clearTestLogBtn.addEventListener('click', () => {
        testLog.innerHTML = '';
    });

    // モーダルを閉じる
    closeModalBtn.addEventListener('click', () => {
        organizeModal.style.display = 'none';
    });
}


/**
 * テストモードの状態を読み込む
 */
async function loadTestModeState() {
    try {
        // fetch: サーバーにHTTPリクエストを送る関数
        const response = await fetch('/test_mode');
        const data = await response.json();
        testModeToggle.checked = data.test_mode;
        updateTestPanelVisibility();
    } catch (error) {
        console.error('テストモード状態の取得に失敗:', error);
    }
}


/**
 * テストモードを切り替える
 */
async function toggleTestMode() {
    try {
        const response = await fetch('/test_mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: testModeToggle.checked })
        });
        const data = await response.json();
        updateTestPanelVisibility();
    } catch (error) {
        console.error('テストモードの切り替えに失敗:', error);
    }
}


/**
 * テストパネルの表示/非表示を更新する
 */
function updateTestPanelVisibility() {
    testPanel.style.display = testModeToggle.checked ? 'flex' : 'none';
}


/**
 * メッセージを送信する
 */
async function sendMessage() {
    const message = messageInput.value.trim();

    // 空のメッセージは送信しない
    if (!message) return;

    // 入力欄をクリア
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // ユーザーメッセージを表示
    addMessage('あなた', message, 'user');

    // ローディング表示
    const loadingId = showLoading();

    // 送信ボタンを無効化
    sendBtn.disabled = true;

    try {
        // サーバーにメッセージを送信
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();

        // ローディングを削除
        removeLoading(loadingId);

        // エラーチェック
        if (data.error) {
            addMessage('システム', data.error, 'system');
            return;
        }

        // 履歴リセットの通知
        if (data.history_reset) {
            addMessage('システム', '会話がリセットされました', 'system');
        }

        // アシスタントの応答を表示
        addMessage('アシスタント', data.response, 'assistant');

        // テストモードの場合、ログを表示
        if (data.test_logs) {
            displayTestLogs(data.test_logs);
        }

        // 記憶処理の監視を開始
        startMemoryStatusCheck();

    } catch (error) {
        removeLoading(loadingId);
        addMessage('システム', 'エラーが発生しました: ' + error.message, 'system');
    } finally {
        // 送信ボタンを有効化
        sendBtn.disabled = false;
        // 入力欄にフォーカス
        messageInput.focus();
    }
}


/**
 * メッセージを表示する
 *
 * @param {string} sender - 送信者名（「あなた」「アシスタント」など）
 * @param {string} content - メッセージ内容
 * @param {string} type - メッセージタイプ（'user', 'assistant', 'system'）
 */
function addMessage(sender, content, type) {
    // メッセージ要素を作成
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;

    // HTMLを構築
    messageDiv.innerHTML = `
        <div class="message-header">${escapeHtml(sender)}</div>
        <div class="message-content">${escapeHtml(content)}</div>
    `;

    // メッセージコンテナに追加
    messagesContainer.appendChild(messageDiv);

    // 最新メッセージまでスクロール
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}


/**
 * ローディング表示を追加する
 *
 * @returns {string} ローディング要素のID
 */
function showLoading() {
    const loadingId = 'loading-' + Date.now();

    const loadingDiv = document.createElement('div');
    loadingDiv.id = loadingId;
    loadingDiv.className = 'message assistant';
    loadingDiv.innerHTML = `
        <div class="message-header">アシスタント</div>
        <div class="loading">
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
            <div class="loading-dot"></div>
        </div>
    `;

    messagesContainer.appendChild(loadingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return loadingId;
}


/**
 * ローディング表示を削除する
 *
 * @param {string} loadingId - 削除するローディング要素のID
 */
function removeLoading(loadingId) {
    const loading = document.getElementById(loadingId);
    if (loading) {
        loading.remove();
    }
}


/**
 * 履歴をクリアする
 */
async function clearHistory() {
    try {
        const response = await fetch('/clear_history', {
            method: 'POST'
        });

        if (response.ok) {
            // 画面上のメッセージをクリア（初期メッセージは残す）
            messagesContainer.innerHTML = `
                <div class="message assistant">
                    <div class="message-header">アシスタント</div>
                    <div class="message-content">
                        こんにちは！AI秘書です。何かお手伝いできることはありますか？
                    </div>
                </div>
            `;
            addMessage('システム', '会話履歴をクリアしました', 'system');
        }
    } catch (error) {
        console.error('履歴のクリアに失敗:', error);
    }
}


/**
 * 情報整理を実行する（属性/エピソード/目標/お願いの全て）
 */
async function organizeMemories() {
    // モーダルを表示
    organizeModal.style.display = 'flex';
    organizeProgress.innerHTML = '<div class="progress-step started">📋 情報整理を開始しています...</div>';
    closeModalBtn.style.display = 'none';

    try {
        const response = await fetch('/organize', {
            method: 'POST'
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || '開始に失敗しました');
        }

        // ポーリング開始
        const pollInterval = setInterval(async () => {
            try {
                const statusRes = await fetch('/organize/status');

                if (!statusRes.ok) {
                    // エラーレスポンスの場合は例外を投げるかログに出してスキップ
                    console.error('Status check failed:', statusRes.statusText);
                    return; // 次のポーリングへ
                }

                const statusData = await statusRes.json();

                // ログを表示更新

                // ここでは既存のログ数と比較して、新しいものだけ追加する
                const currentLogCount = organizeProgress.querySelectorAll('.progress-step').length;

                // 既存の進捗表示をクリアして再描画（シンプルさ優先）
                organizeProgress.innerHTML = '';

                // 初期メッセージ
                const initialDiv = document.createElement('div');
                initialDiv.className = 'progress-step started';
                initialDiv.textContent = '📋 情報整理を開始しています...';
                organizeProgress.appendChild(initialDiv);

                // サーバーからのログを表示 (logsが存在する場合のみ)
                if (statusData.logs && Array.isArray(statusData.logs)) {
                    statusData.logs.forEach(log => {
                        // llm_interaction 以外を進捗に表示
                        if (log.type !== 'llm_interaction') {
                            addProgressStep(log);
                        }
                    });
                }

                // テストモードなら詳細ログを表示
                if (testModeToggle.checked && statusData.logs && statusData.logs.length > 0) {
                    // test-log にも表示（重複しないように制御が必要だが、今回は簡易的に全消し再描画は重いので、
                    // 差分追加したいところだが、テストパネルは時系列でどんどん追加されるもの。
                    // 今回の「リアルタイム表示」はテストパネルに「今何が起きているか」が出ればよい。
                    // 常に最新の状態を反映させるため、オーガナイズ関係のログだけ抽出して表示する？
                    // いや、以前の displayTestLogs は追加型。
                    // ここではシンプルに「まだ表示していないログ」を追加する形にする

                    // 簡易実装: 今回のセッションで表示済みのログID（インデックス）を管理
                    if (!window.lastOrganizeLogIndex) window.lastOrganizeLogIndex = 0;

                    const newLogs = statusData.logs.slice(window.lastOrganizeLogIndex);
                    if (newLogs.length > 0) {
                        const displayLogs = newLogs.map(log => ({
                            type: 'memory_organize', // タイプを統一
                            timestamp: log.timestamp || new Date().toISOString(),
                            // llm_interaction なら詳細を、それ以外ならメッセージを
                            ...(log.type === 'llm_interaction' ? {
                                action: log.action,
                                prompt: log.prompt,
                                response: log.response,
                                details: log // 他のフィールドも全部
                            } : {
                                message: log.message,
                                step: log.step_display || log.step
                            })
                        }));

                        // 専用の表示関数を作るか、既存を拡張する
                        displayOrganizeLogs(displayLogs);
                        window.lastOrganizeLogIndex = statusData.logs.length;
                    }
                }

                if (!statusData.is_organizing) {
                    clearInterval(pollInterval);
                    closeModalBtn.style.display = 'block';
                    window.lastOrganizeLogIndex = 0; // リセット

                    // 完了メッセージ（最後のログが完了でなければ出すなど工夫もできるが、ログに含まれているはず）
                }

            } catch (e) {
                console.error("Polling error", e);
                clearInterval(pollInterval);
                closeModalBtn.style.display = 'block';
                addProgressStep({
                    step: 'error',
                    status: 'error',
                    message: '❌ 通信エラーが発生しました'
                });
            }
        }, 500);

    } catch (error) {
        addProgressStep({
            step: 'error',
            status: 'error',
            message: '❌ エラーが発生しました: ' + error.message
        });
        closeModalBtn.style.display = 'block';
    }
}

/**
 * 記憶整理のログをテストパネルに表示する
 */
function displayOrganizeLogs(logs) {
    logs.forEach(log => {
        const entryDiv = document.createElement('div');
        entryDiv.className = 'test-log-entry';

        let content = `<div class="type">memory_organize</div>`;
        content += `<div class="timestamp">${log.timestamp}</div>`;

        if (log.action) {
            // LLMインタラクション
            content += `<div style="color: #4ec9b0; margin-bottom:4px;">Action: ${log.action}</div>`;
            if (log.prompt) {
                content += `<div style="color: #ce9178;">Prompt:</div><pre>${escapeHtml(log.prompt).replace(/\\n/g, '\n')}</pre>`;
            }
            if (log.response) {
                content += `<div style="color: #ce9178; margin-top:8px;">Response:</div><pre>${escapeHtml(typeof log.response === 'string' ? log.response : JSON.stringify(log.response, null, 2)).replace(/\\n/g, '\n')}</pre>`;
            }
        } else {
            // 通常の進捗ログ
            content += `<pre>${escapeHtml('[' + (log.step || 'INFO') + '] ' + log.message)}</pre>`;
        }

        entryDiv.innerHTML = content;
        testLog.appendChild(entryDiv);
    });

    testLog.scrollTop = testLog.scrollHeight;
}


/**
 * 進捗ステップを表示に追加する
 *
 * @param {Object} log - ログ情報
 */
function addProgressStep(log) {
    const stepDiv = document.createElement('div');
    stepDiv.className = `progress-step ${log.status}`;

    // ステップ表示名があればそれを使う、なければstepを使う
    const stepLabel = log.step_display || log.step;

    // 進捗情報があれば追加
    let progressStr = '';
    if (log.progress && log.progress.total > 0) {
        progressStr = ` (${log.progress.current}/${log.progress.total})`;
    }

    stepDiv.textContent = `[${stepLabel}] ${log.message}${progressStr}`;
    organizeProgress.appendChild(stepDiv);
    organizeProgress.scrollTop = organizeProgress.scrollHeight;
}


/**
 * 記憶処理の状態監視
 */
let memoryCheckInterval = null;

function startMemoryStatusCheck() {
    // 既に実行中なら一旦クリア
    if (memoryCheckInterval) {
        clearInterval(memoryCheckInterval);
    }

    // まず表示する（処理開始直後とみなす）
    memoryIndicator.style.display = 'flex';

    memoryCheckInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/system/processing_status');
            const data = await response.json();

            if (data.processing) {
                memoryIndicator.style.display = 'flex';
            } else {
                // 処理完了
                stopMemoryStatusCheck();

                // 完了時のログがあれば表示（テストモード）
                if (data.logs && data.logs.length > 0) {
                    const logData = [{
                        type: 'memory_extraction',
                        logs: data.logs,
                        timestamp: new Date().toISOString()
                    }];
                    displayTestLogs(logData);
                }
            }
        } catch (error) {
            console.error('ステータス確認エラー:', error);
            stopMemoryStatusCheck();
        }
    }, 1000); // 1秒ごとにチェック
}

function stopMemoryStatusCheck() {
    if (memoryCheckInterval) {
        clearInterval(memoryCheckInterval);
        memoryCheckInterval = null;
    }
    memoryIndicator.style.display = 'none';
}


/**
 * テストログを表示する
 *
 * @param {Array} logs - テストログの配列
 */
function displayTestLogs(logs) {
    logs.forEach(log => {
        const entryDiv = document.createElement('div');
        entryDiv.className = 'test-log-entry';

        let content = `<div class="type">${log.type}</div>`;
        content += `<div class="timestamp">${log.timestamp}</div>`;

        // ログの種類に応じて表示を変える
        if (log.type === 'mcp_context') {
            content += `<pre>${escapeHtml(log.context)}</pre>`;
        } else if (log.type === 'ollama_request') {
            content += `<pre>${escapeHtml(JSON.stringify(log.logs, null, 2)).replace(/\\n/g, '\n')}</pre>`;
        } else if (log.type === 'session_reset') {
            content += `<pre>理由: ${log.reason}</pre>`;
        } else if (log.type === 'memory_extraction') {
            content += `<pre>${escapeHtml(JSON.stringify(log.logs, null, 2)).replace(/\\n/g, '\n')}</pre>`;
        }

        entryDiv.innerHTML = content;
        testLog.appendChild(entryDiv);
    });

    testLog.scrollTop = testLog.scrollHeight;
}


/**
 * HTMLエスケープを行う（XSS対策）
 *
 * @param {string} text - エスケープするテキスト
 * @returns {string} エスケープ済みテキスト
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
