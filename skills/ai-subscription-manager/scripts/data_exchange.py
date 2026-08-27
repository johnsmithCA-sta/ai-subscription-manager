#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0-07 导入导出模块
提供订阅记录的 CSV/JSON 导出、导入、模板生成等功能
"""

import json
import csv
import argparse
import sys
import os
from datetime import datetime
from collections import OrderedDict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.join(SCRIPT_DIR, '..')

CURRENCY_SYMBOLS = {'USD': '$', 'CNY': '¥', 'EUR': '€'}

# CSV 导出字段顺序
CSV_FIELDS = [
    'sub_id', 'product_key', 'tier', 'status', 'start_date',
    'next_billing_date', 'billing_cycle', 'price_paid', 'currency',
    'payment_method', 'auto_renew', 'notes', 'created_at', 'updated_at'
]

# CSV 中文表头映射
CSV_HEADER_CN = {
    'sub_id': '订阅ID',
    'product_key': '产品标识',
    'tier': '套餐档位',
    'status': '状态',
    'start_date': '开始日期',
    'next_billing_date': '下次扣费',
    'billing_cycle': '计费周期',
    'price_paid': '支付价格',
    'currency': '币种',
    'payment_method': '支付方式',
    'auto_renew': '自动续费',
    'notes': '备注',
    'created_at': '创建时间',
    'updated_at': '更新时间',
}


def load_json(filename):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   ✅ 已保存: {filepath}")


def get_product_info(products, product_key):
    for p in products:
        if p['product_key'] == product_key:
            return p
    return None


def get_valid_tiers(product):
    if not product:
        return []
    return [plan['tier'] for plan in product.get('plans', []) if plan.get('tier')]


def format_price(amount, currency):
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    if amount == 0:
        return "免费"
    return f"{symbol}{amount:,.2f}"


def now_iso():
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')


def generate_sub_id(existing_ids):
    """生成新的 sub_id"""
    today = datetime.now().strftime('%Y%m%d')
    prefix = f"sub_{today}_"
    counter = 1
    while f"{prefix}{counter:03d}" in existing_ids:
        counter += 1
    return f"{prefix}{counter:03d}"


# ============================================================
# 命令 1: export-csv — 导出为 CSV
# ============================================================
def cmd_export_csv(args):
    subscriptions = load_json('subscriptions.json')
    output = args.output or os.path.join(DATA_DIR, 'subscriptions_export.csv')
    use_cn_header = not args.english_header

    if not subscriptions:
        print("⚠️  暂无订阅记录可导出")
        return

    with open(output, 'w', newline='', encoding='utf-8-sig') as f:
        if use_cn_header:
            # 写中文表头
            header_writer = csv.writer(f)
            cn_header = [CSV_HEADER_CN.get(field, field) for field in CSV_FIELDS]
            header_writer.writerow(cn_header)
        # 数据行用 DictWriter，fieldnames 为英文
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
        if not use_cn_header:
            writer.writeheader()

        for sub in subscriptions:
            row = {}
            for field in CSV_FIELDS:
                val = sub.get(field, '')
                if field == 'auto_renew':
                    val = '是' if val else '否'
                row[field] = val
            writer.writerow(row)

    print(f"\n{'━' * 50}")
    print(f"📤 CSV 导出完成")
    print(f"{'━' * 50}")
    print(f"   文件: {output}")
    print(f"   记录数: {len(subscriptions)}")
    print(f"   编码: UTF-8 with BOM (Excel 兼容)")
    if use_cn_header:
        print(f"   表头: 中文")
    print()


# ============================================================
# 命令 2: export-json — 导出为 JSON
# ============================================================
def cmd_export_json(args):
    subscriptions = load_json('subscriptions.json')
    output = args.output or os.path.join(DATA_DIR, 'subscriptions_export.json')

    if not subscriptions:
        print("⚠️  暂无订阅记录可导出")
        return

    export_data = {
        'export_info': {
            'exported_at': now_iso(),
            'version': '1.0',
            'record_count': len(subscriptions),
        },
        'subscriptions': subscriptions,
    }

    save_json(export_data, output)

    print(f"\n{'━' * 50}")
    print(f"📤 JSON 导出完成")
    print(f"{'━' * 50}")
    print(f"   文件: {output}")
    print(f"   记录数: {len(subscriptions)}")

    active = sum(1 for s in subscriptions if s.get('status') == 'active')
    cancelled = sum(1 for s in subscriptions if s.get('status') == 'cancelled')
    expired = sum(1 for s in subscriptions if s.get('status') == 'expired')
    print(f"   活跃: {active}  |  已取消: {cancelled}  |  已过期: {expired}")
    print()


# ============================================================
# 命令 3: import-csv — 从 CSV 导入
# ============================================================
def cmd_import_csv(args):
    input_file = args.file
    dry_run = args.dry_run

    if not os.path.exists(input_file):
        print(f"❌ 文件不存在: {input_file}")
        return

    products = load_json('products.json')
    subscriptions = load_json('subscriptions.json')

    # 反向中文表头映射
    cn_to_en = {v: k for k, v in CSV_HEADER_CN.items()}

    print(f"\n{'━' * 50}")
    print(f"📥 CSV 导入{'(预览)' if dry_run else ''}")
    print(f"{'━' * 50}")
    print(f"   文件: {input_file}")

    # 读取 CSV
    imported = []
    errors = []
    existing_ids = {s['sub_id'] for s in subscriptions}

    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        # 自动检测表头是中文还是英文
        header_map = {}
        for h in headers:
            if h in cn_to_en:
                header_map[h] = cn_to_en[h]
            elif h in CSV_FIELDS:
                header_map[h] = h
            else:
                header_map[h] = h  # 保持原样

        for row_num, row in enumerate(reader, start=2):  # 从第2行开始（第1行是表头）
            # 映射字段名
            mapped = {}
            for k, v in row.items():
                en_key = header_map.get(k, k)
                mapped[en_key] = v.strip() if v else ''

            # 验证必填字段
            missing = []
            if not mapped.get('product_key'):
                missing.append('product_key')
            if not mapped.get('tier'):
                missing.append('tier')
            if not mapped.get('start_date'):
                missing.append('start_date')
            if not mapped.get('price_paid') and mapped.get('price_paid') != '0':
                missing.append('price_paid')
            if not mapped.get('currency'):
                missing.append('currency')

            if missing:
                errors.append(f"第{row_num}行: 缺少必填字段 {', '.join(missing)}")
                continue

            # 验证 product_key
            product = get_product_info(products, mapped['product_key'])
            if not product:
                errors.append(f"第{row_num}行: 未知产品 '{mapped['product_key']}'")
                continue

            # 验证 tier
            valid_tiers = get_valid_tiers(product)
            if mapped['tier'] not in valid_tiers:
                errors.append(f"第{row_num}行: {mapped['product_key']} 无档位 '{mapped['tier']}' (可选: {', '.join(valid_tiers)})")
                continue

            # 类型转换
            try:
                price = float(mapped.get('price_paid', 0))
            except ValueError:
                errors.append(f"第{row_num}行: price_paid 格式错误 '{mapped.get('price_paid')}'")
                continue

            auto_renew_val = mapped.get('auto_renew', 'true')
            if auto_renew_val in ('是', 'true', 'True', '1', 'yes'):
                auto_renew = True
            elif auto_renew_val in ('否', 'false', 'False', '0', 'no'):
                auto_renew = False
            else:
                auto_renew = True  # 空值/未知默认自动续费

            # 构建记录
            record = {
                'sub_id': mapped.get('sub_id', '') or generate_sub_id(existing_ids),
                'product_key': mapped['product_key'],
                'tier': mapped['tier'],
                'status': mapped.get('status', '') or 'active',
                'start_date': mapped.get('start_date', ''),
                'next_billing_date': mapped.get('next_billing_date', ''),
                'billing_cycle': mapped.get('billing_cycle', '') or 'monthly',
                'price_paid': price,
                'currency': mapped.get('currency', 'USD').upper(),
                'payment_method': mapped.get('payment_method', ''),
                'auto_renew': auto_renew,
                'notes': mapped.get('notes', ''),
                'created_at': mapped.get('created_at', '') or now_iso(),
                'updated_at': mapped.get('updated_at', '') or now_iso(),
            }

            # 检查 ID 重复
            if record['sub_id'] in existing_ids:
                record['sub_id'] = generate_sub_id(existing_ids)

            existing_ids.add(record['sub_id'])
            imported.append(record)

    # 显示结果
    if errors:
        print(f"\n  ⚠️  发现 {len(errors)} 个错误:")
        for err in errors[:10]:
            print(f"    ❌ {err}")
        if len(errors) > 10:
            print(f"    ... 还有 {len(errors) - 10} 个错误")

    if imported:
        print(f"\n  📋 成功解析 {len(imported)} 条记录:")
        print(f"  {'产品': <14} {'档位': <12} {'价格':>10} {'状态':>6}")
        print(f"  {'─' * 46}")
        for r in imported[:20]:
            p = get_product_info(products, r['product_key'])
            name = p['display_name'] if p else r['product_key']
            print(f"  {name: <14} {r['tier']: <12} {format_price(r['price_paid'], r['currency']):>10} {r['status']:>6}")
        if len(imported) > 20:
            print(f"  ... 还有 {len(imported) - 20} 条")

        if dry_run:
            print(f"\n  🔍 预览模式，未写入数据。去掉 --dry-run 正式导入。")
        else:
            # 写入
            subscriptions.extend(imported)
            save_json(subscriptions, os.path.join(DATA_DIR, 'subscriptions.json'))
            print(f"\n  ✅ 已追加 {len(imported)} 条记录到 subscriptions.json")
    else:
        print(f"\n  ❌ 无有效记录可导入")

    print()


# ============================================================
# 命令 4: import-json — 从 JSON 导入
# ============================================================
def cmd_import_json(args):
    input_file = args.file
    dry_run = args.dry_run
    merge = not args.replace  # 默认合并模式

    if not os.path.exists(input_file):
        print(f"❌ 文件不存在: {input_file}")
        return

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        return

    # 支持两种格式: 带 export_info 包装的 或 纯数组
    if isinstance(data, list):
        new_subs = data
    elif isinstance(data, dict):
        new_subs = data.get('subscriptions', data.get('data', []))
        if not isinstance(new_subs, list):
            print(f"❌ JSON 格式不正确，需要数组或包含 subscriptions 字段的对象")
            return
    else:
        print(f"❌ JSON 格式不正确")
        return

    products = load_json('products.json')
    subscriptions = load_json('subscriptions.json')

    print(f"\n{'━' * 50}")
    print(f"📥 JSON 导入{'(预览)' if dry_run else ''} — {'合并' if merge else '替换'}模式")
    print(f"{'━' * 50}")
    print(f"   文件: {input_file}")
    print(f"   解析到 {len(new_subs)} 条记录")

    # 验证
    valid = []
    errors = []
    existing_ids = {s['sub_id'] for s in subscriptions}
    updated_count = 0

    for i, sub in enumerate(new_subs):
        # 基本字段检查
        if not sub.get('product_key'):
            errors.append(f"记录#{i+1}: 缺少 product_key")
            continue
        if not sub.get('tier'):
            errors.append(f"记录#{i+1}: 缺少 tier")
            continue

        product = get_product_info(products, sub['product_key'])
        if not product:
            errors.append(f"记录#{i+1}: 未知产品 '{sub['product_key']}'")
            continue

        valid_tiers = get_valid_tiers(product)
        if sub['tier'] not in valid_tiers:
            errors.append(f"记录#{i+1}: {sub['product_key']} 无档位 '{sub['tier']}'")
            continue

        # 处理重复 ID
        sub_id = sub.get('sub_id', '')
        if sub_id and sub_id in existing_ids:
            if merge:
                # 合并模式：更新已有记录
                for j, existing in enumerate(subscriptions):
                    if existing['sub_id'] == sub_id:
                        sub['updated_at'] = now_iso()
                        subscriptions[j] = {**existing, **sub}
                        updated_count += 1
                        break
                continue
            # 替换模式不跳过

        if not sub_id:
            sub['sub_id'] = generate_sub_id(existing_ids)
        if not sub.get('created_at'):
            sub['created_at'] = now_iso()
        sub['updated_at'] = now_iso()

        existing_ids.add(sub['sub_id'])
        valid.append(sub)

    if errors:
        print(f"\n  ⚠️  {len(errors)} 个验证错误:")
        for err in errors[:10]:
            print(f"    ❌ {err}")

    if dry_run:
        print(f"\n  📋 有效记录: {len(valid)} 条 (新增) + {updated_count} 条 (更新)")
        print(f"  🔍 预览模式，未写入数据。")
    else:
        if merge:
            subscriptions.extend(valid)
        else:
            subscriptions = valid

        save_json(subscriptions, os.path.join(DATA_DIR, 'subscriptions.json'))
        print(f"\n  ✅ 新增 {len(valid)} 条" + (f"，更新 {updated_count} 条" if updated_count else ""))

    print()


# ============================================================
# 命令 5: template — 生成导入模板
# ============================================================
def cmd_template(args):
    fmt = args.format
    output_dir = args.output_dir or DATA_DIR

    print(f"\n{'━' * 50}")
    print(f"📝 生成导入模板")
    print(f"{'━' * 50}")

    if fmt == 'csv':
        output = os.path.join(output_dir, 'subscription_template.csv')
        with open(output, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # 中文表头
            cn_header = [CSV_HEADER_CN.get(field, field) for field in CSV_FIELDS]
            writer.writerow(cn_header)
            # 示例行
            writer.writerow([
                '(自动生成)', 'chatgpt', 'Plus', 'active',
                '2026-01-15', '2026-02-15', 'monthly',
                '20.00', 'USD', '信用卡', '是', '日常使用',
                '(自动生成)', '(自动生成)'
            ])
            writer.writerow([
                '', 'claude', 'Pro', 'active',
                '2026-02-01', '2026-03-01', 'monthly',
                '20.00', 'USD', '支付宝', '是', '编程辅助',
                '', ''
            ])
        print(f"   📄 CSV 模板: {output}")
        print(f"   编码: UTF-8 with BOM")

    elif fmt == 'json':
        output = os.path.join(output_dir, 'subscription_template.json')
        template = {
            "subscriptions": [
                {
                    "sub_id": "(留空自动生成)",
                    "product_key": "chatgpt",
                    "tier": "Plus",
                    "status": "active",
                    "start_date": "2026-01-15",
                    "next_billing_date": "2026-02-15",
                    "billing_cycle": "monthly",
                    "price_paid": 20.00,
                    "currency": "USD",
                    "payment_method": "信用卡",
                    "auto_renew": True,
                    "notes": "日常使用"
                }
            ]
        }
        save_json(template, output)
        print(f"   📄 JSON 模板: {output}")

    # 打印字段说明
    print(f"\n  📋 字段说明:")
    print(f"  {'字段': <14} {'必填':>4}  {'说明'}")
    print(f"  {'─' * 48}")
    field_notes = {
        'sub_id': '留空自动生成，格式 sub_YYYYMMDD_NNN',
        'product_key': '产品标识，需匹配 products.json',
        'tier': '套餐档位，需匹配产品已有档位',
        'status': '默认 active (active/cancelled/expired)',
        'start_date': '开始日期 YYYY-MM-DD',
        'next_billing_date': '下次扣费日期 YYYY-MM-DD',
        'billing_cycle': '计费周期 (monthly/yearly/one-time)',
        'price_paid': '实际支付金额',
        'currency': '币种 (USD/CNY)',
        'payment_method': '支付方式 (可选)',
        'auto_renew': '是否自动续费 (可选，默认是)',
        'notes': '备注 (可选)',
        'created_at': '留空自动生成',
        'updated_at': '留空自动生成',
    }
    for field in CSV_FIELDS:
        required = '✅' if field in ('product_key', 'tier', 'start_date', 'price_paid', 'currency') else '  '
        print(f"  {CSV_HEADER_CN.get(field, field): <14} {required:>4}  {field_notes.get(field, '')}")

    # 可用产品列表
    products = load_json('products.json')
    print(f"\n  📦 可用产品:")
    for p in products:
        tiers = [plan['tier'] for plan in p['plans'] if plan.get('tier')]
        print(f"    {p['product_key']: <18} {p['display_name']: <16} 档位: {', '.join(tiers[:4])}")

    print()


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='📦 导入导出模块 — CSV/JSON 导出、导入、模板生成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python data_exchange.py export-csv
  python data_exchange.py export-csv --output /tmp/subs.csv --english-header
  python data_exchange.py export-json
  python data_exchange.py import-csv subscriptions.csv --dry-run
  python data_exchange.py import-csv subscriptions.csv
  python data_exchange.py import-json backup.json --dry-run
  python data_exchange.py import-json backup.json --replace
  python data_exchange.py template --format csv
  python data_exchange.py template --format json""")

    sub = parser.add_subparsers(dest='command', help='可用命令')

    # export-csv
    p1 = sub.add_parser('export-csv', help='导出订阅为 CSV')
    p1.add_argument('--output', '-o', help='输出文件路径')
    p1.add_argument('--english-header', action='store_true', help='使用英文表头')

    # export-json
    p2 = sub.add_parser('export-json', help='导出订阅为 JSON')
    p2.add_argument('--output', '-o', help='输出文件路径')

    # import-csv
    p3 = sub.add_parser('import-csv', help='从 CSV 导入订阅')
    p3.add_argument('file', help='CSV 文件路径')
    p3.add_argument('--dry-run', action='store_true', help='预览模式，不写入数据')

    # import-json
    p4 = sub.add_parser('import-json', help='从 JSON 导入订阅')
    p4.add_argument('file', help='JSON 文件路径')
    p4.add_argument('--dry-run', action='store_true', help='预览模式，不写入数据')
    p4.add_argument('--replace', action='store_true', help='替换模式(默认合并)')

    # template
    p5 = sub.add_parser('template', help='生成导入模板')
    p5.add_argument('--format', choices=['csv', 'json'], default='csv', help='模板格式')
    p5.add_argument('--output-dir', help='输出目录')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {
        'export-csv': cmd_export_csv,
        'export-json': cmd_export_json,
        'import-csv': cmd_import_csv,
        'import-json': cmd_import_json,
        'template': cmd_template,
    }
    cmds.get(args.command, lambda a: parser.print_help())(args)


if __name__ == '__main__':
    main()
