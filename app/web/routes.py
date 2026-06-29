from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter()


def _layout(title: str, active: str, body: str, script: str) -> str:
    template = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>__TITLE__ - quant_msx</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0/dist/css/tabler.min.css" />
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.31.0/dist/tabler-icons.min.css" />
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <div class="page">
      <aside class="navbar navbar-vertical navbar-expand-lg" data-bs-theme="dark">
        <div class="container-fluid">
          <h1 class="navbar-brand navbar-brand-autodark">
            <a href="/" class="text-decoration-none">
              <span class="brand-mark">Q</span>
              <span>quant_msx</span>
            </a>
          </h1>
          <div class="collapse navbar-collapse show">
            <ul class="navbar-nav pt-lg-3">
              <li class="nav-item __ACTIVE_DASHBOARD__">
                <a class="nav-link" href="/">
                  <span class="nav-link-icon"><i class="ti ti-layout-dashboard"></i></span>
                  <span class="nav-link-title">控制台</span>
                </a>
              </li>
              <li class="nav-item __ACTIVE_GRIDS__">
                <a class="nav-link" href="/grids">
                  <span class="nav-link-icon"><i class="ti ti-grid-dots"></i></span>
                  <span class="nav-link-title">网格策略</span>
                </a>
              </li>
              <li class="nav-item __ACTIVE_ACCOUNTS__">
                <a class="nav-link" href="/accounts">
                  <span class="nav-link-icon"><i class="ti ti-wallet"></i></span>
                  <span class="nav-link-title">账户管理</span>
                </a>
              </li>
              <li class="nav-item">
                <a class="nav-link" href="/docs">
                  <span class="nav-link-icon"><i class="ti ti-api"></i></span>
                  <span class="nav-link-title">API Docs</span>
                </a>
              </li>
            </ul>
          </div>
        </div>
      </aside>
      <div class="page-wrapper">
        <header class="navbar navbar-expand-md d-print-none">
          <div class="container-xl">
            <div>
              <div class="text-secondary small">MSX 网格量化控制台</div>
              <h2 class="page-title">__TITLE__</h2>
            </div>
            <div class="navbar-nav flex-row order-md-last gap-2">
              <span class="badge bg-blue-lt" id="env-badge">loading</span>
              <span class="badge bg-green-lt" id="live-badge">loading</span>
            </div>
          </div>
        </header>
        <main class="page-body">
          <div class="container-xl">
            __BODY__
          </div>
        </main>
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/@tabler/core@1.0.0/dist/js/tabler.min.js"></script>
    <script>
      const q = (selector, root = document) => root.querySelector(selector);
      const qa = (selector, root = document) => Array.from(root.querySelectorAll(selector));

      async function api(path, options = {}) {
        const response = await fetch(path, {
          headers: { "Content-Type": "application/json", ...(options.headers || {}) },
          ...options,
        });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || `HTTP ${response.status}`);
        }
        if (response.status === 204) return null;
        return response.json();
      }

      function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, (char) => ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;",
        }[char]));
      }

      function badge(value) {
        const status = String(value || "unknown");
        const map = {
          running: "bg-green-lt",
          healthy: "bg-green-lt",
          simulated: "bg-blue-lt",
          open: "bg-blue-lt",
          draft: "bg-yellow-lt",
          paused: "bg-yellow-lt",
          unverified: "bg-yellow-lt",
          stopped: "bg-secondary-lt",
          disabled: "bg-secondary-lt",
          error: "bg-red-lt",
          failed: "bg-red-lt",
          canceled: "bg-secondary-lt",
          filled: "bg-green-lt",
        };
        return `<span class="badge ${map[status] || "bg-secondary-lt"}">${escapeHtml(status)}</span>`;
      }

      function money(value) {
        return `${escapeHtml(value)} USDT`;
      }

      async function loadShellInfo() {
        try {
          const info = await api("/api/system/info");
          q("#env-badge").textContent = info.app_env;
          q("#live-badge").textContent = info.live_trading_enabled ? "live" : "simulation";
          q("#live-badge").className = info.live_trading_enabled
            ? "badge bg-red-lt"
            : "badge bg-green-lt";
        } catch {
          q("#env-badge").textContent = "offline";
          q("#live-badge").textContent = "unknown";
        }
      }

      loadShellInfo();
      __SCRIPT__
    </script>
  </body>
