#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订阅记录管理脚本
支持增删改查、汇总统计等功能
数据文件位于上级目录：products.json, subscriptions.json
"""

import json
import argparse
import sys
import os
import uuid
from datetime import datetime, timedelta

# ========== 路径配置 ==========
# 脚本在 scripts/ 目录，数据文件在上级目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.dirname(SCRIPT_DIR)
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, "subscriptions.json")


# ========== 工具函数 ==========

def load_json(filepath):
    """读取 JSON 文件，文件不存在时返回 None"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath, data):
    """写入 JSON 文件，UTF-8 编码"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_products():
    """加载产品模板库"""
    products = load_json(PRODUCTS_FILE)
    if products is None:
        print(f"❌ 错误：产品模板文件不存在：{os.path.basename(PRODUCTS_FILE)}")
        sys.exit(1)
    return products


def load_subscriptions():
    """加载订阅记录，文件不存在时自动创建空数组"""
    subs = load_json(SUBSCRIPTIONS_FILE)
    if subs is None:
        subs = []
        save_json(SUBSCRIPTIONS_FILE, subs)
    return subs


def save_subscriptions(subs):
    """保存订阅记录"""
    save_json(SUBSCRIPTIONS_FILE, subs)


def find_product(products, product_key):
    """根据 product_key 查找产品"""
    for p in products:
        if p["product_key"] == product_key:
            return p
    return None


def find_plan(product, tier):
    """在产品的 plans 中查找指定 tier"""
    for plan in product.get("plans", []):
        if plan["tier"] == tier:
            return plan
    return None


def generate_sub_id(subs):
    """
    生成新的 sub_id，格式：sub_<8位uuid>
    使用 UUID4 避免并发冲突
    """
    return f"sub_{uuid.uuid4().hex[:8]}"


def calculate_next_billing(start_date_str, billing_cycle):
    """根据开始日期和计费周期计算下次扣费日期"""
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    if billing_cycle == "monthly":
        # 月份加1
        month = start.month + 1
        year = start.year
        if month > 12:
            month = 1
            year += 1
        # 处理月末日期问题
        import calendar
        max_day = calendar.monthrange(year, month)[1]
        day = min(start.day, max_day)
        next_date = start.replace(year=year, month=month, day=day)
    elif billing_cycle == "yearly":
        next_date = start.replace(year=start.year + 1)
    elif billing_cycle == "one-time":
        return None  # 一次性付款没有下次扣费
    else:
        next_date = start + timedelta(days=30)  # 默认30天
    return next_date.strftime("%Y-%m-%d")


def now_iso():
    """返回当前 ISO8601 格式时间"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")


def get_product_display(products, product_key):
    """获取产品显示名称"""
    p = find_product(products, product_key)
    return p["display_name"] if p else product_key


def get_product_category(products, product_key):
    """获取产品分类"""
    p = find_product(products, product_key)
    return p.get("category", "") if p else ""


# ========== 命令实现 ==========

def _load_categories():
    """加载分类定义，返回有效 category 集合"""
    cat_file = os.path.join(DATA_DIR, "categories.json")
    data = load_json(cat_file)
    if data and "categories" in data:
        return set(data["categories"].keys())
    return {"ai_chat", "ai_code", "ai_image", "ai_audio", "ai_writing"}


def _build_product_from_args(args):
    """从命令行参数构建产品对象"""
    plans = []
    for plan_str in (args.plans or []):
        parts = [p.strip() for p in plan_str.split("|")]
        if len(parts) < 4 or not parts[0] or not parts[1]:
            print(f"❌ 错误：套餐参数格式应为 tier|price|currency|billing[|annual_price]，实际：{plan_str}")
            return None
        try:
            plan = {
                "tier": parts[0],
                "price": float(parts[1]),
                "currency": parts[2].upper(),
                "billing_cycle": parts[3],
                "annual_price": float(parts[4]) if len(parts) > 4 and parts[4] else None,
                "has_annual_discount": bool(len(parts) > 4 and parts[4]),
                "features": [],
            }
            plans.append(plan)
        except ValueError:
            print(f"❌ 错误：套餐价格解析失败：{plan_str}")
            return None

    product = {
        "product_key": args.product_key.strip(),
        "display_name": args.display_name.strip(),
        "vendor": args.vendor or "",
        "category": args.category or "",
        "subcategory": args.subcategory or "",
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
        "plans": plans,
        "renewal_url": args.renewal_url or "",
        "cancel_guide": args.cancel_guide or "",
        "description": args.description or "",
        "website": args.website or "",
        "price_updated": datetime.now().strftime("%Y-%m-%d"),
    }
    return product


