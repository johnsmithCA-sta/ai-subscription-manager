# ai-subscription-manager · AI 订阅管理助手

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg) ![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg) ![Release](https://img.shields.io/badge/Release-v1.1.0-green.svg) ![SkillHub](https://img.shields.io/badge/SkillHub-@user_65c8c185%2Fai-subscription-manager-orange.svg)

**English** — Track every AI subscription and API balance in one local ledger: 50 built-in AI product price definitions, renewal alerts, cost analytics, same-category price comparison, feature-overlap detection, and an HTML dashboard. All data stays on your machine.

Two questions this answers without spreadsheets: **how much am I actually spending on AI every month**, and **which of these subscriptions am I paying for twice**.

**Install / 安装**

```bash
skillhub install ai-subscription-manager --namespace user_65c8c185
# or / 或
git clone https://github.com/johnsmithCA-sta/ai-subscription-manager.git
```

---

## 它解决什么问题 / Why

AI 订阅的特点是**散、小、自动续费**：每月几十块、分散在十几家、到期日各不相同，单看都不心疼，加起来一年可能过万。而「哪个还该续」这个问题的答案，取决于你实际用了多少——不是看定价页。

AI subscriptions are scattered, small, and auto-renewing. Individually painless, collectively four figures a year. And "should I renew this" depends on how much you actually used it — not on the pricing page.

## 功能 / Features

| 模块 Module | 脚本 Script | 作用 Purpose |
|---|---|---|
| 台账 Ledger | `subscription_manager.py` | 订阅增删改查 |
| 到期提醒 Renewal alerts | `renewal_checker.py` | 即将扣费预警 |
| 续费指导 Renewal guide | `renewal_guide.py` | 该不该续的判断依据 |
| 成本统计 Cost analysis | `cost_analyzer.py` | 月度 / 年度支出拆解 |
| 同类比价 Price comparison | `price_comparator.py` | 同类替代品性价比排序 |
| 重叠检测 Overlap detection | `overlap_detector.py` | 找出重复订阅 |
| 仪表盘 Dashboard | `dashboard.py` | 生成独立 HTML 看板 |
| 导入导出 Import / export | `data_exchange.py` | 台账备份与恢复 |
| 价格维护 Price upkeep | `price_updater.py` | 刷新过时定价 |

## 设计取舍 / Design notes

- **本地优先 Local-first** — 台账是磁盘上的纯 JSON，不上传任何数据。
- **可扩展 Extensible** — 新产品、分类、功能标签都是数据文件（`products.json` / `categories.json` / `function_tags.json`），加一个产品不用改代码。
- **定价会过时 Prices go stale** — 内置 50 款产品定价，但明确做「过时检测」而不是假装数字永远准。

## 目录结构 / Layout

```
ai-subscription-manager/
├── LICENSE
└── skills/
    └── ai-subscription-manager/
        ├── SKILL.md
        ├── scripts/
        ├── products.json
        ├── categories.json
        ├── function_tags.json
        ├── rates.json
        ├── remind_config.json
        ├── token_prices.json
        └── subscription_schema.json
```

## 许可 / License

MIT