</html>
"""
    active_map = {
        "__ACTIVE_DASHBOARD__": "active" if active == "dashboard" else "",
        "__ACTIVE_GRIDS__": "active" if active == "grids" else "",
        "__ACTIVE_ACCOUNTS__": "active" if active == "accounts" else "",
    }
    html = template.replace("__TITLE__", title).replace("__BODY__", body).replace("__SCRIPT__", script)
    for placeholder, value in active_map.items():
        html = html.replace(placeholder, value)
    return html


@router.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    body = """
<div class="row row-deck row-cards">
  <div class="col-sm-6 col-lg-3">
    <div class="card">
      <div class="card-body">
        <div class="subheader">运行中网格</div>
        <div class="h1 mb-2" id="running-count">-</div>
        <div class="text-secondary">当前活跃策略数量</div>
      </div>
    </div>
  </div>
  <div class="col-sm-6 col-lg-3">
    <div class="card">
      <div class="card-body">
        <div class="subheader">投入资金</div>
        <div class="h1 mb-2" id="invested-total">-</div>
        <div class="text-secondary">网格保证金合计</div>
      </div>
    </div>
  </div>
  <div class="col-sm-6 col-lg-3">
    <div class="card">
      <div class="card-body">
        <div class="subheader">网格收益</div>
        <div class="h1 mb-2" id="grid-profit-total">-</div>
        <div class="text-secondary">已实现网格收益</div>
      </div>
    </div>
  </div>
  <div class="col-sm-6 col-lg-3">
    <div class="card">
      <div class="card-body">
        <div class="subheader">账户权益</div>
        <div class="h1 mb-2" id="account-equity">-</div>
        <div class="text-secondary">账户管理同步值</div>
      </div>
    </div>
  </div>
  <div class="col-lg-8">
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">最新网格策略</h3>
        <div class="card-actions">
          <a href="/grids" class="btn btn-primary btn-sm"><i class="ti ti-plus"></i> 管理策略</a>
        </div>
      </div>
      <div class="table-responsive">
        <table class="table table-vcenter card-table">
          <thead>
            <tr>
              <th>策略</th><th>状态</th><th>区间</th><th>收益</th><th>轮次</th>
            </tr>
          </thead>
          <tbody id="latest-grids"></tbody>
        </table>
      </div>
    </div>
  </div>
  <div class="col-lg-4">
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">最新订单</h3>
        <div class="card-actions">
          <button class="btn btn-outline-secondary btn-sm" id="refresh-dashboard">
            <i class="ti ti-refresh"></i>
          </button>
        </div>
      </div>
      <div class="list-group list-group-flush" id="latest-orders"></div>
    </div>
  </div>
</div>
"""
    script = """
      async function loadDashboard() {
        const [grids, accountSummary, orders] = await Promise.all([
          api("/api/contract-grids"),
          api("/api/accounts/summary"),
          api("/api/orders?limit=8"),
        ]);
        q("#running-count").textContent = grids.summary.running_count;
        q("#invested-total").textContent = money(grids.summary.total_invested_usdt);
        q("#grid-profit-total").textContent = money(grids.summary.total_grid_profit_usdt);
        q("#account-equity").textContent = money(accountSummary.total_equity_usdt || accountSummary.total_balance_usdt);

        const gridRows = grids.items.slice(0, 8).map((grid) => `
          <tr>
            <td>
              <div class="fw-semibold">${escapeHtml(grid.name)}</div>
              <div class="text-secondary small">${escapeHtml(grid.symbol)} · ${escapeHtml(grid.direction)}</div>
            </td>
            <td>${badge(grid.status)}</td>
            <td>${escapeHtml(grid.price_range)}</td>
            <td>${escapeHtml(grid.grid_profit_usdt)}</td>
            <td>${escapeHtml(grid.current_round)}</td>
          </tr>
        `).join("");
        q("#latest-grids").innerHTML = gridRows || `<tr><td colspan="5" class="text-secondary">暂无策略</td></tr>`;

        q("#latest-orders").innerHTML = orders.items.slice(0, 8).map((order) => `
          <div class="list-group-item">
            <div class="row align-items-center">
              <div class="col">
                <div class="fw-semibold">${escapeHtml(order.symbol)} ${escapeHtml(order.side)}</div>
                <div class="text-secondary small">${escapeHtml(order.qty)} @ ${escapeHtml(order.price)}</div>
              </div>
              <div class="col-auto">${badge(order.status)}</div>
            </div>
          </div>
        `).join("") || `<div class="list-group-item text-secondary">暂无订单</div>`;
      }

      q("#refresh-dashboard").addEventListener("click", () => void loadDashboard());
      loadDashboard().catch((error) => {
        q("#latest-grids").innerHTML = `<tr><td colspan="5" class="text-danger">${escapeHtml(error.message)}</td></tr>`;
      });
