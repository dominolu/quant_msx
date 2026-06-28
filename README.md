# quant_msx

MSX 专用量化交易平台，首期以现货/合约网格策略为核心，后续扩展行情监控、账户风控、策略编排和交易运维控制台。

本项目参考 `/Users/dominolu/dev/gate_arb` 的轻量单仓库架构，但交易接入、策略模型和风控边界按 MSX API 重新设计。

## 当前状态

- 已整理 MSX 官方接口文档：[docs/api.md](docs/api.md)
- 已初始化后端分层目录
- 已初始化 FastAPI 内置 Web 控制台骨架和脚本目录占位
- 已建立首批产品、架构和策略文档

当前仍不包含：

- 真实下单
- WebSocket 订单回报处理
- 数据库模型实现
- 完整 Web 控制台页面实现
- 实盘运行配置

## 快速启动

后端骨架：

```bash
cp .env.example .env
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

检查接口：

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
curl http://127.0.0.1:8000/api/system/info
```

## 目录

```text
quant_msx/
  app/
    broker/        # MSX REST / WebSocket broker 接入
    api/           # FastAPI 路由层
    core/          # 配置、日志、运行时、服务注册
    domain/        # 领域模型和 API schema
    services/      # 策略、行情、账户、订单、风控服务
    storage/       # 数据库模型与仓储
  data/            # 本地运行数据、配置与日志
  docs/            # 产品、架构、接口、策略文档
  app/web/         # FastAPI 内置 Web 控制台和静态资源
  scripts/         # 运维和一次性脚本
  tests/           # 单元测试与集成测试
```

## 首期模块

- MSX broker 接入：签名、REST 请求、WebSocket 订阅、错误归一化。
- 市场数据：ticker、depth、kline、order book 本地维护。
- 账户与订单：资产、持仓、当前委托、历史订单、成交明细。
- 网格策略：创建、启动、暂停、恢复、停止、重配、恢复运行。
- 风控：最大仓位、最大亏损、价格边界、下单频率、kill switch。
- 控制台：由 FastAPI 直接托管策略列表、详情、订单、成交、事件和收益统计页面。

## 文档入口

- [MSX API 汇总](docs/api.md)
- [项目文档索引](docs/README.md)
- [产品需求](docs/architecture/01_product_requirements.md)
- [系统架构](docs/architecture/02_system_architecture.md)
- [网格策略设计](docs/strategy/grid_strategy.md)
- [交付计划](docs/architecture/06_delivery_plan.md)
