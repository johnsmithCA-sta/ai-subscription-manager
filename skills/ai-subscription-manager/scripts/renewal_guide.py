#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
续费指导模块 - 帮助用户快速找到续费链接、取消方法、升降级操作指引
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

# 数据文件相对路径
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, "subscriptions.json")

SEPARATOR = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


# ============ 数据加载 ============

def load_json(filepath):
    """加载 JSON 文件"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_products():
    """加载产品模板库"""
    return load_json(PRODUCTS_FILE)


def load_subscriptions():
    """加载用户订阅记录"""
    return load_json(SUBSCRIPTIONS_FILE)


def find_product(products, product_key):
    """根据 product_key 查找产品"""
    for p in products:
        if p["product_key"] == product_key:
            return p
    return None


def get_active_subscriptions(subscriptions):
    """获取所有活跃订阅"""
    return [s for s in subscriptions if s["status"] == "active"]


def find_subscription(subscriptions, product_key):
    """查找某个产品的活跃订阅"""
    for s in subscriptions:
        if s["product_key"] == product_key and s["status"] == "active":
            return s
    return None


# ============ 套餐名称模糊匹配 ============

def normalize_name(name):
    """去除空格和特殊字符，用于模糊匹配"""
    return re.sub(r"[\s\-_·•\.\(\)（）\[\]【】]+", "", name).lower()


def fuzzy_match_tier(products_plans, target_name):
    """
    在套餐列表中模糊匹配套餐名称。
    返回 (匹配的plan, 匹配方式: 'exact'/'fuzzy'/'none')
    """
    # 先精确匹配
    for plan in products_plans:
        if plan["tier"] == target_name:
            return plan, "exact"

    # 再模糊匹配：去掉空格和特殊字符对比
    normalized_target = normalize_name(target_name)
    fuzzy_candidates = []
    for plan in products_plans:
        normalized_plan = normalize_name(plan["tier"])
        if normalized_plan == normalized_target:
            return plan, "fuzzy"
        # 记录相似度候选项
        if normalized_target in normalized_plan or normalized_plan in normalized_target:
            fuzzy_candidates.append(plan)

    # 如果有模糊候选项，返回第一个
    if fuzzy_candidates:
        return fuzzy_candidates[0], "fuzzy"

    return None, "none"


def list_similar_tiers(plans, target_name):
    """列出相似的套餐名称供参考"""
    normalized_target = normalize_name(target_name)
    suggestions = []
    for plan in plans:
        normalized_plan = normalize_name(plan["tier"])
        # 至少有一个共同字符
        common_chars = set(normalized_target) & set(normalized_plan)
        if len(common_chars) >= 2:
            suggestions.append(plan["tier"])
    return suggestions


# ============ 格式化输出 ============

def format_price(price, currency):
    """格式化价格显示"""
    if price is None:
        return "定制报价"
    if price == 0:
        return "免费"
    symbol = "¥" if currency == "CNY" else "$"
    return f"{symbol}{price:,.2f}"


def format_billing_cycle(cycle):
    """格式化计费周期"""
    mapping = {
        "monthly": "月付",
        "annual": "年付",
        "pay_per_use": "按量付费",
        "custom": "定制",
    }
    return mapping.get(cycle, cycle)


def format_features_truncated(features, max_len=24):
    """截断功能列表显示"""
    text = ", ".join(features)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def pad_to_width(text, width):
    """按显示宽度填充空格（中文字符占2宽度）"""
    display_width = 0
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            display_width += 2
        else:
            display_width += 1
    padding = max(0, width - display_width)
    return text + " " * padding


# ============ 命令实现 ============

def cmd_info(product_key):
    """查看某产品的续费信息"""
    products = load_products()
    product = find_product(products, product_key)
    if not product:
        print(f"❌ 未找到产品: {product_key}")
        print(f"💡 可用产品: {', '.join(p['product_key'] for p in products)}")
        sys.exit(1)

    display_name = product["display_name"]
    renewal_url = product["renewal_url"]
    cancel_guide = product["cancel_guide"]
    plans = product["plans"]

    print(f"📋 {display_name} 续费信息")
    print(SEPARATOR)
    print()
    print(f"🔗 续费链接: {renewal_url}")
    print(f"❌ 取消方法: {cancel_guide}")
    print()

    # 套餐对比表格
    print("📦 当前套餐对比:")
    # 表头
    header = f"│ {'套餐':<12} │ {'价格':<10} │ {'周期':<6} │ {'核心功能':<40} │"
    # 计算显示宽度
    col1_w = 12
    col2_w = 10
    col3_w = 6
    col4_w = 40

    top_border = "┌" + "─" * (col1_w + 2) + "┬" + "─" * (col2_w + 2) + "┬" + "─" * (col3_w + 2) + "┬" + "─" * (col4_w + 2) + "┐"
    mid_border = "├" + "─" * (col1_w + 2) + "┼" + "─" * (col2_w + 2) + "┼" + "─" * (col3_w + 2) + "┼" + "─" * (col4_w + 2) + "┤"
    bottom_border = "└" + "─" * (col1_w + 2) + "┴" + "─" * (col2_w + 2) + "┴" + "─" * (col3_w + 2) + "┴" + "─" * (col4_w + 2) + "┘"

    print(top_border)
    # 表头需要手动处理宽度
    h1 = pad_to_width("套餐", col1_w)
    h2 = pad_to_width("价格", col2_w)
    h3 = pad_to_width("周期", col3_w)
    h4 = pad_to_width("核心功能", col4_w)
    print(f"│ {h1} │ {h2} │ {h3} │ {h4} │")
    print(mid_border)

    for plan in plans:
        tier = pad_to_width(plan["tier"], col1_w)
        price_str = pad_to_width(format_price(plan["price"], plan["currency"]), col2_w)
        cycle_str = pad_to_width(format_billing_cycle(plan["billing_cycle"]), col3_w)
        features_str = pad_to_width(format_features_truncated(plan["features"], col4_w), col4_w)
        print(f"│ {tier} │ {price_str} │ {cycle_str} │ {features_str} │")

    print(bottom_border)
    print()

    # 升降级提示
    if len(plans) > 1:
        print("💡 升降级提示:")
        print("  - 升级: 在 billing 页面选择更高套餐，差价立即生效")
        print("  - 降级: 在当前计费周期结束后生效")


def cmd_list():
    """查看所有已订阅产品的续费信息"""
    products = load_products()
    subscriptions = load_subscriptions()
    active_subs = get_active_subscriptions(subscriptions)

    if not active_subs:
        print("📋 暂无活跃订阅")
        return

    print("📋 已订阅产品续费信息")
    print(SEPARATOR)
    print()

    for i, sub in enumerate(active_subs, 1):
        product = find_product(products, sub["product_key"])
        if not product:
            continue

        display_name = product["display_name"]
        tier = sub["tier"]
        currency = sub["currency"]
        price = sub["price_paid"]
        next_billing = sub["next_billing_date"]
        renewal_url = product["renewal_url"]
        cancel_guide = product["cancel_guide"]

        print(f"{i}. {display_name} ({tier}) - {format_price(price, currency)}/{format_billing_cycle(sub['billing_cycle'])}")
        print(f"   🔗 续费: {renewal_url}")
        print(f"   ❌ 取消: {cancel_guide}")
        print(f"   📅 下次扣费: {next_billing}")
        print()


def cmd_change(product_key, from_tier, to_tier, direction="upgrade"):
    """套餐升降级指引"""
    products = load_products()
    product = find_product(products, product_key)
    if not product:
        print(f"❌ 未找到产品: {product_key}")
        sys.exit(1)

    display_name = product["display_name"]
    plans = product["plans"]
    renewal_url = product["renewal_url"]

    # 查找源套餐
    from_plan, from_match = fuzzy_match_tier(plans, from_tier)
    if not from_plan:
        print(f"❌ 未找到套餐: {from_tier}")
        suggestions = list_similar_tiers(plans, from_tier)
        if suggestions:
            print(f"💡 相似套餐: {', '.join(suggestions)}")
        print(f"📦 可用套餐: {', '.join(p['tier'] for p in plans)}")
        sys.exit(1)
    if from_match == "fuzzy":
        print(f"💡 模糊匹配: '{from_tier}' → '{from_plan['tier']}'")

    # 查找目标套餐
    to_plan, to_match = fuzzy_match_tier(plans, to_tier)
    if not to_plan:
        print(f"❌ 未找到套餐: {to_tier}")
        suggestions = list_similar_tiers(plans, to_tier)
        if suggestions:
            print(f"💡 相似套餐: {', '.join(suggestions)}")
        print(f"📦 可用套餐: {', '.join(p['tier'] for p in plans)}")
        sys.exit(1)
    if to_match == "fuzzy":
        print(f"💡 模糊匹配: '{to_tier}' → '{to_plan['tier']}'")

    if from_plan["tier"] == to_plan["tier"]:
        print(f"⚠️ 当前套餐和目标套餐相同: {from_plan['tier']}")
        sys.exit(1)

    direction_label = "升级" if direction == "upgrade" else "降级"

    print(f"🔄 {display_name} 套餐{direction_label}指引")
    print(SEPARATOR)
    print()
    print(f"当前: {from_plan['tier']} ({format_price(from_plan['price'], from_plan['currency'])}/月) → 目标: {to_plan['tier']} ({format_price(to_plan['price'], to_plan['currency'])}/月)")
    print()

    # 操作步骤
    action_word = "Change Plan" if direction == "upgrade" else "Downgrade"
    print("📝 操作步骤:")
    print(f"  1. 打开 {renewal_url}")
    print(f"  2. 点击 \"{action_word}\" 或 \"{direction_label}\"")
    print(f"  3. 选择 \"{to_plan['tier']}\" 套餐")
    print("  4. 确认支付方式")
    print("  5. 确认变更")
    print()

    # 费用变化
    if from_plan["price"] is not None and to_plan["price"] is not None:
        diff = to_plan["price"] - from_plan["price"]
        sign = "+" if diff >= 0 else ""
        annual_diff = diff * 12
        annual_sign = "+" if annual_diff >= 0 else ""
        currency_symbol = "¥" if from_plan["currency"] == "CNY" else "$"

        print("💰 费用变化:")
        print(f"  - 月费: {format_price(from_plan['price'], from_plan['currency'])} → {format_price(to_plan['price'], to_plan['currency'])} ({sign}{currency_symbol}{abs(diff):,.2f}/月)")
        print(f"  - 年费影响: {annual_sign}{currency_symbol}{abs(annual_diff):,.2f}/年")
        print()

    # 功能对比
    from_features = set(from_plan.get("features", []))
    to_features = set(to_plan.get("features", []))
    gained = to_features - from_features
    lost = from_features - to_features

    if gained or lost:
        print("📊 功能变化:")
        if gained:
            print("  ✅ 新增功能:")
            for f in gained:
                print(f"     + {f}")
        if lost:
            print("  ⚠️ 减少功能:")
            for f in lost:
                print(f"     - {f}")
        print()

    # 注意事项
    print("⚠️ 注意事项:")
    if direction == "upgrade":
        print("  - 升级立即生效，按比例补差价")
        print("  - 新功能在当前计费周期内即可使用")
    else:
        print("  - 降级在当前计费周期结束后生效")
        print("  - 周期结束前仍可使用当前套餐功能")
        print("  - 请提前保存使用中的重要数据")


def cmd_cancel(product_key):
    """取消订阅指引"""
    products = load_products()
    product = find_product(products, product_key)
    if not product:
        print(f"❌ 未找到产品: {product_key}")
        sys.exit(1)

    display_name = product["display_name"]
    renewal_url = product["renewal_url"]
    cancel_guide = product["cancel_guide"]
    plans = product["plans"]

    print(f"❌ {display_name} 取消订阅指引")
    print(SEPARATOR)
    print()

    # 操作步骤
    steps = cancel_guide.split("→")
    print("📝 操作步骤:")
    step_num = 1
    print(f"  {step_num}. 打开 {renewal_url}")
    step_num += 1
    for i, step in enumerate(steps):
        step = step.strip()
        if i == 0:
            print(f"  {step_num}. {step}")
        else:
            print(f"  {step_num}. 进入 {step}")
        step_num += 1
    # 确认步骤
    print(f"  {step_num}. 确认取消")
    print()

    # 注意事项
    print("⚠️ 注意事项:")
    print("  - 取消后当前计费周期内仍可使用")
    print("  - 周期结束后自动降级为免费版")
    print("  - 历史数据不会丢失")
    print()

    # 取消前考虑：推荐免费/低价替代
    free_plans = [p for p in plans if p["price"] == 0]
    lower_plans = []
    sub = find_subscription(load_subscriptions(), product_key)
    if sub:
        current_price = sub["price_paid"]
        lower_plans = [p for p in plans if p["price"] is not None and 0 < p["price"] < current_price]

    if free_plans or lower_plans:
        print("💡 取消前考虑:")
        if free_plans:
            for fp in free_plans:
                print(f"  - 是否可降级到「{fp['tier']}」保留基本功能？")
        if lower_plans:
            for lp in lower_plans:
                print(f"  - 是否可降级到「{lp['tier']}」({format_price(lp['price'], lp['currency'])}/月)？")

        # 推荐同品类免费替代
        all_products = load_products()
        category = product.get("category", "")
        alternatives = [
            p for p in all_products
            if p["category"] == category
            and p["product_key"] != product_key
            and any(pp["price"] == 0 for pp in p["plans"])
        ]
        if alternatives:
            alt_names = [f"{a['display_name']}基础版免费" for a in alternatives[:2]]
            print(f"  - 是否有其他产品可替代？（{'；'.join(alt_names)}）")


def cmd_checklist():
    """生成续费操作清单"""
    products = load_products()
    subscriptions = load_subscriptions()
    active_subs = get_active_subscriptions(subscriptions)

    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")

    print(f"📝 续费操作清单 ({today_str})")
    print(SEPARATOR)
    print()

    if not active_subs:
        print("暂无活跃订阅。")
        return

    print(f"活跃订阅 ({len(active_subs)}个):")
    print()

    total_monthly = {}  # 按币种统计月度总额

    for sub in active_subs:
        product = find_product(products, sub["product_key"])
        if not product:
            continue

        display_name = product["display_name"]
        tier = sub["tier"]
        next_billing_str = sub["next_billing_date"]
        renewal_url = product["renewal_url"]
        currency = sub["currency"]
        price = sub["price_paid"]

        # 计算距下次扣费天数
        try:
            next_billing_date = datetime.strptime(next_billing_str, "%Y-%m-%d").date()
            days_left = (next_billing_date - today).days
            days_text = f"{days_left}天后" if days_left >= 0 else "已过期"
        except ValueError:
            days_text = "未知"

        # 统计月度总额
        if currency not in total_monthly:
            total_monthly[currency] = 0
        total_monthly[currency] += price

        print(f"□ {display_name} {tier} - 下次扣费 {next_billing_str} ({days_text})")
        print(f"  → {renewal_url}")
        print()

    # 月度续费总额
    if total_monthly:
        total_parts = []
        for currency, amount in total_monthly.items():
            symbol = "¥" if currency == "CNY" else "$"
            total_parts.append(f"{currency} {symbol}{amount:,.2f}")
        print(f"💰 月度续费总额: {' + '.join(total_parts)}")


# ============ 主入口 ============



# ============ Usage API 导入与用量分析（v13 STEP4） ============

USAGE_PROVIDERS = {
    "openai": {
        "display": "OpenAI",
        "product_key": "chatgpt",
        "env_key": "OPENAI_API_KEY",
        "usage_endpoint": "https://api.openai.com/v1/organization/usage/completions",
        "price_per_1m_input": 2.5,
        "price_per_1m_output": 10.0,
    },
    "anthropic": {
        "display": "Anthropic",
        "product_key": "claude",
        "env_key": "ANTHROPIC_API_KEY",
        "usage_endpoint": "https://api.anthropic.com/v1/organizations/usage/messages",
        "price_per_1m_input": 3.0,
        "price_per_1m_output": 15.0,
    },
}


def fetch_usage(provider, api_key, days):
    """调用官方 Usage API 获取最近 N 天 token 用量"""
    import urllib.request
    from datetime import timedelta
    cfg = USAGE_PROVIDERS[provider]
    end = datetime.now()
    start = end - timedelta(days=days)
    url = f"{cfg['usage_endpoint']}?start_time={int(start.timestamp())}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def mock_usage(provider, days):
    """生成模拟用量数据（演示/测试链路用）"""
    import random
    from datetime import timedelta
    random.seed(42)
    end = datetime.now()
    data = {"provider": provider, "days": days, "daily": []}
    total_in = total_out = 0
    for i in range(days):
        day = end - timedelta(days=days - 1 - i)
        in_tokens = random.randint(20000, 120000)
        out_tokens = random.randint(5000, 40000)
        total_in += in_tokens
        total_out += out_tokens
        data["daily"].append({"date": day.strftime("%Y-%m-%d"),
                              "input_tokens": in_tokens, "output_tokens": out_tokens})
    data["total_input_tokens"] = total_in
    data["total_output_tokens"] = total_out
    return data


def estimate_usage_cost(cfg, total_in, total_out):
    cost_in = total_in / 1_000_000 * cfg["price_per_1m_input"]
    cost_out = total_out / 1_000_000 * cfg["price_per_1m_output"]
    return cost_in + cost_out


def cmd_usage(args):
    provider = (args.provider or "openai").lower()
    if provider not in USAGE_PROVIDERS:
        print(f"⚠️  不支持的 provider「{provider}」，可选: openai / anthropic")
        return
    cfg = USAGE_PROVIDERS[provider]
    days = args.days or 30

    api_key = args.api_key or os.environ.get(cfg["env_key"], "")

    if args.mock:
        usage = mock_usage(provider, days)
    else:
        if not api_key:
            print(f"\n🔑 未提供 {cfg['display']} API Key")
            print(f"   方式1: --api-key sk-xxx")
            print(f"   方式2: 设置环境变量 {cfg['env_key']}")
            print(f"   或使用 --mock 演示模式生成模拟数据测试链路")
            return
        try:
            usage = fetch_usage(provider, api_key, days)
        except Exception as e:
            print(f"\n❌ 获取用量失败: {e}")
            return

    total_in = usage.get("total_input_tokens", 0) or 0
    total_out = usage.get("total_output_tokens", 0) or 0
    total_tokens = total_in + total_out
    est_cost = estimate_usage_cost(cfg, total_in, total_out)

    # 关联本地订阅
    sub = None
    try:
        subs = load_subscriptions()
        for s in get_active_subscriptions(subs):
            if s.get("product_key") == cfg["product_key"]:
                sub = s
                break
    except Exception:
        pass

    print(f"\n{SEPARATOR}")
    print(f"📊 {cfg['display']} 用量分析（近 {days} 天）")
    print(SEPARATOR)
    print(f"  输入 tokens : {total_in:,}")
    print(f"  输出 tokens : {total_out:,}")
    print(f"  总 tokens   : {total_tokens:,}")
    print(f"  估算 API 成本: ${est_cost:.2f}")
    if sub:
        print(f"  关联订阅   : {sub['product_key']} / {sub.get('tier', '')} / "
              f"{sub.get('price_paid')} {sub.get('currency', '')}")

    # 续费评估（基于日均用量）
    daily_avg = total_tokens / days if days else 0
    print(f"\n{SEPARATOR}")
    print(f"💡 续费评估建议")
    print(SEPARATOR)
    print(f"  日均 tokens : {daily_avg:,.0f}")
    if daily_avg < 2000:
        level = "🔴 建议缩减"
        advice = "用量非常低：若订阅价格较高，可考虑降档或改用按量付费，避免闲置支出"
    elif daily_avg < 10000:
        level = "🟡 正常持有"
        advice = "用量适中：订阅基本物有所值，可继续持有，关注月度趋势"
    else:
        level = "🟢 用量充足"
        advice = "用量较高：确认当前套餐是否满足需求；若频繁触达额度上限，可考虑升档"
    print(f"  评估结论   : {level}")
    print(f"  建议       : {advice}")

    # 保存用量快照
    try:
        usage_file = os.path.join(DATA_DIR, "usage_data.json")
        snapshots = []
        if os.path.exists(usage_file):
            with open(usage_file, "r", encoding="utf-8") as f:
                snapshots = json.load(f)
        snapshots.append({
            "provider": provider,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "days": days,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "est_cost_usd": round(est_cost, 2),
            "mock": bool(args.mock),
        })
        with open(usage_file, "w", encoding="utf-8") as f:
            json.dump(snapshots, f, ensure_ascii=False, indent=2)
        print(f"\n  💾 用量快照已保存: usage_data.json")
    except Exception as e:
        print(f"\n  ⚠️  快照保存失败: {e}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="续费指导模块 - 帮助用户快速找到续费链接、取消方法、升降级操作指引"
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # info 命令
    info_parser = subparsers.add_parser("info", help="查看某产品的续费信息")
    info_parser.add_argument("--product", required=True, help="产品标识（如 chatgpt, claude）")

    # list 命令
    subparsers.add_parser("list", help="查看所有已订阅产品的续费信息")

    # upgrade 命令
    upgrade_parser = subparsers.add_parser("upgrade", help="套餐升级指引")
    upgrade_parser.add_argument("--product", required=True, help="产品标识")
    upgrade_parser.add_argument("--from", dest="from_tier", required=True, help="当前套餐名称")
    upgrade_parser.add_argument("--to", dest="to_tier", required=True, help="目标套餐名称")

    # downgrade 命令
    downgrade_parser = subparsers.add_parser("downgrade", help="套餐降级指引")
    downgrade_parser.add_argument("--product", required=True, help="产品标识")
    downgrade_parser.add_argument("--from", dest="from_tier", required=True, help="当前套餐名称")
    downgrade_parser.add_argument("--to", dest="to_tier", required=True, help="目标套餐名称")

    # cancel 命令
    cancel_parser = subparsers.add_parser("cancel", help="取消订阅指引")
    cancel_parser.add_argument("--product", required=True, help="产品标识")

    # checklist 命令
    subparsers.add_parser("checklist", help="生成续费操作清单")
    usage_parser = subparsers.add_parser("usage", help="导入 OpenAI/Anthropic Usage 用量数据并生成续费评估")
    usage_parser.add_argument("--provider", default="openai", help="provider: openai / anthropic")
    usage_parser.add_argument("--api-key", help="API Key（也可用环境变量 OPENAI_API_KEY / ANTHROPIC_API_KEY）")
    usage_parser.add_argument("--days", type=int, default=30, help="分析最近 N 天（默认 30）")
    usage_parser.add_argument("--mock", action="store_true", help="演示模式：使用模拟数据测试链路")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "info":
        cmd_info(args.product)
    elif args.command == "list":
        cmd_list()
    elif args.command == "upgrade":
        cmd_change(args.product, args.from_tier, args.to_tier, direction="upgrade")
    elif args.command == "downgrade":
        cmd_change(args.product, args.from_tier, args.to_tier, direction="downgrade")
    elif args.command == "cancel":
        cmd_cancel(args.product)
    elif args.command == "checklist":
        cmd_checklist()
    elif args.command == "usage":
        cmd_usage(args)


if __name__ == "__main__":
    main()
