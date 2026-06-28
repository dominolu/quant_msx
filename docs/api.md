# MSX API 接口文档整理

来源：[https://developers.msx.com/](https://developers.msx.com/)（站点 canonical/静态内容来自 [https://msx-docs.pages.dev/](https://msx-docs.pages.dev/)）。
整理日期：2026-06-28。本文按官方 sitemap 页面汇总接口说明、参数表、响应格式、WebSocket 说明和示例 demo。

## 目录

- 公共模块（Next V2.0）：7 页
- 现货接口（Next V2.0）：22 页
- 合约接口（Next V2.0）：24 页
- Legacy V1.0：9 页

## 公共模块（Next V2.0）

<!-- source: https://developers.msx.com/docs/next/common/authentication -->

## 认证

### 请求头

所有请求必须包含以下 HTTP Header：

| Header               | 说明                  |
| -------------------- | --------------------- |
| `ACCESS-KEY`       | API Key（在平台申请） |
| `ACCESS-SIGN`      | 签名字符串            |
| `ACCESS-TIMESTAMP` | 请求时间戳（毫秒）    |

### 签名算法

使用 **HMAC-SHA256** 签名 + **Base64** 编码（业内标准），签名字符串生成规则：

#### POST 请求签名

1. 将时间戳（毫秒）转为字符串
2. 拼接签名字符串：`timestamp + method + requestPath + body`
3. 使用 secretKey 对拼接字符串进行 HMAC-SHA256 签名
4. 将签名结果进行 Base64 编码

#### GET 请求签名

1. 将 Query 参数按 key 字母序排序
2. 拼接成 `?key1=value1&key2=value2` 格式
3. 拼接签名字符串：`timestamp + method + requestPath + queryString`
4. 使用 secretKey 对拼接字符串进行 HMAC-SHA256 签名
5. 将签名结果进行 Base64 编码

### 签名示例

#### POST 请求示例

```
请求体: {"symbol":"AAPL","side":"buy","type":"limit","price":"185.50","quantity":"1000"
}
时间戳: 1705737600000
请求路径: /api/v1/stock/open-api/order
方法: POST

签名字符串 = "1705737600000" + "POST" + "/api/v1/stock/open-api/order" + '{"symbol":"AAPL","side":"buy","type":"limit","price":"185.50","quantity":"1000"
}'
签名 = Base64(HMAC-SHA256(签名字符串, secretKey))
```

#### GET 请求示例

```
参数: symbol=XSM, limit=20
时间戳: 1705737600000
请求路径: /api/v1/stock/open-api/depth
方法: GET

queryString = "?limit=20&symbol=XSM"  (按key排序)
签名字符串 = "1705737600000" + "GET" + "/api/v1/stock/open-api/depth" + "?limit=20&symbol=XSM"
签名 = Base64(HMAC-SHA256(签名字符串, secretKey))
```

### 时间戳校验

- 时间戳必须在服务器时间 ±30秒 范围内
- 超出范围将返回 `401 Unauthorized`

来源：https://developers.msx.com/docs/next/common/authentication

---

<!-- source: https://developers.msx.com/docs/next/common/changelog -->

## 更新日志

### 最近更新： 2026-03-30

### 2026-03-30

- 添加更新日志

来源：https://developers.msx.com/docs/next/common/changelog

---

<!-- source: https://developers.msx.com/docs/next/common/overview -->

## 概述

本平台为做市商和量化交易者提供程序化交易接口，支持现货和合约两套独立的 Open API。

### API 模块

| 模块          | 基础路径                     | 说明                                |
| ------------- | ---------------------------- | ----------------------------------- |
| 现货 Open API | `/api/v1/stock/open-api`   | 提供现货交易和市场数据接口          |
| 合约 Open API | `/api/v1/futures/open-api` | 提供合约市场数据接口 + 订单操作接口 |

### 通用规则

| 项目     | 说明                                                 |
| -------- | ---------------------------------------------------- |
| 请求方式 | 交易和查询接口使用`POST`，市场数据接口使用 `GET` |
| 数据格式 | JSON                                                 |
| 认证方式 | HMAC-SHA256 + Base64 签名（业内标准）                |
| API Key  | 现货和合约共享同一套 API Key                         |
| 限流计数 | 现货和合约限流**独立计数**                     |

来源：https://developers.msx.com/docs/next/common/overview

---

<!-- source: https://developers.msx.com/docs/next/common/rate-limit -->

## 限流规则

| 用户类型 | RPS（每秒请求数） | RPM（每分钟请求数） |
| -------- | ----------------- | ------------------- |
| 普通用户 | 10                | 300                 |
| 做市商   | 100               | 3000                |

### 重要说明

- 现货 Open API 和合约 Open API 的限流**独立计数**
- 例如：调用现货接口不会影响合约接口的限流配额，反之亦然
- 超出限制将返回 `429 Too Many Requests`

来源：https://developers.msx.com/docs/next/common/rate-limit

---

<!-- source: https://developers.msx.com/docs/next/common/response-format -->

## 通用响应格式

### 现货 Open API 响应格式

**成功响应**（code = 0）：

```
{
  "code": 0,
  "msg": "success",
  "data": { ... }
}
```

### 合约 Open API 响应格式

**成功响应**（code = 0）：

```
{
  "code": 0,
  "msg": "success",
  "data": { ... }
}
```

### 错误响应（通用）

```
{
  "code": 400,
  "message": "错误描述"
}
```

### 合约 HTTP 错误码

HTTP status 与 body code 相同。

| 错误码 | 说明                                                      |
| ------ | --------------------------------------------------------- |
| 400    | 参数错误 / 请求体读取失败                                 |
| 401    | 缺少鉴权参数 / 时间戳过期 / 签名验证失败 / 无效的 API Key |
| 403    | IP 不在白名单 / 该 API Key 无交易权限                     |
| 429    | 请求频率超限（每秒/每分钟）/ 下单频率超限                 |
| 500    | 内部错误                                                  |

### 合约业务错误码（HTTP 200）

业务错误以 HTTP 200 返回，通过 body 中的 `code` 字段区分。

| 错误码 | 说明                                       |
| ------ | ------------------------------------------ |
| 0      | 成功                                       |
| 1001   | 系统错误                                   |
| 3000   | 交易对不存在 / 对象不存在                  |
| 3004   | 第三方服务错误（K 线 / Ticker 查询失败等） |
| 8001   | 低于最小交易量                             |
| 8002   | 平仓委托失败，请检查持仓                   |
| 8003   | 平仓余额不足，请检查持仓与挂单             |
| 8004   | 委托订单创建失败                           |
| 8005   | 止盈止损订单创建失败                       |
| 8006   | 止盈止损订单将被立即触发                   |
| 8007   | 调整杠杆需要更多起始保证金                 |
| 8008   | 调整杠杆失败                               |
| 8009   | 切换保证金模式失败                         |
| 8010   | 有持仓，不支持调整保证金模式               |
| 8011   | 杠杆异常                                   |
| 8012   | 保证金模式异常                             |
| 8013   | 追加保证金失败                             |
| 8014   | 逐仓模式下有持仓，不支持调低杠杆           |
| 8015   | 可减少保证金不足                           |
| 8016   | 超过最大交易量                             |
| 8017   | 超过最大持仓量                             |
| 8018   | 保证金不足                                 |
| 8100   | 产品信息异常                               |

### 现货 HTTP 错误码

现货 API 无业务错误码，所有错误均以对应 HTTP 状态码返回，具体原因在 `msg` 字段中。

| 错误码 | 说明                                                                         |
| ------ | ---------------------------------------------------------------------------- |
| 400    | 参数错误 / 交易对不存在 / 下单撤单失败（余额不足等业务错误，具体原因见 msg） |
| 401    | 缺少鉴权参数 / 时间戳过期 / 签名验证失败 / 无效的 API Key                    |
| 403    | IP 不在白名单 / 无交易权限                                                   |
| 404    | 订单不存在                                                                   |
| 429    | 请求频率超限 / 下单频率超限                                                  |
| 500    | 内部错误 / K 线服务不可用                                                    |

来源：https://developers.msx.com/docs/next/common/response-format

---

<!-- source: https://developers.msx.com/docs/next/common/sign-code -->

## 签名代码示例

- Go
- Python
- JavaScript
- cURL

```
package main

import (
    "bytes"
    "crypto/hmac"
    "crypto/sha256"
    "encoding/base64"
    "encoding/json"
    "fmt"
    "net/http"
    "net/url"
    "sort"
    "strconv"
    "strings"
    "time"
)

const (
    APIKey    = "your_api_key"
    SecretKey = "your_secret_key"
    BaseURL   = "{域名}/api/v1/stock/open-api"
)

// sign 生成签名
func sign(method, requestPath, queryString, body string, timestamp int64) string {
    // 拼接签名字符串：timestamp + method + requestPath + queryString + body
    timestampStr := strconv.FormatInt(timestamp, 10)
    preHash := timestampStr + method + requestPath + queryString + body

    // HMAC-SHA256 签名
    mac := hmac.New(sha256.New, []byte(SecretKey))
    mac.Write([]byte(preHash))

    // Base64 编码
    return base64.StdEncoding.EncodeToString(mac.Sum(nil))
}

// request 发送 POST 请求
func request(endpoint string, params map[string]interface{}) (map[string]interface{}, error) {
    timestamp := time.Now().UnixMilli()
    requestPath := "/api/v1/stock/open-api" + endpoint

    body, _ := json.Marshal(params)
    signature := sign("POST", requestPath, "", string(body), timestamp)

    req, _ := http.NewRequest("POST", BaseURL+endpoint, bytes.NewBuffer(body))
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("ACCESS-KEY", APIKey)
    req.Header.Set("ACCESS-SIGN", signature)
    req.Header.Set("ACCESS-TIMESTAMP", strconv.FormatInt(timestamp, 10))

    client := &http.Client{Timeout: 30 * time.Second}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    return result, nil
}

// requestGET 发送 GET 请求
func requestGET(endpoint string, params map[string]interface{}) (map[string]interface{}, error) {
    timestamp := time.Now().UnixMilli()
    requestPath := "/api/v1/stock/open-api" + endpoint

    // 构造 query string
    keys := make([]string, 0, len(params))
    for k := range params {
        keys = append(keys, k)
    }
    sort.Strings(keys)

    queryParts := make([]string, 0, len(keys))
    for _, k := range keys {
        queryParts = append(queryParts, fmt.Sprintf("%s=%v", k, url.QueryEscape(fmt.Sprintf("%v", params[k]))))
    }
    queryString := "?" + strings.Join(queryParts, "&")

    signature := sign("GET", requestPath, queryString, "", timestamp)

    req, _ := http.NewRequest("GET", BaseURL+endpoint+queryString, nil)
    req.Header.Set("ACCESS-KEY", APIKey)
    req.Header.Set("ACCESS-SIGN", signature)
    req.Header.Set("ACCESS-TIMESTAMP", strconv.FormatInt(timestamp, 10))

    client := &http.Client{Timeout: 30 * time.Second}
    resp, err := client.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    return result, nil
}

func main() {
    // 下单示例
    result, _ := request("/order", map[string]interface{}{
        "symbol":    "AAPL",
        "side":      "buy",
        "type":      "limit",
        "price":     "185.50",
        "quantity":  "1000",
        "clientOid": "test-001",
    })
    fmt.Printf("%+v\n", result)

    // 查询深度示例
    depth, _ := requestGET("/depth", map[string]interface{}{
        "symbol": "XSM",
        "limit":  20,
    })
    fmt.Printf("%+v\n", depth)
}
```

```
import hmac
import hashlib
import base64
import json
import time
import requests
from urllib.parse import quote

API_KEY = "your_api_key"
SECRET_KEY = "your_secret_key"
BASE_URL = "{域名}/api/v1/stock/open-api"

def sign(method, request_path, query_string, body, timestamp):
    """
    timestamp + method + requestPath + queryString + body
    """
    pre_hash = (
        str(timestamp)
        + method
        + request_path
        + query_string
        + body
    )

    signature = hmac.new(
        SECRET_KEY.encode(),
        pre_hash.encode(),
        hashlib.sha256
    ).digest()

    return base64.b64encode(signature).decode()

def request_post(endpoint, params):
    timestamp = int(time.time() * 1000)

    request_path = "/api/v1/stock/open-api" + endpoint

    body = json.dumps(
        params,
        separators=(",", ":")
    )

    signature = sign(
        "POST",
        request_path,
        "",
        body,
        timestamp,
    )

    headers = {
        "Content-Type": "application/json",
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": str(timestamp),
    }

    resp = requests.post(
        BASE_URL + endpoint,
        headers=headers,
        data=body,
        timeout=30,
    )

    return resp.json()

def request_get(endpoint, params):
    timestamp = int(time.time() * 1000)

    request_path = "/api/v1/stock/open-api" + endpoint

    # 完全对齐 Go 的排序逻辑
    keys = sorted(params.keys())

    query_parts = []

    for key in keys:
        value = params[key]
        query_parts.append(
            f"{key}={quote(str(value), safe='')}"
        )

    query_string = "?" + "&".join(query_parts)

    signature = sign(
        "GET",
        request_path,
        query_string,
        "",
        timestamp,
    )

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": str(timestamp),
    }

    resp = requests.get(
        BASE_URL + endpoint + query_string,
        headers=headers,
        timeout=30,
    )

    return resp.json()

if __name__ == "__main__":

    # 下单示例
    # result = request_post(
    #     "/order",
    #     {
    #         "symbol": "AAPL",
    #         "side": "buy",
    #         "type": "limit",
    #         "price": "185.50",
    #         "quantity": "1000",
    #         "clientOid": "test-001",
    #     },
    # )

    # print(result)

    # 查询深度
    depth = request_get(
        "/depth",
        {
            "symbol": "XSM",
            "limit": 20,
        },
    )

    print(depth)
```

```
const crypto = require('crypto');

const API_KEY = 'your_api_key';
const SECRET_KEY = 'your_secret_key';
const BASE_URL = '{域名}/api/v1/stock/open-api';

/**
 * 生成签名
 */
function sign(method, requestPath, queryString, body, timestamp) {
    // 拼接签名字符串
    const preHash = `${timestamp}${method}${requestPath}${queryString}${body}`;

    // HMAC-SHA256 签名 + Base64 编码
    return crypto
        .createHmac('sha256', SECRET_KEY)
        .update(preHash)
        .digest('base64');
}

/**
 * 发送 POST 请求
 */
async function requestPost(endpoint, params) {
    const timestamp = Date.now();
    const requestPath = '/api/v1/stock/open-api' + endpoint;
    const body = JSON.stringify(params);

    const signature = sign('POST', requestPath, '', body, timestamp);

    const response = await fetch(BASE_URL + endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'ACCESS-KEY': API_KEY,
            'ACCESS-SIGN': signature,
            'ACCESS-TIMESTAMP': timestamp.toString()
        },
        body: body
    });

    return response.json();
}

/**
 * 发送 GET 请求
 */
async function requestGet(endpoint, params) {
    const timestamp = Date.now();
    const requestPath = '/api/v1/stock/open-api' + endpoint;

    // 构造 query string（按 key 排序，空参数时为空字符串）
    const sortedKeys = Object.keys(params).sort();
    const queryString = sortedKeys.length > 0
        ? '?' + sortedKeys.map(k => `${k}=${encodeURIComponent(params[k])}`).join('&')
        : '';

    const signature = sign('GET', requestPath, queryString, '', timestamp);

    const response = await fetch(BASE_URL + endpoint + queryString, {
        method: 'GET',
        headers: {
            'ACCESS-KEY': API_KEY,
            'ACCESS-SIGN': signature,
            'ACCESS-TIMESTAMP': timestamp.toString()
        }
    });

    return response.json();
}

// 下单示例
(async () => {
    const result = await requestPost('/order', {
        symbol: 'AAPL',
        side: 'buy',
        type: 'limit',
        price: '185.50',
        quantity: '1000',
        clientOid: 'test-001'
    });
    console.log(result);

    // 查询深度示例
    const depth = await requestGet('/depth', { symbol: 'XSM', limit: 20 });
    console.log(depth);
})();
```

```
# 计算签名（示例）
# timestamp=1705737600000
# preHash="1705737600000POST/api/v1/stock/open-api/order{\"symbol\":\"AAPL\",\"side\":\"buy\",\"type\":\"limit\",\"price\":\"185.50\",\"quantity\":\"1000\"
}"
# signature=HMAC-SHA256(preHash, secretKey) -> Base64

# 下单请求
curl -X POST "{域名}/api/v1/stock/open-api/order" \
  -H "Content-Type: application/json" \
  -H "ACCESS-KEY: your_api_key" \
  -H "ACCESS-SIGN: your_signature" \
  -H "ACCESS-TIMESTAMP: 1705737600000" \
  -d '{
    "symbol": "AAPL",
    "side": "buy",
    "type": "limit",
    "price": "185.50",
    "quantity": "1000",
    "clientOid": "test-001"
  }'

# 查询深度请求
curl -X GET "{域名}/api/v1/stock/open-api/depth?limit=20&symbol=XSM" \
  -H "ACCESS-KEY: your_api_key" \
  -H "ACCESS-SIGN: your_signature" \
  -H "ACCESS-TIMESTAMP: 1705737600000"
```

来源：https://developers.msx.com/docs/next/common/sign-code

---

<!-- source: https://developers.msx.com/docs/next/common/websocket -->

## WebSocket 连接说明

### 连接地址

| 模块 | WebSocket 地址         | 说明                    |
| ---- | ---------------------- | ----------------------- |
| 现货 | `/api/v1/spot/ws`    | K线实时推送             |
| 合约 | `/api/v1/futures/ws` | 订单簿、Ticker、K线推送 |

### 通用规则

| 项目         | 说明                                               |
| ------------ | -------------------------------------------------- |
| 协议         | WebSocket (ws:// 或 wss://)                        |
| 数据格式     | JSON                                               |
| 心跳超时     | 现货 60 秒无消息自动断开；合约 70 秒无消息自动断开 |
| 建议心跳间隔 | 每 20 秒发送一次 ping                              |

### 连接示例

**现货 K线：**

```
wss://api9528mystks.mystonks.org/api/v1/spot/ws
```

**合约行情：**

```
wss://api9528mystks.mystonks.org/api/v1/futures/ws
```

### 心跳机制

**心跳请求：**

```
{"action": "ping"
}
```

**现货心跳响应：**

```
{"event": "pong", "time": 1736163000000}
```

**合约心跳响应：**

```
{"event": "pong", "timestamp": 1736163000000}
```

提示

现货和合约使用不同的 WebSocket 连接地址，心跳超时和部分推送结构也存在差异，请以各模块文档为准。

来源：https://developers.msx.com/docs/next/common/websocket

---

## 现货接口（Next V2.0）

<!-- source: https://developers.msx.com/docs/next/spot/ -->

## 现货交易 API

现货交易 API 提供订单管理和市场数据接口，支持 REST API 和 WebSocket 实时推送。

### 主要功能

**REST API**

- 订单管理：下单、撤单、查询订单和成交记录
- 市场数据：资产列表、订单簿深度、Ticker、K线、交易精度

**WebSocket**

- K线、Ticker、最优买卖价实时推送
- 订单簿增量更新和全量快照

### 快速开始

订单接口需要签名认证，请参考 [认证说明](/docs/next/common/authentication)。

WebSocket 连接地址：`wss://api9528mystks.mystonks.org/api/v1/spot/ws`

来源：https://developers.msx.com/docs/next/spot/

---

<!-- source: https://developers.msx.com/docs/next/spot/assets -->

## 资产查询

查询账户余额。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/stock/open-api/assets`

#### 请求参数

| 参数   | 类型   | 必填 | 说明                 |
| ------ | ------ | ---- | -------------------- |
| symbol | string | 否   | 币种（不传返回所有） |

#### 请求示例

```
GET /api/v1/stock/open-api/assets
```

#### 响应字段

| 字段                 | 类型   | 说明     |
| -------------------- | ------ | -------- |
| code                 | int    | 状态码   |
| msg                  | string | 返回消息 |
| data.balances        | array  | 余额列表 |
| balances[].symbol    | string | 币种     |
| balances[].available | string | 可用余额 |
| balances[].frozen    | string | 冻结余额 |
| balances[].total     | string | 总余额   |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "balances": [
      {
        "symbol": "USDT",
        "available": "9500.00",
        "frozen": "500.00",
        "total": "10000.00"
      },
      {
        "symbol": "AAPL.M",
        "available": "10.00",
        "frozen": "0.00",
        "total": "10.00"
      }
    ]
  }
}
```

来源：https://developers.msx.com/docs/next/spot/assets

---

<!-- source: https://developers.msx.com/docs/next/spot/batch-cancel -->

## 批量撤单

批量取消多个订单。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/stock/open-api/batchCancelOrder`

#### 请求参数

| 参数     | 类型   | 必填 | 说明                 |
| -------- | ------ | ---- | -------------------- |
| symbol   | string | 是   | 股票代码             |
| orderIds | array  | 是   | 订单ID列表，最多10个 |

#### 请求示例

```
{
  "symbol": "AAPL",
  "orderIds": [
    "123456789",
    "123456790",
    "123456791"
  ]
}
```

#### 响应字段

`data` 为数组，每个元素对应一个订单的撤销结果：

| 字段      | 类型   | 说明                   |
| --------- | ------ | ---------------------- |
| orderId   | string | 订单ID                 |
| success   | bool   | 是否成功               |
| errorMsg  | string | 错误信息（失败时返回） |
| errorCode | int    | 错误码（失败时返回）   |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": [
    {
      "orderId": "123456789",
      "success": true
    },
    {
      "orderId": "123456790",
      "success": false,
      "errorCode": 1001,
      "errorMsg": "订单不存在"
    }
  ]
}
```

来源：https://developers.msx.com/docs/next/spot/batch-cancel

---

<!-- source: https://developers.msx.com/docs/next/spot/batch-order -->

## 批量下单

批量创建多个订单，最多支持20个订单。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/stock/open-api/batchOrder`

#### 请求参数

| 参数   | 类型  | 必填 | 说明               |
| ------ | ----- | ---- | ------------------ |
| orders | array | 是   | 订单列表，最多20个 |

**订单对象字段：**

- symbol: 股票代码
- side: buy/sell
- type: limit/market
- price: 委托价格
- quantity: 委托数量
- clientOid: 客户自定义ID

#### 请求示例

```
{
  "orders": [
    {
      "symbol": "AAPL",
      "side": "buy",
      "type": "limit",
      "price": "185.50",
      "quantity": "500",
      "clientOid": "batch-001"
    },
    {
      "symbol": "TSLA",
      "side": "sell",
      "type": "limit",
      "price": "250.00",
      "quantity": "10",
      "clientOid": "batch-002"
    }
  ]
}
```

#### 响应字段

| 字段                | 类型    | 说明                   |
| ------------------- | ------- | ---------------------- |
| code                | int     | 状态码，0 表示成功     |
| msg                 | string  | 返回消息               |
| data.results        | array   | 结果列表               |
| results[].orderId   | string  | 订单ID（成功时返回）   |
| results[].clientOid | string  | 客户自定义ID           |
| results[].success   | boolean | 是否成功               |
| results[].errorMsg  | string  | 错误信息（失败时返回） |
| results[].errorCode | int     | 错误码（失败时返回）   |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "results": [
      {
        "orderId": "123456789",
        "clientOid": "batch-001",
        "success": true
      },
      {
        "orderId": "",
        "clientOid": "batch-002",
        "success": false,
        "errorCode": 1001,
        "errorMsg": "余额不足"
      }
    ]
  }
}
```

来源：https://developers.msx.com/docs/next/spot/batch-order

---

<!-- source: https://developers.msx.com/docs/next/spot/cancel-order -->

## 撤单

取消一个未完成的订单。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/stock/open-api/cancelOrder`

#### 请求参数

| 参数    | 类型   | 必填 | 说明     |
| ------- | ------ | ---- | -------- |
| symbol  | string | 是   | 股票代码 |
| orderId | string | 是   | 订单ID   |

#### 请求示例

```
{
  "symbol": "AAPL",
  "orderId": "123456789"
}
```

#### 响应字段

| 字段         | 类型   | 说明               |
| ------------ | ------ | ------------------ |
| code         | int    | 状态码，0 表示成功 |
| msg          | string | 返回消息           |
| data.orderId | string | 订单ID             |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "orderId": "123456789"
  }
}
```

来源：https://developers.msx.com/docs/next/spot/cancel-order

---

<!-- source: https://developers.msx.com/docs/next/spot/depth -->

## 订单簿深度

获取指定交易对的买卖盘深度数据。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/stock/open-api/depth`

#### 请求参数

| 参数   | 类型   | 必填 | 说明                          |
| ------ | ------ | ---- | ----------------------------- |
| symbol | string | 是   | 交易对，如XSM                 |
| limit  | int    | 否   | 返回档位数量，默认20，最大400 |

#### 请求示例

```
GET /api/v1/stock/open-api/depth?symbol=XSM&limit=20
```

#### 响应字段

| 字段           | 类型   | 说明                      |
| -------------- | ------ | ------------------------- |
| code           | int    | 状态码                    |
| msg            | string | 返回消息                  |
| data.symbol    | string | 交易对                    |
| data.bids      | array  | 买盘，[[价格, 数量], ...] |
| data.asks      | array  | 卖盘，[[价格, 数量], ...] |
| data.timestamp | int64  | 时间戳                    |
| 说明           |        |                           |

- `bids` 买盘按价格从高到低排序
- `asks` 卖盘按价格从低到高排序

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "symbol": "XSM",
    "bids": [
      ["185.50", "1000"],
      ["185.40", "500"]
    ],
    "asks": [
      ["185.60", "800"],
      ["185.70", "1200"]
    ],
    "timestamp": 1705737600000
  }
}
```

来源：https://developers.msx.com/docs/next/spot/depth

---

<!-- source: https://developers.msx.com/docs/next/spot/history-orders -->

## 历史委托

查询已完成或已撤销的订单列表。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/stock/open-api/historyOrders`

#### 请求参数

| 参数      | 类型   | 必填 | 说明                      |
| --------- | ------ | ---- | ------------------------- |
| symbol    | string | 否   | 股票代码                  |
| side      | string | 否   | 方向筛选                  |
| startTime | int64  | 否   | 开始时间（毫秒时间戳）    |
| endTime   | int64  | 否   | 结束时间（毫秒时间戳）    |
| page      | int    | 否   | 页码，默认1               |
| size      | int    | 否   | 每页数量，默认20，最大100 |

#### 请求示例

```
GET /api/v1/stock/open-api/historyOrders?symbol=AAPL&startTime=1705737600000&endTime=1705824000000&page=1&size=20
```

#### 响应字段

| 字段        | 类型   | 说明     |
| ----------- | ------ | -------- |
| code        | int    | 状态码   |
| msg         | string | 返回消息 |
| data.orders | array  | 订单列表 |
| data.total  | int    | 总数     |
| data.page   | int    | 当前页   |
| data.size   | int    | 每页数量 |

**orders 对象字段参考“订单详情”接口**

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "orders": [
      {
        "orderId": "123456789",
        "symbol": "AAPL",
        "side": "buy",
        "type": "limit",
        "price": "185.50",
        "quantity": "1000",
        "filledQty": "1000",
        "status": "filled",
        "createdAt": 1705737600000,
        "updatedAt": 1705737700000
      }
    ],
    "total": 1,
    "page": 1,
    "size": 20
  }
}
```

来源：https://developers.msx.com/docs/next/spot/history-orders

---

<!-- source: https://developers.msx.com/docs/next/spot/klines -->

## K线数据

获取指定交易对的K线历史数据。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/stock/open-api/klines`

#### 请求参数

| 参数      | 类型   | 必填 | 说明                        |
| --------- | ------ | ---- | --------------------------- |
| symbol    | string | 是   | 交易对符号，如msx、BTCUSDT  |
| interval  | string | 是   | K线周期                     |
| startTime | int64  | 否   | 起始时间戳（毫秒）          |
| endTime   | int64  | 否   | 结束时间戳（毫秒）          |
| limit     | int    | 否   | 返回数量，默认500，最大1500 |

**支持的K线周期：**

`1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1mo`

#### 请求示例

```
GET /api/v1/stock/open-api/klines?symbol=msx&interval=1m&limit=100
```

#### 响应字段

| 字段          | 类型   | 说明        |
| ------------- | ------ | ----------- |
| code          | int    | 状态码      |
| msg           | string | 返回消息    |
| data.symbol   | string | 交易对      |
| data.interval | string | K线周期     |
| data.klines   | array  | K线数据列表 |

**klines 数组元素：**

- `t`: 开盘时间戳（毫秒）
- `o`: 开盘价
- `h`: 最高价
- `l`: 最低价
- `c`: 收盘价
- `v`: 成交量

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "symbol": "msx",
    "interval": "1m",
    "klines": [
      {
        "t": 1737446400000,
        "o": "1.2345",
        "h": "1.2400",
        "l": "1.2300",
        "c": "1.2380",
        "v": "12345.67"
      },
      {
        "t": 1737446460000,
        "o": "1.2380",
        "h": "1.2450",
        "l": "1.2350",
        "c": "1.2420",
        "v": "9876.54"
      }
    ]
  }
}
```

来源：https://developers.msx.com/docs/next/spot/klines

---

<!-- source: https://developers.msx.com/docs/next/spot/open-orders -->

## 当前委托

查询当前未完成的订单列表。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/stock/open-api/openOrders`

#### 请求参数

| 参数   | 类型   | 必填 | 说明                      |
| ------ | ------ | ---- | ------------------------- |
| symbol | string | 否   | 股票代码（不传返回所有）  |
| side   | string | 否   | 方向筛选：buy/sell        |
| page   | int    | 否   | 页码，默认1               |
| size   | int    | 否   | 每页数量，默认20，最大100 |

#### 请求示例

```
GET /api/v1/stock/open-api/openOrders?symbol=AAPL&page=1&size=20
```

#### 响应字段

| 字段        | 类型   | 说明     |
| ----------- | ------ | -------- |
| code        | int    | 状态码   |
| msg         | string | 返回消息 |
| data.orders | array  | 订单列表 |
| data.total  | int    | 总数     |
| data.page   | int    | 当前页   |
| data.size   | int    | 每页数量 |

**orders 对象字段参考“订单详情”接口**

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "orders": [
      {
        "orderId": "123456789",
        "symbol": "AAPL",
        "side": "buy",
        "type": "limit",
        "price": "185.50",
        "quantity": "1000",
        "filledQty": "500",
        "status": "partial",
        "createdAt": 1705737600000
      }
    ],
    "total": 1,
    "page": 1,
    "size": 20
  }
}
```

来源：https://developers.msx.com/docs/next/spot/open-orders

---

<!-- source: https://developers.msx.com/docs/next/spot/order -->

## 下单

创建一个新订单，支持限价单和市价单。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/stock/open-api/order`

#### 请求参数

| 参数      | 类型   | 必填 | 说明                                                                                        |
| --------- | ------ | ---- | ------------------------------------------------------------------------------------------- |
| symbol    | string | 是   | 股票代码，如`AAPL`                                                                        |
| side      | string | 是   | 交易方向:`buy`-买入, `sell`-卖出                                                        |
| type      | string | 是   | 订单类型:`limit`-限价, `market`-市价                                                    |
| price     | string | 条件 | 委托价格（限价单必填）                                                                      |
| quantity  | string | 是   | 委托数量：**限价单和市价卖单**为股数(base coin)，**市价买单**为金额(quote coin) |
| clientOid | string | 否   | 客户自定义订单ID（用于幂等性）                                                              |

#### 请求示例

```
{
  "symbol": "AAPL",
  "side": "buy",
  "type": "limit",
  "price": "185.50",
  "quantity": "1000",
  "clientOid": "my-order-001"
}
```

#### 响应字段

| 字段           | 类型   | 说明               |
| -------------- | ------ | ------------------ |
| code           | int    | 状态码，0 表示成功 |
| msg            | string | 返回消息           |
| data           | object | 返回数据           |
| data.orderId   | string | 订单ID             |
| data.clientOid | string | 客户自定义订单ID   |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "orderId": "123456789",
    "clientOid": "my-order-001"
  }
}
```

来源：https://developers.msx.com/docs/next/spot/order

---

<!-- source: https://developers.msx.com/docs/next/spot/order-detail -->

## 订单详情

查询单个订单的详细信息。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/stock/open-api/orderDetail`

#### 请求参数

| 参数    | 类型   | 必填 | 说明     |
| ------- | ------ | ---- | -------- |
| symbol  | string | 是   | 股票代码 |
| orderId | string | 是   | 订单ID   |

#### 请求示例

```
GET /api/v1/stock/open-api/orderDetail?symbol=AAPL&orderId=123456789
```

#### 响应字段

| 字段         | 类型   | 说明                                                                      |
| ------------ | ------ | ------------------------------------------------------------------------- |
| orderId      | string | 订单ID                                                                    |
| clientOid    | string | 客户自定义订单ID                                                          |
| symbol       | string | 交易对                                                                    |
| side         | string | 方向：buy-买入，sell-卖出                                                 |
| type         | string | 类型：limit-限价，market-市价                                             |
| price        | string | 委托价格                                                                  |
| quantity     | string | 委托数量                                                                  |
| filledQty    | string | 已成交数量                                                                |
| filledAmount | string | 已成交金额                                                                |
| avgPrice     | string | 成交均价                                                                  |
| status       | string | 状态：pending-待成交，partial-部分成交，filled-完全成交，cancelled-已撤销 |
| fee          | string | 手续费                                                                    |
| feeCurrency  | string | 手续费币种                                                                |
| createdAt    | int64  | 创建时间（毫秒时间戳）                                                    |
| updatedAt    | int64  | 更新时间（毫秒时间戳）                                                    |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "orderId": "123456789",
    "clientOid": "my-order-001",
    "symbol": "AAPL",
    "side": "buy",
    "type": "limit",
    "price": "185.50",
    "quantity": "1000",
    "filledQty": "1000",
    "filledAmount": "185500.00",
    "avgPrice": "185.50",
    "status": "filled",
    "fee": "18.55",
    "feeCurrency": "USDT",
    "createdAt": 1705737600000,
    "updatedAt": 1705737700000
  }
}
```

来源：https://developers.msx.com/docs/next/spot/order-detail

---

<!-- source: https://developers.msx.com/docs/next/spot/price-steps -->

## 价格精度

获取指定交易对的价格档位配置。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/stock/open-api/priceSteps`

#### 请求参数

| 参数   | 类型   | 必填 | 说明   |
| ------ | ------ | ---- | ------ |
| symbol | string | 是   | 交易对 |

#### 请求示例

```
GET /api/v1/stock/open-api/priceSteps?symbol=XSM
```

#### 响应字段

| 字段        | 类型   | 说明         |
| ----------- | ------ | ------------ |
| code        | int    | 状态码       |
| msg         | string | 返回消息     |
| data.symbol | string | 交易对       |
| data.steps  | array  | 价格档位数组 |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "symbol": "XSM",
    "steps": [
      "0.0001",
      "0.001",
      "0.01",
      "0.1",
      "1"
    ]
  }
}
```

来源：https://developers.msx.com/docs/next/spot/price-steps

---

<!-- source: https://developers.msx.com/docs/next/spot/ticker -->

## 24小时行情

获取指定交易对的24小时价格变动统计。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/stock/open-api/ticker`

#### 请求参数

| 参数   | 类型   | 必填 | 说明   |
| ------ | ------ | ---- | ------ |
| symbol | string | 是   | 交易对 |

#### 请求示例

```
GET /api/v1/stock/open-api/ticker?symbol=AAPL
```

#### 响应字段

| 字段             | 类型   | 说明                     |
| ---------------- | ------ | ------------------------ |
| symbol           | string | 交易对                   |
| open             | string | 24小时开盘价             |
| high             | string | 24小时最高价             |
| low              | string | 24小时最低价             |
| close            | string | 最新成交价               |
| volume           | string | 24小时成交量（基础资产） |
| quoteVolume      | string | 24小时成交额（报价资产） |
| tradeCount       | int64  | 24小时成交笔数           |
| priceChange      | string | 24小时价格变动           |
| priceChangePct   | string | 24小时涨跌幅（%）        |
| weightedAvgPrice | string | 24小时加权平均价         |
| updateTime       | int64  | 更新时间（毫秒时间戳）   |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "symbol": "AAPL",
    "open": "180.00",
    "high": "186.50",
    "low": "179.50",
    "close": "185.50",
    "volume": "1000000",
    "quoteVolume": "182500000",
    "tradeCount": 5678,
    "priceChange": "5.50",
    "priceChangePct": "3.06",
    "weightedAvgPrice": "182.50",
    "updateTime": 1705737600000
  }
}
```

来源：https://developers.msx.com/docs/next/spot/ticker

---

<!-- source: https://developers.msx.com/docs/next/spot/trades -->

## 成交明细

查询订单的成交记录。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/stock/open-api/trades`

#### 请求参数

| 参数      | 类型   | 必填 | 说明     |
| --------- | ------ | ---- | -------- |
| symbol    | string | 否   | 股票代码 |
| orderId   | string | 否   | 订单ID   |
| startTime | int64  | 否   | 开始时间 |
| endTime   | int64  | 否   | 结束时间 |
| page      | int    | 否   | 页码     |
| size      | int    | 否   | 每页数量 |

#### 请求示例

```
GET /api/v1/stock/open-api/trades?symbol=AAPL&orderId=123456789
```

#### 响应字段

| 字段        | 类型   | 说明                             |
| ----------- | ------ | -------------------------------- |
| tradeId     | string | 成交ID                           |
| orderId     | string | 订单ID                           |
| symbol      | string | 交易对                           |
| side        | string | 方向：buy-买入，sell-卖出        |
| price       | string | 成交价格                         |
| quantity    | string | 成交数量                         |
| amount      | string | 成交金额                         |
| fee         | string | 手续费                           |
| feeCurrency | string | 手续费币种                       |
| role        | string | 角色：maker-挂单方，taker-吃单方 |
| createdAt   | int64  | 成交时间（毫秒时间戳）           |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "trades": [
      {
        "tradeId": "987654321",
        "orderId": "123456789",
        "symbol": "AAPL",
        "side": "buy",
        "price": "185.50",
        "quantity": "500",
        "amount": "92750.00",
        "fee": "9.28",
        "feeCurrency": "USDT",
        "role": "taker",
        "createdAt": 1705737650000
      }
    ],
    "total": 1
  }
}
```

来源：https://developers.msx.com/docs/next/spot/trades

---

<!-- source: https://developers.msx.com/docs/next/spot/ws-book-ticker -->

## 最优买卖价 (BBO)

订阅实时最优买一和卖一价格。

### 订阅格式

`{symbol}@book_ticker`

#### 订阅请求

```
{
  "action": "subscribe",
  "streams": ["MSX@book_ticker"]
}
```

#### 推送数据字段

| 字段 | 类型   | 说明     |
| ---- | ------ | -------- |
| s    | string | 交易对   |
| u    | int64  | 更新ID   |
| b    | string | 最优买价 |
| B    | string | 最优买量 |
| a    | string | 最优卖价 |
| A    | string | 最优卖量 |
| t    | int64  | 时间戳   |

#### 推送示例

```
{
  "action": "book_ticker",
  "result": {
    "s": "MSX",
    "u": 12345,
    "b": "9.9",
    "B": "1000",
    "a": "10.1",
    "A": "800",
    "t": 1736163000000
  }
}
```

来源：https://developers.msx.com/docs/next/spot/ws-book-ticker

---

<!-- source: https://developers.msx.com/docs/next/spot/ws-kline -->

## K线订阅

订阅实时 K线数据推送。

### 订阅格式

`{symbol}@kline_{interval}` (例如: `AAPL@kline_1m`)

### 支持的时间周期

`1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1w`, `1mo`

#### 订阅请求

可以同时订阅多个交易对和周期

```
{
  "action": "subscribe",
  "streams": [
    "AAPL@kline_1m",
    "TSLA@kline_5m"
  ]
}
```

#### 推送数据字段

| 字段          | 类型   | 说明                                               |
| ------------- | ------ | -------------------------------------------------- |
| event         | string | 事件类型: data                                     |
| channel       | string | 频道: kline                                        |
| data.symbol   | string | 交易对                                             |
| data.interval | string | K线周期                                            |
| data.t        | int64  | K线开盘时间戳（毫秒）                              |
| data.o        | string | 开盘价                                             |
| data.h        | string | 最高价                                             |
| data.l        | string | 最低价                                             |
| data.c        | string | 收盘价（当前K线最新价）                            |
| data.v        | string | 成交量                                             |
| data.isClosed | bool   | K线是否已收盘（`true`=已收盘，`false`=进行中） |
| time          | int64  | 推送时间戳（毫秒）                                 |

#### 推送示例

```
{
  "event": "data",
  "channel": "kline",
  "data": {
    "symbol": "AAPL",
    "interval": "1m",
    "t": 1736163000000,
    "o": "150.00",
    "h": "151.50",
    "l": "149.80",
    "c": "151.20",
    "v": "1000000",
    "isClosed": false
  },
  "time": 1736163000000
}
```

### 取消订阅

```
{
  "action": "unsubscribe",
  "streams": ["AAPL@kline_1m"]
}
```

来源：https://developers.msx.com/docs/next/spot/ws-kline

---

<!-- source: https://developers.msx.com/docs/next/spot/ws-mini-ticker -->

## MiniTicker 全量推送

订阅所有交易对的 24 小时精简行情，每 3000ms 推送一次全量快照。

### 订阅格式

`!miniTicker@arr@3000ms`

#### 订阅请求

```
{
  "action": "subscribe",
  "streams": ["!miniTicker@arr@3000ms"]
}
```

#### 订阅成功响应

```
{
  "event": "subscribed",
  "channel": "miniTickerArr",
  "message": "订阅成功: !miniTicker@arr@3000ms",
  "time": 1719290000000
}
```

| 字段    | 类型   | 说明                    |
| ------- | ------ | ----------------------- |
| event   | string | 固定为`subscribed`    |
| channel | string | 固定为`miniTickerArr` |
| message | string | 提示信息                |
| time    | int64  | 时间戳（毫秒）          |

### 推送数据

#### 外层字段

| 字段    | 类型   | 说明                                |
| ------- | ------ | ----------------------------------- |
| event   | string | 固定为`data`                      |
| channel | string | 固定为`miniTickerArr`             |
| data    | array  | MiniTickerItem 数组，包含所有交易对 |
| time    | int64  | 推送时间戳（毫秒）                  |

#### data[] 单条字段

| 字段 | 类型   | 说明                    |
| ---- | ------ | ----------------------- |
| s    | string | 交易对，如`BTCUSDT`   |
| c    | string | 最新价（收盘价）        |
| o    | string | 开盘价                  |
| h    | string | 24h 最高价              |
| l    | string | 24h 最低价              |
| v    | string | 24h 成交量              |
| P    | string | 涨跌幅 %，保留 4 位小数 |
| E    | int64  | 本条数据时间戳（毫秒）  |

#### 推送示例

```
{
  "event": "data",
  "channel": "miniTickerArr",
  "data": [
    {
      "s": "BTCUSDT",
      "c": "65000.00",
      "o": "63000.00",
      "h": "66000.00",
      "l": "62000.00",
      "v": "1234.5678",
      "P": "3.1746",
      "E": 1719290000000
    }
  ],
  "time": 1719290000000
}
```

### 取消订阅

#### 取消订阅请求

```
{
  "action": "unsubscribe",
  "streams": ["!miniTicker@arr@3000ms"]
}
```

#### 取消订阅响应

```
{
  "event": "unsubscribed",
  "channel": "miniTickerArr",
  "message": "取消订阅: !miniTicker@arr@3000ms",
  "time": 1719290000000
}
```

来源：https://developers.msx.com/docs/next/spot/ws-mini-ticker

---

<!-- source: https://developers.msx.com/docs/next/spot/ws-order-book -->

## 订单簿全量快照

订阅定时推送的完整订单簿快照。

### 订阅格式

`{symbol}@order_book{N}[@speed]`

- **N**: 档位深度，可选值: 5, 10, 20, 50, 100
- **speed**: 推送频率，可选值: 100ms, 1000ms

### 示例

- `AAPL@order_book20` - 20档深度，默认频率
- `AAPL@order_book20@100ms` - 20档深度，100毫秒推送一次

#### 订阅请求

```
{
  "action": "subscribe",
  "streams": ["AAPL@order_book20"]
}
```

#### 推送数据字段

| 字段           | 类型   | 说明              |
| -------------- | ------ | ----------------- |
| event          | string | 事件类型: data    |
| channel        | string | 频道: order_book  |
| data.symbol    | string | 交易对            |
| data.bids      | array  | 买盘 [价格, 数量] |
| data.asks      | array  | 卖盘 [价格, 数量] |
| data.timestamp | int64  | 快照时间戳        |
| time           | int64  | 推送时间戳        |

#### 推送示例

```
{
  "event": "data",
  "channel": "order_book",
  "data": {
    "symbol": "AAPL",
    "bids": [
      ["150.00", "100"],
      ["149.99", "200"]
    ],
    "asks": [
      ["150.01", "150"],
      ["150.02", "180"]
    ],
    "timestamp": 1736163000000
  },
  "time": 1736163000000
}
```

来源：https://developers.msx.com/docs/next/spot/ws-order-book

---

<!-- source: https://developers.msx.com/docs/next/spot/ws-order-book-update -->

## 订单簿增量更新

订阅订单簿的增量变化，用于本地维护完整订单簿。

### 订阅格式

`{symbol}@order_book_update`

#### 订阅请求

```
{
  "action": "subscribe",
  "streams": ["MSX@order_book_update"]
}
```

#### 推送数据字段

| 字段 | 类型   | 说明                  |
| ---- | ------ | --------------------- |
| s    | string | 交易对                |
| U    | int64  | 首次更新ID            |
| u    | int64  | 末次更新ID            |
| b    | array  | 买盘变化 [价格, 数量] |
| a    | array  | 卖盘变化 [价格, 数量] |
| t    | int64  | 时间戳                |
| 重要 |        |                       |

数量为 `"0"` 表示删除该价格档位

#### 推送示例

```
{
  "action": "order_book_update",
  "result": {
    "s": "MSX",
    "U": 100,
    "u": 105,
    "b": [
      ["9.9", "1000"],
      ["9.8", "500"]
    ],
    "a": [
      ["10.1", "800"],
      ["10.2", "0"]
    ],
    "t": 1736163000000
  }
}
```

来源：https://developers.msx.com/docs/next/spot/ws-order-book-update

---

<!-- source: https://developers.msx.com/docs/next/spot/ws-orderbook-sync -->

## 订单簿本地维护

如何使用增量更新维护本地订单簿的完整指南。

### 核心同步流程

#### 1. 订阅增量更新

```
{
  "action": "subscribe",
  "streams": ["{symbol}@order_book_update"]
}
```

#### 2. 缓存增量消息

在获取快照前，缓存所有接收到的增量更新消息。

#### 3. 获取初始快照

调用 REST API 获取订单簿快照：

```
GET /api/v1/stock/open-api/depth?symbol=XSM&limit=100
```

响应中的 `lastUpdateId` 用于后续同步。

#### 4. 处理缓存消息

丢弃所有 `u < lastUpdateId + 1` 的增量消息。

#### 5. 持续应用增量

按顺序应用增量更新：

- 如果价格档位已存在，更新数量
- 如果数量为 `"0"`，删除该价格档位
- 如果价格档位不存在且数量不为 `"0"`，添加新档位

### 示例代码

```
class OrderBookManager {
  constructor(symbol) {
    this.symbol = symbol;
    this.bids = new Map(); // price -> quantity
    this.asks = new Map();
    this.lastUpdateId = 0;
    this.buffer = []; // 缓存增量消息
  }

  // 1. 订阅增量
  subscribe() {
    this.ws.send(JSON.stringify({
      action: 'subscribe',
      streams: [`${this.symbol}@order_book_update`]
    }));
  }

  // 2. 接收增量，先缓存
  onMessage(data) {
    if (data.action === 'order_book_update') {
      if (!this.lastUpdateId) {
        this.buffer.push(data.result);
      } else {
        this.processUpdate(data.result);
      }
    }
  }

  // 3. 获取快照并初始化
  async initSnapshot() {
    const snapshot = await fetch(
      `/api/v1/stock/open-api/depth?symbol=${this.symbol}&limit=100`
    ).then(r => r.json());

    this.lastUpdateId = snapshot.data.lastUpdateId;

    // 初始化订单簿
    snapshot.data.bids.forEach(([price, qty]) => {
      this.bids.set(price, qty);
    });
    snapshot.data.asks.forEach(([price, qty]) => {
      this.asks.set(price, qty);
    });

    // 4. 处理缓存
    this.buffer = this.buffer.filter(msg => msg.u >= this.lastUpdateId + 1);
    this.buffer.forEach(msg => this.processUpdate(msg));
    this.buffer = [];
  }

  // 5. 应用增量更新
  processUpdate(update) {
    // 验证连续性
    if (update.U !== this.lastUpdateId + 1) {
      console.error('序列断裂，需要重新同步');
      return;
    }

    // 更新买盘
    update.b.forEach(([price, qty]) => {
      if (qty === '0') {
        this.bids.delete(price);
      } else {
        this.bids.set(price, qty);
      }
    });

    // 更新卖盘
    update.a.forEach(([price, qty]) => {
      if (qty === '0') {
        this.asks.delete(price);
      } else {
        this.asks.set(price, qty);
      }
    });

    this.lastUpdateId = update.u;
  }
}
```

### 注意事项

1. **序列连续性**: 确保 `U = lastUpdateId + 1`，否则需要重新同步
2. **数量为0**: 表示删除该价格档位
3. **并发控制**: 使用队列确保增量消息按顺序处理
4. **断线重连**: 重连后需要重新执行完整同步流程

来源：https://developers.msx.com/docs/next/spot/ws-orderbook-sync

---

<!-- source: https://developers.msx.com/docs/next/spot/ws-overview -->

## WebSocket 连接说明

现货 WebSocket 实时行情接口，支持K线、Ticker、订单簿等数据推送。

### 连接地址

```
wss://api9528mystks.mystonks.org/api/v1/spot/ws
```

### 通用规则

- **协议**: WebSocket (ws:// 或 wss://)
- **数据格式**: JSON
- **心跳超时**: 60 秒无消息自动断开
- **建议心跳间隔**: 每 20 秒发送一次 ping

### 心跳机制

#### 心跳请求

客户端需要定期发送心跳以保持连接

```
{"action": "ping"
}
```

#### 心跳响应

服务器返回 pong 响应

```
{"event": "pong", "time": 1736163000000}
```

来源：https://developers.msx.com/docs/next/spot/ws-overview

---

<!-- source: https://developers.msx.com/docs/next/spot/ws-ticker -->

## Ticker 订阅

订阅24小时滚动窗口统计数据。

### 订阅格式

`{symbol}@ticker`

#### 订阅请求

```
{
  "action": "subscribe",
  "streams": ["MSX@ticker"]
}
```

#### 推送数据字段

| 字段 | 说明          |
| ---- | ------------- |
| s    | 交易对        |
| o    | 24h开盘价     |
| h    | 24h最高价     |
| l    | 24h最低价     |
| c    | 最新价        |
| v    | 24h成交量     |
| q    | 24h成交额     |
| n    | 24h成交笔数   |
| p    | 24h价格变动   |
| P    | 24h涨跌幅%    |
| w    | 24h加权平均价 |
| E    | 事件时间戳    |

#### 推送示例

```
{
  "action": "ticker",
  "result": {
    "s": "MSX",
    "o": "10.00",
    "h": "10.50",
    "l": "9.80",
    "c": "10.25",
    "v": "1000000",
    "q": "10250000",
    "n": 5678,
    "p": "0.25",
    "P": "2.50",
    "w": "10.15",
    "E": 1736163000000
  }
}
```

来源：https://developers.msx.com/docs/next/spot/ws-ticker

---

## 合约接口（Next V2.0）

<!-- source: https://developers.msx.com/docs/next/futures/ -->

## 合约交易 API

合约交易 API 提供订单管理、持仓查询和市场数据接口，支持 REST API 和 WebSocket 实时推送。

### 主要功能

**REST API**

- 订单操作：创建订单、撤销订单、查询订单历史和委托记录
- 持仓查询：当前持仓、历史持仓
- 市场数据：订单簿深度、Ticker、K线、交易精度

**WebSocket**

- K线、Ticker、最优买卖价实时推送
- 订单簿增量更新和全量快照

### 快速开始

订单和持仓接口需要签名认证，请参考 [认证说明](/docs/next/common/authentication)。

WebSocket 连接地址：`wss://api9528mystks.mystonks.org/api/v1/futures/ws`

来源：https://developers.msx.com/docs/next/futures/

---

<!-- source: https://developers.msx.com/docs/next/futures/account-config -->

## 账户合约配置

查询指定合约交易对的账户配置，包括当前杠杆、保证金模式及可用杠杆档位。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/futures/open-api/account/config`

#### 请求参数

| 参数   | 类型   | 必填 | 说明                   |
| ------ | ------ | ---- | ---------------------- |
| symbol | string | 是   | 合约交易对，如`AAPL` |

#### 请求示例

```
GET /api/v1/futures/open-api/account/config?symbol=AAPL
```

#### 响应字段

| 字段            | 类型   | 说明                                                                           |
| --------------- | ------ | ------------------------------------------------------------------------------ |
| code            | int    | 状态码，0 表示成功                                                             |
| data.id         | int64  | 配置记录 ID                                                                    |
| data.coType     | int    | 合约类型：1=美股，2=港股，3=数字货币                                           |
| data.symbol     | string | 合约交易对                                                                     |
| data.leverage   | string | 当前杠杆倍数                                                                   |
| data.marginMode | int    | 当前保证金模式：1=全仓，2=逐仓。创建订单时服务端使用此值，无需在下单请求中传递 |
| data.leverTypes | string | 可用杠杆档位，逗号分隔，如`"2,5,10,20"`                                      |

#### 响应示例

```
{
  "code": 0,
  "data": {
    "id": 1,
    "coType": 1,
    "symbol": "AAPL",
    "leverage": "10",
    "marginMode": 1,
    "leverTypes": "2,5,10,20"
  }
}
```

来源：https://developers.msx.com/docs/next/futures/account-config

---

<!-- source: https://developers.msx.com/docs/next/futures/account-leverage -->

## 修改杠杆

修改指定合约交易对的杠杆倍数和保证金模式。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/futures/open-api/account/leverage`

#### 请求参数

| 参数       | 类型   | 必填 | 说明                       |
| ---------- | ------ | ---- | -------------------------- |
| symbol     | string | 是   | 合约交易对，如`AAPL`     |
| leverage   | string | 是   | 杠杆倍数，如`"10"`       |
| marginMode | int    | 是   | 保证金模式：1=全仓，2=逐仓 |

#### 请求示例

```
{
  "symbol": "AAPL",
  "leverage": "10",
  "marginMode": 1
}
```

#### 响应字段

| 字段            | 类型   | 说明               |
| --------------- | ------ | ------------------ |
| code            | int    | 状态码，0 表示成功 |
| data.symbol     | string | 合约交易对         |
| data.leverage   | string | 生效的杠杆倍数     |
| data.marginMode | int    | 生效的保证金模式   |

#### 响应示例

```
{
  "code": 0,
  "data": {
    "symbol": "AAPL",
    "leverage": "10",
    "marginMode": 1
  }
}
```

### 错误码

业务错误以 HTTP 200 返回，通过 body `code` 字段区分。

| code | 说明                             |
| ---- | -------------------------------- |
| 3000 | 交易对不存在                     |
| 8007 | 调整杠杆需要更多起始保证金       |
| 8008 | 调整杠杆失败                     |
| 8011 | 杠杆异常                         |
| 8014 | 逐仓模式下有持仓，不支持调低杠杆 |

来源：https://developers.msx.com/docs/next/futures/account-leverage

---

<!-- source: https://developers.msx.com/docs/next/futures/account-margin-mode -->

## 修改保证金模式

修改指定合约交易对的保证金模式。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/futures/open-api/account/margin-mode`

#### 请求参数

| 参数       | 类型   | 必填 | 说明                       |
| ---------- | ------ | ---- | -------------------------- |
| symbol     | string | 是   | 合约交易对，如`AAPL`     |
| marginMode | int    | 是   | 保证金模式：1=全仓，2=逐仓 |

#### 请求示例

```
{
  "symbol": "AAPL",
  "marginMode": 2
}
```

#### 响应字段

| 字段            | 类型   | 说明               |
| --------------- | ------ | ------------------ |
| code            | int    | 状态码，0 表示成功 |
| data.symbol     | string | 合约交易对         |
| data.marginMode | int    | 生效的保证金模式   |

#### 响应示例

```
{
  "code": 0,
  "data": {
    "symbol": "AAPL",
    "marginMode": 2
  }
}
```

### 与下单的关系

此接口是切换保证金模式的专用 API，下单接口不支持通过传参切换模式。

切换成功后，后续 [创建订单](/docs/next/futures/order-create) 将自动使用新的保证金模式。建议先通过 [账户合约配置](/docs/next/futures/account-config) 查询当前 `marginMode`，确认是否需要调用本接口。

### 错误码

业务错误以 HTTP 200 返回，通过 body `code` 字段区分。

| code | 说明                         |
| ---- | ---------------------------- |
| 3000 | 交易对不存在                 |
| 8009 | 切换保证金模式失败           |
| 8010 | 有持仓，不支持调整保证金模式 |

来源：https://developers.msx.com/docs/next/futures/account-margin-mode

---

<!-- source: https://developers.msx.com/docs/next/futures/klines -->

## K线数据

获取合约交易对的K线历史数据。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/futures/open-api/kline`

#### 请求参数

| 参数      | 类型   | 必填 | 说明                        |
| --------- | ------ | ---- | --------------------------- |
| symbol    | string | 是   | 合约交易对，如`BTCUSDT`   |
| interval  | string | 否   | K线周期，默认1m             |
| startTime | int64  | 否   | 起始时间戳（毫秒）          |
| endTime   | int64  | 否   | 结束时间戳（毫秒）          |
| limit     | int    | 否   | 返回数量，默认500，最大1000 |

**支持的K线周期：**

`1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1mo`

#### 请求示例

```
GET /api/v1/futures/open-api/kline?symbol=BTCUSDT&interval=1m&limit=100
```

#### 响应字段

| 字段 | 类型   | 说明               |
| ---- | ------ | ------------------ |
| code | int    | 状态码，0 表示成功 |
| msg  | string | 返回消息           |
| data | array  | K线数据列表        |

**K线数据对象：**

- `t`: 开盘时间戳（毫秒）
- `o`: 开盘价
- `h`: 最高价
- `l`: 最低价
- `c`: 收盘价
- `v`: 成交量
- `f`: true 表示无交易时填充的横盘K线

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": [
    {
      "t": 1737446400000,
      "o": "68637.5",
      "h": "68637.5",
      "l": "68637.5",
      "c": "68637.5",
      "v": "0",
      "f": true
    },
    {
      "t": 1737446460000,
      "o": "68580.0",
      "h": "68650.2",
      "l": "68550.8",
      "c": "68620.5",
      "v": "12.5"
    }
  ]
}
```

来源：https://developers.msx.com/docs/next/futures/klines

---

<!-- source: https://developers.msx.com/docs/next/futures/order-cancel -->

## 取消订单

取消未成交或部分成交的委托订单。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/futures/open-api/order/cancel`

#### 请求参数

| 参数    | 类型  | 必填 | 说明   |
| ------- | ----- | ---- | ------ |
| orderId | int64 | 是   | 订单ID |

#### 请求示例

```
{"orderId": 123456789}
```

#### 响应字段

| 字段         | 类型   | 说明               |
| ------------ | ------ | ------------------ |
| code         | int    | 状态码，0 表示成功 |
| msg          | string | 返回消息           |
| data.orderId | int64  | 订单ID             |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "orderId": 123456789
  }
}
```

来源：https://developers.msx.com/docs/next/futures/order-cancel

---

<!-- source: https://developers.msx.com/docs/next/futures/order-create -->

## 创建订单

创建合约开仓或平仓订单，支持市价和限价。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/futures/open-api/order/create`