"""
    return _layout("控制台", "dashboard", body, script)


@router.get("/grids", response_class=HTMLResponse)
async def grids_page() -> str:
    body = """
<div class="row row-cards">
  <div class="col-12">
    <div class="row row-cards mb-3">
      <div class="col-sm-4"><div class="card card-sm"><div class="card-body"><div class="subheader">运行中</div><div class="h2" id="grid-running">-</div></div></div></div>
      <div class="col-sm-4"><div class="card card-sm"><div class="card-body"><div class="subheader">投入资金</div><div class="h2" id="grid-invested">-</div></div></div></div>
      <div class="col-sm-4"><div class="card card-sm"><div class="card-body"><div class="subheader">网格收益</div><div class="h2" id="grid-profit">-</div></div></div></div>
    </div>
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">策略列表</h3>
        <div class="card-actions">
          <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#grid-modal">
            <i class="ti ti-plus"></i> 新增网格
          </button>
          <button class="btn btn-outline-secondary btn-sm" id="refresh-grids"><i class="ti ti-refresh"></i> 刷新</button>
        </div>
      </div>
      <div class="table-responsive">
        <table class="table table-vcenter card-table">
          <thead>
            <tr>
              <th>策略</th><th>状态</th><th>价格区间</th><th>挂单</th><th>收益</th><th class="w-1">操作</th>
            </tr>
          </thead>
          <tbody id="grid-list"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>
<div class="modal modal-blur fade" id="grid-modal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-centered" role="document">
    <form class="modal-content" id="grid-form">
      <div class="modal-header">
        <h5 class="modal-title">新增 MSX 网格</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <div class="mb-3">
          <label class="form-label">策略名称</label>
          <input class="form-control" id="grid-name" required maxlength="128" value="BTCUSDT 中性网格" />
        </div>
        <div class="row">
          <div class="col-md-6 mb-3">
            <label class="form-label">交易对</label>
            <input class="form-control" id="grid-symbol" required value="BTCUSDT" />
          </div>
          <div class="col-md-6 mb-3">
            <label class="form-label">方向</label>
            <select class="form-select" id="grid-direction">
              <option value="neutral">中性</option>
              <option value="long_bias">偏多</option>
              <option value="short_bias">偏空</option>
            </select>
          </div>
        </div>
        <div class="row">
          <div class="col-md-6 mb-3">
            <label class="form-label">间距模式</label>
            <select class="form-select" id="grid-spacing-mode">
              <option value="geometric">等比</option>
              <option value="arithmetic">等差</option>
            </select>
          </div>
          <div class="col-md-6 mb-3">
            <label class="form-label">杠杆</label>
            <input class="form-control" id="grid-leverage" type="number" min="1" step="1" value="2" />
          </div>
        </div>
        <div class="row">
          <div class="col-md-6 mb-3">
            <label class="form-label">保证金 USDT</label>
            <input class="form-control" id="grid-margin" type="number" min="0" step="0.01" value="100" />
          </div>
          <div class="col-md-6 mb-3">
            <label class="form-label">网格数量</label>
            <input class="form-control" id="grid-levels" type="number" min="1" step="1" value="10" />
          </div>
        </div>
        <div class="row">
          <div class="col-md-4 mb-3">
            <label class="form-label">下边界</label>
            <input class="form-control" id="grid-lower" type="number" min="0" step="0.0001" value="90" />
          </div>
          <div class="col-md-4 mb-3">
            <label class="form-label">基准价</label>
            <input class="form-control" id="grid-base-price" type="number" min="0" step="0.0001" value="100" />
          </div>
          <div class="col-md-4 mb-3">
            <label class="form-label">上边界</label>
            <input class="form-control" id="grid-upper" type="number" min="0" step="0.0001" value="110" />
          </div>
        </div>
        <div class="row">
          <div class="col-md-6 mb-3">
            <label class="form-label">单格数量</label>
            <input class="form-control" id="grid-order-qty" type="number" min="0" step="0.00000001" placeholder="自动计算" />
          </div>
          <div class="col-md-6 mb-3">
            <label class="form-label">最大亏损 USDT</label>
            <input class="form-control" id="grid-max-loss" type="number" min="0" step="0.01" value="0" />
          </div>
        </div>
        <label class="form-check">
          <input class="form-check-input" id="grid-start-now" type="checkbox" />
          <span class="form-check-label">创建后立即启动</span>
        </label>
        <div class="form-hint mt-2" id="grid-form-message"></div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">取消</button>
        <button class="btn btn-primary" type="submit"><i class="ti ti-plus"></i> 创建策略</button>
      </div>
    </form>
  </div>
