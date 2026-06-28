# quant_msx 文档索引

## API

- [MSX API 汇总](api.md)：官方 REST / WebSocket 接口、参数表和 demo 汇总。

## 架构

- [01 产品需求](architecture/01_product_requirements.md)
- [02 系统架构](architecture/02_system_architecture.md)
- [03 领域模型](architecture/03_domain_models.md)
- [04 交易执行与风控](architecture/04_execution_risk.md)
- [05 FastAPI Web 控制台](architecture/05_web_ui.md)
- [06 交付计划](architecture/06_delivery_plan.md)

## 策略

- [网格策略设计](strategy/grid_strategy.md)

## 当前原则

- 先做 MSX 单平台闭环，再做多交易所扩展。
- 先做网格策略真实运行所需的最小闭环，再做复杂组合策略。
- 所有真实交易命令必须通过 `OrderService`、`RiskService` 和审计日志。
- REST 与 WebSocket 接入细节只允许存在于 `app/broker`。
- 策略服务不直接拼签名、不直接调用 HTTP、不直接读写密钥。