### 保证金模式

创建订单**不接受** `marginMode` 参数。服务端按该交易对账户当前配置执行，取值：1=全仓，2=逐仓。

- **查询当前模式**：[账户合约配置](/docs/next/futures/account-config) — `GET /account/config?symbol=...` → `data.marginMode`
- **切换模式**：[修改保证金模式](/docs/next/futures/account-margin-mode) — `POST /account/margin-mode`（或通过 [修改杠杆](/docs/next/futures/account-leverage) 一并设置）

**逐仓下单工作流：**

```
1. GET  /account/config?symbol=BTCUSDT        → 确认当前 marginMode
2. POST /account/margin-mode { symbol, marginMode: 2 }  → 如需切换
3. POST /order/create { ... }               → 无需传 marginMode
```

#### 请求参数

| 参数            | 类型   | 必填     | 说明                                     |
| --------------- | ------ | -------- | ---------------------------------------- |
| symbol          | string | 是       | 合约交易对，如`BTCUSDT`                |
| coType          | int    | 是       | 合约类型：1=美股，2=港股，3=数字货币     |
| orderType       | int    | 是       | 订单类型：1=限价单，2=市价单             |
| openType        | int    | 是       | 开平仓：1=开仓，2=平仓                   |
| side            | int    | 是       | 方向：1=多仓(买)，2=空仓(卖)             |
| price           | string | 条件     | 委托价格（限价单必填）                   |
| vol             | string | 条件     | 数量（与amt二选一）                      |
| amt             | string | 条件     | 金额USD（与vol二选一，开仓时推荐）       |
| leverage        | string | 开仓必填 | 杠杆倍数，如"10"                         |
| posId           | int64  | 平仓必填 | 仓位ID                                   |
| stopProfitPrice | string | 否       | 止盈价格                                 |
| stopLossPrice   | string | 否       | 止损价格                                 |
| triggerType     | int    | 否       | 触发类型：1=普通，2=止盈，3=止损，4=强平 |