</div>
"""
    script = """
      const gridState = { items: [] };

      function gridPayload() {
        return {
          name: q("#grid-name").value.trim(),
          exchange: "MSX",
          market: "futures",
          symbol: q("#grid-symbol").value.trim().toUpperCase(),
          direction: q("#grid-direction").value,
          leverage: q("#grid-leverage").value,
          margin_usdt: q("#grid-margin").value,
          spacing_mode: q("#grid-spacing-mode").value,
          grid_levels: q("#grid-levels").value,
          order_qty: q("#grid-order-qty").value || "0",
          stop_loss_price: q("#grid-lower").value,
          take_profit_price: q("#grid-upper").value,
          max_loss_usdt: q("#grid-max-loss").value,
          base_price: q("#grid-base-price").value,
          start_immediately: q("#grid-start-now").checked,
        };
      }

      async function refreshGrids() {
        const payload = await api("/api/contract-grids");
        gridState.items = payload.items;
        q("#grid-running").textContent = payload.summary.running_count;
        q("#grid-invested").textContent = money(payload.summary.total_invested_usdt);
        q("#grid-profit").textContent = money(payload.summary.total_grid_profit_usdt);
        renderGrids();
      }

      function renderGrids() {
        q("#grid-list").innerHTML = gridState.items.map((grid) => `
          <tr data-id="${grid.id}">
            <td>
              <div class="fw-semibold">${escapeHtml(grid.name)}</div>
              <div class="text-secondary small">${escapeHtml(grid.exchange)} / ${escapeHtml(grid.symbol)} · ${escapeHtml(grid.direction)}</div>
            </td>
            <td>${badge(grid.status)}</td>
            <td>
              <div>${escapeHtml(grid.price_range)}</div>
              <div class="text-secondary small">基准 ${escapeHtml(grid.base_price)} · 第 ${escapeHtml(grid.current_round)} 轮</div>
            </td>
            <td>
              <div>买 ${escapeHtml(grid.lower_order_price)}</div>
              <div class="text-secondary small">卖 ${escapeHtml(grid.upper_order_price)} · ${escapeHtml(grid.order_qty)}</div>
            </td>
            <td>
              <div>${escapeHtml(grid.grid_profit_usdt)}</div>
              <div class="text-secondary small">${escapeHtml(grid.total_return_pct)}</div>
            </td>
            <td>
              <div class="btn-list flex-nowrap">
                ${grid.status === "running"
                  ? '<button class="btn btn-outline-warning btn-sm" data-action="pause"><i class="ti ti-player-pause"></i></button>'
                  : '<button class="btn btn-outline-primary btn-sm" data-action="start"><i class="ti ti-player-play"></i></button>'}
                ${grid.status === "paused"
                  ? '<button class="btn btn-outline-primary btn-sm" data-action="resume"><i class="ti ti-refresh"></i></button>'
                  : ""}
                <button class="btn btn-outline-danger btn-sm" data-action="stop"><i class="ti ti-square"></i></button>
                <button class="btn btn-outline-secondary btn-sm" data-action="delete"><i class="ti ti-trash"></i></button>
              </div>
            </td>
          </tr>
        `).join("") || `<tr><td colspan="6" class="text-secondary">暂无网格策略</td></tr>`;
      }

      q("#grid-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
          await api("/api/contract-grids", { method: "POST", body: JSON.stringify(gridPayload()) });
          q("#grid-form-message").textContent = "已创建";
          bootstrap.Modal.getOrCreateInstance(q("#grid-modal")).hide();
          event.target.reset();
          await refreshGrids();
        } catch (error) {
          q("#grid-form-message").textContent = error.message;
        }
      });

      q("#refresh-grids").addEventListener("click", () => void refreshGrids());
      q("#grid-list").addEventListener("click", async (event) => {
        const button = event.target.closest("button");
        const row = event.target.closest("tr");
        if (!button || !row) return;
        const grid = gridState.items.find((item) => item.id === Number(row.dataset.id));
        if (!grid) return;
        const action = button.dataset.action;
        if (action === "delete" && !window.confirm(`确认删除策略 ${grid.name}？`)) return;
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
        q("#grid-list").innerHTML = `<tr><td colspan="6" class="text-danger">${escapeHtml(error.message)}</td></tr>`;
      });