def _interactive_add_product(products):
    """交互式询问用户输入产品信息"""
    try:
        print("📝 交互式添加自定义产品（Ctrl+C 取消）")
        product_key = input("产品标识 (product_key，如 my_product): ").strip()
        if not product_key:
            print("❌ product_key 不能为空")
            return None
        if find_product(products, product_key):
            print(f"❌ 产品 '{product_key}' 已存在")
            return None
        display_name = input("产品名称 (display_name): ").strip()
        if not display_name:
            print("❌ display_name 不能为空")
            return None
        vendor = input("厂商 (vendor): ").strip()
        category = input("分类 (category，ai_chat/ai_code/ai_image/ai_audio/ai_writing): ").strip()
        subcategory = input("子分类 (subcategory): ").strip()
        tags = input("标签 (tags，逗号分隔): ").strip()
        website = input("官网 (website): ").strip()
        description = input("简介 (description): ").strip()

        plans = []
        print("\n📦 添加套餐（套餐名留空结束）：")
        while True:
            tier = input("  套餐名 (tier，留空结束): ").strip()
            if not tier:
                break
            try:
                price = float(input("  价格: ").strip())
            except ValueError:
                print("  ❌ 价格格式错误，跳过该套餐")
                continue
            currency = input("  货币 (CNY/USD): ").strip().upper() or "CNY"
            billing = input("  计费周期 (monthly/yearly/one-time): ").strip()
            if billing not in ("monthly", "yearly", "one-time"):
                billing = "monthly"
            annual_price = input("  年付价格 (annual_price，可留空): ").strip()
            plans.append({
                "tier": tier,
                "price": price,
                "currency": currency,
                "billing_cycle": billing,
                "annual_price": float(annual_price) if annual_price else None,
                "has_annual_discount": bool(annual_price),
                "features": [],
            })

        return {
            "product_key": product_key,
            "display_name": display_name,
            "vendor": vendor,
            "category": category,
            "subcategory": subcategory,
            "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
            "plans": plans,
            "renewal_url": "",
            "cancel_guide": "",
            "description": description,
            "website": website,
            "price_updated": datetime.now().strftime("%Y-%m-%d"),
        }
    except EOFError:
        print("\n❌ 检测到无交互终端。请改用参数模式：")
        print("   subscription_manager.py add-product --product-key xxx --display-name xxx --plans \"tier|price|currency|billing\"")
        return None


def cmd_add_product(args):
    """添加自定义产品到产品库（交互式或参数模式）"""
    products = load_products()

    if args.product_key:
        product = _build_product_from_args(args)
    else:
        product = _interactive_add_product(products)

    if product is None:
        return

    if not product.get("product_key") or not product.get("display_name"):
        print("❌ 错误：product_key 和 display_name 为必填项")
        sys.exit(1)

    if find_product(products, product["product_key"]):
        print(f"❌ 错误：产品 '{product['product_key']}' 已存在")
        sys.exit(1)

    cat = product.get("category", "")
    if cat and cat not in _load_categories():
        print(f"❌ 错误：无效分类 '{cat}'，可选：{', '.join(sorted(_load_categories()))}")
        sys.exit(1)

    products.append(product)
    save_json(PRODUCTS_FILE, products)

    print(f"✅ 自定义产品已添加：{product['display_name']} ({product['product_key']})")
    print(f"   分类: {product.get('category', '未分类')} / {product.get('subcategory', '')}")
    print(f"   套餐数: {len(product.get('plans', []))}")
    print(f"   产品总数: {len(products)}")


