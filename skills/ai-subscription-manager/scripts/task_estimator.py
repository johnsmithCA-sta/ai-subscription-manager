#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务成本计算器（token 级计价）
基于 token_prices.json 的模型单价与任务模板，估算批量任务的 token 用量与成本，
输出多模型对比表 + 错峰对比 + 路由建议。
"""
import json
import os
import argparse
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.join(SCRIPT_DIR, '..')

CURRENCY_SYMBOLS = {'USD': '$', 'CNY': '¥', 'EUR': '€'}


def load_json(filename, required=True):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        if required:
            print(f"❌ 错误：数据文件不存在：{os.path.basename(filepath)}")
            sys.exit(1)
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_rates_to_usd():
    """rates.json: 1 USD = X cur -> to-USD 映射，失败时兜底"""
    default = {'USD': 1.0, 'CNY': 1.0 / 7.25, 'EUR': 1.0 / 0.92}
    raw = load_json('rates.json', required=False)
    if not raw:
        return default
    rates = {cur: (1.0 / r if r else 1.0) for cur, r in raw.get('rates', {}).items()}
    rates.setdefault('USD', 1.0)
    return rates


def convert(amount, from_cur, to_cur, rates_to_usd):
    """经 USD 中转换算金额"""
    if from_cur == to_cur:
        return amount
    usd = amount * rates_to_usd.get(from_cur, 1.0)
    return usd / rates_to_usd.get(to_cur, 1.0)


def fmt(amount, currency):
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    if amount < 1:
        return f"{symbol}{amount:.4f}"
    if amount < 100:
        return f"{symbol}{amount:.2f}"
    return f"{symbol}{amount:,.1f}"


def parse_peak_hours(peak_hours):
    """'09:00-12:00,14:00-18:00' -> [(9*60,12*60), ...] 分钟区间列表"""
    spans = []
    if not peak_hours:
        return spans
    for part in peak_hours.split(','):
        try:
            a, b = part.strip().split('-')
            ah, am = map(int, a.split(':'))
            bh, bm = map(int, b.split(':'))
            spans.append((ah * 60 + am, bh * 60 + bm))
        except ValueError:
            continue
    return spans


def in_peak(peak_hours, when=None):
    now = datetime.now()
    minutes = now.hour * 60 + now.minute
    for lo, hi in parse_peak_hours(peak_hours):
        if lo <= minutes < hi:
            return True
    return False


def get_model(token_prices, model_id):
    for m in token_prices.get('models', []):
        if m['model_id'] == model_id:
            return m
    return None


def estimate_cost(model, tmpl_input, tmpl_output, cache_hit, rates_to_usd):
    """返回 (峰时成本CNY, 谷时成本CNY, 总tokens)。单价统一转 CNY 计算。"""
    miss_tokens = tmpl_input * (1 - cache_hit)
    hit_tokens = tmpl_input * cache_hit
    out_tokens = tmpl_output
    total_tokens = tmpl_input + out_tokens

    to_cny = lambda amt, cur: convert(amt, cur, 'CNY', rates_to_usd)
    unit = (miss_tokens * to_cny(model['input_miss'], model['currency'])
            + hit_tokens * to_cny(model['input_hit'], model['currency'])
            + out_tokens * to_cny(model['output'], model['currency'])) / 1e6

    mult = float(model.get('peak_multiplier', 1.0) or 1.0)
    return unit * mult, unit, total_tokens


def cmd_estimate(args):
    token_prices = load_json('token_prices.json')
    rates_to_usd = load_rates_to_usd()
    models = token_prices.get('models', [])
    templates = token_prices.get('task_templates', {})
    display_cur = args.currency

    if args.model:
        models = [m for m in models if m['model_id'] == args.model]
        if not models:
            print(f"❌ 错误：token_prices.json 中无模型 '{args.model}'")
            return 1

    if args.task:
        tmpl = templates.get(args.task)
        if tmpl is None:
            print(f"❌ 错误：无任务模板 '{args.task}'，可用模板见 list-tasks")
            return 1
        tmpl_input = args.input_tokens if args.input_tokens else tmpl['input_tokens_per_unit']
        tmpl_output = args.output_tokens if args.output_tokens else tmpl['output_tokens_per_unit']
        cache_hit = args.cache_hit if args.cache_hit is not None else tmpl['cache_hit_ratio']
        unit_name = tmpl['unit']
        task_label = tmpl['display_name']
    else:
        if not (args.input_tokens and args.output_tokens):
            print("❌ 错误：--task 与 --input-tokens/--output-tokens 至少提供一组")
            return 1
        tmpl_input = args.input_tokens
        tmpl_output = args.output_tokens
        cache_hit = args.cache_hit if args.cache_hit is not None else 0.5
        unit_name = '次'
        task_label = '自定义任务'

    count = args.count
    unverified = [m for m in models if not m.get('verified', False)]
    if unverified:
        print(f"⚠️  以下模型为占位参考价（verified=false），估算仅供结构参考，请核对官方定价后更新 token_prices.json：")
        print(f"   {', '.join(m['model_id'] for m in unverified)}\n")

    rows = []
    for m in models:
        peak_cny, off_cny, total_tokens = estimate_cost(m, tmpl_input, tmpl_output, cache_hit, rates_to_usd)
        is_peak_now = in_peak(m.get('peak_hours', '')) if m.get('peak_hours') else False
        if args.when == 'peak':
            eff_cny = peak_cny
        elif args.when == 'offpeak':
            eff_cny = off_cny
        else:
            eff_cny = peak_cny if is_peak_now else off_cny
        rows.append({
            'model': m, 'unit_eff': convert(eff_cny, 'CNY', display_cur, rates_to_usd),
            'unit_peak': convert(peak_cny, 'CNY', display_cur, rates_to_usd),
            'unit_off': convert(off_cny, 'CNY', display_cur, rates_to_usd),
            'total_tokens': total_tokens, 'is_peak_now': is_peak_now,
        })

    rows.sort(key=lambda r: r['unit_eff'])
    total_tokens_batch = rows[0]['total_tokens'] * count

    print(f"{'━' * 62}")
    print(f"📊 任务成本估算：{task_label} × {count} {unit_name}")
    print(f"   单位用量：输入 {tmpl_input:,} tok（缓存命中 {cache_hit:.0%}）+ 输出 {tmpl_output:,} tok")
    print(f"   批量合计：≈ {total_tokens_batch / 1e6:.2f}M tokens")
    print(f"{'━' * 62}")
    header = f"{'模型':<22}{'单位成本':>12}{'批量成本':>12}  {'分时':<10}"
    print(header)
    print(f"{'-' * 62}")
    for r in rows:
        name = f"{r['model']['display_name']}"
        timing = ''
        if r['model'].get('peak_hours'):
            timing = (f"峰 {fmt(r['unit_peak'], display_cur)} / 谷 {fmt(r['unit_off'], display_cur)}"
                      + (' ⚠️当前峰时' if r['is_peak_now'] else ' ✅当前谷时'))
        print(f"{name:<22}{fmt(r['unit_eff'], display_cur):>12}"
              f"{fmt(r['unit_eff'] * count, display_cur):>12}  {timing}")
    print(f"{'-' * 62}")

    best = rows[0]
    print(f"\n💡 路由建议")
    print(f"   • 首选：{best['model']['display_name']}（单位 {fmt(best['unit_eff'], display_cur)}，批量 {fmt(best['unit_eff'] * count, display_cur)}）")
    if len(rows) > 1:
        print(f"   • 兜底：{rows[1]['model']['display_name']}（约 {rows[1]['unit_eff'] / best['unit_eff']:.1f}× 成本）")
    peak_savers = [r for r in rows if r['model'].get('peak_hours') and float(r['model'].get('peak_multiplier', 1.0)) > 1.0]
    if peak_savers:
        for r in peak_savers:
            save = (r['unit_peak'] - r['unit_off']) * count
            if save > 0:
                print(f"   • 错峰：{r['model']['display_name']} 谷时执行可省 {fmt(save, display_cur)}（峰时系数 {r['model']['peak_multiplier']}×）")
    print(f"\n   数据来源：token_prices.json（updated_at {token_prices.get('updated_at', '未知')}），汇率为 rates.json 参考值")
    return 0


def cmd_list_tasks(args):
    templates = load_json('token_prices.json').get('task_templates', {})
    print(f"\n📋 任务模板（{len(templates)} 个）\n")
    for tid, t in templates.items():
        print(f"• {tid} — {t['display_name']}")
        print(f"  单位 {t['unit']}：输入 {t['input_tokens_per_unit']:,} tok + 输出 {t['output_tokens_per_unit']:,} tok，缓存命中 {t['cache_hit_ratio']:.0%}")
        if t.get('description'):
            print(f"  {t['description']}")
    print()
    return 0


def cmd_list_models(args):
    data = load_json('token_prices.json')
    models = data.get('models', [])
    print(f"\n🤖 模型计价（每百万 tokens，updated_at {data.get('updated_at', '未知')}）\n")
    print(f"{'model_id':<22}{'输入(未命中)':>12}{'输入(命中)':>10}{'输出':>8}  {'分时':<16}{'核价':<6}")
    print(f"{'-' * 80}")
    for m in models:
        peak = f"{m.get('peak_hours')} ×{m.get('peak_multiplier')}" if m.get('peak_hours') else '-'
        flag = '✅' if m.get('verified', False) else '⚠️ 参考价'
        print(f"{m['model_id']:<22}{m['input_miss']:>10}{m['input_hit']:>10}{m['output']:>8}  {peak:<16}{flag:<6}")
    print(f"\n核价提示：⚠️ 参考价模型请核对官方定价页后用 set-price 更新\n")
    return 0


def cmd_set_price(args):
    path = os.path.join(DATA_DIR, 'token_prices.json')
    data = load_json('token_prices.json')
    m = get_model(data, args.model)
    if m is None:
        print(f"❌ 错误：无模型 '{args.model}'")
        return 1
    changed = []
    if args.input_miss is not None:
        m['input_miss'] = args.input_miss; changed.append('input_miss')
    if args.input_hit is not None:
        m['input_hit'] = args.input_hit; changed.append('input_hit')
    if args.output is not None:
        m['output'] = args.output; changed.append('output')
    if args.peak_multiplier is not None:
        m['peak_multiplier'] = args.peak_multiplier; changed.append('peak_multiplier')
    m['verified'] = bool(args.verified)
    m['price_updated'] = datetime.now().strftime('%Y-%m-%d')
    if args.source:
        m['price_source'] = args.source
        changed.append('price_source')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已更新 {m['display_name']}：{', '.join(changed) or '仅核价状态'}，verified={m['verified']}，price_updated={m['price_updated']}")
    if args.source:
        print(f"   核价来源：{args.source}")
    return 0


def main():
    parser = argparse.ArgumentParser(description='任务成本计算器（token 级计价）')
    sub = parser.add_subparsers(dest='command')

    p1 = sub.add_parser('estimate', help='估算任务成本（多模型对比）')
    p1.add_argument('--task', help='任务模板 ID（见 list-tasks）')
    p1.add_argument('--count', type=int, default=1, help='任务数量（默认 1）')
    p1.add_argument('--model', help='只估算指定模型')
    p1.add_argument('--currency', default='CNY', choices=['CNY', 'USD'], help='展示币种（默认 CNY）')
    p1.add_argument('--when', choices=['peak', 'offpeak', 'now'], default='now', help='分时口径（默认按当前时间）')
    p1.add_argument('--input-tokens', type=int, help='覆盖模板：单位输入 tokens')
    p1.add_argument('--output-tokens', type=int, help='覆盖模板：单位输出 tokens')
    p1.add_argument('--cache-hit', type=float, help='覆盖模板：缓存命中率 0-1')

    sub.add_parser('list-tasks', help='列出任务模板')
    sub.add_parser('list-models', help='列出模型计价')

    p2 = sub.add_parser('set-price', help='核对后更新模型单价（含核价溯源）')
    p2.add_argument('--model', required=True, help='model_id')
    p2.add_argument('--input-miss', type=float, help='输入价（未命中，/M tokens）')
    p2.add_argument('--input-hit', type=float, help='输入价（缓存命中，/M tokens）')
    p2.add_argument('--output', type=float, help='输出价（/M tokens）')
    p2.add_argument('--peak-multiplier', type=float, help='峰时系数')
    p2.add_argument('--verified', action='store_true', help='标记已核对官方定价')
    p2.add_argument('--source', help='核价来源（官网 URL 或说明）')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    commands = {'estimate': cmd_estimate, 'list-tasks': cmd_list_tasks,
                'list-models': cmd_list_models, 'set-price': cmd_set_price}
    sys.exit(commands[args.command](args) or 0)


if __name__ == '__main__':
    main()
