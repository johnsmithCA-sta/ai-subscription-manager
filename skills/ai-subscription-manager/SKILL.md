---
name: ai-subscription-manager
slug: ai-subscription-manager
displayName: AI 订阅管理助手
summary: 内置 50 款主流 AI 产品定价库的本地订阅管理工具，覆盖订阅增删改查、到期提醒、成本统计、续费指导、同类比价、功能重叠检测与 HTML 可视化仪表盘全流程。
description: 管理AI产品订阅的综合工具，内置50款AI产品定价库，覆盖订阅增删改查、到期提醒、成本统计、续费指导、同类比价、导入导出、功能重叠检测、HTML可视化仪表盘等全流程。当用户提到以下任意关键词时立即触发：管理订阅、订阅管理、我的订阅、查看订阅、订阅列表、订阅状态、订阅仪表盘、AI订阅、AI会员、AI工具订阅、会员管理、查看会员、续费提醒、到期提醒、即将扣费、续费评估、续费建议、要不要续费、成本分析、花了多少钱、订阅开销、月度支出、年度支出、订阅费用、订阅比价、同类比价、价格对比、哪个便宜、性价比排行、替代方案、功能重叠、重复订阅、订阅导入、订阅导出、订阅备份、添加订阅、新增订阅、删除订阅、修改订阅、取消订阅、自定义产品、定价过时、定价更新、砍订建议、订阅优化。触发后必须生成HTML仪表盘并交付给用户，同时根据用户具体需求执行对应分析。
version: 1.1.0
license: MIT
author: johnsmithCA-sta
---

# AI 订阅管理助手

管理 50 款主流 AI 产品的订阅数据，提供从添加订阅到优化组合的全流程分析能力。所有数据存储在本地 JSON 文件中，脚本通过命令行调用。

## 依赖与运行环境

- **Python 3.8+**（全部脚本使用标准库，无第三方依赖）
- 完全本地运行：不联网、不上传任何数据，所有数据文件均为本地 JSON
- 跨平台：macOS / Linux / Windows（`--open` 打开仪表盘仅在 macOS 生效，Windows 可用 `start` / Linux 可用 `xdg-open` 自行打开）

## 数据文件

所有数据文件位于技能根目录（`scripts/` 的上级目录）：

| 文件 | 内容 |
|------|------|
| `products.json` | 50 款 AI 产品信息（名称、分类、标签、多档定价、功能列表） |
| `categories.json` | 5 大分类（AI对话/代码/图像/音频/写作） |
| `function_tags.json` | 19 个功能标签（含权重和分组） |
| `rates.json` | 汇率参考表（USD 基准，含更新时间，可手动更新） |
| `subscriptions.json` | 用户的订阅记录 |
| `subscription_schema.json` | 订阅字段定义和验证规则 |
| `remind_config.json` | 到期提醒配置（提醒天数、是否显示费用等） |

### 环境变量

- `SUBMGR_DATA_DIR`：自定义数据目录。设置后，所有脚本从该目录读取 `products.json`、`subscriptions.json`、`rates.json` 等文件，仪表盘也输出到该目录。适合需要把数据放在技能目录之外（如 iCloud / Git 仓库）的用户。未设置时默认使用技能根目录。

## 脚本一览

共 9 个脚本，均位于 `scripts/` 目录。所有脚本使用 `python3` 运行，参数通过 argparse 传递。

### 1. subscription_manager.py — 订阅 CRUD

```bash
python3 scripts/subscription_manager.py list                          # 列出所有订阅
python3 scripts/subscription_manager.py add --product chatgpt --tier Plus --price 20 --currency USD --start 2026-01-15 --billing monthly  # 添加订阅
python3 scripts/subscription_manager.py update <sub_id> --tier Pro    # 更新订阅
python3 scripts/subscription_manager.py remove <sub_id>               # 删除订阅
python3 scripts/subscription_manager.py summary                       # 订阅概览
python3 scripts/subscription_manager.py add-product                # 交互式添加自定义产品
python3 scripts/subscription_manager.py add-product --product-key myapp --display-name "我的应用" --category ai_chat --plans "Pro|39|CNY|monthly"  # 参数式添加
```

