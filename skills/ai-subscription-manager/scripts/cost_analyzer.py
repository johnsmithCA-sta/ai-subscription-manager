#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会员订阅成本统计分析模块
提供总览、分类统计、产品统计、历史趋势、预算对比、节省建议等功能
"""

import json
import argparse
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

# 路径配置：脚本在 scripts/ 下，数据在上级目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.join(SCRIPT_DIR, '..')

# 币种符号映射
CURRENCY_SYMBOLS = {
    'USD': '$',
    'CNY': '¥',
    'EUR': '€',
}

# 分类中文名称映射
CATEGORY_NAMES = {
    'ai_chat': 'AI 对话',
    'ai_code': 'AI 编程',
    'ai_image': 'AI 图像',
    'ai_audio': 'AI 音频',
    'ai_writing': 'AI 写作',
}


def load_json(filename):
    """加载 JSON 数据文件"""
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_currency_symbol(currency):
    """获取币种符号"""
    return CURRENCY_SYMBOLS.get(currency, currency)


def format_price(amount, currency):
    """格式化价格显示"""
    symbol = get_currency_symbol(currency)
    return f"{symbol}{amount:,.2f}"


def get_active_subscriptions(subscriptions):
    """获取所有活跃订阅"""
    return [s for s in subscriptions if s.get('status') == 'active']


def get_product_info(products, product_key):
    """根据 product_key 查找产品信息"""
    for p in products:
        if p['product_key'] == product_key:
            return p
    return None


def to_monthly_cost(price_paid, billing_cycle):
    """将不同计费周期的费用统一转换为月费"""
    if billing_cycle == 'monthly':
        return price_paid
    elif billing_cycle == 'yearly':
        return price_paid / 12.0
    elif billing_cycle == 'quarterly':
        return price_paid / 3.0
    else:
        return price_paid  # 默认按月


def generate_bar(ratio, width=10):
    """生成 ASCII 进度条"""
    filled = int(ratio * width)
    if filled > width:
        filled = width
    empty = width - filled
    return '█' * filled + '░' * empty


# ============================================================
# 命令：overview - 总览报告
# ============================================================
def cmd_overview(products, subscriptions):
    """输出订阅成本总览"""
    active = get_active_subscriptions(subscriptions)
    today = datetime.now().strftime('%Y-%m-%d')

    if not active:
        print("⚠️  当前没有活跃的订阅记录。")
        return

    # 按币种汇总月度支出
    monthly_by_currency = defaultdict(float)
    for sub in active:
        monthly = to_monthly_cost(sub['price_paid'], sub['billing_cycle'])
        monthly_by_currency[sub['currency']] += monthly

    # 找出最高和最低单订阅
    highest = max(active, key=lambda s: to_monthly_cost(s['price_paid'], s['billing_cycle']))
    lowest = min(active, key=lambda s: to_monthly_cost(s['price_paid'], s['billing_cycle']))

    highest_monthly = to_monthly_cost(highest['price_paid'], highest['billing_cycle'])
    lowest_monthly = to_monthly_cost(lowest['price_paid'], lowest['billing_cycle'])

    highest_product = get_product_info(products, highest['product_key'])
    lowest_product = get_product_info(products, lowest['product_key'])
    highest_name = highest_product['display_name'] if highest_product else highest['product_key']
    lowest_name = lowest_product['display_name'] if lowest_product else lowest['product_key']
    highest_tier = highest['tier']
    lowest_tier = lowest['tier']

    # 输出
    print(f"💰 订阅成本总览 ({today})")
    print("━" * 40)
    print()
    print(f"📊 活跃订阅: {len(active)} 个")
    print(f"💵 月度支出:")

    # 按固定顺序显示币种
    for curr in ['USD', 'CNY']:
        if curr in monthly_by_currency:
            symbol = get_currency_symbol(curr)
            monthly = monthly_by_currency[curr]
            print(f"   {curr}: {symbol}{monthly:.2f}/月")
    # 其他币种
    for curr, monthly in sorted(monthly_by_currency.items()):
        if curr not in ['USD', 'CNY']:
            symbol = get_currency_symbol(curr)
            print(f"   {curr}: {symbol}{monthly:.2f}/月")

    print()
    print(f"📅 年度预估:")
    for curr in ['USD', 'CNY']:
        if curr in monthly_by_currency:
            symbol = get_currency_symbol(curr)
            yearly = monthly_by_currency[curr] * 12
            print(f"   {curr}: {symbol}{yearly:.2f}/年")
    for curr, monthly in sorted(monthly_by_currency.items()):
        if curr not in ['USD', 'CNY']:
            symbol = get_currency_symbol(curr)
            print(f"   {curr}: {symbol}{monthly * 12:.2f}/年")

    print()
    print(f"📈 单订阅最高: {highest_name} {highest_tier} ({format_price(highest_monthly, highest['currency'])}/月)")
    print(f"📉 单订阅最低: {lowest_name} {lowest_tier} ({format_price(lowest_monthly, lowest['currency'])}/月)")


# ============================================================
# 命令：by-category - 按分类统计
# ============================================================
def cmd_by_category(products, subscriptions):
    """按产品分类统计支出"""
    active = get_active_subscriptions(subscriptions)

    if not active:
        print("⚠️  当前没有活跃的订阅记录。")
        return

    # 按分类汇总（统一转为 USD 进行占比计算）
    category_costs = defaultdict(float)  # 存储月度费用（按原始币种分别存）
    category_costs_usd = defaultdict(float)  # 用于占比计算的统一货币
    category_subs = defaultdict(list)

    for sub in active:
        product = get_product_info(products, sub['product_key'])
        category = product['category'] if product else 'other'
        monthly = to_monthly_cost(sub['price_paid'], sub['billing_cycle'])
        category_subs[category].append(sub)
        category_costs[(category, sub['currency'])] += monthly
        # 简单按 1:1 近似用于占比（同币种场景下精确）
        category_costs_usd[category] += monthly

    total = sum(category_costs_usd.values())

    print("📊 分类支出分析")
    print("━" * 40)
    print()

    # 按费用降序排列
    sorted_categories = sorted(category_costs_usd.items(), key=lambda x: x[1], reverse=True)

    for cat, amount in sorted_categories:
        cat_name_cn = CATEGORY_NAMES.get(cat, cat)
        ratio = amount / total if total > 0 else 0
        bar = generate_bar(ratio)
        pct = ratio * 100

        # 显示该分类下各币种的详细金额
        cost_parts = []
        for (c, curr), val in sorted(category_costs.items()):
            if c == cat:
                cost_parts.append(format_price(val, curr))
        cost_str = '/月'.join(cost_parts)
        if len(cost_parts) > 1:
            cost_str += '/月'

        print(f"{cat_name_cn} ({cat}):".ljust(25) + f"{cost_str}  {bar}  {pct:.1f}%")

    print()
    # 总计（按币种分别显示）
    total_by_currency = defaultdict(float)
    for sub in active:
        monthly = to_monthly_cost(sub['price_paid'], sub['billing_cycle'])
        total_by_currency[sub['currency']] += monthly

    total_parts = []
    for curr in ['USD', 'CNY']:
        if curr in total_by_currency:
            total_parts.append(format_price(total_by_currency[curr], curr))
    for curr, val in sorted(total_by_currency.items()):
        if curr not in ['USD', 'CNY']:
            total_parts.append(format_price(val, curr))
    print(f"总计: {' + '.join(total_parts)}/月")


# ============================================================
# 命令：by-product - 按产品统计
# ============================================================
def cmd_by_product(products, subscriptions):
    """按产品统计支出明细"""
    active = get_active_subscriptions(subscriptions)

    if not active:
        print("⚠️  当前没有活跃的订阅记录。")
        return

    total_monthly_usd = 0
    product_rows = []

    for sub in active:
        product = get_product_info(products, sub['product_key'])
        display_name = product['display_name'] if product else sub['product_key']
        monthly = to_monthly_cost(sub['price_paid'], sub['billing_cycle'])
        yearly = monthly * 12
        total_monthly_usd += monthly  # 简化：假设同币种或 1:1

        product_rows.append({
            'name': display_name,
            'tier': sub['tier'],
            'monthly': monthly,
            'yearly': yearly,
            'currency': sub['currency'],
        })

    # 按月度费用降序排列
    product_rows.sort(key=lambda r: r['monthly'], reverse=True)

    print("📊 产品支出明细")
    print("━" * 40)
    print()

    # 表头
    header = f"{'产品'.ljust(12)} {'套餐'.ljust(8)} {'月费'.rjust(10)} {'年费'.rjust(10)} {'占比'.rjust(8)}"
    print(header)
    print("─" * 50)

    total = sum(r['monthly'] for r in product_rows)
    for row in product_rows:
        ratio = row['monthly'] / total if total > 0 else 0
        pct = f"{ratio * 100:.1f}%"
        name_display = row['name']
        # 中文对齐补偿
        name_len = len(name_display)
        cn_chars = sum(1 for c in name_display if '\u4e00' <= c <= '\u9fff')
        pad = name_len + cn_chars  # 中文字符占两格

        tier_display = row['tier']
        tier_len = len(tier_display)
        tier_cn = sum(1 for c in tier_display if '\u4e00' <= c <= '\u9fff')
        tier_pad = tier_len + tier_cn

        line = f"{name_display:<{pad}} {tier_display:<{tier_pad}} {format_price(row['monthly'], row['currency']).rjust(10)} {format_price(row['yearly'], row['currency']).rjust(10)} {pct.rjust(8)}"
        print(line)

    print("─" * 50)
    print(f"{'合计':<10} {'':8} {format_price(total, product_rows[0]['currency']).rjust(10)} {format_price(total * 12, product_rows[0]['currency']).rjust(10)} {'100.0%'.rjust(8)}")


# ============================================================
# 命令：trend - 历史趋势
# ============================================================
def cmd_trend(products, subscriptions, months=6):
    """基于 start_date 推算历史每月支出"""
    active = get_active_subscriptions(subscriptions)
    today = datetime.now()

    if not active:
        print("⚠️  当前没有活跃的订阅记录。")
        return

    # 构建每月支出（仅统计有订阅生效的月份）
    monthly_costs = defaultdict(lambda: defaultdict(float))  # {month_str: {currency: amount}}

    # 生成最近 N 个月的月份列表
    month_labels = []
    for i in range(months - 1, -1, -1):
        # 取每个月的第一天
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_labels.append((year, month))

    # 对每个订阅，判断它在哪些月份是活跃的
    for sub in active:
        start = datetime.strptime(sub['start_date'], '%Y-%m-%d')
        monthly = to_monthly_cost(sub['price_paid'], sub['billing_cycle'])
        currency = sub['currency']

        for year, month in month_labels:
            # 该月的第一天和最后一天
            if month == 12:
                next_month_start = datetime(year + 1, 1, 1)
            else:
                next_month_start = datetime(year, month + 1, 1)
            month_start = datetime(year, month, 1)

            # 订阅在该月活跃的条件：start_date < 该月最后一天
            if start < next_month_start:
                month_str = f"{year}-{month:02d}"
                monthly_costs[month_str][currency] += monthly

    # 输出趋势
    print(f"📈 最近 {months} 个月支出趋势")
    print("━" * 40)
    print()

    # 找到最大支出用于归一化柱状图
    max_cost = 0
    for ms, currencies in monthly_costs.items():
        for curr, val in currencies.items():
            if val > max_cost:
                max_cost = val

    for year, month in month_labels:
        month_str = f"{year}-{month:02d}"
        currencies = monthly_costs.get(month_str, {})
        if not currencies:
            print(f"  {month_str}  无活跃订阅")
            continue

        parts = []
        total_val = 0
        for curr in ['USD', 'CNY']:
            if curr in currencies:
                parts.append(format_price(currencies[curr], curr))
                total_val += currencies[curr]
        for curr, val in sorted(currencies.items()):
            if curr not in ['USD', 'CNY']:
                parts.append(format_price(val, curr))
                total_val += val

        cost_str = ' + '.join(parts) + '/月'
        bar_ratio = total_val / max_cost if max_cost > 0 else 0
        bar = generate_bar(bar_ratio, 15)
        print(f"  {month_str}  {cost_str:<25} {bar}")

    print()


# ============================================================
# 命令：budget - 预算对比
# ============================================================
def cmd_budget(products, subscriptions, monthly_budget, currency='USD'):
    """当前支出 vs 预算对比"""
    active = get_active_subscriptions(subscriptions)

    if not active:
        print("⚠️  当前没有活跃的订阅记录。")
        return

    # 汇总指定币种的月度支出
    total_monthly = 0.0
    for sub in active:
        if sub['currency'] == currency:
            monthly = to_monthly_cost(sub['price_paid'], sub['billing_cycle'])
            total_monthly += monthly

    symbol = get_currency_symbol(currency)
    diff = monthly_budget - total_monthly
    ratio = total_monthly / monthly_budget if monthly_budget > 0 else 0

    print(f"📊 预算对比 ({currency})")
    print("━" * 40)
    print()
    print(f"  月度预算: {symbol}{monthly_budget:.2f}")
    print(f"  当前支出: {symbol}{total_monthly:.2f}")
    print()

    if diff >= 0:
        print(f"  ✅ 节省: {symbol}{diff:.2f}/月 ({diff * 12:.2f}/年)")
        bar = generate_bar(ratio, 20)
        print(f"  预算使用: {bar} {ratio * 100:.1f}%")
    else:
        print(f"  ⚠️  超支: {symbol}{abs(diff):.2f}/月 ({abs(diff) * 12:.2f}/年)")
        bar = generate_bar(min(ratio, 1.0), 20)
        print(f"  预算使用: {bar} {ratio * 100:.1f}%")
    print()


# ============================================================
# 命令：savings - 节省建议
# ============================================================
def cmd_savings(products, subscriptions):
    """分析潜在节省方案"""
    active = get_active_subscriptions(subscriptions)

    if not active:
        print("⚠️  当前没有活跃的订阅记录。")
        return

    print("💡 节省建议")
    print("━" * 40)
    print()

    total_annual_savings = 0.0

    # 1. 年付优惠检查
    print("1. 年付优惠检查:")
    annual_savings_list = []

    for sub in active:
        product = get_product_info(products, sub['product_key'])
        if not product:
            continue

        display_name = product['display_name']
        tier = sub['tier']
        monthly = sub['price_paid']
        currency = sub['currency']
        symbol = get_currency_symbol(currency)
        current_annual = monthly * 12

        # 在 products.json 中查找对应套餐是否有年付优惠
        matched_plan = None
        for plan in product['plans']:
            if plan['tier'] == tier:
                matched_plan = plan
                break

        if matched_plan and matched_plan.get('has_annual_discount') and matched_plan.get('annual_price'):
            annual_price = matched_plan['annual_price']
            saving = current_annual - annual_price
            annual_savings_list.append({
                'name': display_name,
                'tier': tier,
                'current_annual': current_annual,
                'annual_price': annual_price,
                'saving': saving,
                'currency': currency,
            })
            print(f"   - {display_name} {tier}: 当前月付 {symbol}{monthly:.2f}/月，年付可省 → {symbol}{annual_price:.2f}/年 vs {symbol}{current_annual:.2f}/年，节省 {symbol}{saving:.2f}")
            total_annual_savings += saving
        else:
            print(f"   - {display_name} {tier}: 当前月付 {symbol}{monthly:.2f}/月，无年付折扣")

    print()

    # 2. 功能重叠提示
    print("2. 功能重叠提示:")
    # 获取所有活跃订阅产品的 tags
    active_with_tags = []
    for sub in active:
        product = get_product_info(products, sub['product_key'])
        if product and 'tags' in product:
            active_with_tags.append({
                'name': product['display_name'],
                'tags': set(product['tags']),
                'product_key': product['product_key'],
                'category': product['category'],
            })

    overlap_found = False
    for i in range(len(active_with_tags)):
        for j in range(i + 1, len(active_with_tags)):
            a = active_with_tags[i]
            b = active_with_tags[j]
            overlap = a['tags'] & b['tags']
            if overlap:
                overlap_str = '、'.join(sorted(overlap))
                print(f"   - {a['name']} 和 {b['name']} 在「{overlap_str}」{len(overlap)}项功能重叠")
                overlap_found = True

    if overlap_found:
        print(f"   💬 考虑是否可以合并为一个产品以减少支出")
    else:
        print(f"   （未发现明显功能重叠）")

    print()

    # 3. 更便宜的替代方案
    print("3. 更便宜的替代方案:")
    alternative_found = False

    for sub in active:
        product = get_product_info(products, sub['product_key'])
        if not product:
            continue

        category = product['category']
        current_price = sub['price_paid']
        currency = sub['currency']
        symbol = get_currency_symbol(currency)

        # 在同一分类下找更便宜的付费产品
        cheaper_options = []
        for p in products:
            if p['category'] == category and p['product_key'] != sub['product_key']:
                for plan in p['plans']:
                    if plan['price'] is not None and plan['price'] > 0 and plan['price'] < current_price and plan['currency'] == currency:
                        # 检查功能重叠度
                        overlap = set(product.get('tags', [])) & set(p.get('tags', []))
                        if overlap:
                            cheaper_options.append({
                                'name': p['display_name'],
                                'tier': plan['tier'],
                                'price': plan['price'],
                                'overlap': overlap,
                                'currency': currency,
                            })

        if cheaper_options:
            # 取最便宜的
            cheaper_options.sort(key=lambda x: x['price'])
            best = cheaper_options[0]
            overlap_names = '、'.join(sorted(best['overlap']))
            saving = current_price - best['price']
            print(f"   - {product['display_name']} {sub['tier']} ({symbol}{current_price:.2f}/月) → 可考虑 {best['name']} {best['tier']} ({symbol}{best['price']:.2f}/月)，节省 {symbol}{saving:.2f}/月")
            print(f"     共享功能: {overlap_names}")
            alternative_found = True

    # 检查是否有免费替代品
    for sub in active:
        product = get_product_info(products, sub['product_key'])
        if not product:
            continue
        category = product['category']

        free_options = []
        for p in products:
            if p['category'] == category and p['product_key'] != sub['product_key']:
                for plan in p['plans']:
                    if plan['price'] is not None and plan['price'] == 0:
                        overlap = set(product.get('tags', [])) & set(p.get('tags', []))
                        if overlap:
                            free_options.append({
                                'name': p['display_name'],
                                'tier': plan['tier'],
                                'overlap': overlap,
                            })

        if free_options:
            best_free = free_options[0]
            overlap_names = '、'.join(sorted(best_free['overlap']))
            print(f"   - {product['display_name']} 部分功能可被 {best_free['name']}（{best_free['tier']}）免费替代")
            print(f"     共享功能: {overlap_names}")
            alternative_found = True

    if not alternative_found:
        print("   （未发现明显更便宜的替代方案）")

    print()

    # 总结
    if total_annual_savings > 0:
        symbol = get_currency_symbol(active[0]['currency'])
        print(f"潜在节省: 约 {symbol}{total_annual_savings:.2f}/年（仅年付优化）")
    else:
        print("当前所有订阅均无年付折扣可用。建议关注功能重叠，考虑合并同类产品。")


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='会员订阅成本统计分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令说明:
  overview        总览报告：月度总支出、年度预估
  by-category     按分类统计：AI对话/编程/图像等各分类占比
  by-product      按产品统计：每个产品的月费、年费、占比
  trend           历史趋势：基于 start_date 推算每月支出变化
  budget          预算对比：当前支出 vs 设定预算
  savings         节省建议：年付优惠、功能重叠、替代方案
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # overview
    subparsers.add_parser('overview', help='总览报告')

    # by-category
    subparsers.add_parser('by-category', help='按分类统计')

    # by-product
    subparsers.add_parser('by-product', help='按产品统计')

    # trend
    trend_parser = subparsers.add_parser('trend', help='历史趋势')
    trend_parser.add_argument('--months', type=int, default=6, help='统计月份数（默认6）')

    # budget
    budget_parser = subparsers.add_parser('budget', help='预算对比')
    budget_parser.add_argument('--monthly', type=float, required=True, help='月度预算金额')
    budget_parser.add_argument('--currency', type=str, default='USD', help='预算币种（默认USD）')

    # savings
    subparsers.add_parser('savings', help='节省建议')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 加载数据
    products = load_json('products.json')
    subscriptions = load_json('subscriptions.json')

    # 执行对应命令
    if args.command == 'overview':
        cmd_overview(products, subscriptions)
    elif args.command == 'by-category':
        cmd_by_category(products, subscriptions)
    elif args.command == 'by-product':
        cmd_by_product(products, subscriptions)
    elif args.command == 'trend':
        cmd_trend(products, subscriptions, args.months)
    elif args.command == 'budget':
        cmd_budget(products, subscriptions, args.monthly, args.currency)
    elif args.command == 'savings':
        cmd_savings(products, subscriptions)


if __name__ == '__main__':
    main()
