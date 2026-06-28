# 网格策略设计

## 1. 策略模型

首期采用“单中心、双边挂单、成交后重置”的网格模型：

- 一个网格实例只管理一个 MSX 交易对。
- 每轮最多保持两张有效挂单：
  - 下方买单，价格低于基准价。
  - 上方卖单，价格高于基准价。
- 启动时使用最新行情作为基准价。
- 成交后使用成交价作为新的基准价。
- 一侧成交后必须撤销另一侧未成交订单。
- 撤销完成后再按新基准价挂出下一轮订单。

## 2. 适用市场

### 2.1 现货

适合低杠杆或无杠杆网格。

注意点：

- 买单需要可用 quote 资产。
- 卖单需要可用 base 资产。
- 中性网格可能需要初始持仓或资金预分配。

### 2.2 合约

适合 U 本位合约网格。

注意点：

- 必须确认保证金模式和杠杆。
- 必须限制最大净持仓。
- 必须监控强平风险。
- funding fee 应计入收益统计。

## 3. 网格间距

支持两种模式：

- `geometric`: 百分比间距。
- `arithmetic`: 固定价格间距。

首期优先实现 `geometric`。

计算示例：

```text
base_price = 100
grid_spacing_pct = 0.5
lower_order_price = 100 * (1 - 0.5 / 100) = 99.5
upper_order_price = 100 * (1 + 0.5 / 100) = 100.5
```

最终下单价格必须按 MSX price steps 合法化。

## 4. 状态机

```text
draft
  -> running
running
  -> paused
  -> stopping
  -> error
paused
  -> running
  -> stopped
stopping
  -> stopped
error
  -> paused
  -> stopped
```

## 5. 每轮执行流程

1. 获取最新基准价。
2. 计算上下挂单价格。
3. 按价格精度和数量精度合法化。
4. 风控检查。
5. 提交下方订单。
6. 提交上方订单。
7. 等待成交回报。
8. 一侧成交后记录成交。
9. 撤销对侧订单。
10. 更新基准价。
11. 进入下一轮。

## 6. 异常处理

### 6.1 下单失败

- 如果第一张订单失败：本轮不继续。
- 如果第二张订单失败：撤销第一张订单。
- 写入事件并转入 `error` 或 `paused`。

### 6.2 撤单失败

- 立即触发 REST 补同步。
- 如果订单已成交，则按成交处理。
- 如果订单仍 open，重试撤单。
- 超过重试次数转入 `error`。

### 6.3 WebSocket 断线

- 暂停依赖 WS 的成交触发。
- 重连后恢复订阅。
- 立即执行 REST 对账。

## 7. 收益口径

- `grid_profit`: 已配对网格成交收益。
- `unmatched_profit`: 未配对持仓按当前价格估算收益。
- `realized_pnl`: 交易所已实现盈亏。
- `unrealized_pnl`: 当前持仓未实现盈亏。
- `funding_fee`: 合约资金费。
- `total_pnl`: 上述口径汇总后的策略总收益。

首期先持久化成交与订单，收益统计可先按本地成交估算，后续接入交易所 PnL 字段校正。

## 8. 参数建议

创建参数：

- `market`
- `symbol`
- `direction`
- `margin_mode`
- `leverage`
- `margin_usdt`
- `spacing_mode`
- `grid_spacing_pct`
- `grid_levels`
- `order_qty`
- `max_position_qty`
- `stop_loss_price`
- `take_profit_price`
- `max_loss_usdt`
- `start_immediately`

运行参数：

- `base_price`
- `lower_order_price`
- `upper_order_price`
- `current_position_qty`
- `round_no`
- `health`
- `rest_sync_count`
