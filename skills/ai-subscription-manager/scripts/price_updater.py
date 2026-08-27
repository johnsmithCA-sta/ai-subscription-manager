#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0 定价保鲜检测模块
检测产品库中定价信息的"新鲜度"，识别可能过时的定价，并支持引导更新（半自动）。

设计原则：先做"一键检测哪些产品定价可能过时"，不盲目自动抓取。
定价是否真的过时，需人工/Agent 核对官网后确认，再通过 update 命令标记更新。

命令：
  price_updater.py status                          # 定价新鲜度概览
  price_updater.py check [--category xxx] [--all]  # 列出可能过时的产品
  price_updater.py update --product <key> --touch  # 仅标记定价已核对更新
  price_updater.py update --product <key> --tier <tier> --price <num> [--currency] [--billing]  # 更新指定套餐价格
"""

import json
import argparse
import sys
import os
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.join(SCRIPT_DIR, '..')
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")

# 新鲜度阈值（天）
FRESH_DAYS = 90       # <90 天：新鲜
STALE_DAYS = 180      # >=180 天：过时风险高

CATEGORY_NAMES = {
    'ai_chat': 'AI 对话',
    'ai_code': 'AI 编程',
    'ai_image': 'AI 图像/视频',
    'ai_audio': 'AI 音频',
    'ai_writing': 'AI 写作/效率',
}


def load_products():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_products(products):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def parse_price_updated(p):
    """返回 (date 对象或 None, 是否缺失/解析失败)"""
    s = p.get("price_updated")
    if not s:
        return None, True
    try:
        return date.fromisoformat(s), False
    except ValueError:
        return None, True


def judge_level(dt, missing, today):
    """返回 ('high'/'mid'/'low', 说明)"""
    if missing:
        return "high", "未标注 price_updated"
    days = (today - dt).days
    if days >= STALE_DAYS:
        return "high", f"{days} 天未更新"
    if days >= FRESH_DAYS:
        return "mid", f"{days} 天未更新"
    return "low", f"{days} 天前更新"


def cmd_status(args):
    products = load_products()
    today = date.today()
    stats = {"low": 0, "mid": 0, "high": 0}
    missing = 0
    for p in products:
        dt, is_missing = parse_price_updated(p)
        if is_missing:
            level = "high"
            missing += 1
        else:
            days = (today - dt).days
            level = "high" if days >= STALE_DAYS else ("mid" if days >= FRESH_DAYS else "low")
        stats[level] += 1
    total = len(products)
    print("🗓️  产品库定价新鲜度概览")
    print(f"   产品总数: {total}")
    print(f"   🟢 新鲜(<{FRESH_DAYS}天): {stats['low']} 款")
    print(f"   🟡 待关注({FRESH_DAYS}-{STALE_DAYS}天): {stats['mid']} 款")
    print(f"   🔴 可能过时(>={STALE_DAYS}天或未标注): {stats['high']} 款")
    if missing:
        print(f"       其中未标注 price_updated: {missing} 款")
    print(f"   (当前日期 {today.isoformat()})")
    print()
    print("   建议: 运行 check 查看明细，用 update 标记核对后的定价")


def cmd_check(args):
    products = load_products()
    today = date.today()
    result = []
    for p in products:
        cat = p.get("category", "")
        if args.category and cat != args.category:
            continue
        dt, is_missing = parse_price_updated(p)
        level, desc = judge_level(dt, is_missing, today)
        if level == "high" or (level == "mid" and args.all):
            days = None if is_missing else (today - dt).days
            result.append((p, level, desc, days))
    order = {"high": 0, "mid": 1}
    result.sort(key=lambda x: (order[x[1]], -(x[3] if x[3] is not None else 99999)))

    if not result:
        print(f"✅ 未检测到{'待关注/过时' if args.all else '可能过时'}的产品，定价信息新鲜")
        return

    high_cnt = sum(1 for r in result if r[1] == "high")
    mid_cnt = sum(1 for r in result if r[1] == "mid")
    print(f"📋 定价健康检查（{'全部风险' if args.all else '高风险'}）")
    print(f"   🔴 高风险: {high_cnt}  |  🟡 待关注: {mid_cnt}  (共 {len(result)} 款)")
    print()
    for p, level, desc, days in result:
        icon = "🔴" if level == "high" else "🟡"
        cat_name = CATEGORY_NAMES.get(p.get("category", ""), p.get("category", "未知"))
        print(f"   {icon} {p.get('display_name', p.get('product_key'))} [{cat_name}]")
        print(f"       {desc} | product_key: {p.get('product_key')}")
        print(f"       上次更新: {p.get('price_updated') or '未标注'}")
    print()
    print("   💡 核对官网定价后，用 update 命令标记更新：")
    print("      price_updater.py update --product <product_key> --touch")
    print("      或更新具体套餐价格：--tier <tier> --price <num> [--currency USD/CNY] [--billing monthly/yearly/one-time]")


def cmd_update(args):
    products = load_products()
    p = None
    for prod in products:
        if prod["product_key"] == args.product:
            p = prod
            break
    if not p:
        print(f"❌ 未找到产品 '{args.product}'")
        sys.exit(1)

    today = date.today().isoformat()

    if args.tier and args.price is not None:
        plan = None
        for pl in p.get("plans", []):
            if pl["tier"] == args.tier:
                plan = pl
                break
        if not plan:
            print(f"❌ 产品 '{args.product}' 没有套餐 '{args.tier}'")
            print(f"   可用套餐: {', '.join(pl['tier'] for pl in p.get('plans', []))}")
            sys.exit(1)
        plan["price"] = args.price
        if args.currency:
            plan["currency"] = args.currency.upper()
        if args.billing:
            plan["billing_cycle"] = args.billing
        p["price_updated"] = today
        save_products(products)
        print(f"✅ 已更新 {p.get('display_name')} 套餐「{args.tier}」价格")
        print(f"   → {args.currency.upper() if args.currency else plan['currency']} {args.price} | billing: {args.billing or plan['billing_cycle']}")
        print(f"   price_updated → {today}")
    elif args.touch:
        p["price_updated"] = today
        save_products(products)
        print(f"✅ 已标记 {p.get('display_name')} 定价核对更新")
        print(f"   price_updated → {today}")
    else:
        print("❌ 请指定更新方式：")
        print("   仅标记:  --product <key> --touch")
        print("   更新价格: --product <key> --tier <tier> --price <num> [--currency] [--billing]")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="🗓️ 定价保鲜检测 — 检测产品库定价是否过时并引导更新",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
使用示例:
  python price_updater.py status
  python price_updater.py check
  python price_updater.py check --all --category ai_chat
  python price_updater.py update --product chatgpt --touch
  python price_updater.py update --product chatgpt --tier Plus --price 20 --currency USD --billing monthly
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    p_status = subparsers.add_parser("status", help="定价新鲜度概览")
    p_check = subparsers.add_parser("check", help="列出可能过时的产品")
    p_check.add_argument("--category", default="", help="限定分类(ai_chat/ai_code/ai_image/ai_audio/ai_writing)")
    p_check.add_argument("--all", action="store_true", help="同时列出待关注(中风险)产品")
    p_update = subparsers.add_parser("update", help="标记/更新产品定价")
    p_update.add_argument("--product", required=True, help="产品 product_key")
    p_update.add_argument("--touch", action="store_true", help="仅将 price_updated 标记为今天(已核对)")
    p_update.add_argument("--tier", default="", help="要更新的套餐档位")
    p_update.add_argument("--price", type=float, help="新价格")
    p_update.add_argument("--currency", default="", help="币种 (CNY/USD)")
    p_update.add_argument("--billing", default="", help="计费周期 (monthly/yearly/one-time)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    commands = {
        "status": cmd_status,
        "check": cmd_check,
        "update": cmd_update,
    }
    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
