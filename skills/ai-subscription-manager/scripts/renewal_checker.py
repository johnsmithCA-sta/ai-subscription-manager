#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
到期提醒检查脚本
支持 check / report / alert 三种模式，用于检查订阅到期状态并生成提醒。
数据文件位于上级目录：products.json, subscriptions.json, remind_config.json
"""

import json
import argparse
import sys
import os
from datetime import datetime, date

# ========== 路径配置 ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.dirname(SCRIPT_DIR)
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, "subscriptions.json")
REMIND_CONFIG_FILE = os.path.join(DATA_DIR, "remind_config.json")


# ========== 工具函数 ==========

def load_json(filepath):
    """读取 JSON 文件，文件不存在时返回 None"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_products():
    """加载产品模板库"""
    products = load_json(PRODUCTS_FILE)
    if products is None:
        print(f"❌ 错误：产品模板文件不存在：{os.path.basename(PRODUCTS_FILE)}")
        sys.exit(1)
    return products


def load_subscriptions():
    """加载订阅记录"""
    subs = load_json(SUBSCRIPTIONS_FILE)
    if subs is None:
        print(f"❌ 错误：订阅记录文件不存在：{os.path.basename(SUBSCRIPTIONS_FILE)}")
        sys.exit(1)
    return subs


def load_remind_config():
    """加载提醒配置，不存在时返回默认配置"""
    config = load_json(REMIND_CONFIG_FILE)
    if config is None:
        # 使用默认配置
        config = {
            "remind_days": [1, 3, 7, 14, 30],
            "default_check_days": [7, 30],
            "show_renewal_url": True,
            "show_cost_info": True,
            "alert_on_expired": True,
            "language": "zh-CN"
        }
    return config


def find_product(products, product_key):
    """根据 product_key 查找产品"""
    for p in products:
        if p["product_key"] == product_key:
            return p
    return None


def get_product_display(products, product_key):
    """获取产品显示名称（含套餐信息）"""
    p = find_product(products, product_key)
    return p["display_name"] if p else product_key


def get_renewal_url(products, product_key):
    """获取产品续费链接"""
    p = find_product(products, product_key)
    return p.get("renewal_url", "") if p else ""


def calc_days_remaining(next_billing_date_str):
    """计算距离下次扣费/到期的剩余天数，返回 int（负数表示已过期）"""
    if not next_billing_date_str:
        return None
    try:
        nb_date = datetime.strptime(next_billing_date_str, "%Y-%m-%d").date()
        return (nb_date - date.today()).days
    except ValueError:
        return None


def classify_subscriptions(subs, products):
    """
    将订阅分类为：
    - expired: 已过期（next_billing_date 已过且 status 仍为 active，或 status 为 expired）
    - urgent: 紧急（7天内到期）
    - warning: 预警（8-30天内到期）
    - normal: 正常（30天以上）
    - billing_soon: 即将扣费（next_billing_date 在7天内，status=active）
    """
    today = date.today()
    result = {
        "expired": [],       # 已过期
        "urgent": [],        # 紧急（0-7天）
        "warning": [],       # 预警（8-30天）
        "normal": [],        # 正常（>30天）
        "billing_soon": [],  # 即将扣费（0-7天内且 active）
    }

    for sub in subs:
        status = sub.get("status", "")
        # 跳过已取消的订阅
        if status == "cancelled":
            continue

        nb = sub.get("next_billing_date")
        delta = calc_days_remaining(nb)
        display = get_product_display(products, sub["product_key"])
        info = {**sub, "_display_name": display, "_days_remaining": delta}

        # 已过期判断：status 标记为 expired，或 active 但 next_billing_date 已过
        if status == "expired" or (status == "active" and delta is not None and delta < 0):
            result["expired"].append(info)
            continue

        # 无有效到期日期的归入 normal
        if delta is None:
            result["normal"].append(info)
            continue

        # 即将扣费（仅 active 且 0-7 天内）
        if status == "active" and 0 <= delta <= 7:
            result["billing_soon"].append(info)

        # 按到期时间分类
        if 0 <= delta <= 7:
            result["urgent"].append(info)
        elif 8 <= delta <= 30:
            result["warning"].append(info)
        else:
            result["normal"].append(info)

    return result