#### 请求示例

**开仓示例：**

```
{
  "symbol": "BTCUSDT",
  "coType": 3,
  "orderType": 2,
  "openType": 1,
  "side": 1,
  "amt": "10000",
  "leverage": "10",
  "triggerType": 1
}
```

**平仓示例：**

```
{
  "symbol": "BTCUSDT",
  "coType": 3,
  "orderType": 2,
  "openType": 2,
  "side": 1,
  "posId": 123456,
  "vol": "0.5",
  "triggerType": 1
}
```

#### 响应字段

| 字段         | 类型   | 说明               |
| ------------ | ------ | ------------------ |
| code         | int    | 状态码，0 表示成功 |
| msg          | string | 返回消息           |
| data.orderId | int64  | 订单ID             |
| data.orderNo | string | 订单编号           |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "orderId": 123456789,
    "orderNo": "ORD20240120001"
  }
}
```

### 错误码

业务错误以 HTTP 200 返回，通过 body `code` 字段区分。

| code | 说明                           |
| ---- | ------------------------------ |
| 3000 | 交易对不存在                   |
| 8001 | 低于最小交易量                 |
| 8002 | 平仓委托失败，请检查持仓       |
| 8003 | 平仓余额不足，请检查持仓与挂单 |
| 8004 | 委托订单创建失败               |
| 8005 | 止盈止损订单创建失败           |
| 8006 | 止盈止损订单将被立即触发       |
| 8016 | 超过最大交易量                 |
| 8017 | 超过最大持仓量                 |
| 8018 | 保证金不足                     |
| 8100 | 产品信息异常                   |

来源：https://developers.msx.com/docs/next/futures/order-create

---

<!-- source: https://developers.msx.com/docs/next/futures/order-entrust-history -->

## 委托历史

查询所有状态的委托历史，支持多维度筛选。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/futures/open-api/order/entrust-history`

