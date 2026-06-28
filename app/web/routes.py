from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter()


@router.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>quant_msx</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <header class="topbar">
      <div>
        <strong>quant_msx</strong>
        <span>MSX 网格量化控制台</span>
      </div>
      <span class="badge">FastAPI Web</span>
    </header>
    <main class="layout">
      <section class="panel">
        <h1>网格策略</h1>
        <p>当前是 FastAPI 内置前端骨架。后续列表、详情、订单、成交和事件日志都在此基础上扩展。</p>
        <div class="actions">
          <a href="/grids">网格策略</a>
          <a href="/accounts">账户管理</a>
          <a href="/api/system/info">系统信息</a>
          <a href="/docs">API Docs</a>
          <a href="/redoc">ReDoc</a>
        </div>
      </section>
      <section class="grid">
        <article>
          <span>交易开关</span>
          <strong id="live-trading">loading</strong>
        </article>
        <article>
          <span>Demo 模式</span>
          <strong id="demo-mode">loading</strong>
        </article>
        <article>
          <span>系统状态</span>
          <strong id="system-status">loading</strong>
        </article>
      </section>
    </main>
    <script>
      fetch("/api/system/info")
        .then((response) => response.json())
        .then((info) => {
          document.querySelector("#live-trading").textContent = String(info.live_trading_enabled);
          document.querySelector("#demo-mode").textContent = String(info.grid_demo_mode);
          document.querySelector("#system-status").textContent = info.app_env;
        })
        .catch(() => {
          document.querySelector("#system-status").textContent = "error";
        });
    </script>
  </body>