# ========== check 命令 ==========

def cmd_check(args):
    """检查订阅到期状态，按指定天数分组展示"""
    products = load_products()
    subs = load_subscriptions()
    config = load_remind_config()

    # 解析天数参数
    if args.days:
        check_days_list = []
        for part in args.days.split(","):
            part = part.strip()
            if part.isdigit():
                check_days_list.append(int(part))
        if not check_days_list:
            check_days_list = config.get("default_check_days", [7, 30])
    else:
        check_days_list = config.get("default_check_days", [7, 30])

    check_days_list = sorted(set(check_days_list))

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    # 只处理 active 的订阅
    active_subs = [s for s in subs if s.get("status") == "active"]

    print(f"📅 到期提醒检查 ({today_str})")
    print("━" * 40)

    any_found = False

    for days_threshold in check_days_list:
        # 筛选出到期日在 days_threshold 天内的订阅
        matching = []
        for sub in active_subs:
            nb = sub.get("next_billing_date")
            delta = calc_days_remaining(nb)
            if delta is not None and 0 <= delta <= days_threshold:
                display = get_product_display(products, sub["product_key"])
                matching.append({
                    "sub_id": sub["sub_id"],
                    "display_name": display,
                    "tier": sub.get("tier", ""),
                    "next_billing_date": nb,
                    "days_remaining": delta
                })

        # 按剩余天数排序
        matching.sort(key=lambda x: x["days_remaining"])

        if matching:
            any_found = True
            icon = "⚠️ " if days_threshold <= 7 else "⏰"
            print(f"\n{icon}  {days_threshold}天内到期 ({len(matching)}条):")
            for item in matching:
                print(f"  {item['sub_id']} | {item['display_name']} {item['tier']} | "
                      f"到期: {item['next_billing_date']} | 剩余{item['days_remaining']}天")
        else:
            print(f"\n✅ {days_threshold}天内无到期订阅")

    # 检查已过期但 status 未更新的
    expired_detected = []
    for sub in active_subs:
        nb = sub.get("next_billing_date")
        delta = calc_days_remaining(nb)
        if delta is not None and delta < 0:
            display = get_product_display(products, sub["product_key"])
            expired_detected.append({
                "sub_id": sub["sub_id"],
                "display_name": display,
                "next_billing_date": nb,
                "days_overdue": abs(delta)
            })

    if expired_detected and config.get("alert_on_expired", True):
        print(f"\n🚨 已过期但状态未更新 ({len(expired_detected)}条):")
        for item in expired_detected:
            print(f"  {item['sub_id']} | {item['display_name']} | "
                  f"到期: {item['next_billing_date']} | 已过期{item['days_overdue']}天")

    if not any_found and not expired_detected:
        print("\n✅ 所有订阅状态正常，无即将到期的订阅")

    print()


# ========== report 命令 ==========

