# 系统架构

## 1. 总体架构

系统采用单仓库、轻量单服务架构：

- `api`: FastAPI REST API，服务 Web 控制台和运维命令。
- `web`: FastAPI 托管的 HTML 页面和静态资源。
- `engine`: 网格策略运行与状态机。
- `broker`: MSX REST / WebSocket 接入层。
- `services`: 行情、账户、订单、风控、对账、策略服务。
- `storage`: SQLite 持久化与仓储。

首期保持一个后端进程，降低调试成本。后续可以拆分为 `api-server` 与 `engine-worker`。

## 2. 技术栈

后端：

- Python 3.11
- FastAPI
- Pydantic 2
- SQLAlchemy 2
- httpx
- websockets
- SQLite
- loguru

Web 控制台：

- FastAPI `HTMLResponse`
- FastAPI `StaticFiles`
- 原生 JavaScript 或 HTMX/Alpine.js 可选
- 无独立 Node 构建链

## 3. 目录职责

```text
app/
  broker/        # MSX REST / WS 接入，签名、重试、订阅
  api/           # FastAPI route，只做参数接收和响应
  core/          # 配置、日志、运行时、服务注册
  domain/        # Pydantic schema、状态枚举、领域对象
  services/      # 策略、行情、订单、账户、风控、对账
  storage/       # SQLAlchemy model、session、repository
  web/           # FastAPI 托管页面、静态资源、轻量交互脚本
```

## 4. 核心模块

### 4.1 MsxRestClient

职责：

- 生成 MSX 签名。
- 统一追加认证头。
- 封装现货和合约 REST 路径。
- 将 HTTP 错误和业务错误归一化。

不负责：

- 策略决策。
- 风控判断。
- 数据库存储。

### 4.2 MsxWebSocketClient

职责：

- 管理 spot / futures WS 连接。
- 发送订阅、取消订阅和 ping。
- 断线重连后恢复订阅。
- 将原始消息交给上层服务。

### 4.3 MarketDataService

职责：

- 维护 ticker、BBO、order book、kline 快照。
- 给策略服务提供最新价格和深度。
- 在 WebSocket 异常时支持 REST 快照补偿。

### 4.4 GridService

职责：

- 管理网格策略生命周期。
- 计算上下挂单价格。
- 处理成交后撤对侧、更新基准价、进入下一轮。
- 生成订单命令，但不直接调用 MSX。

### 4.5 OrderService

职责：

- 统一创建、撤销、查询订单。
- 调用 `RiskService` 做交易前校验。
- 记录审计和订单本地状态。
- 通过 `MsxRestClient` 执行真实交易。

### 4.6 RiskService

职责：

- 交易开关检查。
- 策略级仓位、亏损、边界、频率控制。
- 全局 kill switch。
- 异常状态下阻断新订单。

### 4.7 ReconciliationService

职责：

- 启动时恢复运行中策略。
- 定期查询当前委托、历史订单、成交和持仓。
- 修复本地状态与 MSX 状态偏差。

## 5. 启动流程

1. 加载配置。
2. 初始化日志。
3. 初始化数据库。
4. 初始化 MSX REST / WS broker 接入层。
5. 拉取产品、价格精度、账户配置。
6. 恢复运行中网格。
7. 建立 WebSocket 行情和订单订阅。
8. 开放 API。

## 6. 交易命令流程

1. FastAPI Web 页面、API 客户端或策略服务发起交易意图。
2. `OrderService` 构造订单命令。
3. `RiskService` 做交易开关、精度、仓位、价格边界检查。
4. `MsxRestClient` 签名并提交订单。
5. `OrderService` 写入本地订单和审计事件。
6. WebSocket 或 REST 补同步更新最终状态。
