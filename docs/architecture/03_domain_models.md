# 领域模型

## 1. GridStrategy

网格策略实例。

核心字段：

- `id`
- `grid_key`
- `name`
- `market`: `spot` 或 `futures`
- `symbol`
- `status`: `draft`、`running`、`paused`、`stopping`、`stopped`、`error`
- `direction`: `neutral`、`long_bias`、`short_bias`
- `margin_mode`
- `leverage`
- `spacing_mode`
- `grid_spacing_pct`
- `grid_levels`
- `order_qty`
- `max_position_qty`
- `base_price`
- `lower_order_price`
- `upper_order_price`
- `current_position_qty`
- `health`

## 2. GridOrder

策略关联订单。

核心字段：

- `grid_id`
- `round_no`
- `market`
- `symbol`
- `exchange_order_id`
- `client_order_id`
- `side`
- `price`
- `qty`
- `filled_qty`
- `avg_fill_price`
- `fee`
- `status`
- `role`: `lower` 或 `upper`

## 3. GridFill

策略成交记录。

核心字段：

- `grid_id`
- `order_id`
- `exchange_trade_id`
- `side`
- `price`
- `qty`
- `fee`
- `base_price_before`
- `base_price_after`
- `created_at`

## 4. GridEvent

策略事件和审计日志。

事件类型：

- `created`
- `started`
- `order_submitted`
- `order_filled`
- `opposite_order_cancelled`
- `round_reset`
- `paused`
- `resumed`
- `stopped`
- `risk_rejected`
- `sync_repaired`
- `error`

## 5. MarketSnapshot

行情快照。

核心字段：

- `market`
- `symbol`
- `bid_price`
- `bid_qty`
- `ask_price`
- `ask_qty`
- `last_price`
- `source`
- `updated_at`

## 6. AccountSnapshot

账户资产和持仓快照。

核心字段：

- `market`
- `asset`
- `available`
- `locked`
- `equity`
- `position_qty`
- `entry_price`
- `unrealized_pnl`
- `updated_at`