def cmd_add(args):
    """添加订阅"""
    products = load_products()
    subs = load_subscriptions()

    # 校验 product_key
    product = find_product(products, args.product)
    if not product:
        available = [p["product_key"] for p in products]
        print(f"❌ 错误：产品 '{args.product}' 不存在")
        print(f"   可用产品：{', '.join(available)}")
        sys.exit(1)

    # 校验 tier
    plan = find_plan(product, args.tier)
    if not plan:
        available_tiers = [p["tier"] for p in product.get("plans", [])]
        print(f"❌ 错误：产品 '{args.product}' 不存在套餐 '{args.tier}'")
        print(f"   可用套餐：{', '.join(available_tiers)}")
        sys.exit(1)

    # 生成 sub_id
    sub_id = generate_sub_id(subs)

    # 计算下次扣费日期
    next_billing = calculate_next_billing(args.start, args.billing)

    # 构造记录
    record = {
        "sub_id": sub_id,
        "product_key": args.product,
        "tier": args.tier,
        "status": "active",
        "start_date": args.start,
        "next_billing_date": next_billing,
        "billing_cycle": args.billing,
        "price_paid": args.price,
        "currency": args.currency.upper(),
        "payment_method": args.payment or "",
        "auto_renew": args.auto_renew if args.auto_renew is not None else True,
        "notes": args.notes or "",
        "created_at": now_iso(),
        "updated_at": now_iso()
    }

    subs.append(record)
    save_subscriptions(subs)

    print(f"✅ 订阅已添加")
    print(f"   sub_id: {sub_id}")
    print(f"   产品: {product['display_name']}")
    print(f"   套餐: {args.tier}")
    print(f"   价格: {args.currency.upper()} {args.price}")
    if next_billing:
        print(f"   下次扣费: {next_billing}")


def cmd_list(args):
    """列出订阅"""
    products = load_products()
    subs = load_subscriptions()

    if not subs:
        print("📭 暂无订阅记录")
        return

    # 按状态筛选
    if args.status:
        subs = [s for s in subs if s.get("status") == args.status]
        if not subs:
            print(f"📭 没有状态为 '{args.status}' 的订阅")
            return

    # 按分类筛选
    if args.category:
        filtered = []
        for s in subs:
            cat = get_product_category(products, s["product_key"])
            if cat == args.category:
                filtered.append(s)
        subs = filtered
        if not subs:
            print(f"📭 没有分类为 '{args.category}' 的订阅")
            return

    # JSON 格式输出
    if args.format == "json":
        print(json.dumps(subs, ensure_ascii=False, indent=2))
        return

    # Table 格式输出
    print_table(subs, products)


def print_table(subs, products):
    """美观的表格输出"""
    # 表头
    headers = ["sub_id", "产品名", "套餐", "状态", "月费", "下次扣费", "到期倒计时"]

    # 准备行数据
    rows = []
    today = datetime.now().date()
    for s in subs:
        display_name = get_product_display(products, s["product_key"])
        tier = s.get("tier", "")
        status = s.get("status", "")

        # 状态标签
        status_map = {"active": "✅ active", "cancelled": "❌ cancelled", "expired": "⏰ expired"}
        status_label = status_map.get(status, status)

        # 月费显示
        currency = s.get("currency", "USD")
        price = s.get("price_paid", 0)
        billing = s.get("billing_cycle", "")
        if billing == "monthly":
            price_label = f"{currency} {price:.2f}/月"
        elif billing == "yearly":
            monthly = price / 12
            price_label = f"{currency} {monthly:.2f}/月(年付)"
        else:
            price_label = f"{currency} {price:.2f}"

        # 下次扣费
        next_billing = s.get("next_billing_date", "") or "—"

        # 到期倒计时（基于下次扣费日期）
        countdown = "—"
        if next_billing != "—" and status == "active":
            try:
                nb_date = datetime.strptime(next_billing, "%Y-%m-%d").date()
                delta = (nb_date - today).days
                if delta < 0:
                    countdown = "已过期"
                elif delta == 0:
                    countdown = "今天"
                elif delta == 1:
                    countdown = "明天"
                else:
                    countdown = f"{delta}天"
            except ValueError:
                pass

        rows.append([s["sub_id"], display_name, tier, status_label, price_label, next_billing, countdown])

    # 计算列宽（考虑中文字符宽度）
    def display_width(s):
        """计算字符串的显示宽度（中文占2个字符宽度）"""
        w = 0
        for ch in s:
            if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
                w += 2
            else:
                w += 1
        return w

    def pad_to_width(s, target_width):
        """将字符串填充到目标显示宽度"""
        current = display_width(s)
        return s + ' ' * (target_width - current)

    # 所有列数据（含表头）
    all_data = [headers] + rows
    col_count = len(headers)
    col_widths = []
    for col_idx in range(col_count):
        max_w = 0
        for row in all_data:
            w = display_width(str(row[col_idx]))
            max_w = max(max_w, w)
        col_widths.append(max_w)

    # 打印分隔线
    def print_separator():
        parts = ["+" + "-" * (w + 2) for w in col_widths]
        print("".join(parts) + "+")

    # 打印行
    def print_row(row):
        cells = []
        for col_idx, cell in enumerate(row):
            cells.append("| " + pad_to_width(str(cell), col_widths[col_idx]) + " ")
        print("".join(cells) + "|")

    # 输出表格
    print_separator()
    print_row(headers)
    print_separator()
    for row in rows:
        print_row(row)
    print_separator()
    print(f"共 {len(rows)} 条记录")