### 2. renewal_checker.py — 到期提醒

```bash
python3 scripts/renewal_checker.py check          # 检查即将到期的订阅
python3 scripts/renewal_checker.py check --days 7 # 检查 7 天内到期
python3 scripts/renewal_checker.py status          # 订阅状态总览
```

### 3. cost_analyzer.py — 成本统计

```bash
python3 scripts/cost_analyzer.py overview                    # 成本总览
python3 scripts/cost_analyzer.py by-category                # 按分类统计
python3 scripts/cost_analyzer.py by-product                 # 按产品统计
python3 scripts/cost_analyzer.py trend --months 6           # 月度趋势
python3 scripts/cost_analyzer.py budget --monthly 100 --currency USD  # 预算对比
python3 scripts/cost_analyzer.py savings                    # 节省建议
```

### 4. renewal_guide.py — 续费指导

```bash
python3 scripts/renewal_guide.py evaluate --product chatgpt        # 评估是否续费
python3 scripts/renewal_guide.py evaluate-all                      # 评估所有活跃订阅
python3 scripts/renewal_guide.py compare-plans --product cursor    # 对比该产品各档位
```

### 5. price_comparator.py — 比价功能

```bash
python3 scripts/price_comparator.py compare --category ai_chat                    # 同类对比
python3 scripts/price_comparator.py compare --category ai_code --currency CNY     # 指定币种
python3 scripts/price_comparator.py ranking                                       # 性价比排行
python3 scripts/price_comparator.py ranking --category ai_image                   # 分类排行
python3 scripts/price_comparator.py alternative --product chatgpt                 # 替代方案推荐
python3 scripts/price_comparator.py alternative                                   # 分析当前订阅的替代方案
python3 scripts/price_comparator.py cross-compare --min-tags 6                    # 跨分类全能排行
python3 scripts/price_comparator.py tier-guide --product cursor                   # 套餐指南
python3 scripts/price_comparator.py optimize                                            # 订阅优化建议（砍订分析+月省金额）
```

### 6. data_exchange.py — 导入导出

```bash
python3 scripts/data_exchange.py export-csv                          # 导出 CSV（中文表头）
python3 scripts/data_exchange.py export-json                         # 导出 JSON
python3 scripts/data_exchange.py import-csv file.csv --dry-run       # CSV 导入预览
python3 scripts/data_exchange.py import-csv file.csv                 # 正式导入
python3 scripts/data_exchange.py import-json backup.json --replace   # JSON 替换导入
python3 scripts/data_exchange.py template --format csv               # 生成导入模板
```

### 7. overlap_detector.py — 重叠检测

```bash
python3 scripts/overlap_detector.py overlap      # 功能重叠矩阵
python3 scripts/overlap_detector.py redundancy    # 冗余标签与支出分析
python3 scripts/overlap_detector.py coverage      # 功能覆盖率分析
python3 scripts/overlap_detector.py optimize      # 优化建议
```


### 8. dashboard.py — HTML 可视化仪表盘

```bash
python3 scripts/dashboard.py generate                    # 生成仪表盘（默认 dashboard.html）
python3 scripts/dashboard.py generate --output out.html  # 指定输出路径
python3 scripts/dashboard.py generate --open             # 生成后自动打开
```

仪表盘包含：订阅卡片、成本总览、分类支出环形图、续费日历、功能覆盖率、重叠分析、优化建议、同类产品对比。

### 9. price_updater.py — 定价保鲜检测

```bash
python3 scripts/price_updater.py status                          # 定价新鲜度概览
python3 scripts/price_updater.py check                           # 列出可能过时的产品
python3 scripts/price_updater.py check --all --category ai_chat  # 含中风险+按分类
python3 scripts/price_updater.py update --product chatgpt --touch                  # 标记定价已核对
python3 scripts/price_updater.py update --product chatgpt --tier Plus --price 20 --currency USD --billing monthly  # 更新套餐价格
```

检测 `products.json` 中每款产品的 `price_updated` 新鲜度，识别定价可能过时的产品（>=180 天高风险、90-180 天待关注）。`update` 为半自动引导：核对官网后手动标记或改价，避免盲目自动抓取。

## 入口引导流程

