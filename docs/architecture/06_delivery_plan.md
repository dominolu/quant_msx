# 交付计划

## Phase 0：项目初始化

状态：已开始

- 初始化后端目录。
- 初始化 FastAPI Web、脚本、数据目录。
- 整理 MSX API 文档。
- 建立产品、架构和策略文档。
- 提供健康检查接口。

## Phase 1：MSX 只读接入

- 实现 MSX REST 签名。
- 查询产品、ticker、depth、kline、price steps。
- 建立 spot / futures WebSocket 公共行情连接。
- 建立 MarketDataService 快照缓存。
- 增加只读 API：行情、产品、连接状态。

## Phase 2：网格 demo 闭环

- 实现 GridStrategy / GridOrder / GridFill / GridEvent 表。
- 实现网格创建、列表、详情、启动、暂停、恢复、停止接口。
- demo 模式下模拟挂单、成交、撤对侧、重置下一轮。
- FastAPI Web 页面接入网格列表和详情。

## Phase 3：真实交易接入

- 实现现货与合约下单、撤单、订单查询。
- 接入 RiskService 下单前检查。
- 真实网格首轮下单。
- WebSocket 或 REST 补同步订单状态。
- 暂停时真实撤单。

## Phase 4：恢复与风控

- 服务重启恢复运行中网格。
- 当前委托、历史订单、成交、持仓对账。
- 最大亏损、止盈止损、价格边界、全局 kill switch。
- 异常网格自动转入 `error` 并阻断新订单。

## Phase 5：Web 控制台完善

- FastAPI 托管的网格详情页。
- 收益曲线和订单时间线。
- 系统状态页。
- 策略重配。
- 操作审计展示。

## Phase 6：运行与部署

- Dockerfile 和 docker-compose。
- 远程部署脚本。
- 日志轮转。
- 备份和恢复文档。
- 实盘 checklist。
