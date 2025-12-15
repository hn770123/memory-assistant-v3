/**
 * AI秘書 管理画面JavaScript
 * ==========================
 * DB管理画面の動作を制御します。
 *
 * 機能:
 * - データの表示（テーブル別）
 * - データの追加・編集・削除
 * - タブ切り替え
 */

// ===== 現在の状態を保持する変数 =====
let currentTable = 'attributes';  // 現在表示中のテーブル
let editingId = null;             // 編集中のレコードID（null = 新規追加）


// ===== DOM要素の取得 =====
const tabs = document.querySelectorAll('.tab');
const editModal = document.getElementById('edit-modal');
const deleteModal = document.getElementById('delete-modal');
const editForm = document.getElementById('edit-form');
const formFields = document.getElementById('form-fields');
const modalTitle = document.getElementById('modal-title');


// ===== 初期化処理 =====
document.addEventListener('DOMContentLoaded', () => {
    // タブのイベントリスナーを設定
    tabs.forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.table));
    });

    // フォーム送信イベント
    editForm.addEventListener('submit', (e) => {
        e.preventDefault();
        saveData();
    });

    // 初期データを読み込み
    loadData('attributes');
});


/**
 * タブを切り替える
 *
 * @param {string} tableName - 切り替え先のテーブル名
 */
function switchTab(tableName) {
    // 現在のテーブルを更新
    currentTable = tableName;

    // タブのアクティブ状態を更新
    tabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.table === tableName);
    });

    // テーブル表示を切り替え
    document.querySelectorAll('.data-table').forEach(table => {
        table.style.display = 'none';
    });
    document.getElementById(`${tableName}-table`).style.display = 'block';

    // データを読み込み
    loadData(tableName);
}


/**
 * データを読み込んで表示する
 *
 * @param {string} tableName - テーブル名
 */
async function loadData(tableName) {
    try {
        const response = await fetch(`/api/data/${tableName}`);
        const data = await response.json();

        // テーブルに表示
        displayData(tableName, data.data);
    } catch (error) {
        console.error('データの読み込みに失敗:', error);
        alert('データの読み込みに失敗しました');
    }
}


/**
 * データをテーブルに表示する
 *
 * @param {string} tableName - テーブル名
 * @param {Array} data - 表示するデータ
 */
function displayData(tableName, data) {
    const tbody = document.getElementById(`${tableName}-body`);
    tbody.innerHTML = '';

    if (data.length === 0) {
        // データがない場合
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="7" style="text-align: center; color: #999;">データがありません</td>';
        tbody.appendChild(tr);
        return;
    }

    // データを1行ずつ表示
    data.forEach(item => {
        const tr = document.createElement('tr');

        // テーブルに応じた行を作成
        if (tableName === 'attributes') {
            tr.innerHTML = createAttributeRow(item);
        } else if (tableName === 'memories') {
            tr.innerHTML = createMemoryRow(item);
        } else if (tableName === 'goals') {
            tr.innerHTML = createGoalRow(item);
        } else if (tableName === 'requests') {
            tr.innerHTML = createRequestRow(item);
        }

        tbody.appendChild(tr);
    });
}


/**
 * 属性の行HTMLを作成
 */
function createAttributeRow(item) {
    return `
        <td>${item.id}</td>
        <td>${escapeHtml(item.attribute_name)}</td>
        <td>${escapeHtml(item.attribute_value)}</td>
        <td>${formatDate(item.updated_at)}</td>
        <td class="table-actions">
            <button class="btn btn-small btn-secondary" onclick="editItem(${item.id}, 'attributes')">編集</button>
            <button class="btn btn-small btn-danger" onclick="deleteItem(${item.id}, 'attributes')">削除</button>
        </td>
    `;
}


/**
 * 記憶の行HTMLを作成
 */
function createMemoryRow(item) {
    const statusBadge = item.is_active ?
        '<span class="badge badge-active">有効</span>' :
        '<span class="badge badge-inactive">無効</span>';

    return `
        <td>${item.id}</td>
        <td>${escapeHtml(truncate(item.memory_content, 50))}</td>
        <td>${escapeHtml(item.memory_category)}</td>
        <td>${item.compression_level}</td>
        <td>${statusBadge}</td>
        <td>${formatDate(item.updated_at)}</td>
        <td class="table-actions">
            <button class="btn btn-small btn-secondary" onclick="editItem(${item.id}, 'memories')">編集</button>
            <button class="btn btn-small btn-danger" onclick="deleteItem(${item.id}, 'memories')">削除</button>
        </td>
    `;
}


/**
 * 目標の行HTMLを作成
 */