#### 请求参数

| 参数      | 类型   | 必填 | 说明                                                                                      |
| --------- | ------ | ---- | ----------------------------------------------------------------------------------------- |
| symbol    | string | 否   | 合约交易对筛选                                                                            |
| coType    | int    | 否   | 合约类型筛选                                                                              |
| status    | int    | 否   | 状态筛选：0=全部，1=new，2=filled，3=part_filled，4=canceled，5=pending_cancel，6=expired |
| openFlag  | int    | 否   | 开平仓筛选：1=开仓，2=平仓                                                                |
| longFlag  | int    | 否   | 方向筛选：1=多仓，2=空仓                                                                  |
| startTime | int64  | 否   | 开始时间（毫秒时间戳）                                                                    |
| endTime   | int64  | 否   | 结束时间（毫秒时间戳）                                                                    |
| pageIndex | int    | 否   | 页码，默认1                                                                               |
| pageSize  | int    | 否   | 每页数量，默认10，最大100                                                                 |

#### 请求示例

```
{
  "symbol": "BTCUSDT",
  "status": 2,
  "openFlag": 1,
  "startTime": 1705737600000,
  "endTime": 1705824000000,
  "pageIndex": 1,
  "pageSize": 20
}
```

#### 响应字段

| 字段        | 类型   | 说明                                                                                      |
| ----------- | ------ | ----------------------------------------------------------------------------------------- |
| id          | int64  | 订单 ID                                                                                   |
| symbol      | string | 合约交易对                                                                                |
| price       | string | 挂单价格（市价单为0）                                                                     |
| avgPrice    | string | 成交均价                                                                                  |
| status      | int    | 订单状态：0=init, 1=new, 2=filled, 3=part_filled, 4=canceled, 5=pending_cancel, 6=expired |
| orderNo     | string | 订单编号                                                                                  |
| openFlag    | int    | 开平仓：1=开仓, 2=平仓                                                                    |
| orderType   | int    | 委托类型：1=限价, 2=市价                                                                  |
| longFlag    | int    | 方向：1=多仓(买), 2=空仓(卖)                                                              |
| vol         | string | 委托数量                                                                                  |
| filledVol   | string | 已成交数量                                                                                |
| amtTotal    | string | 订单总价值 (USD)                                                                          |
| leverage    | string | 杠杆倍数                                                                                  |
| realPnl     | string | 已实现盈亏                                                                                |
| realFee     | string | 实际手续费                                                                                |
| orderMargin | string | 保证金                                                                                    |
| marginMode  | int    | 保证金模式：1=全仓, 2=逐仓                                                                |
| coType      | int    | 合约类型：1=美股, 2=港股, 3=数字货币                                                      |
| triggerType | int    | 触发类型：1=普通, 2=止盈, 3=止损, 4=强平                                                  |
| ctime       | int64  | 创建时间（毫秒时间戳）                                                                    |
| tradedTime  | int64  | 成交时间（毫秒时间戳）                                                                    |
| cancelTime  | int64  | 取消时间（毫秒时间戳）                                                                    |
| total       | int64  | 总记录数                                                                                  |
| page        | int    | 当前页码                                                                                  |
| size        | int    | 每页数量                                                                                  |

