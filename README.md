# quant_msx

MSX 专用量化交易平台，首期以现货/合约网格策略为核心，后续扩展行情监控、账户风控、策略编排和交易运维控制台。


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

## 项目规划

| 状态 | 模块 | 规划内容 |
| --- | --- | --- |
| ✅ | MSX API 文档 | 整理官方 REST / WebSocket 接口说明、参数、响应和 demo 到 `docs/api.md`。 |
| ✅ | 项目骨架 | 初始化 FastAPI 单体应用、领域层、服务层、存储层、broker 层、Web 静态资源和脚本目录。 |
| ✅ | MSX broker 接入 | 实现签名、REST 端点表、HTTP transport、WebSocket 订阅、错误归一化和基础回归测试。 |
| ✅ | 市场数据基础能力 | 支持 ticker、depth、kline、futures orderbook、本地 order book 快照和增量维护。 |
| ⬜ | 账户与订单服务 | 对接资产、持仓、当前委托、历史订单、成交明细，并接入统一订单服务。 |
| ⬜ | 网格策略引擎 | 支持策略创建、启动、暂停、恢复、停止、重配、状态持久化和异常恢复。 |
| ⬜ | 风控模块 | 实现最大仓位、最大亏损、价格边界、下单频率、kill switch 和实盘保护开关。 |
| ⬜ | FastAPI 控制台 | 由 FastAPI 直接托管策略列表、详情、订单、成交、事件和收益统计页面。 |
| ⬜ | 实盘运行闭环 | 完成配置校验、日志审计、运行监控、部署脚本和真实账户灰度验证。 |

## 文档入口

- [MSX API 汇总](docs/api.md)
- [项目文档索引](docs/README.md)
- [产品需求](docs/architecture/01_product_requirements.md)
- [系统架构](docs/architecture/02_system_architecture.md)
- [网格策略设计](docs/strategy/grid_strategy.md)
- [交付计划](docs/architecture/06_delivery_plan.md)