当用户首次调用此技能，或表达"管理订阅"/"添加订阅"/"查看订阅"等意图时，按以下流程引导用户完成操作。引导过程应自然对话式推进，避免一次性抛出所有步骤。

### Step 1：意图识别

根据用户表述判断操作类型。如果意图已经明确（如"帮我加个 ChatGPT 订阅"），直接跳到对应步骤，无需再问。

如果意图不明确，用以下选项询问：

```
你想做什么？
1. 📦 查看当前订阅
2. ➕ 添加新订阅
3. ✏️ 修改已有订阅
4. 📊 查看成本分析
5. 🔄 续费评估
6. 💰 同类比价
7. 🔗 重叠检测
8. 📋 可视化仪表盘
```

### Step 2：添加订阅（自然语言一步登记）

**核心原则**：用户用自然语言说，Agent 用 LLM 解析成结构化数据，一次确认后入库。目标 2 轮完成全部登记。

#### 2-1：一句话收集

展示简洁的引导提示，鼓励用户用自然语言表达：

```
📝 快速登记 — 直接告诉我你订阅了什么

示例：
• "ChatGPT Plus, Notion Business"
• "我用 Kimi Andante 套餐"
• "chatgpt, claude, kimi"（不确定套餐也行，我帮你推荐）
• "spotify家庭版 ¥68/月"
```

> **关键**：提示要短，给 3-4 个多样化示例覆盖不同表达风格（精确/模糊/含价格/纯产品名）。

#### 2-2：自然语言解析（Agent 内部执行）

收到用户输入后，Agent 按以下规则解析为结构化数据：

**产品名匹配（模糊匹配 products.json）：**
- 精确匹配：`display_name`、`product_key` → 直接命中
- 别名匹配：常见简称映射（如 "chat"→ChatGPT、"claude"→Claude、"mj"→Midjourney、"cursor"→Cursor、"gh"→GitHub Copilot、"文心"→文心一言、"千问"→通义千问、"kimi"→Kimi、"豆包"→豆包、"gemini"→Gemini、"pplx"→Perplexity、"copilot"→Microsoft 365 Copilot、"ms copilot"→Microsoft 365 Copilot、"adobe"→Adobe Creative Cloud、"ps"→Adobe Creative Cloud、"cc"→Adobe Creative Cloud、"11labs"→ElevenLabs、"leonardo"→Leonardo AI、"replit"→Replit、"grammarly"→Grammarly、"synthesia"→Synthesia、"descript"→Descript）
- 模糊匹配：Levenshtein 距离 ≤ 2 或包含关系
- 未匹配：保留原始名称，标记为 `custom`，提示用户确认 product_key

**套餐匹配（匹配 plans[].tier）：**
- 用户明确说了套餐名 → 模糊匹配 tier 字段（如 "plus"→Plus、"pro"→Pro、"business"→Business）
- 用户没说套餐 → 推荐该产品的第 2 档（通常是主力付费档，如 ChatGPT→Plus、Claude→Pro、Cursor→Pro）
- 推荐时在确认表中标注 `[推荐]`

**价格提取：**
- 用户说了价格（如 "¥68/月"、"$20"）→ 提取数字+币种
- 用户没说价格 → 使用 products.json 中对应 tier 的 price 和 currency
- 自定义产品 → 提示用户补充价格

**起始日期：**
- 默认当天日期（Agent 获取当前日期）
- 用户说了具体日期 → 使用用户指定的

**计费周期：**
- 默认 monthly
- 用户说了"年付"/"annual" → annual

#### 2-3：解析确认表（一轮展示 + 内联编辑）

将解析结果以表格形式展示，标注需要补充的信息，支持内联修改：

```
✅ 解析到 N 条订阅：
┌─┬──────────┬───────────┬────────┬──────────┐
│#│ 产品      │ 套餐       │ 月费    │ 周期     │
├─┼──────────┼───────────┼────────┼──────────┤
│1│ ChatGPT   │ Plus      │ $20/月 │ 月付     │
│2│ Notion AI │ Business  │ $20/月 │ 月付     │
│3│ Spotify   │ Family    │ ¥68/月 │ 月付     │ ← ⚠️ 自定义产品
└─┴──────────┴───────────┴────────┴──────────┘

⚠️ 需确认：
- #3 Spotify 不在产品库中，将作为自定义产品录入（product_key: spotify）

✅ 确认无误回复"ok"直接入库
✏️ 修改回复如：2改为Plus / 删掉3 / 1套餐改Pro
```