#### 响应示例

```
{
  "code": 0,
  "data": [
    {
      "id": 123456,
      "symbol": "BTCUSDT",
      "price": "0",
      "avgPrice": "68520.00",
      "status": 2,
      "orderNo": "CO2026032500001",
      "openFlag": 1,
      "orderType": 2,
      "longFlag": 1,
      "vol": "0.5",
      "filledVol": "0.5",
      "amtTotal": "34260.00",
      "leverage": "10",
      "realPnl": "200.50",
      "realFee": "34.26",
      "orderMargin": "3425.00",
      "marginMode": 1,
      "coType": 3,
      "triggerType": 1,
      "ctime": 1737446400000,
      "tradedTime": 1737446500000,
      "cancelTime": 0
    }
  ],
  "total": 500,
  "page": 1,
  "size": 50
}
```

来源：https://developers.msx.com/docs/next/futures/order-entrust-history

---

<!-- source: https://developers.msx.com/docs/next/futures/order-history -->

## 历史订单

查询已成交或已取消的历史订单（分页）。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/futures/open-api/order/history`

#### 请求参数

| 参数      | 类型   | 必填 | 说明                      |
| --------- | ------ | ---- | ------------------------- |
| symbol    | string | 否   | 合约交易对筛选            |
| coType    | int    | 否   | 合约类型筛选              |
| pageIndex | int    | 否   | 页码，默认1               |
| pageSize  | int    | 否   | 每页数量，默认10，最大100 |

#### 请求示例

```
{
  "symbol": "BTCUSDT",
  "coType": 3,
  "pageIndex": 1,
  "pageSize": 20
}
```

#### 响应字段

| 字段        | 类型   | 说明                                                                                      |
| ----------- | ------ | ----------------------------------------------------------------------------------------- |
| id          | int64  | 订单 ID                                                                                   |
| symbol      | string | 合约交易对                                                                                |
| price       | string | 挂单价格                                                                                  |
| avgPrice    | string | 成交均价                                                                                  |
| status      | int    | 订单状态：0=init, 1=new, 2=filled, 3=part_filled, 4=canceled, 5=pending_cancel, 6=expired |
| orderNo     | string | 订单编号                                                                                  |
| openFlag    | int    | 开平仓：1=开仓, 2=平仓                                                                    |
| orderType   | int    | 委托类型：1=限价, 2=市价                                                                  |
| longFlag    | int    | 方向：1=多仓(买), 2=空仓(卖)                                                              |
| vol         | string | 委托数量                                                                                  |
| amtTotal    | string | 订单总价值 (USD)                                                                          |
| leverage    | string | 杠杆倍数                                                                                  |
| realPnl     | string | 已实现盈亏                                                                                |
| realFee     | string | 实际手续费                                                                                |
| ctime       | int64  | 创建时间（毫秒时间戳）                                                                    |
| tradedTime  | int64  | 成交时间（毫秒时间戳）                                                                    |
| cancelTime  | int64  | 取消时间（毫秒时间戳）                                                                    |
| triggerType | int    | 触发类型：1=普通, 2=止盈, 3=止损, 4=强平                                                  |
| orderMargin | string | 保证金                                                                                    |
| marginMode  | int    | 保证金模式：1=全仓, 2=逐仓                                                                |
| coType      | int    | 合约类型：1=美股, 2=港股, 3=数字货币                                                      |
| total       | int64  | 总记录数                                                                                  |
| page        | int    | 当前页码                                                                                  |
| size        | int    | 每页数量                                                                                  |

#### 响应示例

```
{
  "code": 0,
  "data": [
    {
      "id": 123456,
      "symbol": "BTCUSDT",
      "price": "68500.00",
      "avgPrice": "68520.00",
      "status": 2,
      "orderNo": "CO2026032500001",
      "openFlag": 1,
      "orderType": 2,
      "longFlag": 1,
      "vol": "0.5",
      "amtTotal": "34260.00",
      "leverage": "10",
      "realPnl": "200.50",
      "realFee": "34.26",
      "ctime": 1737446400000,
      "tradedTime": 1737446500000,
      "cancelTime": 0,
      "triggerType": 1,
      "orderMargin": "3425.00",
      "marginMode": 1,
      "coType": 3
    }
  ],
  "total": 150,
  "page": 1,
  "size": 20
}
```

来源：https://developers.msx.com/docs/next/futures/order-history

---

<!-- source: https://developers.msx.com/docs/next/futures/order-limit -->

## 当前委托

查询当前未成交的限价委托订单列表。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/futures/open-api/order/limit`

#### 请求参数

| 参数   | 类型   | 必填 | 说明                                     |
| ------ | ------ | ---- | ---------------------------------------- |
| symbol | string | 否   | 合约交易对筛选                           |
| coType | int    | 否   | 合约类型筛选：1=美股，2=港股，3=数字货币 |

#### 请求示例

```
{
  "symbol": "BTCUSDT",
  "coType": 3
}
```

#### 响应字段