function createGoalRow(item) {
    let statusBadge;
    if (item.goal_status === 'active') {
        statusBadge = '<span class="badge badge-active">進行中</span>';
    } else if (item.goal_status === 'completed') {
        statusBadge = '<span class="badge badge-completed">完了</span>';
    } else {
        statusBadge = '<span class="badge badge-inactive">中止</span>';
    }

    return `
        <td>${item.id}</td>
        <td>${escapeHtml(truncate(item.goal_content, 50))}</td>
        <td>${item.priority}</td>
        <td>${statusBadge}</td>
        <td>${formatDate(item.updated_at)}</td>
        <td class="table-actions">
            <button class="btn btn-small btn-secondary" onclick="editItem(${item.id}, 'goals')">編集</button>
            <button class="btn btn-small btn-danger" onclick="deleteItem(${item.id}, 'goals')">削除</button>
        </td>
    `;
}


/**
 * お願いの行HTMLを作成
 */
function createRequestRow(item) {
    const statusBadge = item.is_active ?
        '<span class="badge badge-active">有効</span>' :
        '<span class="badge badge-inactive">無効</span>';

    return `
        <td>${item.id}</td>
        <td>${escapeHtml(truncate(item.request_content, 50))}</td>
        <td>${escapeHtml(item.request_category)}</td>
        <td>${statusBadge}</td>
        <td>${formatDate(item.updated_at)}</td>
        <td class="table-actions">
            <button class="btn btn-small btn-secondary" onclick="editItem(${item.id}, 'requests')">編集</button>
            <button class="btn btn-small btn-danger" onclick="deleteItem(${item.id}, 'requests')">削除</button>
        </td>
    `;
}


/**
 * 追加フォームを表示する
 *
 * @param {string} tableName - テーブル名
 */
function showAddForm(tableName) {
    editingId = null;
    currentTable = tableName;
    modalTitle.textContent = 'データを追加';

    // フォームフィールドを生成
    formFields.innerHTML = getFormFields(tableName, null);

    // モーダルを表示
    editModal.style.display = 'flex';
}


/**
 * 編集フォームを表示する
 *
 * @param {number} id - 編集するレコードのID
 * @param {string} tableName - テーブル名
 */
async function editItem(id, tableName) {
    try {
        const response = await fetch(`/api/data/${tableName}`);
        const data = await response.json();

        // 該当するアイテムを検索
        const item = data.data.find(d => d.id === id);
        if (!item) {
            alert('データが見つかりません');
            return;
        }

        editingId = id;
        currentTable = tableName;
        modalTitle.textContent = 'データを編集';

        // フォームフィールドを生成（既存データを入力済みに）
        formFields.innerHTML = getFormFields(tableName, item);

        // モーダルを表示
        editModal.style.display = 'flex';
    } catch (error) {
        console.error('データの取得に失敗:', error);
        alert('データの取得に失敗しました');
    }
}


/**
 * フォームフィールドのHTMLを取得する
 *
 * @param {string} tableName - テーブル名
 * @param {Object|null} item - 既存データ（新規の場合null）
 * @returns {string} フォームフィールドのHTML
 */