def cmd_get(args):
    """查看订阅详情"""
    products = load_products()
    subs = load_subscriptions()

    sub = None
    for s in subs:
        if s["sub_id"] == args.sub_id:
            sub = s
            break

    if not sub:
        print(f"❌ 错误：未找到订阅 '{args.sub_id}'")
        sys.exit(1)

    display_name = get_product_display(products, sub["product_key"])
    category = get_product_category(products, sub["product_key"])

    print(f"═══ 订阅详情：{sub['sub_id']} ═══")
    print(f"  产品: {display_name} ({sub['product_key']})")
    print(f"  分类: {category}")
    print(f"  套餐: {sub['tier']}")
    print(f"  状态: {sub['status']}")
    print(f"  开始日期: {sub['start_date']}")
    print(f"  下次扣费: {sub.get('next_billing_date', '—')}")
    print(f"  计费周期: {sub['billing_cycle']}")
    print(f"  支付价格: {sub['currency']} {sub['price_paid']:.2f}")
    print(f"  支付方式: {sub.get('payment_method', '—')}")
    print(f"  自动续费: {'是' if sub.get('auto_renew') else '否'}")
    print(f"  备注: {sub.get('notes', '') or '—'}")
    print(f"  创建时间: {sub['created_at']}")
    print(f"  更新时间: {sub['updated_at']}")


def cmd_update(args):
    """修改订阅"""
    subs = load_subscriptions()

    # 查找目标订阅
    target_idx = None
    for i, s in enumerate(subs):
        if s["sub_id"] == args.sub_id:
            target_idx = i
            break

    if target_idx is None:
        print(f"❌ 错误：未找到订阅 '{args.sub_id}'")
        sys.exit(1)

    sub = subs[target_idx]
    updated_fields = []

    # 更新传入的字段
    if args.tier is not None:
        sub["tier"] = args.tier
        updated_fields.append("tier")

    if args.price is not None:
        sub["price_paid"] = args.price
        updated_fields.append("price_paid")

    if args.currency is not None:
        sub["currency"] = args.currency.upper()
        updated_fields.append("currency")

    if args.billing is not None:
        sub["billing_cycle"] = args.billing
        # 重新计算下次扣费日期
        next_billing = calculate_next_billing(sub["start_date"], args.billing)
        if next_billing:
            sub["next_billing_date"] = next_billing
        updated_fields.append("billing_cycle")

    if args.auto_renew is not None:
        sub["auto_renew"] = args.auto_renew
        updated_fields.append("auto_renew")

    if args.status is not None:
        sub["status"] = args.status
        updated_fields.append("status")

    if args.notes is not None:
        sub["notes"] = args.notes
        updated_fields.append("notes")

    if args.payment is not None:
        sub["payment_method"] = args.payment
        updated_fields.append("payment_method")

    if not updated_fields:
        print("⚠️ 未指定要更新的字段")
        return

    # 更新时间戳
    sub["updated_at"] = now_iso()
    subs[target_idx] = sub
    save_subscriptions(subs)

    print(f"✅ 订阅 {args.sub_id} 已更新")
    print(f"   更新字段: {', '.join(updated_fields)}")


def cmd_delete(args):
    """删除订阅"""
    if not args.confirm:
        print(f"⚠️ 删除操作需要确认")
        print(f"   请添加 --confirm 参数确认删除订阅 '{args.sub_id}'")
        sys.exit(1)

    subs = load_subscriptions()

    new_subs = [s for s in subs if s["sub_id"] != args.sub_id]

    if len(new_subs) == len(subs):
        print(f"❌ 错误：未找到订阅 '{args.sub_id}'")
        sys.exit(1)

    save_subscriptions(new_subs)
    print(f"✅ 订阅 {args.sub_id} 已删除")