</html>
"""


@router.get("/grids", response_class=HTMLResponse)
async def grids_page() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>网格策略 - quant_msx</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <header class="topbar">
      <div>
        <strong>quant_msx</strong>
        <span>MSX 网格策略</span>
      </div>
      <a href="/">返回控制台</a>
    </header>
    <main class="layout">
      <section class="grid account-summary-grid">
        <article>
          <span>运行中</span>
          <strong id="grid-running">loading</strong>
        </article>
        <article>
          <span>投入资金</span>
          <strong id="grid-invested">loading</strong>
        </article>
        <article>
          <span>网格收益</span>
          <strong id="grid-profit">loading</strong>
        </article>
      </section>

      <section class="panel account-form-panel">
        <h1>新增 MSX 网格</h1>
        <form id="grid-form" class="form-grid">
          <label>
            <span>策略名称</span>
            <input id="grid-name" required maxlength="128" value="BTCUSDT 中性网格" />
          </label>
          <label>
            <span>交易对</span>
            <input id="grid-symbol" required value="BTCUSDT" />
          </label>
          <label>
            <span>方向</span>
            <select id="grid-direction">
              <option value="neutral">中性</option>
              <option value="long_bias">偏多</option>
              <option value="short_bias">偏空</option>
            </select>
          </label>
          <label>
            <span>间距模式</span>
            <select id="grid-spacing-mode">
              <option value="geometric">等比</option>
              <option value="arithmetic">等差</option>
            </select>
          </label>
          <label>
            <span>杠杆</span>
            <input id="grid-leverage" type="number" min="1" step="1" value="2" />
          </label>
          <label>
            <span>保证金 USDT</span>
            <input id="grid-margin" type="number" min="0" step="0.01" value="100" />
          </label>
          <label>
            <span>网格数量</span>
            <input id="grid-levels" type="number" min="1" step="1" value="10" />
          </label>
          <label>
            <span>基准价</span>
            <input id="grid-base-price" type="number" min="0" step="0.0001" value="100" />
          </label>
          <label>
            <span>下边界</span>
            <input id="grid-lower" type="number" min="0" step="0.0001" value="90" />
          </label>
          <label>
            <span>上边界</span>
            <input id="grid-upper" type="number" min="0" step="0.0001" value="110" />
          </label>
          <label>
            <span>单格数量，可空</span>
            <input id="grid-order-qty" type="number" min="0" step="0.00000001" />
          </label>
          <label>
            <span>最大亏损 USDT</span>
            <input id="grid-max-loss" type="number" min="0" step="0.01" value="0" />
          </label>
          <label class="wide-field checkbox-field">
            <input id="grid-start-now" type="checkbox" />
            <span>创建后立即启动</span>
          </label>
          <div class="form-actions wide-field">
            <button type="submit">创建策略</button>
            <span id="grid-form-message"></span>
          </div>
        </form>
      </section>

      <section class="panel account-list-panel">
        <div class="section-heading">
          <h1>策略列表</h1>
          <button type="button" id="refresh-grids">刷新</button>
        </div>
        <div id="grid-list" class="account-list"></div>
      </section>
    </main>
    <script>
      const gridState = { items: [] };

      async function api(path, options = {}) {
        const response = await fetch(path, {
          headers: { "Content-Type": "application/json", ...(options.headers || {}) },
          ...options,
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || `HTTP ${response.status}`);
        }
        return response.json();
      }

      function gridPayload() {
        return {
          name: document.querySelector("#grid-name").value.trim(),
          exchange: "MSX",
          market: "futures",
          symbol: document.querySelector("#grid-symbol").value.trim().toUpperCase(),
          direction: document.querySelector("#grid-direction").value,
          leverage: document.querySelector("#grid-leverage").value,
          margin_usdt: document.querySelector("#grid-margin").value,
          spacing_mode: document.querySelector("#grid-spacing-mode").value,
          grid_levels: document.querySelector("#grid-levels").value,
          order_qty: document.querySelector("#grid-order-qty").value || "0",
          stop_loss_price: document.querySelector("#grid-lower").value,
          take_profit_price: document.querySelector("#grid-upper").value,
          max_loss_usdt: document.querySelector("#grid-max-loss").value,
          base_price: document.querySelector("#grid-base-price").value,
          start_immediately: document.querySelector("#grid-start-now").checked,
        };
      }

      async function refreshGrids() {
        const payload = await api("/api/contract-grids");
        gridState.items = payload.items;
        document.querySelector("#grid-running").textContent =
          String(payload.summary.running_count);
        document.querySelector("#grid-invested").textContent =
          `${payload.summary.total_invested_usdt} USDT`;
        document.querySelector("#grid-profit").textContent =
          `${payload.summary.total_grid_profit_usdt} USDT`;
        renderGrids();
      }

      function renderGrids() {
        const target = document.querySelector("#grid-list");
        if (!gridState.items.length) {
          target.innerHTML = '<div class="empty-state">暂无网格策略</div>';
          return;
        }
        target.innerHTML = gridState.items.map((grid) => `
          <div class="account-row grid-row" data-id="${grid.id}">
            <div>
              <strong>${escapeHtml(grid.name)}</strong>
              <span>${escapeHtml(grid.exchange)} / ${escapeHtml(grid.symbol)}</span>
            </div>
            <span class="account-status status-${statusClass(grid.status)}">
              ${escapeHtml(grid.status)}
            </span>
            <div>
              <strong>${escapeHtml(grid.invested_usdt)} USDT</strong>
              <span>${escapeHtml(grid.direction)} · ${escapeHtml(grid.leverage)}x</span>
            </div>
            <div>
              <span>区间 ${escapeHtml(grid.price_range)}</span>
              <span>下单 ${escapeHtml(grid.order_qty)} · ${escapeHtml(grid.grid_levels)} 格</span>
            </div>
            <div>
              <span>买 ${escapeHtml(grid.lower_order_price)}</span>
              <span>卖 ${escapeHtml(grid.upper_order_price)}</span>
            </div>
            <div class="row-actions">
              ${grid.status === "running"
                ? '<button type="button" data-action="pause">暂停</button>'
                : '<button type="button" data-action="start">启动</button>'}
              ${grid.status === "paused"
                ? '<button type="button" data-action="resume">恢复</button>'
                : ""}
              <button type="button" data-action="stop">停止</button>
              <button type="button" data-action="delete">删除</button>
            </div>
          </div>
        `).join("");
      }

      function statusClass(value) {
        return String(value).replace(/[^a-zA-Z0-9_-]/g, "");
      }

      function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, (char) => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;",
        }[char]));
      }

      document.querySelector("#grid-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
          await api("/api/contract-grids", {
            method: "POST",
            body: JSON.stringify(gridPayload()),
          });
          document.querySelector("#grid-form-message").textContent = "已创建";
          await refreshGrids();
        } catch (error) {
          document.querySelector("#grid-form-message").textContent = error.message;
        }
      });

      document.querySelector("#refresh-grids").addEventListener("click", () => void refreshGrids());
      document.querySelector("#grid-list").addEventListener("click", async (event) => {
        const button = event.target.closest("button");
        const row = event.target.closest(".account-row");
        if (!button || !row) return;
        const grid = gridState.items.find((item) => item.id === Number(row.dataset.id));
        if (!grid) return;
        const action = button.dataset.action;
        if (action === "delete" && !window.confirm(`确认删除策略 ${grid.name}？`)) {
          return;
        }
        const method = action === "delete" ? "DELETE" : "POST";
        const path = action === "delete"
          ? `/api/contract-grids/${grid.id}`
          : `/api/contract-grids/${grid.id}/${action}`;
        try {
          await api(path, { method });
          await refreshGrids();
        } catch (error) {
          window.alert(error.message);
        }
      });

      refreshGrids().catch((error) => {
        document.querySelector("#grid-list").innerHTML =
          `<div class="empty-state">${error.message}</div>`;
      });
    </script>
  </body>
</html>
"""


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>账户管理 - quant_msx</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <header class="topbar">
      <div>
        <strong>quant_msx</strong>
        <span>MSX 账户管理</span>
      </div>
      <a href="/">返回控制台</a>
    </header>
    <main class="layout">
      <section class="grid account-summary-grid">
        <article>
          <span>总权益</span>
          <strong id="summary-equity">loading</strong>
        </article>
        <article>
          <span>启用账户</span>
          <strong id="summary-enabled">loading</strong>
        </article>
        <article>
          <span>正常账户</span>
          <strong id="summary-healthy">loading</strong>
        </article>
      </section>

      <section class="panel account-form-panel">
        <h1 id="form-title">新增 MSX 账户</h1>
        <form id="account-form" class="form-grid">
          <input type="hidden" id="account-id" />
          <label>
            <span>账户名称</span>
            <input id="account-name" required maxlength="128" autocomplete="off" />
          </label>
          <label>
            <span>平台</span>
            <input id="account-exchange" value="MSX" disabled />
          </label>
          <label>
            <span>API Key</span>
            <input id="api-key" autocomplete="off" />
          </label>
          <label>
            <span>API Secret</span>
            <input id="api-secret" type="password" autocomplete="off" />
          </label>
          <label class="wide-field">
            <span>备注</span>
            <input id="account-notes" maxlength="500" autocomplete="off" />
          </label>
          <div class="form-actions wide-field">
            <button type="submit">保存</button>
            <button type="button" id="reset-form">取消编辑</button>
            <span id="form-message"></span>
          </div>
        </form>
      </section>

      <section class="panel account-list-panel">
        <div class="section-heading">
          <h1>账户列表</h1>
          <button type="button" id="refresh-accounts">刷新</button>
        </div>
        <div id="account-list" class="account-list"></div>
      </section>
    </main>
    <script>
      const state = { accounts: [] };

      function accountPayload() {
        const id = document.querySelector("#account-id").value;
        const apiKey = document.querySelector("#api-key").value.trim();
        const apiSecret = document.querySelector("#api-secret").value.trim();
        const payload = {
          name: document.querySelector("#account-name").value.trim(),
          exchange: "MSX",
          notes: document.querySelector("#account-notes").value.trim(),
        };
        if (!id || apiKey || apiSecret) {
          payload.credentials = { api_key: apiKey, api_secret: apiSecret };
        }
        if (!id) {
          payload.account_type = "cex";
          payload.permissions = {};
          payload.connection_config = {};
        }
        return payload;
      }

      async function api(path, options = {}) {
        const response = await fetch(path, {
          headers: { "Content-Type": "application/json", ...(options.headers || {}) },
          ...options,
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || `HTTP ${response.status}`);
        }
        if (response.status === 204) {
          return null;
        }
        return response.json();
      }

      async function refresh() {
        const [summary, accounts] = await Promise.all([
          api("/api/accounts/summary"),
          api("/api/accounts"),
        ]);
        state.accounts = accounts.items;
        document.querySelector("#summary-equity").textContent =
          `${summary.total_balance_usdt} USDT`;
        document.querySelector("#summary-enabled").textContent =
          String(summary.enabled_account_count);
        document.querySelector("#summary-healthy").textContent =
          String(summary.healthy_account_count);
        renderAccounts();
      }

      function renderAccounts() {
        const target = document.querySelector("#account-list");
        if (!state.accounts.length) {
          target.innerHTML = '<div class="empty-state">暂无账户</div>';
          return;
        }
        target.innerHTML = state.accounts.map((account) => `
          <div class="account-row" data-id="${account.id}">
            <div>
              <strong>${escapeHtml(account.name)}</strong>
              <span>${account.account_type.toUpperCase()} / ${account.exchange}</span>
            </div>
            <span class="account-status status-${account.status}">${account.status}</span>
            <div>
              <strong>${account.latest_balance_usdt} USDT</strong>
              <span>权益 ${account.latest_equity_usdt}</span>
            </div>
            <div>
              <span>${credentialText(account)}</span>
              <span>${account.last_error || account.last_checked_at || "未验证"}</span>
            </div>
            <div class="row-actions">
              <button type="button" data-action="edit">编辑</button>
              <button type="button" data-action="test">测试</button>
              <button type="button" data-action="toggle">
                ${account.enabled && account.status !== "disabled" ? "停用" : "启用"}
              </button>
              <button type="button" data-action="delete">删除</button>
            </div>
          </div>
        `).join("");
      }

      function credentialText(account) {
        const fields = account.credential_summary.fields || {};
        return fields.api_key ? `Key ${fields.api_key}` : "未显示凭据";
      }

      function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, (char) => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;",
        }[char]));
      }

      function resetForm() {
        document.querySelector("#account-id").value = "";
        document.querySelector("#account-name").value = "";
        document.querySelector("#api-key").value = "";
        document.querySelector("#api-secret").value = "";
        document.querySelector("#account-notes").value = "";
        document.querySelector("#form-title").textContent = "新增 MSX 账户";
        document.querySelector("#form-message").textContent = "";
      }

      document.querySelector("#account-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const id = document.querySelector("#account-id").value;
        const method = id ? "PATCH" : "POST";
        const path = id ? `/api/accounts/${id}` : "/api/accounts";
        try {
          await api(path, { method, body: JSON.stringify(accountPayload()) });
          document.querySelector("#form-message").textContent = "已保存";
          resetForm();
          await refresh();
        } catch (error) {
          document.querySelector("#form-message").textContent = error.message;
        }
      });

      document.querySelector("#reset-form").addEventListener("click", resetForm);
      document.querySelector("#refresh-accounts").addEventListener("click", () => void refresh());
      document.querySelector("#account-list").addEventListener("click", async (event) => {
        const button = event.target.closest("button");
        const row = event.target.closest(".account-row");
        if (!button || !row) return;
        const account = state.accounts.find((item) => item.id === Number(row.dataset.id));
        if (!account) return;
        const action = button.dataset.action;
        if (action === "edit") {
          document.querySelector("#account-id").value = account.id;
          document.querySelector("#account-name").value = account.name;
          document.querySelector("#account-notes").value = account.notes || "";
          document.querySelector("#api-key").value = "";
          document.querySelector("#api-secret").value = "";
          document.querySelector("#form-title").textContent = "编辑 MSX 账户";
          return;
        }
        if (action === "delete" && !window.confirm(`确认删除账户 ${account.name}？`)) {
          return;
        }
        const toggleAction =
          account.enabled && account.status !== "disabled" ? "disable" : "enable";
        const path = action === "test"
          ? `/api/accounts/${account.id}/test`
          : action === "toggle"
            ? `/api/accounts/${account.id}/${toggleAction}`
            : `/api/accounts/${account.id}`;
        const method = action === "delete" ? "DELETE" : "POST";
        try {
          await api(path, { method });
          await refresh();
        } catch (error) {
          window.alert(error.message);
        }
      });

      refresh().catch((error) => {
        document.querySelector("#account-list").innerHTML =
          `<div class="empty-state">${error.message}</div>`;
      });
    </script>
  </body>
</html>
"""