> **设计要点**：
> - 只问缺失/不确定的，已知的不追问
> - 支持内联编辑语法（修改/删除/追加），一轮搞定
> - 用户说"ok"就直接执行，不二次确认

#### 2-4：批量执行 + 自动生成仪表盘

用户确认后，逐条执行 `subscription_manager.py add`：

```bash
python3 scripts/subscription_manager.py add --product chatgpt --tier Plus --price 20 --currency USD --start 2026-08-21 --billing monthly
python3 scripts/subscription_manager.py add --product notion_ai --tier "Business (含完整 AI)" --price 20 --currency USD --start 2026-08-21 --billing monthly
python3 scripts/subscription_manager.py add --product spotify --tier Family --price 68 --currency CNY --start 2026-08-21 --billing monthly
```

执行完毕后自动生成仪表盘：

```bash
python3 scripts/dashboard.py generate --output dashboard.html
```

将仪表盘文件交付给用户预览。

#### 2-5：追问"还要加吗？"

仪表盘交付后，简短追问一次：

```
还有要加的吗？直接说产品名就行。
```

用户说"没了"/"不需要"则结束；否则回到 2-2 继续解析。

### Step 3：其他操作（修改 / 比价 / 续费评估等）

列出已订阅产品和产品库中的产品供用户选择。按分类分组展示，已订阅的标注 ⭐：

```
选择产品：
💬 AI对话：ChatGPT ⭐ / Claude / Gemini / 豆包 / Kimi / 智谱清言 / 文心一言 / 通义千问
💻 AI编程：Cursor ⭐ / GitHub Copilot / Windsurf / CodeGeeX
🎨 AI图像：Midjourney / DALL·E / Stable Diffusion / Runway
🎵 AI音频：Suno / Udio
✍️ AI写作：Notion AI / Jasper
```

> 注：⭐ 标记基于 `subscriptions.json` 中的实际记录动态生成，上方仅为示例。

确定产品后，读取 `products.json` 中该产品的套餐信息，按操作类型执行对应脚本。汇总用户的选择，以简洁摘要确认后执行：

```
确认一下：
• 操作：添加订阅
• 产品：ChatGPT
• 套餐：Plus（$20/月）
• 起始日期：2026-08-21
• 周期：月付

确认添加吗？(y/n)
```

用户确认后，执行对应脚本。执行完毕后将结果友好地展示给用户。

## 使用流程

配合入口引导流程，各脚本的使用逻辑如下：

1. **初始设置**：首次使用时 subscriptions.json 为空。引导用户通过 Step 2-4 添加首批订阅，或通过 `data_exchange.py import-csv` / `import-json` 批量导入。

2. **日常管理**：通过引导流程的"查看订阅"或"修改订阅"入口，调用 `subscription_manager.py` 的 `list` / `update` / `remove` 等命令。

3. **续费决策**：通过引导流程的"续费评估"入口，调用 `renewal_guide.py evaluate` 评估是否值得续费，用 `price_comparator.py compare` 看同类产品对比，用 `alternative` 找替代方案。

4. **优化组合**：通过引导流程的"重叠检测"入口，调用 `overlap_detector.py` 分析功能重叠和冗余支出，用 `optimize` 获取精简建议。

5. **生成仪表盘**：添加/修改订阅后，运行 `dashboard.py generate` 自动生成可交互管理界面，让用户直观掌握订阅全貌。

6. **数据备份**：定期用 `export-json` 导出备份。

## 快速场景

常见场景与自然语言的对应关系，Agent 识别后可直接执行对应命令，无需走完整引导流程：