def cmd_summary(args):
    """汇总统计"""
    products = load_products()
    subs = load_subscriptions()

    if not subs:
        print("📭 暂无订阅记录，无法生成统计")
        return

    today = datetime.now().date()

    # 基本统计
    total = len(subs)
    active_subs = [s for s in subs if s.get("status") == "active"]
    active_count = len(active_subs)

    # 月度支出（分币种）
    monthly_usd = 0.0
    monthly_cny = 0.0
    for s in active_subs:
        price = s.get("price_paid", 0)
        billing = s.get("billing_cycle", "")
        currency = s.get("currency", "USD")
        if billing == "monthly":
            monthly_amount = price
        elif billing == "yearly":
            monthly_amount = price / 12
        else:
            monthly_amount = 0  # one-time 不计入月费
        if currency == "USD":
            monthly_usd += monthly_amount
        elif currency == "CNY":
            monthly_cny += monthly_amount

    # 年度预估
    yearly_usd = monthly_usd * 12
    yearly_cny = monthly_cny * 12

    # 未来 7 天/30 天到期
    expiring_7 = []
    expiring_30 = []
    for s in active_subs:
        nb = s.get("next_billing_date")
        if not nb:
            continue
        try:
            nb_date = datetime.strptime(nb, "%Y-%m-%d").date()
            delta = (nb_date - today).days
            if 0 <= delta <= 7:
                expiring_7.append((s, delta))
            if 0 <= delta <= 30:
                expiring_30.append((s, delta))
        except ValueError:
            pass

    # 按分类统计支出
    category_spending = {}
    for s in active_subs:
        cat = get_product_category(products, s["product_key"])
        if not cat:
            cat = "未分类"
        display_name = get_product_display(products, s["product_key"])
        price = s.get("price_paid", 0)
        billing = s.get("billing_cycle", "")
        currency = s.get("currency", "USD")
        if billing == "monthly":
            monthly_amount = price
        elif billing == "yearly":
            monthly_amount = price / 12
        else:
            monthly_amount = 0

        if cat not in category_spending:
            category_spending[cat] = {"USD": 0.0, "CNY": 0.0}
        if currency == "USD":
            category_spending[cat]["USD"] += monthly_amount
        elif currency == "CNY":
            category_spending[cat]["CNY"] += monthly_amount

    # ===== 输出统计报告 =====
    print("╔══════════════════════════════════════╗")
    print("║        📊 订阅汇总统计               ║")
    print("╚══════════════════════════════════════╝")
    print()

    print(f"  📋 总订阅数: {total}")
    print(f"  ✅ 活跃订阅: {active_count}")
    print(f"  ❌ 已取消: {sum(1 for s in subs if s.get('status') == 'cancelled')}")
    print(f"  ⏰ 已过期: {sum(1 for s in subs if s.get('status') == 'expired')}")
    print()

    print("  💰 月度支出:")
    if monthly_usd > 0:
        print(f"     USD: ${monthly_usd:.2f}/月")
    if monthly_cny > 0:
        print(f"     CNY: ¥{monthly_cny:.2f}/月")
    if monthly_usd == 0 and monthly_cny == 0:
        print("     无活跃月费支出")
    print()

    print("  📅 年度预估支出:")
    if yearly_usd > 0:
        print(f"     USD: ${yearly_usd:.2f}/年")
    if yearly_cny > 0:
        print(f"     CNY: ¥{yearly_cny:.2f}/年")
    if yearly_usd == 0 and yearly_cny == 0:
        print("     无活跃年度支出")
    print()

    # 未来 7 天到期
    print(f"  ⏰ 未来 7 天到期扣费: {len(expiring_7)} 条")
    if expiring_7:
        for s, delta in sorted(expiring_7, key=lambda x: x[1]):
            name = get_product_display(products, s["product_key"])
            nb = s.get("next_billing_date", "")
            label = "今天" if delta == 0 else f"{delta}天后"
            print(f"     - {name} ({s['tier']}): {nb} ({label})")
    print()

    # 未来 30 天到期
    print(f"  📆 未来 30 天到期扣费: {len(expiring_30)} 条")
    if expiring_30:
        for s, delta in sorted(expiring_30, key=lambda x: x[1]):
            name = get_product_display(products, s["product_key"])
            nb = s.get("next_billing_date", "")
            label = "今天" if delta == 0 else f"{delta}天后"
            print(f"     - {name} ({s['tier']}): {nb} ({label})")
    print()

    # 按分类统计
    print("  📊 按分类统计月度支出:")
    if category_spending:
        for cat, amounts in sorted(category_spending.items()):
            parts = []
            if amounts["USD"] > 0:
                parts.append(f"${amounts['USD']:.2f}")
            if amounts["CNY"] > 0:
                parts.append(f"¥{amounts['CNY']:.2f}")
            total_monthly = amounts["USD"] + amounts["CNY"]
            print(f"     {cat}: {' + '.join(parts) if parts else '—'}")
    else:
        print("     无活跃分类支出")

    print()


