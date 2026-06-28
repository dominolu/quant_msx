from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


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