"""
    return _layout("网格策略", "grids", body, script)


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page() -> str:
    body = """
<div class="row row-cards">
  <div class="col-12">
    <div class="row row-cards mb-3">
      <div class="col-sm-4"><div class="card card-sm"><div class="card-body"><div class="subheader">总权益</div><div class="h2" id="summary-equity">-</div></div></div></div>
      <div class="col-sm-4"><div class="card card-sm"><div class="card-body"><div class="subheader">启用账户</div><div class="h2" id="summary-enabled">-</div></div></div></div>
      <div class="col-sm-4"><div class="card card-sm"><div class="card-body"><div class="subheader">正常账户</div><div class="h2" id="summary-healthy">-</div></div></div></div>
    </div>
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">账户列表</h3>
        <div class="card-actions">
          <button class="btn btn-primary btn-sm" id="new-account" data-bs-toggle="modal" data-bs-target="#account-modal">
            <i class="ti ti-plus"></i> 新增账户
          </button>
          <button class="btn btn-outline-secondary btn-sm" id="refresh-accounts"><i class="ti ti-refresh"></i> 刷新</button>
        </div>
      </div>
      <div class="table-responsive">
        <table class="table table-vcenter card-table">
          <thead>
            <tr>
              <th>账户</th><th>状态</th><th>资金</th><th>凭据</th><th class="w-1">操作</th>
            </tr>
          </thead>
          <tbody id="account-list"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>
<div class="modal modal-blur fade" id="account-modal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered" role="document">
    <form class="modal-content" id="account-form">
      <div class="modal-header">
        <h5 class="modal-title" id="form-title">新增 MSX 账户</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <input type="hidden" id="account-id" />
        <div class="mb-3">
          <label class="form-label">账户名称</label>
          <input class="form-control" id="account-name" required maxlength="128" autocomplete="off" />
        </div>
        <div class="mb-3">
          <label class="form-label">平台</label>
          <input class="form-control" id="account-exchange" value="MSX" disabled />
        </div>
        <div class="mb-3">
          <label class="form-label">API Key</label>
          <input class="form-control" id="api-key" autocomplete="off" />
        </div>
        <div class="mb-3">
          <label class="form-label">API Secret</label>
          <input class="form-control" id="api-secret" type="password" autocomplete="off" />
        </div>
        <div class="mb-3">
          <label class="form-label">备注</label>
          <input class="form-control" id="account-notes" maxlength="500" autocomplete="off" />
        </div>
        <div class="form-hint" id="form-message"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline-secondary" type="button" id="reset-form" data-bs-dismiss="modal">取消</button>
        <button class="btn btn-primary" type="submit"><i class="ti ti-device-floppy"></i> 保存</button>
      </div>
    </form>
  </div>