def cmd_report(args):
    """生成结构化的到期报告"""
    products = load_products()
    subs = load_subscriptions()

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    classified = classify_subscriptions(subs, products)

    if args.format == "json":
        # JSON 格式输出
        report = {
            "report_date": today_str,
            "summary": {
                "total_active": len([s for s in subs if s.get("status") == "active"]),
                "expired": len(classified["expired"]),
                "urgent_7days": len(classified["urgent"]),
                "warning_30days": len(classified["warning"]),
                "normal": len(classified["normal"]),
                "billing_soon_7days": len(classified["billing_soon"])
            },
            "expired": [_clean_sub(s) for s in classified["expired"]],
            "urgent": [_clean_sub(s) for s in classified["urgent"]],
            "warning": [_clean_sub(s) for s in classified["warning"]],
            "normal": [_clean_sub(s) for s in classified["normal"]],
            "billing_soon": [_clean_sub(s) for s in classified["billing_soon"]]
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # 纯文本格式输出
    print(f"╔══════════════════════════════════════════════╗")
    print(f"║        📋 订阅到期报告 ({today_str})          ║")
    print(f"╚══════════════════════════════════════════════╝")
    print()

    # 已过期
    expired = classified["expired"]
    if expired:
        print(f"🚨 已过期 ({len(expired)}条):")
        for s in expired:
            nb = s.get("next_billing_date", "—")
            delta = s["_days_remaining"]
            overdue = abs(delta) if delta is not None else "?"
            print(f"  ⛔ {s['sub_id']} | {s['_display_name']} {s.get('tier', '')} | "
                  f"到期: {nb} | 已过期{overdue}天")
    else:
        print("✅ 无已过期订阅")
    print()

    # 紧急（7天内）
    urgent = classified["urgent"]
    if urgent:
        print(f"🔴 紧急 - 7天内到期 ({len(urgent)}条):")
        for s in sorted(urgent, key=lambda x: x["_days_remaining"]):
            nb = s.get("next_billing_date", "—")
            print(f"  ⚠️  {s['sub_id']} | {s['_display_name']} {s.get('tier', '')} | "
                  f"到期: {nb} | 剩余{s['_days_remaining']}天")
    else:
        print("✅ 无紧急到期订阅")
    print()

    # 预警（8-30天）
    warning = classified["warning"]
    if warning:
        print(f"🟡 预警 - 8~30天内到期 ({len(warning)}条):")
        for s in sorted(warning, key=lambda x: x["_days_remaining"]):
            nb = s.get("next_billing_date", "—")
            print(f"  ⏰ {s['sub_id']} | {s['_display_name']} {s.get('tier', '')} | "
                  f"到期: {nb} | 剩余{s['_days_remaining']}天")
    else:
        print("✅ 无预警订阅")
    print()

    # 即将扣费
    billing = classified["billing_soon"]
    if billing:
        print(f"💳 即将扣费 - 7天内 ({len(billing)}条):")
        for s in sorted(billing, key=lambda x: x["_days_remaining"]):
            nb = s.get("next_billing_date", "—")
            currency = s.get("currency", "USD")
            price = s.get("price_paid", 0)
            label = "今天" if s["_days_remaining"] == 0 else f"{s['_days_remaining']}天后"
            print(f"  💰 {s['sub_id']} | {s['_display_name']} {s.get('tier', '')} | "
                  f"{currency} {price:.2f} | 扣费: {nb} ({label})")
    else:
        print("✅ 无即将扣费订阅")
    print()

    # 正常
    normal = classified["normal"]
    if normal:
        print(f"🟢 正常 - 30天以上 ({len(normal)}条):")
        for s in sorted(normal, key=lambda x: x["_days_remaining"] if x["_days_remaining"] is not None else 9999):
            nb = s.get("next_billing_date", "—")
            delta = s["_days_remaining"]
            delta_str = f"剩余{delta}天" if delta is not None else "—"
            print(f"  ✅ {s['sub_id']} | {s['_display_name']} {s.get('tier', '')} | "
                  f"到期: {nb} | {delta_str}")
    print()


def _clean_sub(sub):
    """移除内部辅助字段，返回干净的字典"""
    return {k: v for k, v in sub.items() if not k.startswith("_")}


# ========== alert 命令 ==========

def cmd_alert(args):
    """生成用户友好的提醒消息"""
    products = load_products()
    subs = load_subscriptions()
    config = load_remind_config()

    today = date.today()
    active_subs = [s for s in subs if s.get("status") == "active"]

    # 收集30天内到期的订阅
    expiring = []
    for sub in active_subs:
        nb = sub.get("next_billing_date")
        delta = calc_days_remaining(nb)
        if delta is not None and 0 <= delta <= 30:
            display = get_product_display(products, sub["product_key"])
            renewal_url = get_renewal_url(products, sub["product_key"])
            expiring.append({
                "display_name": display,
                "tier": sub.get("tier", ""),
                "next_billing_date": nb,
                "days_remaining": delta,
                "price_paid": sub.get("price_paid", 0),
                "currency": sub.get("currency", "USD"),
                "renewal_url": renewal_url,
                "auto_renew": sub.get("auto_renew", True)
            })

    # 按剩余天数排序
    expiring.sort(key=lambda x: x["days_remaining"])

    # 检查已过期但未更新状态的
    expired_detected = []
    if config.get("alert_on_expired", True):
        for sub in active_subs:
            nb = sub.get("next_billing_date")
            delta = calc_days_remaining(nb)
            if delta is not None and delta < 0:
                display = get_product_display(products, sub["product_key"])
                expired_detected.append({
                    "display_name": display,
                    "tier": sub.get("tier", ""),
                    "next_billing_date": nb,
                    "days_overdue": abs(delta)
                })

    # 生成消息
    print("🔔 订阅到期提醒")
    print()

    has_content = False

    # 已过期提醒
    if expired_detected:
        has_content = True
        print(f"⛔ 你有 {len(expired_detected)} 个订阅已过期：")
        print()
        for i, item in enumerate(expired_detected, 1):
            print(f"{i}. {item['display_name']} {item['tier']} - 已过期{item['days_overdue']}天 ({item['next_billing_date']})")
        print()

    # 即将到期提醒
    if expiring:
        has_content = True
        print(f"你有 {len(expiring)} 个订阅将在未来30天内到期：")
        print()
        for i, item in enumerate(expiring, 1):
            nb = item["next_billing_date"]
            delta = item["days_remaining"]
            currency = item["currency"]
            price = item["price_paid"]

            # 天数描述
            if delta == 0:
                day_label = "今天到期"
            elif delta == 1:
                day_label = "明天到期"
            else:
                day_label = f"{delta}天后到期"

            print(f"{i}. {item['display_name']} {item['tier']} - {day_label} ({nb})")

            # 费用信息
            if config.get("show_cost_info", True):
                billing_cycle = "月"  # 默认
                print(f"   💰 {currency} {price:.2f}/{billing_cycle}", end="")

                # 续费链接
                if config.get("show_renewal_url", True) and item["renewal_url"]:
                    print(f" | 续费链接: {item['renewal_url']}")
                else:
                    print()
            else:
                # 即使不显示费用，有链接也显示
                if config.get("show_renewal_url", True) and item["renewal_url"]:
                    print(f"   🔗 续费链接: {item['renewal_url']}")

        print()

    if not has_content:
        print("✅ 太棒了！你的所有订阅状态良好，暂无即将到期的订阅。")
        print()

    # 温馨提示
    auto_renew_items = [e for e in expiring if e.get("auto_renew")]
    if auto_renew_items:
        print("💡 如需取消或更换套餐，请提前操作避免自动扣费。")
    elif expiring:
        print("💡 部分订阅已关闭自动续费，到期后将停止服务，请及时续费。")

    print()


# ========== 主入口 ==========

def main():
    parser = argparse.ArgumentParser(
        description="订阅到期提醒检查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s check                       # 使用默认天数(7,30)检查
  %(prog)s check --days 7              # 检查7天内到期的
  %(prog)s check --days 30             # 检查30天内到期的
  %(prog)s check --days 7,30           # 同时显示7天和30天的
  %(prog)s report --format text        # 纯文本报告
  %(prog)s report --format json        # JSON格式报告
  %(prog)s alert                       # 生成用户友好的提醒消息
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # check 命令
    check_parser = subparsers.add_parser("check", help="检查订阅到期状态")
    check_parser.add_argument("--days", default=None,
                              help="检查天数范围，逗号分隔（默认读取 remind_config.json，无配置则 7,30）")

    # report 命令
    report_parser = subparsers.add_parser("report", help="生成到期报告")
    report_parser.add_argument("--format", choices=["text", "json"], default="text",
                               help="输出格式（默认 text）")

    # alert 命令
    subparsers.add_parser("alert", help="生成用户友好的提醒消息")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 路由到对应命令
    commands = {
        "check": cmd_check,
        "report": cmd_report,
        "alert": cmd_alert,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
