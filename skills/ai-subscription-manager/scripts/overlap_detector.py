#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1-08 重叠检测模块
分析订阅产品间的功能重叠、冗余支出、优化建议
"""

import json
import argparse
import sys
import os
from collections import defaultdict
from itertools import combinations

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.join(SCRIPT_DIR, '..')

CURRENCY_SYMBOLS = {'USD': '$', 'CNY': '¥', 'EUR': '€'}
EXCHANGE_RATES = {'USD': 1.0, 'CNY': 1.0 / 7.25, 'EUR': 1.0 / 1.08}


def load_json(filename):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_price(amount, currency='USD'):
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    if amount == 0:
        return "免费"
    return f"{symbol}{amount:,.2f}"


def to_usd(amount, currency):
    return amount * EXCHANGE_RATES.get(currency, 1.0)


def get_product_info(products, product_key):
    for p in products:
        if p['product_key'] == product_key:
            return p
    return None


def get_active_subscriptions(subscriptions, products):
    """获取活跃订阅及其产品信息"""
    result = []
    for s in subscriptions:
        if s.get('status') == 'active':
            product = get_product_info(products, s['product_key'])
            if product:
                result.append({'sub': s, 'product': product})
    return result


def jaccard_similarity(set_a, set_b):
    """计算 Jaccard 相似度"""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def generate_bar(ratio, width=10):
    filled = min(int(ratio * width), width)
    return '█' * filled + '░' * (width - filled)


def pad_display(text, display_width):
    actual_width = 0
    for ch in str(text):
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            actual_width += 2
        else:
            actual_width += 1
    padding = max(0, display_width - actual_width)
    return text + ' ' * padding


# ============================================================
# 命令 1: overlap — 重叠矩阵
# ============================================================
def cmd_overlap(args):
    products = load_json('products.json')
    subscriptions = load_json('subscriptions.json')
    active = get_active_subscriptions(subscriptions, products)

    if len(active) < 2:
        print("\n⚠️  活跃订阅不足 2 个，无法进行重叠分析")
        if active:
            p = active[0]['product']
            print(f"   当前仅有: {p['display_name']} ({len(p['tags'])} 个功能标签)")
        else:
            print("   当前无活跃订阅")
        return

    print(f"\n{'━' * 60}")
    print(f"🔍 订阅功能重叠分析")
    print(f"{'━' * 60}")
    print(f"   活跃订阅: {len(active)} 个\n")

    # 列出各订阅信息
    print(f"  {'产品': <16} {'档位': <10} {'月费':>10} {'标签数':>6}")
    print(f"  {'─' * 46}")
    for item in active:
        s, p = item['sub'], item['product']
        monthly_usd = to_usd(s['price_paid'], s['currency'])
        print(f"  {pad_display(p['display_name'], 16)} {s['tier']: <10} {format_price(monthly_usd, 'USD'):>10} {len(p['tags']):>6}")

    # 两两重叠矩阵
    print(f"\n{'─' * 60}\n📊 功能重叠矩阵 (Jaccard 相似度)\n{'─' * 60}")

    names = [item['product']['display_name'] for item in active]
    tag_sets = [set(item['product']['tags']) for item in active]

    # 表头
    name_w = 10
    header = f"  {pad_display('', name_w)}"
    for name in names:
        header += f" {pad_display(name[:8], 8)}"
    print(header)
    print(f"  {'─' * (name_w + len(names) * 9)}")

    # 矩阵内容
    for i, (name_i, tags_i) in enumerate(zip(names, tag_sets)):
        row = f"  {pad_display(name_i, name_w)}"
        for j, (name_j, tags_j) in enumerate(zip(names, tag_sets)):
            if i == j:
                row += f" {pad_display('—', 8)}"
            else:
                sim = jaccard_similarity(tags_i, tags_j)
                overlap_tags = tags_i & tags_j
                cell = f"{sim:.0%}({len(overlap_tags)})"
                row += f" {pad_display(cell, 8)}"
        print(row)

    # 详细配对分析
    print(f"\n{'─' * 60}\n📋 配对详情\n{'─' * 60}")
    for i, j in combinations(range(len(active)), 2):
        p_i = active[i]['product']
        p_j = active[j]['product']
        tags_i = set(p_i['tags'])
        tags_j = set(p_j['tags'])
        overlap = tags_i & tags_j
        only_i = tags_i - tags_j
        only_j = tags_j - tags_i
        sim = jaccard_similarity(tags_i, tags_j)

        if not overlap:
            continue

        s_i = active[i]['sub']
        s_j = active[j]['sub']
        cost_i = to_usd(s_i['price_paid'], s_i['currency'])
        cost_j = to_usd(s_j['price_paid'], s_j['currency'])

        print(f"\n  🔗 {p_i['display_name']} ↔ {p_j['display_name']}")
        print(f"     重叠度: {sim:.0%} ({len(overlap)}/{len(tags_i | tags_j)} 标签)")
        print(f"     共同功能: {', '.join(sorted(overlap))}")
        if only_i:
            print(f"     仅 {p_i['display_name']}: {', '.join(sorted(only_i))}")
        if only_j:
            print(f"     仅 {p_j['display_name']}: {', '.join(sorted(only_j))}")

        # 冗余支出估算
        if len(tags_i | tags_j) > 0:
            redundancy_i = len(overlap) / len(tags_i) * cost_i
            redundancy_j = len(overlap) / len(tags_j) * cost_j
            print(f"     冗余支出估算: {p_i['display_name']} ~{format_price(redundancy_i)}/月, {p_j['display_name']} ~{format_price(redundancy_j)}/月")

    print()


# ============================================================
# 命令 2: redundancy — 冗余标签分析
# ============================================================
def cmd_redundancy(args):
    products = load_json('products.json')
    subscriptions = load_json('subscriptions.json')
    tag_data = load_json('function_tags.json')
    tag_weights = tag_data.get('tags', {})
    active = get_active_subscriptions(subscriptions, products)

    if not active:
        print("\n⚠️  无活跃订阅")
        return

    print(f"\n{'━' * 60}")
    print(f"💸 冗余标签分析")
    print(f"{'━' * 60}")
    print(f"   分析 {len(active)} 个活跃订阅间的功能重叠\n")

    # 统计每个标签被多少个付费产品覆盖
    tag_coverage = defaultdict(list)
    for item in active:
        p = item['product']
        s = item['sub']
        for tag in p['tags']:
            tag_coverage[tag].append({
                'product': p,
                'sub': s,
                'cost_usd': to_usd(s['price_paid'], s['currency'])
            })

    # 找出被多个产品覆盖的标签
    redundant_tags = {tag: items for tag, items in tag_coverage.items() if len(items) > 1}

    if not redundant_tags:
        print("  ✅ 当前订阅间无功能冗余，每个标签仅由一个产品覆盖")
        return

    # 按冗余程度排序
    sorted_tags = sorted(redundant_tags.items(), key=lambda x: len(x[1]), reverse=True)

    print(f"  {'标签': <12} {'覆盖数':>6}  {'涉及产品': <30} {'冗余成本':>12}")
    print(f"  {'─' * 64}")

    total_redundancy = 0.0
    for tag, items in sorted_tags:
        weight = tag_weights.get(tag, {}).get('weight', 0.5)
        products_str = ', '.join(item['product']['display_name'] for item in items)
        # 冗余成本 = 除最便宜的那个外，其余按标签权重分摊的成本
        sorted_items = sorted(items, key=lambda x: x['cost_usd'])
        redundancy_cost = sum(
            item['cost_usd'] * weight / len(item['product']['tags'])
            for item in sorted_items[1:]
        )
        total_redundancy += redundancy_cost

        bar = generate_bar(len(items) / len(active), 6)
        print(f"  {pad_display(tag, 12)} {bar} {len(items):>2}x   {pad_display(products_str, 30)} ~{format_price(redundancy_cost):>10}/月")

    total_monthly = sum(to_usd(item['sub']['price_paid'], item['sub']['currency']) for item in active)
    redundancy_pct = total_redundancy / total_monthly * 100 if total_monthly > 0 else 0

    print(f"\n  {'─' * 60}")
    print(f"  💰 月总支出: {format_price(total_monthly)}")
    print(f"  💸 估算冗余: ~{format_price(total_redundancy)}/月 ({redundancy_pct:.0f}%)")
    print(f"  💡 如果消除冗余，理论上可节省 ~{format_price(total_redundancy)}/月")
    print()


# ============================================================
# 命令 3: coverage — 标签覆盖率分析
# ============================================================
def cmd_coverage(args):
    products = load_json('products.json')
    subscriptions = load_json('subscriptions.json')
    tag_data = load_json('function_tags.json')
    tag_weights = tag_data.get('tags', {})
    active = get_active_subscriptions(subscriptions, products)

    if not active:
        print("\n⚠️  无活跃订阅")
        return

    print(f"\n{'━' * 60}")
    print(f"📊 功能覆盖率分析")
    print(f"{'━' * 60}\n")

    # 当前已覆盖的标签
    covered_tags = set()
    for item in active:
        covered_tags.update(item['product']['tags'])

    # 所有可能的标签
    all_tags = set(tag_weights.keys())
    uncovered_tags = all_tags - covered_tags

    # 按分组统计
    tag_groups = defaultdict(lambda: {'total': 0, 'covered': 0, 'tags': []})
    for tag, info in tag_weights.items():
        group = info.get('group', '其他')
        tag_groups[group]['total'] += 1
        tag_groups[group]['tags'].append(tag)
        if tag in covered_tags:
            tag_groups[group]['covered'] += 1

    print(f"  已覆盖标签: {len(covered_tags)}/{len(all_tags)} ({len(covered_tags)/len(all_tags):.0%})")
    print(f"  活跃订阅: {len(active)} 个\n")

    # 按分组展示
    print(f"  {'分组': <12} {'覆盖':>6} {'进度':>12}")
    print(f"  {'─' * 34}")
    for group, info in sorted(tag_groups.items(), key=lambda x: x[1]['covered']/x[1]['total'] if x[1]['total'] > 0 else 0, reverse=True):
        ratio = info['covered'] / info['total'] if info['total'] > 0 else 0
        bar = generate_bar(ratio, 8)
        print(f"  {pad_display(group, 12)} {info['covered']:>2}/{info['total']:<2}  {bar} {ratio:.0%}")

    # 未覆盖标签详情
    if uncovered_tags:
        print(f"\n{'─' * 60}\n❌ 未覆盖功能 ({len(uncovered_tags)} 个)\n{'─' * 60}")
        for tag in sorted(uncovered_tags, key=lambda t: tag_weights.get(t, {}).get('weight', 0), reverse=True):
            weight = tag_weights.get(tag, {}).get('weight', 0.5)
            group = tag_weights.get(tag, {}).get('group', '')
            # 找哪些产品提供此标签
            providers = [p for p in products if tag in p['tags']]
            paid_providers = [p for p in providers if any(pl.get('price') is not None and pl['price'] > 0 for pl in p['plans'])]
            free_providers = [p for p in providers if any(pl.get('price') is not None and pl['price'] == 0 for pl in p['plans'])]

            provider_str = ''
            if free_providers:
                provider_str = f"免费可选: {', '.join(p['display_name'] for p in free_providers[:3])}"
            elif paid_providers:
                cheapest = None
                min_cost = float('inf')
                for p in paid_providers:
                    for plan in p['plans']:
                        if plan.get('price') and plan['price'] > 0:
                            cost = to_usd(plan['price'], plan['currency'])
                            if cost < min_cost:
                                min_cost = cost
                                cheapest = p
                if cheapest:
                    provider_str = f"最低: {cheapest['display_name']} {format_price(min_cost)}/月"

            print(f"  {pad_display(tag, 16)} 权重:{weight:.1f}  [{group}]  {provider_str}")

    # 已覆盖标签详情
    print(f"\n{'─' * 60}\n✅ 已覆盖功能 ({len(covered_tags)} 个)\n{'─' * 60}")
    for tag in sorted(covered_tags, key=lambda t: tag_weights.get(t, {}).get('weight', 0), reverse=True):
        providers = [item['product']['display_name'] for item in active if tag in item['product']['tags']]
        multi = ' ⚠️冗余' if len(providers) > 1 else ''
        print(f"  {pad_display(tag, 16)} 由 {', '.join(providers)}{multi}")

    print()


# ============================================================
# 命令 4: optimize — 优化建议
# ============================================================
def cmd_optimize(args):
    products = load_json('products.json')
    subscriptions = load_json('subscriptions.json')
    tag_data = load_json('function_tags.json')
    tag_weights = tag_data.get('tags', {})
    active = get_active_subscriptions(subscriptions, products)

    if len(active) < 2:
        print("\n⚠️  活跃订阅不足 2 个，暂无优化空间")
        return

    print(f"\n{'━' * 60}")
    print(f"💡 订阅优化建议")
    print(f"{'━' * 60}\n")

    total_monthly_usd = sum(to_usd(item['sub']['price_paid'], item['sub']['currency']) for item in active)
    print(f"  当前月支出: {format_price(total_monthly_usd)} ({len(active)} 个订阅)\n")

    suggestions = []

    # 分析 1: 高重叠配对
    for i, j in combinations(range(len(active)), 2):
        p_i = active[i]['product']
        p_j = active[j]['product']
        tags_i = set(p_i['tags'])
        tags_j = set(p_j['tags'])
        sim = jaccard_similarity(tags_i, tags_j)
        overlap = tags_i & tags_j

        if sim >= 0.6:  # 重叠度 >= 60%
            s_i = active[i]['sub']
            s_j = active[j]['sub']
            cost_i = to_usd(s_i['price_paid'], s_i['currency'])
            cost_j = to_usd(s_j['price_paid'], s_j['currency'])

            # 建议保留功能更丰富的那个
            if len(tags_i) >= len(tags_j) and cost_i <= cost_j:
                keep, drop = p_i, p_j
                keep_cost, drop_cost = cost_i, cost_j
                keep_tags, drop_tags = tags_i, tags_j
                keep_name, drop_name = p_i['display_name'], p_j['display_name']
            elif len(tags_j) > len(tags_i) and cost_j <= cost_i:
                keep, drop = p_j, p_i
                keep_cost, drop_cost = cost_j, cost_i
                keep_tags, drop_tags = tags_j, tags_i
                keep_name, drop_name = p_j['display_name'], p_i['display_name']
            else:
                keep, drop = (p_i, p_j) if cost_i <= cost_j else (p_j, p_i)
                keep_cost = min(cost_i, cost_j)
                drop_cost = max(cost_i, cost_j)
                keep_tags = tags_i if keep == p_i else tags_j
                drop_tags = tags_j if keep == p_i else tags_i
                keep_name = keep['display_name']
                drop_name = drop['display_name']

            lost_tags = drop_tags - keep_tags
            saving = drop_cost

            suggestions.append({
                'type': '合并同类',
                'priority': 'high' if sim >= 0.7 else 'medium',
                'title': f"考虑用 {keep_name} 替代 {drop_name}",
                'detail': f"两者功能重叠 {sim:.0%}({len(overlap)} 标签共同)",
                'saving': saving,
                'lost': lost_tags,
                'keep': keep_name,
                'drop': drop_name,
            })

    # 分析 2: 低利用率（独占标签少的产品）
    for item in active:
        p = item['product']
        s = item['sub']
        cost = to_usd(s['price_paid'], s['currency'])
        p_tags = set(p['tags'])

        # 计算独占标签（其他订阅没有的）
        other_tags = set()
        for other in active:
            if other['product']['product_key'] != p['product_key']:
                other_tags.update(other['product']['tags'])
        unique_tags = p_tags - other_tags

        if len(unique_tags) <= 1 and len(p_tags) > 0:
            unique_ratio = len(unique_tags) / len(p_tags)
            suggestions.append({
                'type': '低独占',
                'priority': 'medium' if unique_ratio <= 0.1 else 'low',
                'title': f"{p['display_name']} 的独占功能很少",
                'detail': f"{len(p_tags)} 个标签中仅 {len(unique_tags)} 个是独有的 ({unique_ratio:.0%})",
                'saving': cost,
                'lost': p_tags,
                'unique': unique_tags,
                'drop': p['display_name'],
            })

    # 分析 3: 免费替代可能
    for item in active:
        p = item['product']
        s = item['sub']
        cost = to_usd(s['price_paid'], s['currency'])
        if cost == 0:
            continue

        # 找同分类的免费产品
        free_alternatives = [
            fp for fp in products
            if fp['category'] == p['category']
            and fp['product_key'] != p['product_key']
            and any(pl.get('price') is not None and pl['price'] == 0 for pl in fp['plans'])
        ]

        for fa in free_alternatives:
            fa_tags = set(fa['tags'])
            p_tags = set(p['tags'])
            coverage = len(p_tags & fa_tags) / len(p_tags) if p_tags else 0
            if coverage >= 0.7:
                suggestions.append({
                    'type': '免费替代',
                    'priority': 'high',
                    'title': f"{fa['display_name']}(免费版) 可覆盖 {p['display_name']} {coverage:.0%} 功能",
                    'detail': f"免费替代，覆盖 {len(p_tags & fa_tags)}/{len(p_tags)} 个标签",
                    'saving': cost,
                    'lost': p_tags - fa_tags,
                    'drop': p['display_name'],
                    'alternative': fa['display_name'],
                })

    # 输出建议
    if not suggestions:
        print("  ✅ 当前订阅组合合理，未发现明显优化空间")
    else:
        # 按优先级排序
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        suggestions.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 2))

        # 去重
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            key = s.get('drop', '') + s.get('title', '')
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(s)

        for i, s in enumerate(unique_suggestions, 1):
            icon = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(s.get('priority', 'low'), '⚪')
            print(f"  {icon} 建议 {i}: {s['title']}")
            print(f"     {s['detail']}")
            if s.get('alternative'):
                print(f"     替代: {s['alternative']}")
            if s.get('lost'):
                print(f"     将失去: {', '.join(sorted(s['lost']))}")
            if s.get('unique'):
                print(f"     独占功能: {', '.join(sorted(s['unique'])) if s['unique'] else '无'}")
            print(f"     可节省: ~{format_price(s['saving'])}/月")
            print()

        total_saving = sum(s['saving'] for s in unique_suggestions if s.get('priority') == 'high')
        if total_saving > 0:
            print(f"  {'─' * 50}")
            print(f"  💰 高优先级建议可节省: ~{format_price(total_saving)}/月")
            print(f"  ⚠️  以上为功能重叠分析，实际选择请结合使用体验和需求")

    print()


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='🔍 重叠检测模块 — 功能重叠/冗余分析/覆盖率/优化建议',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python overlap_detector.py overlap
  python overlap_detector.py redundancy
  python overlap_detector.py coverage
  python overlap_detector.py optimize""")

    sub = parser.add_subparsers(dest='command', help='可用命令')
    sub.add_parser('overlap', help='订阅间功能重叠矩阵')
    sub.add_parser('redundancy', help='冗余标签与支出分析')
    sub.add_parser('coverage', help='功能覆盖率分析')
    sub.add_parser('optimize', help='订阅优化建议')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {
        'overlap': cmd_overlap,
        'redundancy': cmd_redundancy,
        'coverage': cmd_coverage,
        'optimize': cmd_optimize,
    }
    cmds.get(args.command, lambda a: parser.print_help())(args)


if __name__ == '__main__':
    main()
