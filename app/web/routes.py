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