function getFormFields(tableName, item) {
    if (tableName === 'attributes') {
        return `
            <div class="form-group">
                <label for="attr-name">属性名</label>
                <input type="text" id="attr-name" required
                    value="${item ? escapeHtml(item.attribute_name) : ''}"
                    ${item ? 'readonly' : ''}>
            </div>
            <div class="form-group">
                <label for="attr-value">属性値</label>
                <input type="text" id="attr-value" required
                    value="${item ? escapeHtml(item.attribute_value) : ''}">
            </div>
        `;
    } else if (tableName === 'memories') {
        return `
            <div class="form-group">
                <label for="mem-content">内容</label>
                <textarea id="mem-content" rows="4" required>${item ? escapeHtml(item.memory_content) : ''}</textarea>
            </div>
            <div class="form-group">
                <label for="mem-category">カテゴリ</label>
                <select id="mem-category">
                    <option value="general" ${item?.memory_category === 'general' ? 'selected' : ''}>一般</option>
                    <option value="preference" ${item?.memory_category === 'preference' ? 'selected' : ''}>好み</option>
                    <option value="event" ${item?.memory_category === 'event' ? 'selected' : ''}>出来事</option>
                    <option value="knowledge" ${item?.memory_category === 'knowledge' ? 'selected' : ''}>知識</option>
                </select>
            </div>
        `;
    } else if (tableName === 'goals') {
        return `
            <div class="form-group">
                <label for="goal-content">内容</label>
                <textarea id="goal-content" rows="4" required>${item ? escapeHtml(item.goal_content) : ''}</textarea>
            </div>
            <div class="form-group">
                <label for="goal-priority">優先度（1:最高 ～ 10:最低）</label>
                <input type="number" id="goal-priority" min="1" max="10"
                    value="${item ? item.priority : 5}">
            </div>
            ${item ? `
            <div class="form-group">
                <label for="goal-status">状態</label>
                <select id="goal-status">
                    <option value="active" ${item.goal_status === 'active' ? 'selected' : ''}>進行中</option>
                    <option value="completed" ${item.goal_status === 'completed' ? 'selected' : ''}>完了</option>
                    <option value="cancelled" ${item.goal_status === 'cancelled' ? 'selected' : ''}>中止</option>
                </select>
            </div>
            ` : ''}
        `;
    } else if (tableName === 'requests') {
        return `
            <div class="form-group">
                <label for="req-content">内容</label>
                <textarea id="req-content" rows="4" required>${item ? escapeHtml(item.request_content) : ''}</textarea>
            </div>
            <div class="form-group">
                <label for="req-category">カテゴリ</label>
                <select id="req-category">
                    <option value="general" ${item?.request_category === 'general' ? 'selected' : ''}>一般</option>
                    <option value="tone" ${item?.request_category === 'tone' ? 'selected' : ''}>話し方</option>
                    <option value="behavior" ${item?.request_category === 'behavior' ? 'selected' : ''}>振る舞い</option>
                    <option value="format" ${item?.request_category === 'format' ? 'selected' : ''}>形式</option>
                </select>
            </div>
        `;
    }

    return '';
}


/**
 * データを保存する
 */
async function saveData() {
    let data = {};
    let url = `/api/data/${currentTable}`;
    let method = 'POST';

    // フォームからデータを取得
    if (currentTable === 'attributes') {
        data = {
            name: document.getElementById('attr-name').value,
            value: document.getElementById('attr-value').value
        };
    } else if (currentTable === 'memories') {
        data = {
            content: document.getElementById('mem-content').value,
            category: document.getElementById('mem-category').value
        };
    } else if (currentTable === 'goals') {
        data = {
            content: document.getElementById('goal-content').value,
            priority: parseInt(document.getElementById('goal-priority').value)
        };
        const statusEl = document.getElementById('goal-status');
        if (statusEl) {
            data.status = statusEl.value;
        }
    } else if (currentTable === 'requests') {
        data = {
            content: document.getElementById('req-content').value,
            category: document.getElementById('req-category').value
        };
    }

    // 編集の場合はPUTメソッドを使用
    if (editingId !== null) {
        url = `/api/data/${currentTable}/${editingId}`;
        method = 'PUT';
    }

    try {
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success || result.id) {
            closeModal();
            loadData(currentTable);
        } else {
            alert('保存に失敗しました');
        }
    } catch (error) {
        console.error('保存に失敗:', error);
        alert('保存に失敗しました');
    }
}


/**
 * 削除確認ダイアログを表示する
 *
 * @param {number} id - 削除するレコードのID
 * @param {string} tableName - テーブル名
 */
function deleteItem(id, tableName) {
    currentTable = tableName;
    editingId = id;

    // 確認メッセージを設定
    document.getElementById('delete-message').textContent =
        `ID: ${id} のデータを削除しますか？この操作は取り消せません。`;

    // 削除確認ボタンのイベントを設定
    document.getElementById('confirm-delete-btn').onclick = confirmDelete;

    // モーダルを表示
    deleteModal.style.display = 'flex';
}


/**
 * 削除を実行する
 */
async function confirmDelete() {
    try {
        const response = await fetch(`/api/data/${currentTable}/${editingId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            closeDeleteModal();
            loadData(currentTable);
        } else {
            alert('削除に失敗しました');
        }
    } catch (error) {
        console.error('削除に失敗:', error);
        alert('削除に失敗しました');
    }
}


/**
 * 編集モーダルを閉じる
 */
function closeModal() {
    editModal.style.display = 'none';
    editingId = null;
}


/**
 * 削除確認モーダルを閉じる
 */
function closeDeleteModal() {
    deleteModal.style.display = 'none';
    editingId = null;
}


// ===== ユーティリティ関数 =====

/**
 * HTMLエスケープを行う（XSS対策）
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


/**
 * 文字列を指定長で切り詰める
 */
function truncate(text, length) {
    if (!text) return '';
    if (text.length <= length) return text;
    return text.substring(0, length) + '...';
}


/**
 * 日付をフォーマットする
 */
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('ja-JP', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}