# ========== 主入口 ==========

def main():
    parser = argparse.ArgumentParser(
        description="订阅记录管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s list --format table
  %(prog)s add --product chatgpt --tier Plus --start 2026-08-15 --billing monthly --price 20 --currency USD --payment "信用卡" --auto-renew true
  %(prog)s get sub_a1b2c3d4
  %(prog)s update sub_a1b2c3d4 --tier Pro --price 100
  %(prog)s delete sub_a1b2c3d4 --confirm
  %(prog)s summary
  %(prog)s add-product --product-key myapp --display-name "我的应用" --category ai_chat --plans "Pro|39|CNY|monthly"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加订阅")
    add_parser.add_argument("--product", required=True, help="产品标识（关联 products.json）")
    add_parser.add_argument("--tier", required=True, help="套餐档位")
    add_parser.add_argument("--start", required=True, help="开始日期 (YYYY-MM-DD)")
    add_parser.add_argument("--billing", required=True, choices=["monthly", "yearly", "one-time"], help="计费周期")
    add_parser.add_argument("--price", required=True, type=float, help="支付价格")
    add_parser.add_argument("--currency", required=True, help="货币 (CNY/USD)")
    add_parser.add_argument("--payment", default="", help="支付方式")
    add_parser.add_argument("--auto-renew", type=str, default="true", help="是否自动续费 (true/false)")
    add_parser.add_argument("--notes", default="", help="备注")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出订阅")
    list_parser.add_argument("--status", choices=["active", "cancelled", "expired"], help="按状态筛选")
    list_parser.add_argument("--category", help="按分类筛选")
    list_parser.add_argument("--format", choices=["json", "table"], default="json", help="输出格式")

    # get 命令
    get_parser = subparsers.add_parser("get", help="查看订阅详情")
    get_parser.add_argument("sub_id", help="订阅ID")

    # update 命令
    update_parser = subparsers.add_parser("update", help="修改订阅")
    update_parser.add_argument("sub_id", help="订阅ID")
    update_parser.add_argument("--tier", help="套餐档位")
    update_parser.add_argument("--price", type=float, help="支付价格")
    update_parser.add_argument("--currency", help="货币 (CNY/USD)")
    update_parser.add_argument("--billing", choices=["monthly", "yearly", "one-time"], help="计费周期")
    update_parser.add_argument("--auto-renew", type=str, help="是否自动续费 (true/false)")
    update_parser.add_argument("--status", choices=["active", "cancelled", "expired"], help="状态")
    update_parser.add_argument("--notes", help="备注")
    update_parser.add_argument("--payment", help="支付方式")

    # delete 命令
    delete_parser = subparsers.add_parser("delete", help="删除订阅")
    delete_parser.add_argument("sub_id", help="订阅ID")
    delete_parser.add_argument("--confirm", action="store_true", help="确认删除")

    # summary 命令
    subparsers.add_parser("summary", help="汇总统计")

    # add-product 命令（交互式/参数式添加自定义产品）
    ap_parser = subparsers.add_parser("add-product", help="添加自定义产品到产品库")
    ap_parser.add_argument("--product-key", default="", help="产品标识（必填）")
    ap_parser.add_argument("--display-name", default="", help="产品名称（必填）")
    ap_parser.add_argument("--vendor", default="", help="厂商")
    ap_parser.add_argument("--category", default="", help="分类 (ai_chat/ai_code/ai_image/ai_audio/ai_writing)")
    ap_parser.add_argument("--subcategory", default="", help="子分类")
    ap_parser.add_argument("--tags", default="", help="标签，逗号分隔")
    ap_parser.add_argument("--website", default="", help="官网")
    ap_parser.add_argument("--description", default="", help="简介")
    ap_parser.add_argument("--renewal-url", default="", help="续费链接")
    ap_parser.add_argument("--cancel-guide", default="", help="取消订阅指引")
    ap_parser.add_argument("--plans", action="append", default=[], help="套餐，格式 tier|price|currency|billing[|annual_price]，可多次")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 处理 boolean 参数转换
    if hasattr(args, "auto_renew") and args.auto_renew is not None:
        if isinstance(args.auto_renew, str):
            args.auto_renew = args.auto_renew.lower() in ("true", "1", "yes")

    # 路由到对应命令
    commands = {
        "add-product": cmd_add_product,
        "add": cmd_add,
        "list": cmd_list,
        "get": cmd_get,
        "update": cmd_update,
        "delete": cmd_delete,
        "summary": cmd_summary,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