| 字段        | 类型   | 说明                                     |
| ----------- | ------ | ---------------------------------------- |
| id          | int64  | 订单ID                                   |
| symbol      | string | 合约交易对                               |
| price       | string | 委托价格                                 |
| status      | int    | 订单状态：0=init，1=new，3=part_filled   |
| orderNo     | string | 订单编号                                 |
| openFlag    | int    | 开平仓：1=开仓，2=平仓                   |
| longFlag    | int    | 方向：1=多仓(买)，2=空仓(卖)             |
| vol         | string | 委托数量                                 |
| amtTotal    | string | 订单总价值(USD)                          |
| orderMargin | string | 保证金                                   |
| orderType   | int    | 委托类型：1=限价，2=市价                 |
| leverage    | string | 杠杆倍数                                 |
| ctime       | int64  | 创建时间（毫秒时间戳）                   |
| triggerType | int    | 触发类型：1=普通，2=止盈，3=止损，4=强平 |
| marginMode  | int    | 保证金模式：1=全仓，2=逐仓               |
| coType      | int    | 合约类型：1=美股，2=港股，3=数字货币     |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": [
    {
      "id": 123456789,
      "symbol": "BTCUSDT",
      "price": "68500.0",
      "status": 1,
      "orderNo": "ORD20240120001",
      "openFlag": 1,
      "longFlag": 1,
      "vol": "0.5",
      "amtTotal": "34250.00",
      "orderMargin": "3425.00",
      "orderType": 1,
      "leverage": "10",
      "ctime": 1705737600000,
      "triggerType": 1,
      "marginMode": 1,
      "coType": 3
    }
  ]
}
```

来源：https://developers.msx.com/docs/next/futures/order-limit

---

<!-- source: https://developers.msx.com/docs/next/futures/orderbook -->

## 订单簿深度

获取合约交易对的买卖盘深度数据。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/futures/open-api/orderbook/{symbol}`

#### 请求参数

| 参数    | 位置  | 类型   | 必填 | 说明                                      |
| ------- | ----- | ------ | ---- | ----------------------------------------- |
| symbol  | path  | string | 是   | 合约交易对，如`BTCUSDT`                 |
| depth   | query | int    | 否   | 深度档位数量，默认20，最大400             |
| with_id | query | bool   | 否   | 是否返回序列号（用于增量同步），默认false |
| step    | query | string | 否   | 价格聚合精度，如0.01、0.1、1              |

#### 请求示例

```
GET /api/v1/futures/open-api/orderbook/BTCUSDT?depth=20&with_id=true
```

#### 响应字段

| 字段           | 类型   | 说明                        |
| -------------- | ------ | --------------------------- |
| code           | int    | 状态码，0 表示成功          |
| msg            | string | 返回消息                    |
| data.symbol    | string | 合约交易对                  |
| data.bids      | array  | 买盘，[[价格, 数量], ...]   |
| data.asks      | array  | 卖盘，[[价格, 数量], ...]   |
| data.timestamp | int64  | 时间戳                      |
| data.id        | int64  | 序列号（when with_id=true） |
| 说明           |        |                             |

- `bids` 买盘按价格从高到低排序
- `asks` 卖盘按价格从低到高排序
- `id` 序列号用于增量同步（需要 `with_id=true`）

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "symbol": "BTCUSDT",
    "bids": [
      ["68500.5", "1.25"],
      ["68500.0", "2.50"]
    ],
    "asks": [
      ["68501.0", "1.50"],
      ["68501.5", "2.00"]
    ],
    "timestamp": 1737536400000,
    "id": 12345678
  }
}
```

来源：https://developers.msx.com/docs/next/futures/orderbook

---

<!-- source: https://developers.msx.com/docs/next/futures/position-current -->

## 当前持仓

查询用户当前未平仓的合约持仓及资产统计。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/futures/open-api/position/current`

#### 请求参数

| 参数   | 类型   | 必填 | 说明                                     |
| ------ | ------ | ---- | ---------------------------------------- |
| symbol | string | 否   | 合约交易对筛选                           |
| coType | int    | 否   | 合约类型筛选：1=美股，2=港股，3=数字货币 |

**响应结构（data对象）：**

| 字段           | 类型   | 说明         |
| -------------- | ------ | ------------ |
| balance        | string | 钱包余额     |
| AcctBalance    | string | 账户余额     |
| assetValuation | string | 资产估值     |
| pnlTotal       | string | 浮动盈亏总计 |
| posList        | array  | 持仓列表     |

#### 请求示例

```
{
  "symbol": "BTCUSDT",
  "coType": 3
}
```

#### 持仓对象字段（posList数组）

| 字段            | 类型   | 说明                                         |
| --------------- | ------ | -------------------------------------------- |
| id              | int64  | 持仓 ID                                      |
| symbol          | string | 合约交易对                                   |
| posNo           | string | 仓位编号                                     |
| longFlag        | int    | 方向：1=多仓(买), 2=空仓(卖)                 |
| marginMode      | int    | 保证金模式：1=全仓, 2=逐仓                   |
| leverage        | string | 当前杠杆倍数                                 |
| posMargin       | string | 仓位保证金                                   |
| useMargin       | string | 可用保证金（逐仓）                           |
| feeCost         | string | 已扣手续费                                   |
| nowAmtTotal     | string | 当前仓位总价值 (USD)                         |
| nowVolTotal     | string | 当前仓位总数量                               |
| sellVolTotal    | string | 卖出成交总量                                 |
| sellAmtTotal    | string | 卖出总金额（USD）                            |
| buyVolTotal     | string | 买入成交总量                                 |
| freezeVol       | string | 挂单冻结数量                                 |
| pnl             | string | 浮动盈亏                                     |
| realPnl         | string | 已实现盈亏                                   |
| liqPrice        | string | 预计强平价                                   |
| avgPrice        | string | 平均开仓价                                   |
| markPrice       | string | 标记价格                                     |
| maintMargin     | string | 维持保证金金额                               |
| closePrice      | string | 实际平仓/强平价格（当前持仓为0）             |
| closeTime       | int64  | 完全平仓时间（当前持仓为0）                  |
| ctime           | int64  | 创建时间（毫秒时间戳）                       |
| rateReturn      | string | 回报率(%)                                    |
| marginRate      | string | 保证金比率(%) = 维持保证金 / 账户权益 × 100 |
| holdMarginRatio | string | 维持保证金率                                 |
| initMargin      | string | 初始保证金率                                 |
| posStatus       | int    | 仓位状态：1=未触发（活跃持仓）               |
| pricePrecision  | int    | 价格精度                                     |
| coType          | int    | 合约类型：1=美股, 2=港股, 3=数字货币         |
| profitPrice     | string | 止盈价格                                     |
| lossPrice       | string | 止损价格                                     |

#### 响应示例

```
{
  "code": 0,
  "data": {
    "balance": "5000.00",
    "AcctBalance": "5150.50",
    "assetValuation": "15150.50",
    "pnlTotal": "150.50",
    "posList": [
      {
        "id": 123456,
        "symbol": "BTCUSDT",
        "posNo": "P20260325001",
        "longFlag": 1,
        "marginMode": 1,
        "leverage": "10",
        "posMargin": "1000.00",
        "useMargin": "0.00",
        "feeCost": "20.00",
        "nowAmtTotal": "10000.00",
        "nowVolTotal": "0.15",
        "sellVolTotal": "0",
        "sellAmtTotal": "0",
        "buyVolTotal": "0.15",
        "freezeVol": "0",
        "pnl": "150.50",
        "realPnl": "0",
        "liqPrice": "62000.00",
        "avgPrice": "68000.00",
        "markPrice": "69000.00",
        "maintMargin": "100.00",
        "closePrice": "0",
        "closeTime": 0,
        "ctime": 1737446400000,
        "rateReturn": "15.05",
        "marginRate": "2.00",
        "holdMarginRatio": "0.01",
        "initMargin": "0.1",
        "posStatus": 1,
        "pricePrecision": 2,
        "coType": 3,
        "profitPrice": "70000.00",
        "lossPrice": "66000.00"
      }
    ]
  }
}
```

来源：https://developers.msx.com/docs/next/futures/position-current

---

<!-- source: https://developers.msx.com/docs/next/futures/position-history -->

## 历史持仓

查询已平仓/已强平的历史持仓记录（分页）。

### 接口信息

- **方法**: `POST`
- **路径**: `/api/v1/futures/open-api/position/history`

#### 请求参数

| 参数      | 类型   | 必填 | 说明                                     |
| --------- | ------ | ---- | ---------------------------------------- |
| symbol    | string | 否   | 合约交易对筛选                           |
| coType    | int    | 否   | 合约类型筛选：1=美股, 2=港股, 3=数字货币 |
| pageIndex | int    | 否   | 页码，默认1                              |
| pageSize  | int    | 否   | 每页数量，默认10，最大100                |

#### 请求示例

```
{
  "symbol": "BTCUSDT",
  "coType": 3,
  "pageIndex": 1,
  "pageSize": 20
}
```

#### 响应字段（data 数组元素）

| 字段            | 类型   | 说明                                 |
| --------------- | ------ | ------------------------------------ |
| id              | int64  | 持仓 ID                              |
| symbol          | string | 合约交易对                           |
| posNo           | string | 仓位编号                             |
| longFlag        | int    | 方向：1=多仓(买), 2=空仓(卖)         |
| marginMode      | int    | 保证金模式：1=全仓, 2=逐仓           |
| leverage        | string | 杠杆倍数                             |
| posMargin       | string | 仓位保证金                           |
| useMargin       | string | 可用保证金（逐仓）                   |
| feeCost         | string | 已扣手续费                           |
| nowAmtTotal     | string | 仓位总价值 (USD)                     |
| nowVolTotal     | string | 仓位总数量                           |
| sellVolTotal    | string | 卖出成交总量                         |
| sellAmtTotal    | string | 卖出总金额（USD）                    |
| buyVolTotal     | string | 买入成交总量                         |
| freezeVol       | string | 挂单冻结数量                         |
| pnl             | string | 浮动盈亏（历史持仓通常为0）          |
| realPnl         | string | 已实现盈亏                           |
| liqPrice        | string | 预计强平价（历史持仓通常为0）        |
| avgPrice        | string | 平均开仓价                           |
| markPrice       | string | 标记价格（历史持仓通常为0）          |
| maintMargin     | string | 维持保证金金额（历史持仓通常为0）    |
| closePrice      | string | 实际平仓/强平价格                    |
| closeTime       | int64  | 平仓时间（毫秒时间戳）               |
| ctime           | int64  | 创建时间（毫秒时间戳）               |
| rateReturn      | string | 回报率(%)                            |
| marginRate      | string | 保证金比率(%)                        |
| holdMarginRatio | string | 维持保证金率                         |
| initMargin      | string | 初始保证金率                         |
| posStatus       | int    | 仓位状态：4=已平仓, 5=已强平         |
| pricePrecision  | int    | 价格精度                             |
| coType          | int    | 合约类型：1=美股, 2=港股, 3=数字货币 |
| profitPrice     | string | 止盈价格                             |
| lossPrice       | string | 止损价格                             |
| total           | int64  | 总记录数                             |
| page            | int    | 当前页码                             |
| size            | int    | 每页数量                             |

#### 响应示例

```
{
  "code": 0,
  "data": [
    {
      "id": 123456,
      "symbol": "BTCUSDT",
      "posNo": "P20260325001",
      "longFlag": 1,
      "marginMode": 1,
      "leverage": "10",
      "posMargin": "1000.00",
      "useMargin": "0.00",
      "feeCost": "25.00",
      "nowAmtTotal": "10000.00",
      "nowVolTotal": "0.15",
      "sellVolTotal": "0.15",
      "sellAmtTotal": "10425.00",
      "buyVolTotal": "0.15",
      "freezeVol": "0",
      "pnl": "0",
      "realPnl": "200.50",
      "liqPrice": "0",
      "avgPrice": "68000.00",
      "markPrice": "0",
      "maintMargin": "0",
      "closePrice": "69500.00",
      "closeTime": 1737450000000,
      "ctime": 1737446400000,
      "rateReturn": "20.05",
      "marginRate": "0",
      "holdMarginRatio": "0.01",
      "initMargin": "0.1",
      "posStatus": 4,
      "pricePrecision": 2,
      "coType": 3,
      "profitPrice": "70000.00",
      "lossPrice": "66000.00"
    }
  ],
  "total": 150,
  "page": 1,
  "size": 20
}
```

来源：https://developers.msx.com/docs/next/futures/position-history

---

<!-- source: https://developers.msx.com/docs/next/futures/price-steps -->

## 价格精度

获取合约交易对的价格档位配置。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/futures/open-api/price-steps/{symbol}`

#### 请求参数

| 参数   | 位置 | 类型   | 必填 | 说明       |
| ------ | ---- | ------ | ---- | ---------- |
| symbol | path | string | 是   | 合约交易对 |

#### 请求示例

```
GET /api/v1/futures/open-api/price-steps/BTCUSDT
```

#### 响应字段

| 字段        | 类型   | 说明               |
| ----------- | ------ | ------------------ |
| code        | int    | 状态码，0 表示成功 |
| msg         | string | 返回消息           |
| data.symbol | string | 合约交易对         |
| data.steps  | array  | 价格档位数组       |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "symbol": "BTCUSDT",
    "steps": [
      "0.01",
      "0.1",
      "1",
      "10",
      "100"
    ]
  }
}
```

来源：https://developers.msx.com/docs/next/futures/price-steps

---

<!-- source: https://developers.msx.com/docs/next/futures/products -->

## 合约产品列表

获取所有合约产品信息，可按合约类型筛选。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/futures/open-api/products`

#### 请求参数

| 参数 | 位置  | 类型 | 必填 | 说明                                               |
| ---- | ----- | ---- | ---- | -------------------------------------------------- |
| type | query | int  | 否   | 合约类型：1=美股，2=港股，3=数字货币；不传返回全部 |

#### 请求示例

```
# 全部产品
GET /api/v1/futures/open-api/products