</div>
"""
    script = """
      const state = { accounts: [] };

      function accountPayload() {
        const id = q("#account-id").value;
        const apiKey = q("#api-key").value.trim();
        const apiSecret = q("#api-secret").value.trim();
        const payload = {
          name: q("#account-name").value.trim(),
          exchange: "MSX",
          notes: q("#account-notes").value.trim(),
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

      async function refresh() {
        const [summary, accounts] = await Promise.all([
          api("/api/accounts/summary"),
          api("/api/accounts"),
        ]);
        state.accounts = accounts.items;
        q("#summary-equity").textContent = money(summary.total_equity_usdt || summary.total_balance_usdt);
        q("#summary-enabled").textContent = summary.enabled_account_count;
        q("#summary-healthy").textContent = summary.healthy_account_count;
        renderAccounts();
      }

      function credentialText(account) {
        const fields = account.credential_summary.fields || {};
        return fields.api_key ? `Key ${fields.api_key}` : "未显示凭据";
      }

      function renderAccounts() {
        q("#account-list").innerHTML = state.accounts.map((account) => `
          <tr data-id="${account.id}">
            <td>
              <div class="fw-semibold">${escapeHtml(account.name)}</div>
              <div class="text-secondary small">${escapeHtml(account.account_type).toUpperCase()} / ${escapeHtml(account.exchange)}</div>
            </td>
            <td>${badge(account.status)}</td>
            <td>
              <div>${money(account.latest_balance_usdt)}</div>
              <div class="text-secondary small">权益 ${escapeHtml(account.latest_equity_usdt)}</div>
            </td>
            <td>
              <div>${escapeHtml(credentialText(account))}</div>
              <div class="text-secondary small">${escapeHtml(account.last_error || account.last_checked_at || "未验证")}</div>
            </td>
            <td>
              <div class="btn-list flex-nowrap">
                <button class="btn btn-outline-primary btn-sm" data-action="edit"><i class="ti ti-pencil"></i></button>
                <button class="btn btn-outline-info btn-sm" data-action="test"><i class="ti ti-plug-connected"></i></button>
                <button class="btn btn-outline-warning btn-sm" data-action="toggle"><i class="ti ti-power"></i></button>
                <button class="btn btn-outline-danger btn-sm" data-action="delete"><i class="ti ti-trash"></i></button>
              </div>
            </td>
          </tr>
        `).join("") || `<tr><td colspan="5" class="text-secondary">暂无账户</td></tr>`;
      }

      function resetForm() {
        q("#account-id").value = "";
        q("#account-name").value = "";
        q("#api-key").value = "";
        q("#api-secret").value = "";
        q("#account-notes").value = "";
        q("#form-title").textContent = "新增 MSX 账户";
        q("#form-message").textContent = "";
      }

      q("#account-form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const id = q("#account-id").value;
        const method = id ? "PATCH" : "POST";
        const path = id ? `/api/accounts/${id}` : "/api/accounts";
        try {
          await api(path, { method, body: JSON.stringify(accountPayload()) });
          q("#form-message").textContent = "已保存";
          bootstrap.Modal.getOrCreateInstance(q("#account-modal")).hide();
          resetForm();
          await refresh();
        } catch (error) {
          q("#form-message").textContent = error.message;
        }
      });

      q("#new-account").addEventListener("click", resetForm);
      q("#reset-form").addEventListener("click", resetForm);
      q("#refresh-accounts").addEventListener("click", () => void refresh());
      q("#account-list").addEventListener("click", async (event) => {
        const button = event.target.closest("button");
        const row = event.target.closest("tr");
        if (!button || !row) return;
        const account = state.accounts.find((item) => item.id === Number(row.dataset.id));
        if (!account) return;
        const action = button.dataset.action;
        if (action === "edit") {
          q("#account-id").value = account.id;
          q("#account-name").value = account.name;
          q("#account-notes").value = account.notes || "";
          q("#api-key").value = "";
          q("#api-secret").value = "";
          q("#form-title").textContent = "编辑 MSX 账户";
          bootstrap.Modal.getOrCreateInstance(q("#account-modal")).show();
          return;
        }
        if (action === "delete" && !window.confirm(`确认删除账户 ${account.name}？`)) return;
        const toggleAction = account.enabled && account.status !== "disabled" ? "disable" : "enable";
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
        q("#account-list").innerHTML = `<tr><td colspan="5" class="text-danger">${escapeHtml(error.message)}</td></tr>`;
      });
"""
    return _layout("账户管理", "accounts", body, script)