| 用户说 | 执行命令 |
|--------|----------|
| "帮我看看每月花了多少钱" / "订阅开销" | `cost_analyzer.py overview` |
| "按分类看看花费" | `cost_analyzer.py by-category` |
| "未来几个月大概要花多少" | `cost_analyzer.py trend --months 6` |
| "ChatGPT 该续费吗" / "Cursor 值不值得续" | `renewal_guide.py evaluate --product <产品id>` |
| "所有订阅都评估一下" | `renewal_guide.py evaluate-all` |
| "我的订阅有哪些功能重叠" | `overlap_detector.py overlap` |
| "有没有浪费的钱" / "冗余支出" | `overlap_detector.py redundancy` |
| "怎么优化订阅组合" | `overlap_detector.py optimize` |
| "AI对话类产品哪个性价比高" | `price_comparator.py compare --category ai_chat` |
| "性价比排行" | `price_comparator.py ranking` |
| "有什么替代方案" | `price_comparator.py alternative` |
| "生成可视化仪表盘" / "看看仪表盘" | `dashboard.py generate` |
| "最近有什么要到的" / "到期提醒" | `renewal_checker.py check` |
| "导出备份" | `data_exchange.py export-json` |
| "看看我的所有订阅" | `subscription_manager.py list` |
| "帮我添加多个订阅" | 走 Step 2 自然语言引导流程 |
| "生成仪表盘" / "看看我的订阅面板" | `dashboard.py generate` |
| "我订阅了ChatGPT和Claude" / "加了个kimi" | 直接进入 Step 2，解析用户自然语言中的产品信息 |
| "chatgpt plus 和 claude pro" | 直接进入 Step 2，解析产品+套餐 |

> **注意**：快速场景是引导流程的快捷方式。如果用户的表述模糊、包含多步意图、或涉及需要选择产品的操作，仍应回到引导流程逐步确认。当用户直接说出产品名/套餐时，跳过 2-1 的提示，直接进入 2-2 解析。

## 输出风格

所有脚本输出为终端友好格式，使用 emoji 标记、ASCII 表格和进度条。中文显示，支持多币种（USD/CNY/EUR）。用户已订阅的产品会标注 ⭐。

## 产品库

当前内置 50 款产品覆盖 5 大分类：
- **AI 对话**(16)：ChatGPT、Claude、Gemini、豆包、Kimi、智谱清言、文心一言、通义千问、Perplexity、扣子、Manus、Genspark、海螺AI、讯飞星火、天工AI、Grok
- **AI 代码**(10)：Cursor、GitHub Copilot、Windsurf、CodeGeeX、Replit、CodeBuddy、Dify、Cline、Devin、Lovable
- **AI 图像/视频**(11)：Midjourney、DALL·E、Stable Diffusion、Runway、Canva、Adobe Creative Cloud、Leonardo AI、Synthesia、Recraft、可灵AI、即梦AI
- **AI 音频**(7)：Suno、Udio、ElevenLabs、Descript、AIVA、Mubert、Soundraw
- **AI 写作/效率**(6)：Notion AI、Jasper、Microsoft 365 Copilot、Grammarly、WorkBuddy、n8n

## 边界与安全

- **数据本地性**：全部数据（产品库/订阅/配置）仅存于本机 JSON 文件，脚本完全不联网、无任何数据外发，可放心使用。
- **敏感字段提示**：`subscriptions.json` 中的 `payment_method`（支付方式）与 `notes`（自由备注）会随 CSV/JSON 导出与仪表盘 HTML 一并落盘到本机。建议不要在 `notes` 中填写身份证号、银行卡号、密码等高度敏感信息；如需记录，注意导出的备份文件同样属于本地明文。
- **导出物管理**：`dashboard.html`、`subscriptions_export.csv/json` 默认生成在数据目录，请勿将含真实订阅数据的导出文件上传至公开仓库。
- **环境变量隔离**：如需将数据放在技能目录之外（iCloud/私有 Git 仓库），设置 `SUBMGR_DATA_DIR` 指向目标目录即可，技能包本身不携带用户数据。

## Changelog

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-08-26 | 1.1.0 | 产品库 36→50 款；新增 `price_updater.py` 定价保鲜检测、`add-product` 自定义产品、`optimize` 砍订建议；修复 CSV 导入 auto_renew 解析与仪表盘 `--open` 命令注入面；错误信息仅显示文件名；补全 SkillHub frontmatter 与依赖/安全说明 |