# 仅美股
GET /api/v1/futures/open-api/products?type=1
```

#### 响应字段

| 字段  | 类型  | 说明               |
| ----- | ----- | ------------------ |
| code  | int   | 状态码，0 表示成功 |
| total | int   | 产品总数           |
| data  | array | 产品列表           |

**data 数组元素字段：**

| 字段           | 类型   | 说明                                 |
| -------------- | ------ | ------------------------------------ |
| symbol         | string | 合约交易对                           |
| name           | string | 产品英文名称                         |
| nameZh         | string | 产品中文名称                         |
| type           | int    | 合约类型：1=美股，2=港股，3=数字货币 |
| quoteSymbol    | string | 计价币种（数字货币有效）             |
| baseSymbol     | string | 基础币种（数字货币有效）             |
| pricePrecision | int    | 价格精度（小数位数）                 |
| volPrecision   | int    | 数量精度（小数位数）                 |
| minOrderVolume | string | 最小下单数量                         |
| maxOrderVolume | string | 最大下单数量                         |
| leverageLevel  | int    | 最大杠杆倍数                         |
| leverTypes     | string | 可用杠杆档位，逗号分隔               |
| feeRateMaker   | string | Maker 手续费率                       |
| feeRateTaker   | string | Taker 手续费率                       |
| tradeStatus    | int    | 交易状态：1=正常                     |

#### 响应示例

```
{
  "code": 0,
  "total": 3,
  "data": [
    {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "nameZh": "苹果公司",
      "type": 1,
      "quoteSymbol": "",
      "baseSymbol": "",
      "pricePrecision": 2,
      "volPrecision": 0,
      "minOrderVolume": "1",
      "maxOrderVolume": "10000",
      "leverageLevel": 50,
      "leverTypes": "1,2,3,5,10,25,50",
      "feeRateMaker": "0.00045",
      "feeRateTaker": "0.0007",
      "tradeStatus": 1
    },
    {
      "symbol": "00700",
      "name": "Tencent Holdings",
      "nameZh": "腾讯控股",
      "type": 2,
      "quoteSymbol": "",
      "baseSymbol": "",
      "pricePrecision": 2,
      "volPrecision": 0,
      "minOrderVolume": "1",
      "maxOrderVolume": "5000",
      "leverageLevel": 10,
      "leverTypes": "1,2,3,5,10",
      "feeRateMaker": "0.00045",
      "feeRateTaker": "0.0007",
      "tradeStatus": 1
    },
    {
      "symbol": "BTCUSDT",
      "name": "Bitcoin",
      "nameZh": "比特币",
      "type": 3,
      "quoteSymbol": "USDT",
      "baseSymbol": "BTC",
      "pricePrecision": 2,
      "volPrecision": 4,
      "minOrderVolume": "0.001",
      "maxOrderVolume": "100",
      "leverageLevel": 100,
      "leverTypes": "1,2,3,5,10,20,50,100",
      "feeRateMaker": "0.0002",
      "feeRateTaker": "0.0005",
      "tradeStatus": 1
    }
  ]
}
```

来源：https://developers.msx.com/docs/next/futures/products

---

<!-- source: https://developers.msx.com/docs/next/futures/ticker -->

## 24小时行情

获取合约交易对的24小时价格变动统计。

### 接口信息

- **方法**: `GET`
- **路径**: `/api/v1/futures/open-api/ticker/{symbol}`

#### 请求参数

| 参数   | 位置 | 类型   | 必填 | 说明                      |
| ------ | ---- | ------ | ---- | ------------------------- |
| symbol | path | string | 是   | 合约交易对，如`BTCUSDT` |

#### 请求示例

```
GET /api/v1/futures/open-api/ticker/BTCUSDT
```

#### 响应字段

| 字段             | 类型   | 说明                             |
| ---------------- | ------ | -------------------------------- |
| symbol           | string | 合约交易对                       |
| open             | string | 24小时开盘价                     |
| high             | string | 24小时最高价                     |
| low              | string | 24小时最低价                     |
| markPrice        | string | 标记价格                         |
| close            | string | 最新成交价                       |
| volume           | string | 24小时成交量（基础资产，如BTC）  |
| quoteVolume      | string | 24小时成交额（计价资产，如USDT） |
| tradeCount       | int64  | 24小时成交笔数                   |
| priceChange      | string | 24小时价格变动（绝对值）         |
| priceChangePct   | string | 24小时涨跌幅（百分比）           |
| weightedAvgPrice | string | 24小时加权平均价                 |
| updateTime       | int64  | 更新时间（毫秒时间戳）           |

#### 响应示例

```
{
  "code": 0,
  "msg": "success",
  "data": {
    "symbol": "BTCUSDT",
    "open": "67500.0",
    "high": "69200.5",
    "low": "67200.0",
    "markPrice": "67200.0",
    "close": "68620.5",
    "volume": "1250.85",
    "quoteVolume": "85500000.50",
    "tradeCount": 12345,
    "priceChange": "1120.5",
    "priceChangePct": "1.66",
    "weightedAvgPrice": "68350.0",
    "updateTime": 1737536400000
  }
}
```

来源：https://developers.msx.com/docs/next/futures/ticker

---

<!-- source: https://developers.msx.com/docs/next/futures/ws-book-ticker -->

## 最优买卖价 (BBO)

订阅合约实时最优买一和卖一价格。

### 订阅格式

`{symbol}@book_ticker`

#### 订阅请求

```
{
  "action": "subscribe",
  "streams": ["BTCUSD@book_ticker"]
}
```

#### 推送数据字段

| 字段 | 类型   | 说明     |
| ---- | ------ | -------- |
| s    | string | 合约标识 |
| u    | int64  | 更新ID   |
| b    | string | 最优买价 |
| B    | string | 最优买量 |
| a    | string | 最优卖价 |
| A    | string | 最优卖量 |
| t    | int64  | 时间戳   |

#### 推送示例

```
{
  "action": "book_ticker",
  "result": {
    "s": "BTCUSD",
    "u": 123456,
    "b": "50100.00",
    "B": "10",
    "a": "50120.00",
    "A": "8",
    "t": 1736163000000
  }
}
```

来源：https://developers.msx.com/docs/next/futures/ws-book-ticker

---

<!-- source: https://developers.msx.com/docs/next/futures/ws-kline -->

## K线订阅

订阅合约实时 K线数据推送。

### 订阅格式

`{symbol}@kline_{interval}` (例如: `BTCUSD@kline_1m`)

### 支持的时间周期

`1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1w`, `1mo`

#### 订阅请求

可以同时订阅多个合约和周期

```
{
  "action": "subscribe",
  "streams": [
    "BTCUSD@kline_1m",
    "ETHUSD@kline_5m"
  ]
}
```

#### 推送数据字段

| 字段          | 类型   | 说明                                               |
| ------------- | ------ | -------------------------------------------------- |
| event         | string | 事件类型: data                                     |
| channel       | string | 频道: kline                                        |
| data.symbol   | string | 合约标识                                           |
| data.interval | string | K线周期                                            |
| data.t        | int64  | K线开盘时间戳（毫秒）                              |
| data.o        | string | 开盘价                                             |
| data.h        | string | 最高价                                             |
| data.l        | string | 最低价                                             |
| data.c        | string | 收盘价（当前K线最新价）                            |
| data.v        | string | 成交量                                             |
| data.isClosed | bool   | K线是否已收盘（`true`=已收盘，`false`=进行中） |
| time          | int64  | 推送时间戳（毫秒）                                 |

#### 推送示例

```
{
  "event": "data",
  "channel": "kline",
  "data": {
    "symbol": "BTCUSD",
    "interval": "1m",
    "t": 1736163000000,
    "o": "50000.00",
    "h": "50150.00",
    "l": "49980.00",
    "c": "50120.00",
    "v": "1000000",
    "isClosed": false
  },
  "time": 1736163000000
}
```

### 取消订阅

```
{
  "action": "unsubscribe",
  "streams": ["BTCUSD@kline_1m"]
}
```

来源：https://developers.msx.com/docs/next/futures/ws-kline

---

<!-- source: https://developers.msx.com/docs/next/futures/ws-mini-ticker -->

## MiniTicker 全量推送

订阅所有合约交易对的 24 小时精简行情，每 3000ms 推送一次全量快照。

### 连接成功（欢迎消息）

连接建立后，服务端主动推送一条欢迎消息：

```
{
  "event": "connected",
  "message": "合约行情WebSocket连接成功",
  "timestamp": 1719290000000,
  "data": {
    "clientId": "abc123",
    "supportChannels": ["order_book", "ticker", "book_ticker", "kline", "miniTickerArr", "markPrice"],
    "streamFormat": "SYMBOL@CHANNEL (例如: BTCUSDT@order_book20, BTCUSDT@kline_1m, BTCUSDT@markPrice) 或 !miniTicker@arr@3000ms"
  }
}
```

### 订阅格式

`!miniTicker@arr@3000ms`

#### 订阅请求

```
{
  "action": "subscribe",
  "streams": ["!miniTicker@arr@3000ms"]
}
```

#### 订阅成功响应

```
{
  "event": "subscribed",
  "message": "订阅成功",
  "timestamp": 1719290000000,
  "data": {
    "streams": ["!miniTicker@arr@3000ms"]
  }
}
```

| 字段         | 类型     | 说明                       |
| ------------ | -------- | -------------------------- |
| event        | string   | 固定为`subscribed`       |
| message      | string   | 提示信息                   |
| timestamp    | int64    | 时间戳（毫秒）             |
| data.streams | string[] | 本次成功订阅的 stream 列表 |

### 推送数据

#### 外层字段

| 字段      | 类型   | 说明                                |
| --------- | ------ | ----------------------------------- |
| event     | string | 固定为`data`                      |
| stream    | string | 固定为`!miniTicker@arr@3000ms`    |
| channel   | string | 固定为`miniTickerArr`             |
| timestamp | int64  | 推送时间戳（毫秒）                  |
| data      | array  | MiniTickerItem 数组，包含所有交易对 |

#### data[] 单条字段

| 字段 | 类型   | 说明                    |
| ---- | ------ | ----------------------- |
| s    | string | 交易对，如`BTCUSDT`   |
| c    | string | 最新价（收盘价）        |
| o    | string | 开盘价                  |
| h    | string | 24h 最高价              |
| l    | string | 24h 最低价              |
| v    | string | 24h 成交量              |
| P    | string | 涨跌幅 %，保留 4 位小数 |
| E    | int64  | 本条数据时间戳（毫秒）  |

#### 推送示例

```
{
  "event": "data",
  "stream": "!miniTicker@arr@3000ms",
  "channel": "miniTickerArr",
  "timestamp": 1719290000000,
  "data": [
    {
      "s": "BTCUSDT",
      "c": "65000.00",
      "o": "63000.00",
      "h": "66000.00",
      "l": "62000.00",
      "v": "1234.5678",
      "P": "3.1746",
      "E": 1719290000000
    }
  ]
}
```

### 取消订阅

#### 取消订阅请求

```
{
  "action": "unsubscribe",
  "streams": ["!miniTicker@arr@3000ms"]
}
```

#### 取消订阅响应

```
{
  "event": "unsubscribed",
  "message": "取消订阅成功",
  "timestamp": 1719290000000,
  "data": {
    "streams": ["!miniTicker@arr@3000ms"]
  }
}
```

来源：https://developers.msx.com/docs/next/futures/ws-mini-ticker

---

<!-- source: https://developers.msx.com/docs/next/futures/ws-order-book -->

## 订单簿全量快照

订阅定时推送的完整合约订单簿快照。

### 订阅格式

`{symbol}@order_book{N}[@speed]`

- **N**: 档位深度，可选值: 5, 10, 20, 50, 100
- **speed**: 推送频率，可选值: 100ms, 1000ms

### 示例

- `BTCUSD@order_book20` - 20档深度，默认频率
- `BTCUSD@order_book20@100ms` - 20档深度，100毫秒推送一次

#### 订阅请求

```
{
  "action": "subscribe",
  "streams": ["BTCUSD@order_book20"]
}
```

#### 推送数据字段

| 字段           | 类型   | 说明              |
| -------------- | ------ | ----------------- |
| event          | string | 事件类型: data    |
| channel        | string | 频道: order_book  |
| data.symbol    | string | 合约标识          |
| data.bids      | array  | 买盘 [价格, 数量] |
| data.asks      | array  | 卖盘 [价格, 数量] |
| data.timestamp | int64  | 快照时间戳        |
| time           | int64  | 推送时间戳        |

#### 推送示例

```
{
  "event": "data",
  "channel": "order_book",
  "data": {
    "symbol": "BTCUSD",
    "bids": [
      ["50100.00", "10"],
      ["50090.00", "5"]
    ],
    "asks": [
      ["50120.00", "8"],
      ["50130.00", "12"]
    ],
    "timestamp": 1736163000000
  },
  "time": 1736163000000
}
```

来源：https://developers.msx.com/docs/next/futures/ws-order-book

---

<!-- source: https://developers.msx.com/docs/next/futures/ws-order-book-update -->

## 订单簿增量更新

订阅合约订单簿的增量变化，用于本地维护完整订单簿。

### 订阅格式

`{symbol}@order_book_update`

#### 订阅请求

```
{
  "action": "subscribe",
  "streams": ["BTCUSD@order_book_update"]
}
```

#### 推送数据字段

| 字段 | 类型   | 说明                  |
| ---- | ------ | --------------------- |
| s    | string | 合约标识              |
| U    | int64  | 首次更新ID            |
| u    | int64  | 末次更新ID            |
| b    | array  | 买盘变化 [价格, 数量] |
| a    | array  | 卖盘变化 [价格, 数量] |
| t    | int64  | 时间戳                |
| 重要 |        |                       |

数量为 `"0"` 表示删除该价格档位

#### 推送示例

```
{
  "action": "order_book_update",
  "result": {
    "s": "BTCUSD",
    "U": 1000,
    "u": 1005,
    "b": [
      ["50100.00", "10"],
      ["50090.00", "5"]
    ],
    "a": [
      ["50120.00", "8"],
      ["50130.00", "0"]
    ],
    "t": 1736163000000
  }
}
```

来源：https://developers.msx.com/docs/next/futures/ws-order-book-update

---

<!-- source: https://developers.msx.com/docs/next/futures/ws-orderbook-sync -->

## 本地订单簿维护

通过 WebSocket 增量更新维护本地订单簿，实现低延迟的深度数据访问。

### 核心概念

| 字段   | 说明                                                     |
| ------ | -------------------------------------------------------- |
| `U`  | 首个更新ID (first_update_id) - 本次推送包含的第一个更新  |
| `u`  | 末尾更新ID (last_update_id) - 本次推送包含的最后一个更新 |
| `id` | REST API 快照返回的序列号（需要`with_id=true`）        |

### 同步流程

1. **订阅增量更新**：订阅 `{symbol}@order_book_update`
2. **缓存消息**：在获取快照前，缓存收到的所有增量消息
3. **获取快照**：调用 REST API 获取订单簿快照（带序列号）

```
GET /api/v1/futures/open-api/orderbook/BTCUSDT?depth=100&with_id=true
```

1. **处理缓存**：
   丢弃 `u < id + 1` 的消息（已过期）
   找到 `U <= id + 1 && u >= id + 1` 的消息开始同步
   如果 `U > id + 1` 说明快照落后，需要重新获取
2. **持续更新**：检查每条消息 `U <= lastProcessedId + 1`，否则重建

### 更新规则

- 数量为 `"0"` 表示**删除**该价格档位
- 数量非零表示**更新或新增**该价格档位
- 买单 (b) 按价格**从高到低**排序
- 卖单 (a) 按价格**从低到高**排序

### 伪代码示例

```
// 1. 建立 WebSocket 连接并订阅
ws.send(JSON.stringify({
    action: 'subscribe',
    streams: ['BTCUSDT@order_book_update']
}));

// 2. 缓存收到的增量消息
const buffer = [];
ws.onmessage = (msg) => {
    const data = JSON.parse(msg.data);
    if (data.action === 'order_book_update') {
        buffer.push(data.result);
    }
};

