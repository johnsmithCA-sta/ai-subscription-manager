#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0-06 比价功能模块
提供同类产品价格对比、性价比排行、替代方案推荐、跨分类全能排行、套餐指南等功能
"""

import json
import argparse
import sys
import os
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

# 参考汇率（统一转为 USD 进行跨币种比较）
EXCHANGE_RATES = {
    'USD': 1.0,
    'CNY': 1.0 / 7.25,
    'EUR': 1.0 / 1.08,
}

# 分类中文名称映射
CATEGORY_NAMES = {
    'ai_chat': 'AI 对话',
    'ai_code': 'AI 编程',
    'ai_image': 'AI 图像/视频',
    'ai_audio': 'AI 音频',
    'ai_writing': 'AI 写作/效率',
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
    if amount == 0:
        return "免费"
    return f"{symbol}{amount:,.2f}"


def to_usd(amount, currency):
    """将金额转换为 USD"""
    rate = EXCHANGE_RATES.get(currency, 1.0)
    return amount * rate


def get_product_info(products, product_key):
    """根据 product_key 查找产品信息"""
    for p in products:
        if p['product_key'] == product_key:
            return p
    return None


def get_lowest_paid_plan(plans):
    """获取最低付费档位（排除免费和价格为 null 的）"""
    paid_plans = [p for p in plans if p.get('price') is not None and p['price'] > 0]
    if not paid_plans:
        return None
    return min(paid_plans, key=lambda x: to_usd(x['price'], x['currency']))


def get_cheapest_plan(plans):
    """获取最便宜的档位（含免费）"""
    valid_plans = [p for p in plans if p.get('price') is not None]
    if not valid_plans:
        return None
    return min(valid_plans, key=lambda x: to_usd(x['price'], x['currency']))


def calc_tag_score(tags, tag_weights):
    """计算标签加权得分"""
    score = 0.0
    for tag in tags:
        if tag in tag_weights:
            score += tag_weights[tag].get('weight', 0.5)
    return score


def pad_display(text, display_width):
    """考虑中文字符宽度的对齐填充"""
    actual_width = 0
    for ch in str(text):
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            actual_width += 2
        else:
            actual_width += 1
    padding = max(0, display_width - actual_width)
    return text + ' ' * padding


def generate_bar(ratio, width=10):
    """生成 ASCII 进度条"""
    filled = int(ratio * width)
    filled = min(filled, width)
    return '█' * filled + '░' * (width - filled)


def get_user_subscriptions(subscriptions):
    """获取用户当前订阅字典 {product_key: sub_info}"""
    result = {}
    for s in subscriptions:
        if s.get('status') == 'active':
            result[s['product_key']] = s
    return result


# ============================================================
# 命令 1: compare - 同类产品价格对比
# ============================================================
def cmd_compare(args):
    """同类产品价格对比"""
    products = load_json('products.json')
    cat_data = load_json('categories.json')
    categories = cat_data.get('categories', cat_data)
    tag_data = load_json('function_tags.json')
    subscriptions = load_json('subscriptions.json')
    tag_weights = tag_data.get('tags', {})
    user_subs = get_user_subscriptions(subscriptions)

    category = args.category
    target_currency = args.currency.upper() if args.currency else None

    # 验证分类
    cat_key = None
    for k, v in categories.items():
        if k == category or v.get('name', '') == category or category in k:
            cat_key = k
            break
    if not cat_key:
        print(f"❌ 未找到分类「{category}」")
        cat_list = ', '.join(f"{k}({v['name']})" for k, v in categories.items())
        print(f"   可选分类: {cat_list}")
        return

    cat_info = categories[cat_key]
    cat_products = [p for p in products if p['category'] == cat_key]

    if not cat_products:
        print(f"❌ 分类「{cat_info['name']}」下暂无产品")
        return

    print(f"\n{'━' * 60}")
    print(f"📊 {cat_info['name']}类产品价格对比")
    print(f"{'━' * 60}")
    print(f"   分类: {cat_info['name']} — {cat_info['description']}")
    print(f"   产品数: {len(cat_products)}")
    print()

    # 收集比较数据
    comparison = []
    for p in cat_products:
        paid = get_lowest_paid_plan(p['plans'])
        tag_score = calc_tag_score(p['tags'], tag_weights)
        feature_count = len(p['tags'])

        # 计算性价比
        if paid and paid['price'] > 0:
            monthly_usd = to_usd(paid['price'], paid['currency'])
            value_score = (tag_score + feature_count * 0.2) / monthly_usd
        else:
            value_score = float('inf')

        comparison.append({
            'product': p,
            'paid': paid,
            'tag_score': tag_score,
            'feature_count': feature_count,
            'value_score': value_score,
        })

    # 按性价比排序
    comparison.sort(key=lambda x: x['value_score'] if x['value_score'] != float('inf') else 9999, reverse=True)

    max_score = max((c['value_score'] for c in comparison if c['value_score'] != float('inf')), default=1)

    print(f"  {'产品': <16} {'最低月费':>10}  {'标签':>4} {'得分':>6}  {'性价比':>10}")
    print(f"  {'─' * 54}")

    for c in comparison:
        p = c['product']
        paid = c['paid']
        display_name = p['display_name']
        is_subscribed = p['product_key'] in user_subs

        # 价格显示
        if paid:
            if target_currency:
                usd_price = to_usd(paid['price'], paid['currency'])
                price_display = format_price(usd_price / EXCHANGE_RATES.get(target_currency, 1.0), target_currency)
            else:
                price_display = format_price(paid['price'], paid['currency'])
        else:
            price_display = "免费"

        # 性价比条
        if c['value_score'] == float('inf'):
            bar = generate_bar(1.0, 8)
            score_display = "  ∞ 免费"
        else:
            ratio = c['value_score'] / max_score if max_score > 0 else 0
            bar = generate_bar(ratio, 8)
            score_display = f"{c['value_score']:.1f}"

        sub_mark = " ⭐" if is_subscribed else ""
        print(f"  {pad_display(display_name + sub_mark, 16)} {price_display:>10}  {c['feature_count']:>4} {c['tag_score']:>6.1f}  {bar} {score_display}")

    # 功能覆盖矩阵
    print(f"\n{'─' * 60}")
    print(f"📋 功能覆盖矩阵")
    print(f"{'─' * 60}")

    all_tags = set()
    for p in cat_products:
        all_tags.update(p['tags'])
    all_tags = sorted(all_tags, key=lambda t: tag_weights.get(t, {}).get('weight', 0), reverse=True)

    name_width = 12
    header = f"  {pad_display('标签', name_width)}"
    for p in cat_products:
        short = p['display_name'][:6]
        header += f" {pad_display(short, 6)}"
    print(header)
    print(f"  {'─' * (name_width + len(cat_products) * 7)}")

    for tag in all_tags:
        row = f"  {pad_display(tag, name_width)}"
        for p in cat_products:
            if tag in p['tags']:
                row += "   ✓  "
            else:
                row += "   ·  "
        weight = tag_weights.get(tag, {}).get('weight', 0)
        row += f"  (权重{weight})"
        print(row)

    # 用户订阅提示
    if user_subs:
        print(f"\n💡 你当前订阅了该分类的产品：")
        for p in cat_products:
            if p['product_key'] in user_subs:
                sub = user_subs[p['product_key']]
                print(f"   ⭐ {p['display_name']} — {sub['tier']} ({format_price(sub['price_paid'], sub['currency'])}/月)")

    print()


# ============================================================
# 命令 2: ranking - 性价比排行
# ============================================================
def cmd_ranking(args):
    """性价比排行"""
    products = load_json('products.json')
    cat_data = load_json('categories.json')
    categories = cat_data.get('categories', cat_data)
    tag_data = load_json('function_tags.json')
    tag_weights = tag_data.get('tags', {})

    category = args.category
    cat_key = None
    if category:
        for k, v in categories.items():
            if k == category or v.get('name', '') == category or category in k:
                cat_key = k
                break
        if not cat_key:
            print(f"❌ 未找到分类「{category}」")
            return

    # 筛选产品
    if cat_key:
        target_products = [p for p in products if p['category'] == cat_key]
        title = f"{categories[cat_key]['name']}类"
    else:
        target_products = products
        title = "全部产品"

    print(f"\n{'━' * 60}")
    print(f"🏆 性价比排行榜 — {title}")
    print(f"{'━' * 60}")
    print(f"   评分公式: (标签加权分 + 功能数×0.2) / 月费(USD)")
    print()

    rankings = []
    for p in target_products:
        paid = get_lowest_paid_plan(p['plans'])
        if not paid or paid['price'] <= 0:
            tag_score = calc_tag_score(p['tags'], tag_weights)
            rankings.append({
                'product': p,
                'monthly_usd': 0,
                'tag_score': tag_score,
                'feature_count': len(p['tags']),
                'value_score': float('inf'),
                'tier': paid['tier'] if paid else '免费',
                'price_display': '免费',
            })
            continue

        monthly_usd = to_usd(paid['price'], paid['currency'])
        tag_score = calc_tag_score(p['tags'], tag_weights)
        feature_count = len(p['tags'])
        value_score = (tag_score + feature_count * 0.2) / monthly_usd

        rankings.append({
            'product': p,
            'monthly_usd': monthly_usd,
            'tag_score': tag_score,
            'feature_count': feature_count,
            'value_score': value_score,
            'tier': paid['tier'],
            'price_display': f"${monthly_usd:.2f}/月",
        })

    # 排序
    rankings.sort(key=lambda x: x['value_score'] if x['value_score'] != float('inf') else 9999, reverse=True)

    finite_scores = [r['value_score'] for r in rankings if r['value_score'] != float('inf')]
    max_score = max(finite_scores) if finite_scores else 1

    print(f"  {'排名':>4}  {'产品': <14} {'档位': <12} {'月费':>10}  {'标签分':>6} {'功能':>4}  {'性价比':>12}")
    print(f"  {'─' * 66}")

    for i, r in enumerate(rankings, 1):
        medal = '🥇' if i == 1 else ('🥈' if i == 2 else ('🥉' if i == 3 else f'#{i:<2}'))

        if r['value_score'] == float('inf'):
            bar = generate_bar(1.0, 10)
            score_str = "∞ 免费"
        else:
            ratio = r['value_score'] / max_score if max_score > 0 else 0
            bar = generate_bar(ratio, 10)
            score_str = f"{r['value_score']:.1f}"

        print(f"  {medal}  {pad_display(r['product']['display_name'], 14)} {pad_display(r['tier'], 12)} {r['price_display']:>10}  {r['tag_score']:>6.1f} {r['feature_count']:>4}  {bar} {score_str}")

    # 分类冠军
    print(f"\n{'─' * 60}")
    print(f"📊 分类性价比冠军")
    print(f"{'─' * 60}")

    for cat_k, cat_v in categories.items():
        cat_items = [r for r in rankings if r['product']['category'] == cat_k]
        if cat_items:
            best = cat_items[0]
            print(f"  🏅 {cat_v['name']:<8} → {best['product']['display_name']} ({best['tier']}, {best['price_display']})")

    print()


# ============================================================
# 命令 3: alternative - 替代方案推荐
# ============================================================
def cmd_alternative(args):
    """替代方案推荐"""
    products = load_json('products.json')
    categories = load_json('categories.json')
    tag_data = load_json('function_tags.json')
    subscriptions = load_json('subscriptions.json')
    tag_weights = tag_data.get('tags', {})
    user_subs = get_user_subscriptions(subscriptions)

    product_key = args.product

    # 如果未指定产品，分析用户所有订阅
    if not product_key:
        if not user_subs:
            print("❌ 未指定产品且无活跃订阅")
            print("   用法: python price_comparator.py alternative --product <product_key>")
            return
        targets = list(user_subs.keys())
    else:
        targets = [product_key]

    for pk in targets:
        product = get_product_info(products, pk)
        if not product:
            print(f"❌ 未找到产品「{pk}」")
            continue

        user_sub = user_subs.get(pk)
        current_price_usd = 0
        current_tier = ""
        if user_sub:
            current_price_usd = to_usd(user_sub['price_paid'], user_sub['currency'])
            current_tier = user_sub['tier']
        else:
            paid = get_lowest_paid_plan(product['plans'])
            if paid:
                current_price_usd = to_usd(paid['price'], paid['currency'])
                current_tier = paid['tier']

        print(f"\n{'━' * 60}")
        print(f"🔄 替代方案推荐 — {product['display_name']}")
        print(f"{'━' * 60}")
        if user_sub:
            print(f"   当前: {current_tier} ({format_price(user_sub['price_paid'], user_sub['currency'])}/月)")
        else:
            print(f"   参考价位: ${current_price_usd:.2f}/月")
        print(f"   核心标签: {', '.join(product['tags'][:6])}")
        print()

        my_tags = set(product['tags'])

        # 1. 免费替代
        print(f"  💰 免费替代方案")
        free_alts = []
        for p in products:
            if p['product_key'] == pk:
                continue
            cheapest = get_cheapest_plan(p['plans'])
            if cheapest and cheapest['price'] == 0:
                overlap = set(p['tags']) & my_tags
                if len(overlap) >= 2:
                    overlap_ratio = len(overlap) / len(my_tags) if my_tags else 0
                    free_alts.append((p, cheapest, overlap, overlap_ratio))

        free_alts.sort(key=lambda x: x[3], reverse=True)
        if free_alts:
            for p, plan, overlap, ratio in free_alts[:5]:
                overlap_bar = generate_bar(ratio, 8)
                print(f"    ✓ {pad_display(p['display_name'], 16)} 功能重叠{overlap_bar} {len(overlap)}/{len(my_tags)}标签")
                print(f"      共享: {', '.join(list(overlap)[:4])}")
        else:
            print(f"    · 暂无合适的免费替代")

        # 2. 更便宜的付费替代
        print(f"\n  📉 更便宜的付费替代")
        cheaper = []
        for p in products:
            if p['product_key'] == pk:
                continue
            paid = get_lowest_paid_plan(p['plans'])
            if paid and to_usd(paid['price'], paid['currency']) < current_price_usd * 0.9:
                overlap = set(p['tags']) & my_tags
                if len(overlap) >= 2:
                    overlap_ratio = len(overlap) / len(my_tags) if my_tags else 0
                    saving = current_price_usd - to_usd(paid['price'], paid['currency'])
                    cheaper.append((p, paid, overlap, overlap_ratio, saving))

        cheaper.sort(key=lambda x: x[3], reverse=True)
        if cheaper:
            for p, plan, overlap, ratio, saving in cheaper[:5]:
                overlap_bar = generate_bar(ratio, 8)
                print(f"    ✓ {pad_display(p['display_name'], 16)} {format_price(plan['price'], plan['currency'])}/月 → 省${saving:.2f}/月")
                print(f"      功能重叠{overlap_bar} {len(overlap)}/{len(my_tags)}标签")
        else:
            print(f"    · 暂无明显更便宜的替代方案")

        # 3. 同价位功能更强的
        print(f"\n  ⚡ 同价位功能更强的")
        stronger = []
        for p in products:
            if p['product_key'] == pk:
                continue
            paid = get_lowest_paid_plan(p['plans'])
            if not paid or paid['price'] <= 0:
                continue
            price_usd = to_usd(paid['price'], paid['currency'])
            if price_usd <= current_price_usd * 1.3:
                overlap = set(p['tags']) & my_tags
                extra = set(p['tags']) - my_tags
                my_score = calc_tag_score(product['tags'], tag_weights)
                their_score = calc_tag_score(p['tags'], tag_weights)
                if their_score > my_score and len(overlap) >= 2:
                    stronger.append((p, paid, overlap, extra, their_score - my_score))

        stronger.sort(key=lambda x: x[4], reverse=True)
        if stronger:
            for p, plan, overlap, extra, diff in stronger[:5]:
                print(f"    ✓ {pad_display(p['display_name'], 16)} {format_price(plan['price'], plan['currency'])}/月 → 功能得分+{diff:.1f}")
                if extra:
                    print(f"      独有: {', '.join(list(extra)[:4])}")
        else:
            print(f"    · 同价位区间内暂无明显更强的选择")

        # 4. 同产品档位参考
        if len(product['plans']) > 1:
            print(f"\n  📈 同产品档位参考")
            for plan in product['plans']:
                if plan.get('price') is None:
                    continue
                plan_usd = to_usd(plan['price'], plan['currency'])
                is_current = user_sub and user_sub['tier'] == plan['tier']
                mark = " ← 当前" if is_current else ""
                diff_pct = ((plan_usd - current_price_usd) / current_price_usd * 100) if current_price_usd > 0 else 0
                if is_current:
                    print(f"    ⭐ {pad_display(plan['tier'], 16)} {format_price(plan['price'], plan['currency'])}/月{mark}")
                elif diff_pct > 0:
                    print(f"    → {pad_display(plan['tier'], 16)} {format_price(plan['price'], plan['currency'])}/月 (+{diff_pct:.0f}% 费用)")
                else:
                    print(f"    → {pad_display(plan['tier'], 16)} {format_price(plan['price'], plan['currency'])}/月 ({diff_pct:.0f}% 费用)")
                if plan.get('features'):
                    print(f"      亮点: {plan['features'][0]}")

    print()


def cmd_optimize(args):
    """订阅优化建议：基于当前订阅给出砍订建议 + 月省金额"""
    products = load_json('products.json')
    subscriptions = load_json('subscriptions.json')

    user_subs = [s for s in subscriptions if s.get('status') == 'active']
    if not user_subs:
        print("❌ 当前没有活跃订阅，无需优化")
        return

    # 1. 计算每项订阅的月度成本
    items = []
    for s in user_subs:
        pk = s['product_key']
        product = get_product_info(products, pk)
        display = product['display_name'] if product else pk
        category = (product or {}).get('category', '未知')
        tags = set((product or {}).get('tags', []))
        price = s.get('price_paid', 0)
        currency = s.get('currency', 'CNY')
        billing = s.get('billing_cycle', 'monthly')
        if billing == 'yearly':
            monthly = price / 12.0
        elif billing == 'one-time':
            monthly = 0.0
        else:
            monthly = price
        items.append({
            'pk': pk, 'display': display, 'category': category, 'tags': tags,
            'monthly': monthly, 'currency': currency, 'monthly_usd': to_usd(monthly, currency),
            'billing': billing, 'tier': s.get('tier', ''),
        })

    total_usd = sum(i['monthly_usd'] for i in items)

    # 2. 按分类分组，检测功能重叠
    by_cat = defaultdict(list)
    for i in items:
        by_cat[i['category']].append(i)

    cuts = []
    for cat, group in by_cat.items():
        if len(group) < 2:
            continue
        for x in range(len(group)):
            for y in range(x + 1, len(group)):
                a, b = group[x], group[y]
                if not a['tags'] or not b['tags']:
                    continue
                inter = a['tags'] & b['tags']
                ratio = len(inter) / min(len(a['tags']), len(b['tags']))
                if ratio >= 0.3:
                    # 功能重叠：保留月成本低的，建议砍掉贵的
                    if a['monthly_usd'] >= b['monthly_usd']:
                        cut, keep = a, b
                    else:
                        cut, keep = b, a
                    if not any(c['pk'] == cut['pk'] for c in cuts):
                        cuts.append({
                            'pk': cut['pk'], 'display': cut['display'], 'tier': cut['tier'],
                            'monthly': cut['monthly'], 'currency': cut['currency'],
                            'saving_usd': cut['monthly_usd'],
                            'overlap': sorted(inter)[:5], 'keep': keep['display'],
                        })

    cut_pks = set(c['pk'] for c in cuts)
    keeps = [i for i in items if i['pk'] not in cut_pks and i['monthly_usd'] > 0]
    free_items = [i for i in items if i['pk'] not in cut_pks and i['monthly_usd'] == 0]
    saving_usd = sum(c['saving_usd'] for c in cuts)

    # 3. 输出
    print("📊 订阅优化建议（砍订分析）")
    print(f"   当前订阅: {len(items)} 项 | 月度支出: ${total_usd:.2f}/月")
    print()
    print("🔴 建议砍掉（功能重叠，保留更优替代）")
    if cuts:
        for c in cuts:
            overlap_str = ", ".join(c['overlap']) if c['overlap'] else "-"
            print(f"  ✂️  {pad_display(c['display'], 16)} {c['tier']}  | 月费 {format_price(c['monthly'], c['currency'])}")
            print(f"     重叠功能: {overlap_str}")
            print(f"     建议: 保留「{c['keep']}」即可 → 月省 ${c['saving_usd']:.2f}")
    else:
        print("  ✓ 未检测到明显功能重叠的订阅，无需砍单")
    print()
    print("🟢 建议保留")
    for k in keeps:
        print(f"  ✅  {pad_display(k['display'], 16)} {k['tier']}  | 月费 {format_price(k['monthly'], k['currency'])}")
    if free_items:
        print("  ⚪  免费/一次性（不计月费）")
        for f in free_items:
            print(f"      {pad_display(f['display'], 16)} {f['tier']}  | 不计月费")
    print()
    print("💰 优化汇总")
    print(f"   当前月支出: ${total_usd:.2f}")
    print(f"   优化后月支出: ${total_usd - saving_usd:.2f}")
    print(f"   每月可省: ${saving_usd:.2f}")
    if saving_usd > 0:
        print(f"   全年可省: ${saving_usd * 12:.2f}")
    else:
        print("   （当前组合已较合理，无需调整）")


# ============================================================
# 命令 4: cross-compare - 跨分类全能排行
# ============================================================
def cmd_cross_compare(args):
    """跨分类全能选手排行"""
    products = load_json('products.json')
    cat_data = load_json('categories.json')
    categories = cat_data.get('categories', cat_data)
    tag_data = load_json('function_tags.json')
    tag_weights = tag_data.get('tags', {})
    min_tags = args.min_tags

    print(f"\n{'━' * 60}")
    print(f"🌐 跨分类全能选手排行")
    print(f"{'━' * 60}")
    print(f"   筛选条件: 至少覆盖 {min_tags} 个功能标签")
    print(f"   排序依据: 标签加权总分")
    print()

    cross_data = []
    for p in products:
        tag_score = calc_tag_score(p['tags'], tag_weights)
        feature_count = len(p['tags'])

        if feature_count < min_tags:
            continue

        paid = get_lowest_paid_plan(p['plans'])
        cheapest = get_cheapest_plan(p['plans'])
        cat_name = categories.get(p['category'], {}).get('name', p['category'])

        cross_data.append({
            'product': p,
            'tag_score': tag_score,
            'feature_count': feature_count,
            'tags': p['tags'],
            'category': cat_name,
            'cheapest': cheapest,
            'paid': paid,
        })

    cross_data.sort(key=lambda x: x['tag_score'], reverse=True)

    if not cross_data:
        print(f"  暂无产品覆盖 {min_tags} 个以上标签")
        return

    max_score = cross_data[0]['tag_score']

    print(f"  {'排名':>4}  {'产品': <14} {'分类': <10} {'标签':>4} {'加权分':>6}  {'综合能力':>12}  {'最低付费':>10}")
    print(f"  {'─' * 70}")

    for i, c in enumerate(cross_data, 1):
        medal = '🥇' if i == 1 else ('🥈' if i == 2 else ('🥉' if i == 3 else f'#{i:<2}'))
        ratio = c['tag_score'] / max_score
        bar = generate_bar(ratio, 12)

        if c['paid']:
            price_str = format_price(c['paid']['price'], c['paid']['currency'])
        else:
            price_str = "免费"

        print(f"  {medal}  {pad_display(c['product']['display_name'], 14)} {pad_display(c['category'], 10)} {c['feature_count']:>4} {c['tag_score']:>6.1f}  {bar}  {price_str:>10}")

    # Top5 标签覆盖对比
    top5 = cross_data[:5]
    if len(top5) >= 2:
        print(f"\n{'─' * 60}")
        print(f"📋 Top {len(top5)} 标签覆盖对比")
        print(f"{'─' * 60}")

        all_tags = set()
        for c in top5:
            all_tags.update(c['tags'])
        all_tags = sorted(all_tags, key=lambda t: tag_weights.get(t, {}).get('weight', 0), reverse=True)

        name_w = 12
        header = f"  {pad_display('标签', name_w)}"
        for c in top5:
            short = c['product']['display_name'][:5]
            header += f" {pad_display(short, 5)}"
        print(header)
        print(f"  {'─' * (name_w + len(top5) * 6)}")

        for tag in all_tags:
            row = f"  {pad_display(tag, name_w)}"
            for c in top5:
                if tag in c['tags']:
                    row += "  ✓  "
                else:
                    row += "  ·  "
            print(row)

    # 洞察
    print(f"\n💡 洞察")
    if cross_data:
        best = cross_data[0]
        free_count = sum(1 for c in cross_data if c['cheapest'] and c['cheapest']['price'] == 0)
        print(f"  • 综合最强: {best['product']['display_name']}（{best['feature_count']}个标签，得分{best['tag_score']:.1f}）")
        print(f"  • Top10 中有 {free_count} 个提供免费版本")

    print()


# ============================================================
# 命令 5: tier-guide - 套餐指南
# ============================================================
def cmd_tier_guide(args):
    """单产品各档位功能差异矩阵"""
    products = load_json('products.json')
    product_key = args.product

    product = get_product_info(products, product_key)
    if not product:
        print(f"❌ 未找到产品「{product_key}」")
        print(f"   可用产品: {', '.join(p['product_key'] for p in products)}")
        return

    plans = [p for p in product['plans'] if p.get('price') is not None]
    if not plans:
        print(f"❌ {product['display_name']} 暂无可比较的定价信息")
        return

    print(f"\n{'━' * 60}")
    print(f"📋 套餐指南 — {product['display_name']}")
    print(f"{'━' * 60}")
    print(f"   厂商: {product['vendor']}")
    print(f"   分类: {product.get('subcategory', '')}")
    print(f"   官网: {product.get('website', '')}")
    print()

    # 档位概览
    print(f"  {'档位': <16} {'月费':>10} {'年付月均':>10} {'计费方式':>8}")
    print(f"  {'─' * 50}")

    for plan in plans:
        monthly = plan['price']
        annual_monthly = None
        if plan.get('annual_price') and plan.get('has_annual_discount'):
            annual_monthly = plan['annual_price'] / 12.0

        annual_str = format_price(annual_monthly, plan['currency']) if annual_monthly else "—"
        cycle_map = {
            'monthly': '月付',
            'yearly': '年付',
            'quarterly': '季付',
            'pay_per_use': '按量',
            'custom': '定制',
        }
        cycle = cycle_map.get(plan['billing_cycle'], plan['billing_cycle'])

        print(f"  {pad_display(plan['tier'], 16)} {format_price(monthly, plan['currency']):>10} {annual_str:>10} {cycle:>8}")

    # 功能矩阵
    print(f"\n{'─' * 60}")
    print(f"📊 功能对比矩阵")
    print(f"{'─' * 60}")

    all_features = []
    seen = set()
    for plan in plans:
        for f in plan.get('features', []):
            if f not in seen:
                all_features.append(f)
                seen.add(f)

    tier_w = 14

    header = f"  {pad_display('功能', 28)}"
    for plan in plans:
        header += f" {pad_display(plan['tier'], tier_w)}"
    print(header)
    print(f"  {'─' * (28 + len(plans) * (tier_w + 1))}")

    for feature in all_features:
        row = f"  {pad_display(feature[:26], 28)}"
        for plan in plans:
            plan_features = plan.get('features', [])
            found = False
            for pf in plan_features:
                if feature == pf or feature in pf or pf in feature:
                    found = True
                    break
            if found:
                row += f" {pad_display('✓', tier_w)}"
            else:
                row += f" {pad_display('·', tier_w)}"
        print(row)

    # 选择建议
    print(f"\n{'─' * 60}")
    print(f"💡 选择建议")
    print(f"{'─' * 60}")

    if len(plans) >= 2:
        cheapest = plans[0]
        mid = plans[len(plans) // 2] if len(plans) >= 3 else plans[1]
        premium = plans[-1]

        print(f"  🟢 入门/试用 → {cheapest['tier']} ({format_price(cheapest['price'], cheapest['currency'])}/月)")
        if cheapest.get('features'):
            print(f"     包含: {cheapest['features'][0]}")

        if mid != cheapest:
            print(f"  🟡 日常使用 → {mid['tier']} ({format_price(mid['price'], mid['currency'])}/月)")
            if mid.get('features'):
                print(f"     包含: {mid['features'][0]}")

        if premium != mid and premium != cheapest:
            print(f"  🔴 重度/专业 → {premium['tier']} ({format_price(premium['price'], premium['currency'])}/月)")
            if premium.get('features'):
                print(f"     包含: {premium['features'][0]}")

        discounted = [p for p in plans if p.get('has_annual_discount') and p.get('annual_price')]
        if discounted:
            print(f"\n  📅 年付优惠:")
            for p in discounted:
                saving = (p['price'] - p['annual_price'] / 12.0) / p['price'] * 100
                print(f"     {p['tier']}: 年付月均 {format_price(p['annual_price']/12, p['currency'])} (省{saving:.0f}%)")

    print()


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='📊 比价功能模块 — 同类产品价格对比、性价比评分、替代方案推荐',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python price_comparator.py compare --category ai_chat
  python price_comparator.py compare --category ai_code --currency CNY
  python price_comparator.py ranking
  python price_comparator.py ranking --category ai_image
  python price_comparator.py alternative --product chatgpt
  python price_comparator.py alternative
  python price_comparator.py cross-compare
  python price_comparator.py cross-compare --min-tags 8
  python price_comparator.py tier-guide --product cursor
  python price_comparator.py optimize
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # compare
    p_compare = subparsers.add_parser('compare', help='同类产品价格对比')
    p_compare.add_argument('--category', required=True, help='分类标识(ai_chat/ai_code/ai_image/ai_audio/ai_writing)或中文名')
    p_compare.add_argument('--currency', help='统一显示的币种(USD/CNY/EUR)')

    # ranking
    p_ranking = subparsers.add_parser('ranking', help='性价比排行榜')
    p_ranking.add_argument('--category', help='限定分类(可选)')

    # alternative
    p_alt = subparsers.add_parser('alternative', help='替代方案推荐')
    p_alt.add_argument('--product', help='目标产品 product_key(不传则分析当前订阅)')

    # cross-compare
    p_cross = subparsers.add_parser('cross-compare', help='跨分类全能选手排行')
    p_cross.add_argument('--min-tags', type=int, default=6, help='最少标签数阈值(默认6)')

    # tier-guide
    p_tier = subparsers.add_parser('tier-guide', help='单产品套餐指南')
    p_tier.add_argument('--product', required=True, help='产品 product_key')

    # optimize
    p_opt = subparsers.add_parser('optimize', help='订阅优化建议（砍订分析 + 月省金额）')
    p_opt.add_argument('--overlap-threshold', type=float, default=0.3, help='功能重叠判定阈值(默认0.3)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        'compare': cmd_compare,
        'ranking': cmd_ranking,
        'alternative': cmd_alternative,
        'cross-compare': cmd_cross_compare,
        'tier-guide': cmd_tier_guide,
        'optimize': cmd_optimize,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
