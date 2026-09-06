#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 余额资产分析器
管理 balances.json 中的充值余额资产（平台/余额/充值日/用途/消耗记录），
按历史消耗速率折算余额寿命与可跑批数，并输出低余额预警。
"""
import json
import os
import argparse
import sys
from datetime import datetime, date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.join(SCRIPT_DIR, '..')

CURRENCY_SYMBOLS = {'USD': '$', 'CNY': '¥', 'EUR': '€'}
BALANCES_FILE = 'balances.json'


def load_json(filename, required=True):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        if required:
            print(f"❌ 错误：数据文件不存在：{os.path.basename(filepath)}")
            sys.exit(1)
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_balances(data):
    filepath = os.path.join(DATA_DIR, BALANCES_FILE)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_balances():
    data = load_json(BALANCES_FILE, required=False)
    if data is None:
        return {'balances': []}
    return data


def fmt(amount, currency):
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    if abs(amount) < 100:
        return f"{symbol}{amount:,.2f}"
    return f"{symbol}{amount:,.1f}"


def find_balance(data, balance_id):
    for b in data.get('balances', []):
        if b['balance_id'] == balance_id:
            return b
    return None


def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d').date()


def burn_rate(b):
    """日均消耗速率：消耗记录跨度内的平均。无记录返回 0。"""
    logs = [l for l in b.get('consumption_log', []) if l.get('type') != 'topup']
    if not logs:
        return 0.0, None
    dates = sorted(parse_date(l['date']) for l in logs)
    total = sum(float(l['amount']) for l in logs)
    span = max((dates[-1] - dates[0]).days, 1)
    span = max(span, len(logs) - 1, 1)  # 单日多条时避免速率被高估
    rate = total / span
    if len(dates) == 1:
        rate = total  # 仅一条记录：按当日消耗量作为日速率参考
    return rate, dates[0]


def alert_threshold():
    cfg = load_json('remind_config.json', required=False) or {}
    ba = cfg.get('balance_alert', {})
    return ba.get('threshold_pct', 20), ba.get('enabled', True)


def cmd_add(args):
    data = load_balances()
    bid = args.id or f"bal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if find_balance(data, bid):
        print(f"❌ 错误：余额 ID '{bid}' 已存在")
        return 1
    entry = {
        'balance_id': bid,
        'platform': args.platform,
        'currency': args.currency.upper(),
        'balance': args.balance,
        'topup_amount': args.balance,
        'topup_date': args.topup_date or datetime.now().strftime('%Y-%m-%d'),
        'purpose': args.purpose or '',
        'model_hint': args.model or '',
        'consumption_log': [],
    }
    data['balances'].append(entry)
    save_balances(data)
    print(f"✅ 已添加余额资产 {bid}：{args.platform} {fmt(args.balance, entry['currency'])}"
          + (f"（{args.purpose}）" if args.purpose else ''))
    return 0


def cmd_topup(args):
    data = load_balances()
    b = find_balance(data, args.id)
    if b is None:
        print(f"❌ 错误：无余额资产 '{args.id}'")
        return 1
    b['balance'] = round(b['balance'] + args.amount, 4)
    b['topup_amount'] = round(b.get('topup_amount', 0) + args.amount, 4)
    b['topup_date'] = args.date or datetime.now().strftime('%Y-%m-%d')
    b.setdefault('consumption_log', []).append(
        {'date': b['topup_date'], 'amount': 0, 'type': 'topup', 'note': f"充值 {args.amount}"})
    save_balances(data)
    print(f"✅ {b['platform']} 充值 {fmt(args.amount, b['currency'])}，当前余额 {fmt(b['balance'], b['currency'])}")
    return 0


def cmd_record(args):
    data = load_balances()
    b = find_balance(data, args.id)
    if b is None:
        print(f"❌ 错误：无余额资产 '{args.id}'")
        return 1
    b.setdefault('consumption_log', []).append(
        {'date': args.date or datetime.now().strftime('%Y-%m-%d'),
         'amount': args.amount, 'type': 'usage', 'note': args.note or ''})
    b['balance'] = round(b['balance'] - args.amount, 4)
    save_balances(data)
    print(f"✅ 已记录消耗 {fmt(args.amount, b['currency'])}，当前余额 {fmt(b['balance'], b['currency'])}")
    return 0


def cmd_list(args):
    data = load_balances()
    balances = data.get('balances', [])
    if not balances:
        print("\n📭 暂无余额资产。用 add 命令登记第一笔充值余额。\n")
        return 0
    print(f"\n💰 API 余额资产（{len(balances)} 项）\n")
    for b in balances:
        rate, _ = burn_rate(b)
        days = b['balance'] / rate if rate > 0 else None
        print(f"• {b['balance_id']} — {b['platform']} {fmt(b['balance'], b['currency'])}"
              f"（充值 {fmt(b.get('topup_amount', 0), b['currency'])} @ {b.get('topup_date', '?')}）")
        if b.get('purpose'):
            print(f"  用途：{b['purpose']}" + (f" ｜ 常用模型：{b['model_hint']}" if b.get('model_hint') else ''))
        if rate > 0:
            print(f"  消耗速率：{fmt(rate, b['currency'])}/天 ｜ 按当前速率约可撑 {days:.0f} 天")
        else:
            print(f"  消耗速率：暂无消耗记录（用 record 命令登记）")
    print()
    return 0


def cmd_analyze(args):
    data = load_balances()
    b = find_balance(data, args.id)
    if b is None:
        print(f"❌ 错误：无余额资产 '{args.id}'")
        return 1
    rate, first_date = burn_rate(b)
    cur = b['currency']
    print(f"{'━' * 56}")
    print(f"📈 余额寿命分析：{b['platform']}（{b['balance_id']}）")
    print(f"{'━' * 56}")
    print(f"   当前余额：{fmt(b['balance'], cur)}（充值 {fmt(b.get('topup_amount', 0), cur)}）")
    if rate <= 0:
        print("   ⚠️ 无消耗记录，无法折算寿命。先用 record 登记几次消耗。")
        return 0
    days = b['balance'] / rate
    print(f"   消耗速率：{fmt(rate, cur)}/天（自 {first_date} 起均摊）")
    from datetime import timedelta
    runout = date.today() + timedelta(days=int(days))
    print(f"   预计可用：≈ {days:.0f} 天（至 ~{runout.isoformat()}）")

    if args.task:
        est_path = os.path.join(DATA_DIR, 'token_prices.json')
        if not os.path.exists(est_path):
            print("   ⚠️ 无 token_prices.json，跳过批数折算")
            return 0
        tp = json.load(open(est_path, encoding='utf-8'))
        tmpl = tp.get('task_templates', {}).get(args.task)
        if tmpl is None:
            print(f"   ⚠️ 无任务模板 '{args.task}'，跳过批数折算")
            return 0
        sys.path.insert(0, SCRIPT_DIR)
        import task_estimator as te
        rates = te.load_rates_to_usd()
        monthly = rate * 30
        print(f"\n   按任务模板折算（月耗 {fmt(monthly, cur)} 可跑）：")
        print(f"   {'模型':<24}{'单位成本':>10}{'余额可跑':>12}")
        print(f"   {'-' * 50}")
        def fmt4(amount, currency):
            symbol = CURRENCY_SYMBOLS.get(currency, currency)
            return f"{symbol}{amount:.4f}" if amount < 1 else fmt(amount, currency)
        rows = []
        for m in tp.get('models', []):
            _, off_cny, _ = te.estimate_cost(m, tmpl['input_tokens_per_unit'],
                                             tmpl['output_tokens_per_unit'],
                                             tmpl['cache_hit_ratio'], rates)
            unit_cur = te.convert(off_cny, 'CNY', cur, rates)
            if unit_cur <= 0:
                continue
            units = b['balance'] / unit_cur
            rows.append((m['display_name'], unit_cur, units))
        for name, unit_cur, units in sorted(rows, key=lambda r: -r[2]):
            print(f"   {name:<24}{fmt4(unit_cur, cur):>10}{units:>10.0f} {tmpl['unit']}")
        print(f"\n   💡 以最省模型计，余额约可跑 {max(r[2] for r in rows):.0f} {tmpl['unit']}"
              f"（{args.task}）；按月耗速率约 {b['balance'] / monthly:.1f} 个月耗尽")
    return 0


def cmd_check(args):
    data = load_balances()
    balances = data.get('balances', [])
    if not balances:
        print("📭 暂无余额资产，无需预警。")
        return 0
    threshold_pct, enabled = alert_threshold()
    if not enabled:
        print("🔕 余额预警已在 remind_config.json 中关闭（balance_alert.enabled=false）")
        return 0
    print(f"🔔 低余额预警检查（阈值：余额 < 充值额的 {threshold_pct}%）\n")
    alerts = []
    for b in balances:
        topup = float(b.get('topup_amount', 0) or 0)
        floor = topup * threshold_pct / 100.0
        if topup > 0 and b['balance'] < floor:
            rate, _ = burn_rate(b)
            days = b['balance'] / rate if rate > 0 else None
            alerts.append((b, floor, days))
            print(f"   ⚠️ {b['platform']}（{b['balance_id']}）：{fmt(b['balance'], b['currency'])}"
                  f" 低于预警线 {fmt(floor, b['currency'])}"
                  + (f"，按当前速率约 {days:.0f} 天耗尽，建议续充" if days else "，建议续充"))
    if not alerts:
        print("   ✅ 全部余额资产均在预警线之上")
    print()
    return 0


# ============ sync：在线余额同步（显式 opt-in 的唯一网络功能） ============

SYNC_ENDPOINTS = {
    'deepseek': {
        'match': ('deepseek',),
        'url': 'https://api.deepseek.com/user/balance',
        'parse': lambda r: float(r['balance_infos'][0]['total_balance']),
        'currency': 'CNY',
    },
    'moonshot': {
        'match': ('moonshot', 'kimi'),
        'url': 'https://api.moonshot.cn/v1/users/me/balance',
        'parse': lambda r: float(r['data']['available_balance']),
        'currency': 'CNY',
    },
}


def _resolve_keys(from_workbuddy=False):
    """解析 API Key：环境变量优先，其次 WorkBuddy models.json（本机便利，可选）"""
    keys = {}
    import os as _os
    if _os.environ.get('DEEPSEEK_API_KEY'):
        keys['deepseek'] = _os.environ['DEEPSEEK_API_KEY']
    if _os.environ.get('MOONSHOT_API_KEY'):
        keys['moonshot'] = _os.environ['MOONSHOT_API_KEY']
    if from_workbuddy:
        mb = _os.path.expanduser('~/.workbuddy/models.json')
        if _os.path.exists(mb):
            data = json.load(open(mb, encoding='utf-8'))
            models = data if isinstance(data, list) else data.get('models', [])
            for m in models:
                text = (m.get('vendor', '') + ' ' + m.get('url', '') + ' ' + m.get('name', '')).lower()
                k = m.get('apiKey')
                if not k:
                    continue
                for prov, cfg in SYNC_ENDPOINTS.items():
                    if prov not in keys and any(t in text for t in cfg['match']):
                        keys[prov] = k
    return keys


def cmd_sync(args):
    keys = _resolve_keys(from_workbuddy=args.from_workbuddy)
    if not keys:
        print("❌ 未找到可用 Key：设 DEEPSEEK_API_KEY / MOONSHOT_API_KEY 环境变量，或加 --from-workbuddy 复用本机 WorkBuddy 模型配置")
        return 1
    import urllib.request
    today = datetime.now().strftime('%Y-%m-%d')
    data = load_balances()
    changed, manual, skipped = [], [], []
    for b in data.get('balances', []):
        text = (b['platform'] + ' ' + b.get('model_hint', '')).lower()
        prov = next((p for p, cfg in SYNC_ENDPOINTS.items() if any(t in text for t in cfg['match'])), None)
        if prov is None:
            manual.append(b)
            continue
        if prov not in keys:
            skipped.append((b, prov))
            continue
        req = urllib.request.Request(SYNC_ENDPOINTS[prov]['url'],
                                     headers={'Authorization': f'Bearer {keys[prov]}'})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                new_bal = SYNC_ENDPOINTS[prov]['parse'](json.loads(resp.read().decode()))
        except Exception as e:
            print(f"   ❌ {b['platform']}：查询失败 {str(e)[:80]}")
            continue
        old = b['balance']
        if abs(new_bal - old) < 0.0001:
            print(f"   ✅ {b['platform']}：{fmt(old, b['currency'])}（无变化）")
            continue
        b['balance'] = round(new_bal, 6)
        diff = round(abs(new_bal - old), 4)
        if new_bal < old:
            b.setdefault('consumption_log', []).append(
                {'date': today, 'amount': diff, 'type': 'usage', 'note': 'API 同步差额'})
            direction = f"↓ 消耗 {fmt(diff, b['currency'])}"
        else:
            b.setdefault('consumption_log', []).append(
                {'date': today, 'amount': 0, 'type': 'topup', 'note': f'API 同步：充值 {diff}'})
            b['topup_amount'] = round(b.get('topup_amount', 0) + diff, 4)
            direction = f"↑ 充值 {fmt(diff, b['currency'])}"
        print(f"   🔄 {b['platform']}：{fmt(old, b['currency'])} → {fmt(new_bal, b['currency'])}（{direction}）")
        changed.append(b['platform'])
    if manual:
        names = ', '.join(x['platform'] for x in manual)
        print(f"\n   ✋ 无公开余额 API，请手动更新：{names}")
    if skipped:
        print(f"   ⚠️ 有资产但无对应 Key：{', '.join(f'{b['platform']}({p})' for b, p in skipped)}")
    if changed:
        save_balances(data)
        print(f"\n✅ 已同步 {len(changed)} 项并写回 balances.json")
    else:
        print("\n（无变化，未写文件）")
    return 0


def main():
    parser = argparse.ArgumentParser(description='API 余额资产分析器')
    sub = parser.add_subparsers(dest='command')

    p = sub.add_parser('add', help='登记余额资产')
    p.add_argument('--platform', required=True, help='平台名（如 DeepSeek/Kimi/智谱）')
    p.add_argument('--balance', type=float, required=True, help='当前余额')
    p.add_argument('--currency', default='CNY', choices=['CNY', 'USD'], help='币种（默认 CNY）')
    p.add_argument('--topup-date', help='充值日期 YYYY-MM-DD（默认今天）')
    p.add_argument('--purpose', help='主要用途')
    p.add_argument('--model', dest='model', help='常用模型')
    p.add_argument('--id', help='自定义余额 ID（默认自动生成）')

    p = sub.add_parser('topup', help='记录充值')
    p.add_argument('--id', required=True, help='余额 ID')
    p.add_argument('--amount', type=float, required=True, help='充值金额')
    p.add_argument('--date', help='充值日期（默认今天）')

    p = sub.add_parser('record', help='记录一笔消耗')
    p.add_argument('--id', required=True, help='余额 ID')
    p.add_argument('--amount', type=float, required=True, help='消耗金额')
    p.add_argument('--date', help='消耗日期（默认今天）')
    p.add_argument('--note', help='备注')

    sub.add_parser('list', help='列出余额资产与寿命')

    p = sub.add_parser('analyze', help='余额寿命 + 可跑批数折算')
    p.add_argument('--id', required=True, help='余额 ID')
    p.add_argument('--task', help='任务模板 ID（用 token_prices.json 折算可跑批数）')

    sub.add_parser('check', help='低余额预警检查')

    p = sub.add_parser('sync', help='在线同步余额（DeepSeek/Moonshot，需 API Key）')
    p.add_argument('--from-workbuddy', action='store_true',
                   help='复用本机 ~/.workbuddy/models.json 中已配置的模型 Key（不落盘）')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    commands = {'add': cmd_add, 'topup': cmd_topup, 'record': cmd_record,
                'list': cmd_list, 'analyze': cmd_analyze, 'check': cmd_check, 'sync': cmd_sync}
    sys.exit(commands[args.command](args) or 0)


if __name__ == '__main__':
    main()