// 3. 获取 REST API 快照（带序列号）
const snapshot = await fetch('/api/v1/futures/open-api/orderbook/BTCUSDT?depth=100&with_id=true');
const { bids, asks, id: snapshotId } = snapshot.data;

// 4. 初始化本地订单簿
const orderbook = {
    bids: new Map(bids.map(([p, q]) => [p, q])),
    asks: new Map(asks.map(([p, q]) => [p, q])),
    lastUpdateId: snapshotId
};

// 5. 处理缓存的消息
for (const update of buffer) {
    if (update.u < snapshotId + 1) continue;
    if (update.U > snapshotId + 1) {
        rebuildOrderbook();
        break;
    }
    applyUpdate(update);
}

// 6. 应用增量更新
function applyUpdate(update) {
    for (const [price, qty] of update.b) {
        if (qty === '0') orderbook.bids.delete(price);
        else orderbook.bids.set(price, qty);
    }
    for (const [price, qty] of update.a) {
        if (qty === '0') orderbook.asks.delete(price);
        else orderbook.asks.set(price, qty);
    }
    orderbook.lastUpdateId = update.u;
}
```

### 错误处理

| 错误场景                          | 处理方式                       |
| --------------------------------- | ------------------------------ |
| WebSocket 断开                    | 自动重连，重新订阅，重建订单簿 |
| 序列号不连续 (`U > lastId + 1`) | 重新获取快照，重建订单簿       |
| 快照落后                          | 重新获取快照                   |

### 注意事项

- 增量推送频率：100ms 聚合一次
- 价格和数量为字符串类型，避免浮点精度问题
- 建议定期校验本地订单簿与 REST API 快照的一致性

来源：https://developers.msx.com/docs/next/futures/ws-orderbook-sync

---

<!-- source: https://developers.msx.com/docs/next/futures/ws-overview -->

## WebSocket 连接说明

### 连接地址

```
wss://api9528mystks.mystonks.org/api/v1/futures/ws
```

### 通用规则

- **协议**: WebSocket (ws:// 或 wss://)
- **数据格式**: JSON
- **心跳超时**: 70 秒无消息自动断开
- **建议心跳间隔**: 每 20 秒发送一次 ping

### 心跳机制

#### 心跳请求

```
{"action": "ping"
}
```

#### 心跳响应

```
{"event": "pong", "timestamp": 1736163000000}
```

来源：https://developers.msx.com/docs/next/futures/ws-overview

---

<!-- source: https://developers.msx.com/docs/next/futures/ws-ticker -->

## Ticker 订阅

订阅合约 24 小时行情统计，每秒推送一次。

### 订阅格式

`{symbol}@ticker`

#### 订阅请求

```
{"action": "subscribe", "streams": ["BTCUSDT@ticker"]}
```

#### 推送字段

| 字段                    | 类型   | 说明                     |
| ----------------------- | ------ | ------------------------ |
| event                   | string | 事件类型，固定为`data` |
| stream                  | string | 订阅的流                 |
| channel                 | string | 频道，固定为`ticker`   |
| data.symbol             | string | 合约交易对               |
| data.lastPrice          | string | 最新成交价               |
| data.markPrice          | string | 标记价格                 |
| data.priceChange        | string | 24小时价格变动（绝对值） |
| data.priceChangePercent | string | 24小时涨跌幅（百分比）   |
| data.high24h            | string | 24小时最高价             |
| data.low24h             | string | 24小时最低价             |
| data.volume24h          | string | 24小时成交量             |
| data.timestamp          | int64  | 数据时间戳（毫秒）       |
| timestamp               | int64  | 推送时间戳（毫秒）       |

#### 推送示例

```
{
  "event": "data",
  "stream": "BTCUSDT@ticker",
  "channel": "ticker",
  "timestamp": 1736163000000,
  "data": {
    "symbol": "BTCUSDT",
    "lastPrice": "68620.5",
    "markPrice": "67200.0",
    "priceChange": "1120.5",
    "priceChangePercent": "1.66",
    "high24h": "69200.5",
    "low24h": "67200.0",
    "volume24h": "1250.85",
    "timestamp": 1736163000000
  }
}
```

#### 说明

- 推送频率为每秒一次。
- 价格与数量字段均为字符串类型。

来源：https://developers.msx.com/docs/next/futures/ws-ticker

---

## Legacy V1.0

<!-- source: https://developers.msx.com/docs/1.0/derivatives/ -->

## Derivatives Endpoints

MSX 衍生品数据接口规范，对外提供三个核心端点：产品列表（B1）、合约规格/价格（B2）与订单簿（B3）。

| 配置项      | 值                                     |
| ----------- | -------------------------------------- |
| 测试域名    | `https://test.test9529.xyz`          |
| 生产域名    | `https://api9528mystks.mystonks.org` |
| Base URL    | `/api/v1/fdata`                      |
| Symbol 格式 | `\{BASE\}-USD-PERP`                  |
| 接口数量    | 3 个 GET 接口                          |

### 接口一览

| Endpoint     | 路由                               | 描述                        |
| ------------ | ---------------------------------- | --------------------------- |
| **B1** | `GET /api/v1/fdata/productList`  | 全量产品列表（行情 + 费率） |
| **B2** | `GET /api/v1/fdata/ticker/price` | 合约规格 / 标记价格         |
| **B3** | `GET /api/v1/fdata/depth`        | 订单簿深度                  |

来源：https://developers.msx.com/docs/1.0/derivatives/

---

<!-- source: https://developers.msx.com/docs/1.0/derivatives/errors -->

## 错误响应

| HTTP 状态码 | error 字段                           | 原因                                   |
| ----------- | ------------------------------------ | -------------------------------------- |
| 500         | `invalid symbol format: XXX`       | symbol 格式不符合`\{BASE\}-USD-PERP` |
| 500         | `unsupported symbol: XXXUSDT`      | 该 symbol 不在系统支持的产品列表中     |
| 500         | `no data returned for symbol: XXX` | 未返回数据（超时或异常）               |

危险

所有错误均以 HTTP 500 + JSON body 返回，字段为 `{ "error": "..." }`。

### Error Response Example

```
{
  "error": "invalid symbol format: BTC-USDT"
}
```

来源：https://developers.msx.com/docs/1.0/derivatives/errors

---

<!-- source: https://developers.msx.com/docs/1.0/derivatives/legend -->

## 字段标注说明

| 标注                  | 含义                   |
| --------------------- | ---------------------- |
| **必填**        | 接口必须返回该字段     |
| **推荐 / 可选** | 强烈建议提供或有默认值 |
| **仅期货/期权** | 永续合约固定返回 0     |

来源：https://developers.msx.com/docs/1.0/derivatives/legend

---

<!-- source: https://developers.msx.com/docs/1.0/derivatives/order-book -->

## Endpoint B3 — Order Book

`GET /api/v1/fdata/depth`

返回指定合约的订单簿深度，默认深度 100 档（买卖各 50）。

### Request Parameters

| 参数   | 类型    | 必填           | 说明                                                     |
| ------ | ------- | -------------- | -------------------------------------------------------- |
| symbol | string  | **必填** | 合约标识，格式`\{BASE\}-USD-PERP`，如 `ETH-USD-PERP` |
| limit  | integer | 可选           | 深度档数，默认`100`                                    |

### Response Fields

| 字段名    | 类型             | 必填           | 描述                                               |
| --------- | ---------------- | -------------- | -------------------------------------------------- |
| ticker_id | string           | **必填** | 合约标识，与请求 symbol 一致                       |
| timestamp | Integer (UTC ms) | **必填** | 订单簿最后更新时间戳                               |
| bids      | float64[][]      | **必填** | 买单数组，每项`[价格, 数量]`，按价格从高到低排列 |
| asks      | float64[][]      | **必填** | 卖单数组，每项`[价格, 数量]`，按价格从低到高排列 |

### Request Example

```
GET /api/v1/fdata/depth?symbol=BTC-USD-PERP&limit=10
```

### Response Example

```
{
  "ticker_id": "BTC-USD-PERP",
  "timestamp": 1743091200000,
  "bids": [
    [65418.00, 0.263],
    [65415.50, 0.184],
    [65410.00, 0.441]
    // ... 最多 limit 档
  ],
  "asks": [
    [65422.00, 0.105],
    [65425.00, 0.273],
    [65430.50, 0.158]
    // ... 最多 limit 档
  ]
}
```

来源：https://developers.msx.com/docs/1.0/derivatives/order-book

---

<!-- source: https://developers.msx.com/docs/1.0/derivatives/product-list -->

## Endpoint B1 — Product List

`GET /api/v1/fdata/productList`

返回系统内所有已上线的永续合约产品摘要信息，包含 24h 行情、资金费率、手续费等。无需传参。

### Request Parameters

无需传参

### Response Fields

| 字段名                      | 类型             | 必填           | 描述                                                       |
| --------------------------- | ---------------- | -------------- | ---------------------------------------------------------- |
| ticker_id                   | string           | **必填** | 合约标识符，格式`\{BASE\}-USD-PERP`，如 `BTC-USD-PERP` |
| base_currency               | string           | **必填** | 基础资产符号，如`BTC`                                    |
| quote_currency              | string           | **必填** | 报价资产，固定为`USD`                                    |
| last_price                  | decimal          | **必填** | 最新成交价                                                 |
| base_volume                 | decimal          | **必填** | 24h 基础货币成交量                                         |
| USD_volume                  | decimal          | 推荐           | 24h USD 成交量                                             |
| quote_volume                | decimal          | **必填** | 24h 报价货币成交量                                         |
| bid                         | decimal          | **必填** | 当前买一价（取 last_price 近似）                           |
| ask                         | decimal          | **必填** | 当前卖一价（取 last_price 近似）                           |
| high                        | decimal          | **必填** | 24h 最高价                                                 |
| low                         | decimal          | **必填** | 24h 最低价                                                 |
| product_type                | string           | **必填** | 合约类型，固定为`PERPETUAL`                              |
| open_interest               | decimal          | **必填** | 未平仓合约数量（暂返回`0`）                              |
| open_interest_usd           | decimal          | **必填** | 未平仓 USD 价值（暂返回`0`）                             |
| index_price                 | decimal          | **必填** | 指数价格                                                   |
| creation_timestamp          | Integer (UTC ms) | 仅期货/期权    | 永续合约固定返回`0`                                      |
| expiry_timestamp            | Integer (UTC ms) | 仅期货/期权    | 永续合约固定返回`0`                                      |
| funding_rate                | decimal          | **必填** | 当前资金费率（lastFundingRate）                            |
| next_funding_rate           | decimal          | 推荐           | 预测下期资金费率                                           |
| next_funding_rate_timestamp | Integer (UTC ms) | **必填** | 下次资金费率结算时间戳（nextFundingTime）                  |
| maker_fee                   | decimal          | 推荐           | Maker 费率，来自产品配置（负值表示返佣）                   |
| taker_fee                   | decimal          | 推荐           | Taker 费率，来自产品配置                                   |

### Response Example

```
[
  {
    "ticker_id": "BTC-USD-PERP",
    "base_currency": "BTC",
    "quote_currency": "USD",
    "last_price": "65420.50",
    "base_volume": "2890.07",
    "USD_volume": "188978040.17",
    "quote_volume": "188978040.17",
    "bid": "65420.50",
    "ask": "65420.50",
    "high": "66100.00",
    "low": "64800.00",
    "product_type": "PERPETUAL",
    "open_interest": "0",
    "open_interest_usd": "0",
    "index_price": "65419.80",
    "creation_timestamp": 0,
    "expiry_timestamp": 0,
    "funding_rate": "0.0001",
    "next_funding_rate": "0.0001",
    "next_funding_rate_timestamp": 1743091200000,
    "maker_fee": "-0.0002",
    "taker_fee": "0.0005"
  }
]
```

来源：https://developers.msx.com/docs/1.0/derivatives/product-list

---

<!-- source: https://developers.msx.com/docs/1.0/derivatives/symbol-format -->

## Symbol 格式说明

注意

所有需要传 `symbol` 参数的接口（B2、B3），均使用 **{BASE}-USD-PERP** 格式，大小写敏感。

### 映射关系

| 请求 symbol  | 内部交易对 | 说明            |
| ------------ | ---------- | --------------- |
| BTC-USD-PERP | BTCUSDT    | 比特币永续合约  |
| ETH-USD-PERP | ETHUSDT    | 以太坊永续合约  |
| SOL-USD-PERP | SOLUSDT    | Solana 永续合约 |

提示

格式解析规则：按 `-` 分隔为三段，必须满足 `\{BASE\}-USD-PERP`（第二段 `USD`，第三段 `PERP`），否则返回 `invalid symbol format` 错误。

来源：https://developers.msx.com/docs/1.0/derivatives/symbol-format

---

<!-- source: https://developers.msx.com/docs/1.0/derivatives/ticker-price -->

## Endpoint B2 — Ticker / Price

`GET /api/v1/fdata/ticker/price`

返回指定合约的规格信息，包括合约类型、标记价格及计价货币。

### Request Parameters

| 参数   | 类型   | 必填           | 说明                                                     |
| ------ | ------ | -------------- | -------------------------------------------------------- |
| symbol | string | **必填** | 合约标识，格式`\{BASE\}-USD-PERP`，如 `BTC-USD-PERP` |

### Response Fields

| 字段名                  | 类型    | 必填           | 描述                          |
| ----------------------- | ------- | -------------- | ----------------------------- |
| contract_type           | string  | **必填** | 合约类型，固定为`PERPETUAL` |
| contract_price          | decimal | **必填** | 当前标记价格（markPrice）     |
| contract_price_currency | string  | **必填** | 计价货币，固定为`USD`       |

### Request Example

```
GET /api/v1/fdata/ticker/price?symbol=BTC-USD-PERP
```

### Response Example

```
{
  "contract_type": "PERPETUAL",
  "contract_price": "65419.80",
  "contract_price_currency": "USD"
}
```

来源：https://developers.msx.com/docs/1.0/derivatives/ticker-price

---

<!-- source: https://developers.msx.com/docs/1.0/futures-notice -->

## 合约 API

信息

V1.0 版本仅包含 **衍生品数据接口**（Derivatives Endpoints），合约 API 请查看最新版本文档。

来源：https://developers.msx.com/docs/1.0/futures-notice

---

<!-- source: https://developers.msx.com/docs/1.0/spot-notice -->

## 现货 API

信息

V1.0 版本仅包含 **衍生品数据接口**（Derivatives Endpoints），现货 API 请查看最新版本文档。

来源：https://developers.msx.com/docs/1.0/spot-notice

---
