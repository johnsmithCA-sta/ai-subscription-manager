#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 订阅管理助手 — HTML 订阅管理工具
Notion/Airtable 风格，以增删改查为核心，弱化统计图表
"""

import json
import argparse
import os
import sys
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR_OVERRIDE = os.environ.get("SUBMGR_DATA_DIR")
DATA_DIR = _DATA_DIR_OVERRIDE if _DATA_DIR_OVERRIDE else os.path.join(SCRIPT_DIR, '..')

CATEGORY_COLORS = {
    'ai_chat':    '#667eea',
    'ai_code':    '#48bb78',
    'ai_image':   '#ed8936',
    'ai_audio':   '#ed64a6',
    'ai_writing': '#9f7aea',
}
CATEGORY_EMOJI = {
    'ai_chat': '💬', 'ai_code': '💻', 'ai_image': '🎨',
    'ai_audio': '🎵', 'ai_writing': '✍️',
}
CURRENCY_SYMBOLS = {'USD': '$', 'CNY': '¥', 'EUR': '€'}
# 默认汇率兜底（1 USD = X 目标货币），优先从 rates.json 读取
_DEFAULT_RATES_RAW = {'USD': 1.0, 'CNY': 7.25, 'EUR': 0.92}


def _load_exchange_rates():
    """从 rates.json 加载汇率，返回 (to_usd_map, updated_at_str)"""
    try:
        raw = load_json('rates.json') or {}
        raw_rates = raw.get('rates', _DEFAULT_RATES_RAW)
        updated = raw.get('updated_at', '')
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        raw_rates = _DEFAULT_RATES_RAW
        updated = ''
    # 转换为 to-USD：除以基准汇率
    to_usd = {}
    for cur, rate in raw_rates.items():
        to_usd[cur] = 1.0 / rate if rate else 1.0
    return to_usd, updated


def load_json(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)



def _open_in_browser(path):
    """跨平台安全打开生成的 HTML：列表参数不经过 shell，杜绝命令注入；先校验文件存在"""
    import subprocess
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        print(f"⚠️  文件不存在，无法打开: {abs_path}")
        return
    url = 'file://' + abs_path
    try:
        if sys.platform == 'darwin':
            subprocess.run(['open', url], check=False)
        elif os.name == 'nt':
            subprocess.run(['cmd', '/c', 'start', '', url], check=False)
        else:
            subprocess.run(['xdg-open', url], check=False)
        print(f"🌐 已在浏览器打开: {url}")
    except OSError as e:
        print(f"⚠️  无法自动打开浏览器: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='🤖 AI 订阅管理工具 — 生成可交互 HTML',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python dashboard.py generate
  python dashboard.py generate --output /tmp/dashboard.html
  python dashboard.py generate --open""")

    sub = parser.add_subparsers(dest='command')
    p1 = sub.add_parser('generate', help='生成管理面板')
    p1.add_argument('--output', '-o', default=None, help='输出文件路径')
    p1.add_argument('--open', action='store_true', help='生成后自动打开')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == 'generate':
        products = load_json('products.json')
        categories = load_json('categories.json')
        tags_data = load_json('function_tags.json')
        if products is None or categories is None or tags_data is None:
            print("❌ 错误：技能自带数据文件（products/categories/function_tags）缺失，请检查技能目录完整性")
            return 1
        subscriptions = load_json('subscriptions.json')
        if subscriptions is None:
            subscriptions = []  # 首次使用：无订阅记录时生成空状态仪表盘
        exchange_rates, rates_updated = _load_exchange_rates()

        now = datetime.now().strftime('%Y-%m-%d %H:%M')

        balances_data = load_json('balances.json') or {}
        if isinstance(balances_data, dict):
            balances_data = balances_data.get('balances', [])

        html = generate_html(
            products=json.dumps(products, ensure_ascii=False),
            categories=json.dumps(categories, ensure_ascii=False),
            tags=json.dumps(tags_data, ensure_ascii=False),
            subscriptions=json.dumps(subscriptions, ensure_ascii=False),
            colors=json.dumps(CATEGORY_COLORS, ensure_ascii=False),
            emoji=json.dumps(CATEGORY_EMOJI, ensure_ascii=False),
            symbols=json.dumps(CURRENCY_SYMBOLS, ensure_ascii=False),
            rates=json.dumps(exchange_rates, ensure_ascii=False),
            rates_updated=rates_updated,
            remind_config=json.dumps(load_json('remind_config.json') if os.path.exists(os.path.join(DATA_DIR, 'remind_config.json')) else {}, ensure_ascii=False),
            balances=json.dumps(balances_data, ensure_ascii=False),
            now=now,
            product_count=len(products),
        )

        output_path = args.output or os.path.join(DATA_DIR, 'dashboard.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'✅ 管理面板已生成: {output_path}')
        print(f'   产品库: {len(products)} 款')
        print(f'   当前订阅: {len(subscriptions)} 条')
        if args.open:
            _open_in_browser(output_path)


def generate_html(products, categories, tags, subscriptions,
                  colors, emoji, symbols, rates, rates_updated, remind_config, now, product_count,
                  balances='[]'):

    # ── 生成产品分组选项 HTML ──
    cats_data = json.loads(categories)
    prods_data = json.loads(products)
    cat_order = ['ai_chat', 'ai_code', 'ai_image', 'ai_audio', 'ai_writing']
    cat_info = cats_data.get('categories', cats_data)

    product_options_html = ''
    for cat_key in cat_order:
        ci = cat_info.get(cat_key, {})
        cat_name = ci.get('name', cat_key) if isinstance(ci, dict) else cat_key
        cat_emoji = CATEGORY_EMOJI.get(cat_key, '📦')
        prods_in_cat = [p for p in prods_data if p.get('category') == cat_key]
        if not prods_in_cat:
            continue
        product_options_html += f'<optgroup label="{cat_emoji} {cat_name}">\n'
        for p in prods_in_cat:
            product_options_html += f'<option value="{p["product_key"]}">{p["display_name"]} — {p["vendor"]}</option>\n'
        product_options_html += '</optgroup>\n'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 订阅管理</title>
<style>
:root {{
  --bg: #f0f2f5; --surface: #ffffff; --text: #1a1a2e; --text2: #64748b;
  --border: #e2e8f0; --radius: 14px; --radius-sm: 10px;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-lg: 0 10px 40px rgba(0,0,0,0.12);
  --primary: #667eea; --primary-light: #eef0ff;
  --danger: #ef4444; --danger-light: #fef2f2;
  --success: #22c55e; --success-light: #f0fdf4;
  --warning: #f59e0b; --warning-light: #fffbeb;
  --info: #3b82f6; --info-light: #eff6ff;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}
.app {{ max-width: 1200px; margin: 0 auto; padding: 16px; min-height: 100vh; }}

/* ── Header ── */
.header {{
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff; padding: 20px 24px; border-radius: var(--radius);
  margin-bottom: 16px; display: flex; justify-content: space-between;
  align-items: center; flex-wrap: wrap; gap: 12px;
}}
.header-left h1 {{ font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }}
.header-meta {{ font-size: 12px; opacity: 0.75; margin-top: 2px; }}
.header-actions {{ display: flex; gap: 8px; }}
.btn {{ display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
  border-radius: 8px; border: none; cursor: pointer; font-size: 13px;
  font-weight: 500; transition: all 0.15s; font-family: inherit; }}
.btn-primary {{ background: #fff; color: var(--primary); }}
.btn-primary:hover {{ background: rgba(255,255,255,0.9); transform: translateY(-1px); }}
.btn-ghost {{ background: rgba(255,255,255,0.15); color: #fff; border: 1px solid rgba(255,255,255,0.25); }}
.btn-ghost:hover {{ background: rgba(255,255,255,0.25); }}

/* ── Filter Bar ── */
.filter-bar {{
  background: var(--surface); border-radius: var(--radius); padding: 14px 20px;
  margin-bottom: 16px; box-shadow: var(--shadow); display: flex;
  align-items: center; gap: 12px; flex-wrap: wrap;
}}
.filter-tabs {{ display: flex; gap: 4px; flex-wrap: wrap; flex: 1; }}
.filter-tab {{
  padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
  background: transparent; cursor: pointer; font-size: 13px; color: var(--text2);
  transition: all 0.15s; white-space: nowrap; font-family: inherit;
}}
.filter-tab:hover {{ border-color: var(--primary); color: var(--primary); }}
.filter-tab.active {{ background: var(--primary); color: #fff; border-color: var(--primary); }}
.filter-sep {{ width: 1px; height: 24px; background: var(--border); flex-shrink: 0; }}
.filter-right {{ display: flex; gap: 8px; align-items: center; flex-shrink: 0; }}
.filter-select {{
  padding: 6px 12px; border-radius: 8px; border: 1px solid var(--border);
  font-size: 13px; color: var(--text2); background: var(--surface);
  cursor: pointer; font-family: inherit;
}}
.sub-count {{
  font-size: 13px; color: var(--text2); padding: 6px 12px;
  background: var(--bg); border-radius: 8px; white-space: nowrap;
}}


/* ── Quickstart 30秒上手指引 ── */
.quickstart {{
  background: linear-gradient(135deg, #eef0ff 0%, #fdf4ff 100%);
  border: 1px solid #c7d2fe; border-radius: var(--radius);
  padding: 14px 20px; margin-bottom: 16px; box-shadow: var(--shadow);
}}
.quickstart-head {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }}
.quickstart-title {{ font-size: 14px; font-weight: 700; color: var(--primary); }}
.quickstart-close {{ background: transparent; border: none; cursor: pointer; font-size: 14px; color: var(--text2); padding: 2px 6px; border-radius: 6px; font-family: inherit; }}
.quickstart-close:hover {{ background: rgba(102,126,234,0.1); color: var(--primary); }}
.quickstart-steps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.quickstart-step {{ display: flex; gap: 10px; align-items: flex-start; background: #fff; border-radius: 10px; padding: 10px 12px; }}
.quickstart-num {{ flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%; background: var(--primary); color: #fff; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; }}
.quickstart-step b {{ font-size: 13px; color: var(--text); }}
.quickstart-desc {{ font-size: 12px; color: var(--text2); margin-top: 2px; }}

/* ── Renewal Banner ── */
.renewal-banner {{
  border-radius: var(--radius); padding: 14px 20px; margin-bottom: 16px;
  display: flex; align-items: center; gap: 12px; box-shadow: var(--shadow);
  animation: bannerPulse 2s ease-in-out infinite;
}}
.renewal-banner.urgent {{
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border: 1px solid #fca5a5;
}}
.renewal-banner.warning {{
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border: 1px solid #fcd34d;
}}
.renewal-banner.safe {{
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border: 1px solid #86efac;
  animation: none;
}}
.renewal-banner-icon {{ font-size: 26px; flex-shrink: 0; }}
.renewal-banner-body {{ flex: 1; min-width: 0; }}
.renewal-banner-title {{ font-size: 14px; font-weight: 700; margin-bottom: 2px; }}
.renewal-banner.urgent .renewal-banner-title {{ color: #991b1b; }}
.renewal-banner.warning .renewal-banner-title {{ color: #92400e; }}
.renewal-banner.safe .renewal-banner-title {{ color: #166534; }}
.renewal-banner-items {{ font-size: 12.5px; color: var(--text2); line-height: 1.5; }}
.renewal-banner.urgent .renewal-banner-items {{ color: #7f1d1d; }}
.renewal-banner.warning .renewal-banner-items {{ color: #78350f; }}
.renewal-banner.safe .renewal-banner-items {{ color: #14532d; }}
.renewal-banner-action {{ flex-shrink: 0; }}
.renewal-banner-action button {{
  padding: 7px 14px; border-radius: 8px; border: none; cursor: pointer;
  font-size: 12.5px; font-weight: 600; font-family: inherit; transition: all 0.15s;
}}
.renewal-banner.urgent .renewal-banner-action button {{ background: #dc2626; color: #fff; }}
.renewal-banner.urgent .renewal-banner-action button:hover {{ background: #b91c1c; }}
.renewal-banner.warning .renewal-banner-action button {{ background: #d97706; color: #fff; }}
.renewal-banner.warning .renewal-banner-action button:hover {{ background: #b45309; }}
.renewal-banner.safe .renewal-banner-action button {{ background: #16a34a; color: #fff; }}
.renewal-banner.safe .renewal-banner-action button:hover {{ background: #15803d; }}
@keyframes bannerPulse {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(220,38,38,0.2); }}
  50% {{ box-shadow: 0 0 0 6px rgba(220,38,38,0); }}
}}
.renewal-banner.warning {{ animation-name: bannerPulseWarn; }}
@keyframes bannerPulseWarn {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(217,119,6,0.2); }}
  50% {{ box-shadow: 0 0 0 6px rgba(217,119,6,0); }}
}}
.rates-meta {{ font-size: 11px; color: var(--text2); margin-top: 2px; }}

/* ── Card Grid ── */
.card-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px; margin-bottom: 16px;
}}

/* ── Subscription Card ── */
.sub-card {{
  background: var(--surface); border-radius: var(--radius); overflow: hidden;
  box-shadow: var(--shadow); transition: all 0.2s; position: relative;
  display: flex; flex-direction: column;
}}
.sub-card:hover {{ box-shadow: var(--shadow-md); transform: translateY(-2px); }}
.card-bar {{ height: 4px; flex-shrink: 0; }}
.card-top {{ padding: 16px 18px 0; display: flex; align-items: flex-start; gap: 12px; }}
.card-icon {{
  width: 42px; height: 42px; border-radius: 10px; display: flex;
  align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0;
}}
.card-identity {{ flex: 1; min-width: 0; }}
.card-product {{ font-size: 15px; font-weight: 600; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }}
.card-vendor {{ font-size: 12px; color: var(--text2); }}
.card-actions {{
  display: flex; gap: 4px; flex-shrink: 0;
}}
.card-actions button {{
  width: 30px; height: 30px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface); cursor: pointer; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}}
.card-actions button:hover {{ background: var(--bg); }}
.card-actions button.del-btn:hover {{ background: var(--danger-light); border-color: var(--danger); }}

.card-price-row {{
  padding: 10px 18px; display: flex; align-items: baseline; gap: 8px;
}}
.card-price {{
  font-size: 26px; font-weight: 700; letter-spacing: -1px;
}}
.card-price-unit {{ font-size: 13px; color: var(--text2); }}
.card-tier {{
  display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px;
  font-weight: 500; margin-left: auto;
}}

.card-body {{ padding: 0 18px 14px; flex: 1; }}
.card-renew {{
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  border-radius: var(--radius-sm); margin-bottom: 12px;
}}
.card-renew-date {{ font-size: 13px; font-weight: 500; }}
.card-renew-countdown {{ font-size: 12px; font-weight: 600; margin-left: auto; }}
.card-auto-renew {{ font-size: 12px; color: var(--text2); margin-bottom: 10px; }}
.card-tags {{ display: flex; flex-wrap: wrap; gap: 4px; }}
.tag {{
  padding: 2px 8px; border-radius: 6px; font-size: 11px;
  background: var(--bg); color: var(--text2); white-space: nowrap;
}}
.tag-more {{ background: var(--border); }}

.card-footer {{
  padding: 10px 18px; border-top: 1px solid var(--border);
  display: flex; gap: 6px;
}}
.card-footer .btn-sm {{
  padding: 5px 12px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--surface); cursor: pointer; font-size: 12px;
  font-family: inherit; transition: all 0.15s; display: inline-flex;
  align-items: center; gap: 4px; color: var(--text2);
}}
.card-footer .btn-sm:hover {{ background: var(--bg); color: var(--text); }}
.card-footer .btn-sm.btn-renew:hover {{ background: var(--success-light); color: var(--success); border-color: var(--success); }}

/* ── Empty State ── */
.empty-state {{
  grid-column: 1 / -1; text-align: center; padding: 60px 20px;
}}
.empty-icon {{ font-size: 56px; margin-bottom: 16px; opacity: 0.6; }}
.empty-title {{ font-size: 18px; font-weight: 600; color: var(--text); margin-bottom: 8px; }}
.empty-desc {{ font-size: 14px; color: var(--text2); margin-bottom: 20px; }}
.empty-cta {{
  display: inline-flex; align-items: center; gap: 6px; padding: 10px 24px;
  border-radius: 10px; background: var(--primary); color: #fff; border: none;
  cursor: pointer; font-size: 14px; font-weight: 500; font-family: inherit;
  transition: all 0.15s;
}}
.empty-cta:hover {{ opacity: 0.9; transform: translateY(-1px); box-shadow: var(--shadow-md); }}

/* ── Bottom Stats ── */
.bottom-bar {{
  background: var(--surface); border-radius: var(--radius); padding: 16px 20px;
  box-shadow: var(--shadow); margin-bottom: 16px;
}}
.stats-row {{
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  justify-content: center;
}}
.stat-item {{
  display: flex; align-items: center; gap: 6px; font-size: 14px;
}}
.stat-value {{ font-weight: 700; font-size: 16px; }}
.stat-label {{ color: var(--text2); font-size: 13px; }}
.stat-sep {{ width: 1px; height: 20px; background: var(--border); }}

/* ── Quick Actions ── */
.quick-actions {{
  background: var(--surface); border-radius: var(--radius); padding: 16px 20px;
  box-shadow: var(--shadow); margin-bottom: 16px;
}}
.quick-actions-title {{ font-size: 14px; font-weight: 600; margin-bottom: 10px; color: var(--text2); }}
.quick-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px;
}}
.quick-btn {{
  display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  border-radius: var(--radius-sm); border: 1px solid var(--border);
  background: var(--surface); cursor: pointer; transition: all 0.15s;
  text-align: left; font-family: inherit;
}}
.quick-btn:hover {{ border-color: var(--primary); background: var(--primary-light); }}
.quick-btn-icon {{ font-size: 22px; flex-shrink: 0; }}
.quick-btn-text {{ flex: 1; }}
.quick-btn-name {{ font-size: 13px; font-weight: 500; color: var(--text); display: block; }}
.quick-btn-desc {{ font-size: 11px; color: var(--text2); display: block; }}

/* ── Command Toast ── */
.cmd-toast {{
  display: none; position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: #1e293b; color: #e2e8f0; padding: 12px 20px; border-radius: 12px;
  font-size: 13px; z-index: 2000; max-width: 90vw; box-shadow: var(--shadow-lg);
  animation: toastIn 0.25s ease-out;
}}
.cmd-toast.show {{ display: block; }}
.cmd-toast code {{
  background: rgba(255,255,255,0.12); padding: 2px 8px; border-radius: 4px;
  font-family: 'SF Mono', Monaco, monospace; font-size: 12px; cursor: pointer;
}}
.cmd-toast code:hover {{ background: rgba(255,255,255,0.2); }}
.cmd-toast .toast-close {{
  position: absolute; top: 6px; right: 10px; background: none; border: none;
  color: #94a3b8; cursor: pointer; font-size: 16px;
}}
@keyframes toastIn {{
  from {{ opacity: 0; transform: translateX(-50%) translateY(10px); }}
  to {{ opacity: 1; transform: translateX(-50%) translateY(0); }}
}}

/* ── Coverage Section (Collapsible) ── */
.collapse-section {{
  background: var(--surface); border-radius: var(--radius); padding: 16px 20px;
  box-shadow: var(--shadow); margin-bottom: 16px;
}}
.collapse-header {{
  display: flex; align-items: center; justify-content: space-between;
  cursor: pointer; user-select: none;
}}
.collapse-title {{ font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
.collapse-arrow {{ font-size: 14px; color: var(--text2); transition: transform 0.2s; }}
.collapse-arrow.open {{ transform: rotate(180deg); }}
.collapse-body {{ overflow: hidden; transition: max-height 0.3s ease; }}
.cov-bar-bg {{ height: 10px; background: var(--bg); border-radius: 5px; overflow: hidden; margin: 12px 0; }}
.cov-bar {{ height: 100%; border-radius: 5px; background: linear-gradient(90deg, var(--success), #16a34a); transition: width 0.5s; }}
.cov-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 6px; margin-top: 10px; }}
.cov-tag {{
  display: flex; align-items: center; gap: 6px; padding: 5px 10px;
  border-radius: 6px; font-size: 12px; border: 1px solid var(--border);
}}
.cov-tag.covered {{ background: var(--success-light); border-color: #bbf7d0; }}
.cov-tag.uncovered {{ background: #fafafa; border-color: var(--border); opacity: 0.7; }}
.cov-name {{ font-weight: 500; flex: 1; }}
.cov-subs {{ font-size: 11px; color: var(--primary); }}
.cov-subs.none {{ color: var(--text2); }}

/* ── Modal ── */
.modal-overlay {{
  display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(0,0,0,0.4); z-index: 1000; align-items: center;
  justify-content: center; backdrop-filter: blur(4px);
}}
.modal-overlay.active {{ display: flex; }}
.modal {{
  background: var(--surface); border-radius: 18px; width: 92%; max-width: 520px;
  max-height: 90vh; overflow-y: auto; box-shadow: var(--shadow-lg);
  animation: modalSlide 0.25s ease-out;
}}
.modal-wide {{ max-width: 720px; }}
@keyframes modalSlide {{
  from {{ opacity: 0; transform: translateY(16px) scale(0.97); }}
  to {{ opacity: 1; transform: translateY(0) scale(1); }}
}}
.modal-head {{
  padding: 20px 24px; display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--surface);
  border-radius: 18px 18px 0 0; z-index: 1;
}}
.modal-head h2 {{ font-size: 18px; font-weight: 600; }}
.modal-close {{
  width: 32px; height: 32px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface); cursor: pointer; font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s; color: var(--text2);
}}
.modal-close:hover {{ background: var(--bg); color: var(--text); }}
.modal-body {{ padding: 20px 24px; }}
.fg {{ margin-bottom: 14px; }}
.fg label {{
  display: block; font-size: 12px; font-weight: 600; color: var(--text2);
  margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.3px;
}}
.fg label .req {{ color: var(--danger); }}
.fg select, .fg input {{
  width: 100%; padding: 9px 12px; border: 1px solid var(--border); border-radius: 8px;
  font-size: 14px; background: var(--surface); transition: border-color 0.15s;
  font-family: inherit; color: var(--text);
}}
.fg select:focus, .fg input:focus {{ outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(102,126,234,0.1); }}
.fr2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
.fr3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }}
.toggle-row {{
  display: flex; align-items: center; gap: 10px; padding: 4px 0;
}}
.toggle {{
  width: 42px; height: 24px; border-radius: 12px; background: #cbd5e1;
  position: relative; cursor: pointer; transition: background 0.2s; flex-shrink: 0;
}}
.toggle.on {{ background: var(--success); }}
.toggle::after {{
  content: ''; position: absolute; top: 2px; left: 2px; width: 20px; height: 20px;
  border-radius: 50%; background: #fff; transition: transform 0.2s;
  box-shadow: 0 1px 2px rgba(0,0,0,0.15);
}}
.toggle.on::after {{ transform: translateX(18px); }}
.toggle-label {{ font-size: 14px; color: var(--text); }}
.modal-foot {{
  padding: 16px 24px; border-top: 1px solid var(--border);
  display: flex; gap: 10px; justify-content: flex-end;
  position: sticky; bottom: 0; background: var(--surface);
  border-radius: 0 0 18px 18px;
}}
.btn-m {{ padding: 9px 20px; border-radius: 8px; font-size: 14px;
  font-weight: 500; cursor: pointer; transition: all 0.15s; border: none; font-family: inherit; }}
.btn-m-cancel {{ background: var(--bg); color: var(--text); border: 1px solid var(--border); }}
.btn-m-cancel:hover {{ background: var(--border); }}
.btn-m-save {{ background: var(--primary); color: #fff; }}
.btn-m-save:hover {{ opacity: 0.9; }}

/* ── Confirm Dialog ── */
.confirm-overlay {{
  display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(0,0,0,0.45); z-index: 1100; align-items: center;
  justify-content: center; backdrop-filter: blur(4px);
}}
.confirm-overlay.active {{ display: flex; }}
.confirm-box {{
  background: var(--surface); border-radius: 16px; padding: 28px 32px;
  width: 90%; max-width: 380px; text-align: center;
  box-shadow: var(--shadow-lg); animation: modalSlide 0.2s ease-out;
}}
.confirm-icon {{ font-size: 40px; margin-bottom: 12px; }}
.confirm-box h3 {{ font-size: 17px; font-weight: 600; margin-bottom: 6px; }}
.confirm-box p {{ font-size: 14px; color: var(--text2); margin-bottom: 20px; line-height: 1.5; }}
.confirm-actions {{ display: flex; gap: 10px; justify-content: center; }}
.confirm-actions button {{
  padding: 9px 24px; border-radius: 8px; font-size: 14px; font-weight: 500;
  cursor: pointer; border: none; font-family: inherit; transition: all 0.15s;
}}
.btn-c-cancel {{ background: var(--bg); color: var(--text); }}
.btn-c-danger {{ background: var(--danger); color: #fff; }}
.btn-c-danger:hover {{ background: #dc2626; }}

/* ── Footer ── */
.footer {{ text-align: center; padding: 12px; font-size: 11px; color: var(--text2); }}

/* ── Responsive ── */
@media (max-width: 768px) {{
  .app {{ padding: 10px; }}
  .header {{ padding: 16px; }}
  .header h1 {{ font-size: 18px; }}
  .card-grid {{ grid-template-columns: 1fr; }}
  .filter-bar {{ flex-direction: column; align-items: stretch; }}
  .filter-sep {{ display: none; }}
  .filter-right {{ justify-content: space-between; }}
  .stats-row {{ flex-direction: column; gap: 8px; }}
  .stat-sep {{ width: 100%; height: 1px; }}
  .quick-grid {{ grid-template-columns: 1fr 1fr; }}
  .fr3 {{ grid-template-columns: 1fr; }}
}}

/* ── API 余额资产 ── */
.bal-section {{ margin: 22px 0; }}
.bal-title {{ font-size: 16px; font-weight: 700; margin-bottom: 12px; color: var(--text); display: flex; align-items: center; gap: 8px; }}
.bal-count {{ font-size: 12px; font-weight: 500; color: var(--text2); background: var(--bg); border-radius: 10px; padding: 2px 10px; }}
.bal-alert {{ display: flex; align-items: center; gap: 10px; background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; border-radius: 12px; padding: 10px 14px; margin-bottom: 12px; font-size: 13px; }}
.bal-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
.bal-card {{ background: var(--bg); border-radius: 14px; padding: 16px; border: 1px solid rgba(0,0,0,0.05); }}
.bal-head {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
.bal-platform {{ font-size: 14px; font-weight: 600; color: var(--text); }}
.bal-model {{ font-size: 11px; color: var(--text2); background: var(--surface, rgba(0,0,0,0.04)); border-radius: 8px; padding: 2px 8px; max-width: 55%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.bal-amount {{ font-size: 24px; font-weight: 700; color: var(--text); margin: 4px 0 2px; }}
.bal-sub {{ font-size: 12px; color: var(--text2); margin-bottom: 10px; }}
.bal-bar {{ height: 6px; background: rgba(0,0,0,0.08); border-radius: 3px; overflow: hidden; margin-bottom: 6px; }}
.bal-bar-fill {{ height: 100%; border-radius: 3px; background: linear-gradient(90deg,#48bb78,#38a169); }}
.bal-bar-fill.warn {{ background: linear-gradient(90deg,#ed8936,#dd6b20); }}
.bal-bar-fill.danger {{ background: linear-gradient(90deg,#f56565,#c53030); }}
.bal-meta {{ display: flex; justify-content: space-between; font-size: 11px; color: var(--text2); }}
.bal-days {{ font-size: 12px; font-weight: 600; border-radius: 8px; padding: 2px 8px; }}
.bal-days.ok {{ color: #276749; background: #c6f6d5; }}
.bal-days.warn {{ color: #975a16; background: #feebc8; }}
.bal-days.danger {{ color: #9b2c2c; background: #fed7d7; }}
.bal-days.na {{ color: var(--text2); background: rgba(0,0,0,0.05); }}

/* ── Analysis Modal ── */
.an-section {{ margin-bottom: 22px; }}
.an-section:last-child {{ margin-bottom: 0; }}
.an-title {{ font-size: 15px; font-weight: 600; margin-bottom: 12px; color: var(--text); }}
.an-cards {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 10px; }}
.an-card {{
  background: var(--bg); border-radius: 12px; padding: 14px; text-align: center;
}}
.an-card-label {{ font-size: 12px; color: var(--text2); margin-bottom: 4px; }}
.an-card-value {{ font-size: 20px; font-weight: 700; color: var(--primary); }}
.an-table {{
  width: 100%; border-collapse: collapse; font-size: 13px;
}}
.an-table th {{
  text-align: left; padding: 8px 10px; font-size: 11px; font-weight: 600;
  color: var(--text2); text-transform: uppercase; letter-spacing: 0.3px;
  border-bottom: 2px solid var(--border); background: var(--bg);
}}
.an-table td {{
  padding: 10px; border-bottom: 1px solid var(--border); vertical-align: middle;
}}
.an-table tr.ar-head td {{ font-weight: 600; background: var(--bg); }}
.an-table tr:last-child td {{ border-bottom: none; }}
.an-alert {{
  background: var(--warning-light); border: 1px solid #fde68a; color: #92400e;
  padding: 12px 16px; border-radius: 10px; font-size: 13px; margin-top: 8px;
}}
.an-note {{
  background: var(--success-light); border: 1px solid #bbf7d0; color: #166534;
  padding: 12px 16px; border-radius: 10px; font-size: 13px; margin-top: 8px;
}}
.an-overlap {{
  background: var(--bg); border-radius: 12px; padding: 14px; margin-bottom: 10px;
}}
.an-overlap-pair {{ font-size: 14px; margin-bottom: 8px; }}
.an-overlap-tags {{ display: flex; flex-wrap: wrap; gap: 6px; }}
</style>
</head>
<body>
<div class="app" id="app"></div>

<!-- Toast -->
<div class="cmd-toast" id="cmdToast">
  <button class="toast-close" onclick="hideToast()">&times;</button>
  <div id="toastContent"></div>
</div>

<!-- Add/Edit Modal -->
<div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <div class="modal-head">
      <h2 id="modalTitle">添加订阅</h2>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <form id="subForm" onsubmit="return handleSubmit(event)">
      <div class="modal-body">
        <input type="hidden" id="editIdx" value="-1">
        <div class="fg">
          <label>产品 <span class="req">*</span></label>
          <select id="fProduct" required onchange="onProductChange()">
            <option value="">-- 选择产品 --</option>
            {product_options_html}
          </select>
        </div>
        <div class="fg">
          <label>套餐 <span class="req">*</span></label>
          <select id="fTier" required onchange="onTierChange()"></select>
        </div>
        <div class="fr3">
          <div class="fg">
            <label>价格 <span class="req">*</span></label>
            <input type="number" id="fPrice" step="0.01" min="0" required>
          </div>
          <div class="fg">
            <label>货币</label>
            <select id="fCurrency">
              <option value="USD">USD ($)</option>
              <option value="CNY">CNY (¥)</option>
            </select>
          </div>
          <div class="fg">
            <label>周期 <span class="req">*</span></label>
            <select id="fBilling" required>
              <option value="monthly">月付</option>
              <option value="yearly">年付</option>
            </select>
          </div>
        </div>
        <div class="fg">
          <label>开始日期 <span class="req">*</span></label>
          <input type="date" id="fStartDate" required>
        </div>
        <div class="fg">
          <label>下次扣费</label>
          <input type="date" id="fNextBill">
        </div>
        <div class="fr2">
          <div class="fg">
            <label>支付方式</label>
            <input type="text" id="fPayment" placeholder="信用卡">
          </div>
          <div class="fg">
            <label>备注</label>
            <input type="text" id="fNotes" placeholder="可选">
          </div>
        </div>
        <div class="fg">
          <label>自动续费</label>
          <div class="toggle-row">
            <div class="toggle on" id="fAutoRenew" onclick="this.classList.toggle('on')"></div>
            <span class="toggle-label" id="arLabel">开启</span>
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button type="button" class="btn-m btn-m-cancel" onclick="closeModal()">取消</button>
        <button type="submit" class="btn-m btn-m-save" id="submitBtn">添加</button>
      </div>
    </form>
  </div>
</div>

<!-- Confirm Dialog -->
<div class="confirm-overlay" id="confirmOverlay" onclick="if(event.target===this)closeConfirm()">
  <div class="confirm-box">
    <div class="confirm-icon">⚠️</div>
    <h3>确认删除</h3>
    <p id="confirmText">确定要删除此订阅吗？此操作不可撤销。</p>
    <div class="confirm-actions">
      <button class="btn-c-cancel" onclick="closeConfirm()">取消</button>
      <button class="btn-c-danger" id="confirmDelBtn">删除</button>
    </div>
  </div>
</div>

<!-- Analysis Modal -->
<div class="modal-overlay" id="analysisOverlay" onclick="if(event.target===this)closeAnalysis()">
  <div class="modal modal-wide">
    <div class="modal-head">
      <h2 id="analysisTitle">分析</h2>
      <button class="modal-close" onclick="closeAnalysis()">&times;</button>
    </div>
    <div class="modal-body" id="analysisBody"></div>
  </div>
</div>

<script>
// ══════════════════════════════════════════════════
// 嵌入数据
// ══════════════════════════════════════════════════
const PRODUCTS = {products};
const CATEGORIES = {categories};
const TAGS_DATA = {tags};
const COLORS = {colors};
const EMOJI = {emoji};
const SYMBOLS = {symbols};
const RATES = {rates};
const RATES_UPDATED = '{rates_updated}';
const REMIND_CONFIG = {remind_config};
const BALANCES = {balances};
const PRODUCT_COUNT = {product_count};
const NOW = '{now}';

let subs = {subscriptions};

// ══════════════════════════════════════════════════
// 工具
// ══════════════════════════════════════════════════
function toUsd(a,c){{ return a*(RATES[c]||1); }}
function fmtPrice(a,c){{
  c=c||'USD'; var s=SYMBOLS[c]||c;
  if(!a||a===0) return '免费';
  return s+a.toLocaleString('zh-CN',{{maximumFractionDigits:1,minimumFractionDigits:1}});
}}
function fmtUsd(a){{ if(!a||a===0) return '免费'; return '$'+a.toLocaleString('zh-CN',{{maximumFractionDigits:1,minimumFractionDigits:1}}); }}
function daysUntil(d){{
  var dd=new Date(d); dd.setHours(0,0,0,0);
  var now=new Date(); now.setHours(0,0,0,0);
  return Math.round((dd-now)/86400000);
}}
function todayStr(){{ var d=new Date(); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }}
function addMonths(ds,m){{ var d=new Date(ds); d.setMonth(d.getMonth()+m); return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }}
function getProduct(k){{ for(var i=0;i<PRODUCTS.length;i++) if(PRODUCTS[i].product_key===k) return PRODUCTS[i]; return null; }}
function esc(s){{ if(!s) return ''; return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}
function catOf(p){{ return (p&&p.category)||'ai_chat'; }}
function colorOf(cat){{ return COLORS[cat]||'#667eea'; }}
function emojiOf(cat){{ return EMOJI[cat]||'📦'; }}
function catName(cat){{
  var ci=(CATEGORIES.categories||CATEGORIES); return ci[cat]?ci[cat].name:cat;
}}

// ══════════════════════════════════════════════════
// 状态
// ══════════════════════════════════════════════════
let filterCat = 'all';
let filterStatus = 'active';
let sortBy = 'date_asc';

// ══════════════════════════════════════════════════
// 分析
// ══════════════════════════════════════════════════
function calc(){{
  var active=subs.filter(function(s){{ return s.status==='active'; }});
  var monthly=0;
  active.forEach(function(s){{
    var m=s.billing_cycle==='yearly'?s.price_paid/12:s.price_paid;
    monthly+=toUsd(m,s.currency);
  }});
  // Coverage
  var tagsRef=TAGS_DATA.tags||TAGS_DATA;
  var allTags=Object.keys(tagsRef).sort(function(a,b){{ return tagsRef[b].weight-tagsRef[a].weight; }});
  var allUserTags=new Set();
  active.forEach(function(s){{
    var p=getProduct(s.product_key); if(!p) return;
    (p.tags||[]).forEach(function(t){{ allUserTags.add(t); }});
  }});
  var covered=allTags.filter(function(t){{ return allUserTags.has(t); }});
  var covPct=allTags.length?Math.round(covered.length/allTags.length*100):0;
  return {{ active:active, monthly:monthly, annual:monthly*12,
           covered:covered, allTags:allTags, covPct:covPct }};
}}

// ══════════════════════════════════════════════════
// 过滤 & 排序
// ══════════════════════════════════════════════════
function getFiltered(){{
  var list=subs.filter(function(s){{ return s.status==='active'; }});
  // category
  if(filterCat!=='all'){{
    list=list.filter(function(s){{
      var p=getProduct(s.product_key); return p&&p.category===filterCat;
    }});
  }}
  // status
  var now=todayStr();
  if(filterStatus==='expiring'){{
    list=list.filter(function(s){{
      var d=daysUntil(s.next_billing_date); return d>=0&&d<=7;
    }});
  }} else if(filterStatus==='expired'){{
    list=list.filter(function(s){{ return daysUntil(s.next_billing_date)<0; }});
  }}
  // sort
  if(sortBy==='date_asc'){{
    list.sort(function(a,b){{ return daysUntil(a.next_billing_date)-daysUntil(b.next_billing_date); }});
  }} else if(sortBy==='price_desc'){{
    list.sort(function(a,b){{ return toUsd(b.price_paid,b.currency)-toUsd(a.price_paid,a.currency); }});
  }} else if(sortBy==='price_asc'){{
    list.sort(function(a,b){{ return toUsd(a.price_paid,a.currency)-toUsd(b.price_paid,b.currency); }});
  }}
  return list;
}}

// ══════════════════════════════════════════════════
// 渲染
// ══════════════════════════════════════════════════
function render(){{
  var data=calc();
  var filtered=getFiltered();
  var h='';

  // ── Header ──
  h+='<div class="header">';
  h+='<div class="header-left"><h1>🤖 AI 订阅管理</h1>';
  h+='<div class="header-meta">共 '+PRODUCT_COUNT+' 款产品 · '+NOW+(RATES_UPDATED?' · 汇率参考 '+RATES_UPDATED:'')+'</div></div>';
  h+='<div class="header-actions">';
  h+='<button class="btn btn-ghost" onclick="exportData()">📥 导出</button>';
  h+='<button class="btn btn-primary" onclick="openAdd()">+ 添加订阅</button>';
  h+='</div></div>';

  // ── Filter Bar ──
  var catKeys=['all','ai_chat','ai_code','ai_image','ai_audio','ai_writing'];
  var catLabels=['📦 全部','💬 对话','💻 编程','🎨 图像','🎵 音频','✍️ 写作'];
  h+='<div class="filter-bar">';
  h+='<div class="filter-tabs">';
  catKeys.forEach(function(k,i){{
    var cls=filterCat===k?'filter-tab active':'filter-tab';
    h+='<button class="'+cls+'" data-cat="'+k+'" onclick="setCat(this.dataset.cat)">'+catLabels[i]+'</button>';
  }});
  h+='</div>';
  h+='<div class="filter-sep"></div>';
  h+='<div class="filter-right">';
  var statusOpts=[['active','✅ 活跃'],['expiring','⏰ 即将到期'],['expired','⚠️ 已过期']];
  h+='<select class="filter-select" onchange="setStatus(this.value)">';
  statusOpts.forEach(function(o){{
    h+='<option value="'+o[0]+'"'+(filterStatus===o[0]?' selected':'')+'>'+o[1]+'</option>';
  }});
  h+='</select>';
  var sortOpts=[['date_asc','按扣款日期'],['price_desc','价格↓'],['price_asc','价格↑']];
  h+='<select class="filter-select" onchange="setSort(this.value)">';
  sortOpts.forEach(function(o){{
    h+='<option value="'+o[0]+'"'+(sortBy===o[0]?' selected':'')+'>'+o[1]+'</option>';
  }});
  h+='</select>';
  h+='<span class="sub-count">'+filtered.length+' 个</span>';
  h+='</div></div>';

  // ── Renewal Banner ──
  h+=renderRenewalBanner();

  // ── Quickstart 上手指引 ──
  h+=renderQuickstart();

  // ── Card Grid ──
  h+='<div class="card-grid">';
  if(filtered.length===0){{
    h+=renderEmpty();
  }} else {{
    filtered.forEach(function(s){{
      h+=renderCard(s);
    }});
  }}
  h+='</div>';

  // ── API 余额资产 ──
  h+=renderBalances();

  // ── Bottom Stats ──
  var apiStats=apiBurnStats();
  h+='<div class="bottom-bar"><div class="stats-row">';
  h+='<div class="stat-item"><span class="stat-label">月支出</span><span class="stat-value">'+fmtUsd(data.monthly)+'</span></div>';
  h+='<div class="stat-sep"></div>';
  h+='<div class="stat-item"><span class="stat-label">年支出</span><span class="stat-value">'+fmtUsd(data.annual)+'</span></div>';
  h+='<div class="stat-sep"></div>';
  if(apiStats.count>0){{
    h+='<div class="stat-item"><span class="stat-label">API 月耗</span><span class="stat-value">'+fmtUsd(apiStats.monthlyUsd)+'</span></div>';
    h+='<div class="stat-sep"></div>';
    h+='<div class="stat-item"><span class="stat-label">AI 总支出</span><span class="stat-value">'+fmtUsd(data.monthly+apiStats.monthlyUsd)+'</span></div>';
    h+='<div class="stat-sep"></div>';
    h+='<div class="stat-item"><span class="stat-label">API 总余额</span><span class="stat-value">'+fmtUsd(apiStats.totalUsd)+'</span></div>';
    h+='<div class="stat-sep"></div>';
  }}
  h+='<div class="stat-item"><span class="stat-value">'+subs.filter(function(s){{return s.status==='active';}}).length+'</span><span class="stat-label">个活跃订阅</span></div>';
  h+='<div class="stat-sep"></div>';
  h+='<div class="stat-item"><span class="stat-label">覆盖率</span><span class="stat-value">'+data.covPct+'%</span></div>';
  h+='</div></div>';

  // ── Quick Actions ──
  h+='<div class="quick-actions">';
  h+='<div class="quick-actions-title">💡 快捷操作</div>';
  h+='<div class="quick-grid">';
  var actions=[
    ['📊','成本分析','查看支出明细','showCostAnalysis'],
    ['🔄','续费评估','检查续费合理性','showRenewalCheck'],
    ['💰','同类比价','对比同类产品价格','showPriceCompare'],
    ['🔗','重叠检测','发现功能重复订阅','showOverlap'],
    ['📋','导出数据','导出JSON备份','exportData'],
  ];
  actions.forEach(function(a){{
    h+='<button class="quick-btn" onclick="'+a[3]+'()">';
    h+='<span class="quick-btn-icon">'+a[0]+'</span>';
    h+='<span class="quick-btn-text"><span class="quick-btn-name">'+a[1]+'</span>';
    h+='<span class="quick-btn-desc">'+a[2]+'</span></span>';
    h+='</button>';
  }});
  h+='</div></div>';

  // ── Coverage (Collapsible) ──
  h+=renderCoverage(data);

  // ── Footer ──
  h+='<div class="footer">AI 订阅管理助手 · Coze Skill · '+NOW+'</div>';

  document.getElementById('app').innerHTML=h;
}}


// ══════════════════════════════════════════════════
// API 余额资产（余额卡片 + 预警 + 寿命折算）
// ══════════════════════════════════════════════════
function balanceBurn(b) {{
  var logs=(b.consumption_log||[]).filter(function(l){{ return l.type!=='topup'; }});
  if(logs.length===0) return null;
  var dates=logs.map(function(l){{ return new Date(l.date).getTime(); }}).sort(function(a,b){{ return a-b; }});
  var total=logs.reduce(function(s,l){{ return s+(+l.amount||0); }},0);
  var span=Math.max(Math.round((dates[dates.length-1]-dates[0])/86400000), logs.length-1, 1);
  var rate=logs.length===1? total : total/span;
  return rate>0? {{rate:rate,days:b.balance/rate}} : null;
}}

function renderBalances() {{
  if(!BALANCES || BALANCES.length===0) return '';
  var th=((REMIND_CONFIG.balance_alert||{{}}).threshold_pct!==undefined)? REMIND_CONFIG.balance_alert.threshold_pct : 20;
  var low=BALANCES.filter(function(b){{ return (b.topup_amount||0)>0 && b.balance<(b.topup_amount||0)*th/100; }});
  var h='<div class="bal-section">';
  h+='<div class="bal-title">💳 API 余额资产 <span class="bal-count">'+BALANCES.length+' 项</span></div>';
  if(low.length>0) {{
    h+='<div class="bal-alert">🚨 <b>'+low.length+'</b> 项余额低于充值额的 '+th+'%：'+low.map(function(b){{ return esc(b.platform)+' '+fmtPrice(b.balance,b.currency); }}).join('、')+'，建议续充</div>';
  }}
  h+='<div class="bal-grid">';
  BALANCES.forEach(function(b) {{
    var burn=balanceBurn(b);
    var topup=b.topup_amount||0;
    var usedPct= topup>0? Math.min(100,Math.max(0,(topup-b.balance)/topup*100)) : 0;
    var cls= usedPct>=80?'danger':(usedPct>=60?'warn':'');
    var daysHtml;
    if(burn) {{
      var d=Math.floor(burn.days);
      var dcls= d<30?'danger':(d<60?'warn':'ok');
      daysHtml='<span class="bal-days '+dcls+'">≈'+d+' 天</span>';
    }} else {{ daysHtml='<span class="bal-days na">记账后可折算寿命</span>'; }}
    h+='<div class="bal-card">';
    h+='<div class="bal-head"><span class="bal-platform">'+esc(b.platform)+'</span>'+(b.model_hint?'<span class="bal-model">'+esc(b.model_hint)+'</span>':'')+'</div>';
    h+='<div class="bal-amount">'+fmtPrice(b.balance,b.currency)+'</div>';
    h+='<div class="bal-sub">'+(topup>0?'充值 '+fmtPrice(topup,b.currency)+' · 已用 '+usedPct.toFixed(0)+'%':'充值额未登记')+(b.tokens_used?' · 已用 '+esc(b.tokens_used)+' tok':'')+'</div>';
    if(topup>0) {{ h+='<div class="bal-bar"><div class="bal-bar-fill '+cls+'" style="width:'+usedPct+'%"></div></div>'; }}
    h+='<div class="bal-meta"><span>'+(burn? '月耗 ≈'+fmtPrice(burn.rate*30,b.currency):'消耗速率：待记账')+'</span>'+daysHtml+'</div>';
    h+='</div>';
  }});
  h+='</div></div>';
  return h;
}}

function apiBurnStats() {{
  var monthlyUsd=0, totalUsd=0;
  (BALANCES||[]).forEach(function(b) {{
    totalUsd+=toUsd(b.balance,b.currency);
    var burn=balanceBurn(b);
    if(burn) monthlyUsd+=toUsd(burn.rate*30,b.currency);
  }});
  return {{monthlyUsd:monthlyUsd,totalUsd:totalUsd,count:(BALANCES||[]).length}};
}}


function renderQuickstart() {{
  try {{ if(localStorage.getItem('submgr_qs_done')) return ''; }} catch(e) {{}}
  var h='';
  h+='<div class="quickstart" id="quickstart">';
  h+='<div class="quickstart-head"><span class="quickstart-title">🚀 30 秒上手指引</span>';
  h+='<button class="quickstart-close" onclick="closeQuickstart()" aria-label="关闭">✕</button></div>';
  h+='<div class="quickstart-steps">';
  var steps=[
    ['1','➕ 添加订阅','点击右上角「+ 添加订阅」，登记产品与扣款日'],
    ['2','⏰ 关注续费','顶部横幅提示 30 天内到期的订阅'],
    ['3','💡 快捷分析','成本分析 / 续费评估 / 同类比价 / 重叠检测'],
    ['4','📥 导出备份','随时导出 JSON 备份订阅数据'],
  ];
  steps.forEach(function(s) {{
    h+='<div class="quickstart-step"><span class="quickstart-num">'+s[0]+'</span><div><b>'+s[1]+'</b><div class="quickstart-desc">'+s[2]+'</div></div></div>';
  }});
  h+='</div></div>';
  return h;
}}
function closeQuickstart() {{
  try {{ localStorage.setItem('submgr_qs_done','1'); }} catch(e) {{}}
  var el=document.getElementById('quickstart'); if(el) el.style.display='none';
}}

function renderRenewalBanner() {{

  var active=subs.filter(function(s){{ return s.status==='active'; }});
  if(active.length===0) return '';
  var daysList=(REMIND_CONFIG.remind_days||[1,3,7,14,30]).slice().sort(function(a,b){{return a-b;}});
  var urgentThreshold=daysList.length?daysList[0]:3;
  var warnThreshold=daysList.length?daysList[daysList.length-1]:30;
  var urgent=[], warn=[];
  active.forEach(function(s){{
    var d=daysUntil(s.next_billing_date);
    if(d<0){{ urgent.push({{s:s,d:d}}); }}
    else if(d<=urgentThreshold){{ urgent.push({{s:s,d:d}}); }}
    else if(d<=warnThreshold){{ warn.push({{s:s,d:d}}); }}
  }});
  if(urgent.length===0 && warn.length===0){{
    return '<div class="renewal-banner safe"><span class="renewal-banner-icon">✅</span>'+
      '<div class="renewal-banner-body"><div class="renewal-banner-title">近期无续费提醒</div>'+
      '<div class="renewal-banner-items">未来 '+warnThreshold+' 天内没有即将扣费的订阅，安心使用。</div></div>'+
      '<div class="renewal-banner-action"><button onclick="showRenewalCheck()">查看详情</button></div></div>';
  }}
  var level, icon, title, items;
  if(urgent.length>0){{
    level='urgent'; icon='🚨';
    title='有 '+urgent.length+' 条订阅即将扣费或已过期';
    var uItems=urgent.map(function(x){{
      var p=getProduct(x.s.product_key)||{{}};
      var name=p.display_name||x.s.product_key;
      if(x.d<0) return name+'（已过期 '+Math.abs(x.d)+' 天）';
      if(x.d===0) return name+'（今天扣费）';
      return name+'（'+x.d+' 天后）';
    }});
    var wItems=warn.map(function(x){{
      var p=getProduct(x.s.product_key)||{{}};
      return (p.display_name||x.s.product_key)+'（'+x.d+' 天后）';
    }});
    items=uItems.join('、');
    if(wItems.length>0) items+='；另外 '+wItems.length+' 条在 '+warnThreshold+' 天内：'+wItems.join('、');
  }} else {{
    level='warning'; icon='⏰';
    title='未来 '+warnThreshold+' 天有 '+warn.length+' 条订阅待续费';
    items=warn.map(function(x){{
      var p=getProduct(x.s.product_key)||{{}};
      return (p.display_name||x.s.product_key)+'（'+x.d+' 天后）';
    }}).join('、');
  }}
  return '<div class="renewal-banner '+level+'"><span class="renewal-banner-icon">'+icon+'</span>'+
    '<div class="renewal-banner-body"><div class="renewal-banner-title">'+title+'</div>'+
    '<div class="renewal-banner-items">'+esc(items)+'</div></div>'+
    '<div class="renewal-banner-action"><button onclick="showRenewalCheck()">续费评估</button></div></div>';
}}

function renderEmpty(){{
  var h='<div class="empty-state">';
  h+='<div class="empty-icon">📋</div>';
  h+='<div class="empty-title">还没有订阅</div>';
  h+='<div class="empty-desc">点击上方「+ 添加订阅」开始管理你的 AI 订阅</div>';
  h+='<button class="empty-cta" onclick="openAdd()">+ 添加第一个订阅</button>';
  h+='</div>';
  return h;
}}

function renderCard(s){{
  var p=getProduct(s.product_key)||{{}};
  var cat=catOf(p), clr=colorOf(cat), emj=emojiOf(cat);
  var d=daysUntil(s.next_billing_date);
  var urgClr=d<0?'var(--danger)':d<=3?'var(--danger)':d<=7?'var(--warning)':d<=14?'var(--success)':'var(--info)';
  var urgText=d<0?'已过期 '+Math.abs(d)+'天':d===0?'今天到期':d+'天后到期';
  var bgColor=d<0||d<=3?'var(--danger-light)':d<=7?'var(--warning-light)':d<=14?'var(--success-light)':'var(--info-light)';
  var monthly=s.billing_cycle==='yearly'?s.price_paid/12:s.price_paid;
  var tags=p.tags||[];
  var tierClr=clr;

  var h='<div class="sub-card">';
  h+='<div class="card-bar" style="background:'+clr+'"></div>';
  h+='<div class="card-top">';
  h+='<div class="card-icon" style="background:'+clr+'15">'+emj+'</div>';
  h+='<div class="card-identity"><div class="card-product">'+esc(p.display_name||s.product_key)+'</div>';
  h+='<div class="card-vendor">'+esc(p.vendor||'')+'</div></div>';
  h+='<div class="card-actions">';
  var rIdx=subs.indexOf(s);
  h+='<button onclick="openEdit('+rIdx+')" title="编辑">✏️</button>';
  h+='<button class="del-btn" onclick="confirmDel('+rIdx+')" title="删除">🗑️</button>';
  h+='</div></div>';

  h+='<div class="card-price-row">';
  h+='<span class="card-price" style="color:'+clr+'">'+fmtPrice(monthly,s.currency)+'</span>';
  h+='<span class="card-price-unit">/月</span>';
  h+='<span class="card-tier" style="background:'+clr+'15;color:'+clr+'">'+esc(s.tier)+'</span>';
  h+='</div>';

  h+='<div class="card-body">';
  h+='<div class="card-renew" style="background:'+bgColor+'">';
  h+='<span style="font-size:16px">'+(d<0?'⚠️':'📅')+'</span>';
  h+='<span class="card-renew-date">'+s.next_billing_date+'</span>';
  h+='<span class="card-renew-countdown" style="color:'+urgClr+'">'+urgText+'</span>';
  h+='</div>';
  h+='<div class="card-auto-renew">自动续费：'+(s.auto_renew?'✅ 开启':'❌ 关闭')+'</div>';
  h+='<div class="card-tags">';
  var showTags=tags.slice(0,4);
  showTags.forEach(function(t){{ h+='<span class="tag">'+esc(t)+'</span>'; }});
  if(tags.length>4) h+='<span class="tag tag-more">+' +(tags.length-4)+'</span>';
  h+='</div></div>';

  h+='<div class="card-footer">';
  h+='<button class="btn-sm" onclick="openEdit('+rIdx+')">✏️ 编辑</button>';
  h+='<button class="btn-sm" onclick="confirmDel('+rIdx+')">🗑️ 删除</button>';
  h+='<button class="btn-sm btn-renew" onclick="openEdit('+rIdx+')" title="去续费">🔄 续费</button>';
  h+='</div>';
  h+='</div>';
  return h;
}}

function renderCoverage(data){{
  if(data.allTags.length===0) return '';
  var tagsRef=TAGS_DATA.tags||TAGS_DATA;
  var covSet=new Set(data.covered);
  var h='<div class="collapse-section">';
  h+='<div class="collapse-header" onclick="toggleCollapse(this)">';
  h+='<div class="collapse-title">🏷️ 功能覆盖率 <span style="font-weight:400;font-size:13px;color:var(--text2)">'+data.covPct+'% ('+data.covered.length+'/'+data.allTags.length+')</span></div>';
  h+='<span class="collapse-arrow">▼</span></div>';
  h+='<div class="collapse-body" style="max-height:0">';
  h+='<div class="cov-bar-bg"><div class="cov-bar" style="width:'+data.covPct+'%"></div></div>';
  h+='<div class="cov-grid">';

  // Build subTags for coverage detail
  var active=subs.filter(function(s){{return s.status==='active';}});
  var subTags=[];
  active.forEach(function(s){{
    var p=getProduct(s.product_key); if(!p) return;
    subTags.push({{name:p.display_name, tags:new Set(p.tags||[])}});
  }});

  data.allTags.forEach(function(tag){{
    var isCov=covSet.has(tag);
    var covering=[];
    subTags.forEach(function(st){{ if(st.tags.has(tag)) covering.push(st.name); }});
    h+='<div class="cov-tag '+(isCov?'covered':'uncovered')+'">';
    h+='<span>'+(isCov?'✅':'⬜')+'</span>';
    h+='<span class="cov-name">'+esc(tag)+'</span>';
    if(covering.length>0) h+='<span class="cov-subs">'+covering.map(esc).join(', ')+'</span>';
    else h+='<span class="cov-subs none">未覆盖</span>';
    h+='</div>';
  }});
  h+='</div></div></div>';
  return h;
}}

// ══════════════════════════════════════════════════
// 交互
// ══════════════════════════════════════════════════
function setCat(c){{ filterCat=c; render(); }}
function setStatus(s){{ filterStatus=s; render(); }}
function setSort(s){{ sortBy=s; render(); }}
function toggleCollapse(el){{
  var body=el.nextElementSibling;
  var arrow=el.querySelector('.collapse-arrow');
  if(body.style.maxHeight==='0px'){{
    body.style.maxHeight=body.scrollHeight+'px';
    arrow.classList.add('open');
  }} else {{
    body.style.maxHeight='0px';
    arrow.classList.remove('open');
  }}
}}

// ── Toast ──
var toastTimer=null;
function hideToast(){{ document.getElementById('cmdToast').classList.remove('show'); }}
function copyCmd(el){{
  var text=el.textContent;
  if(navigator.clipboard){{ navigator.clipboard.writeText(text); }}
  else{{ var ta=document.createElement('textarea'); ta.value=text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); }}
  el.style.background='rgba(34,197,94,0.3)'; el.textContent='已复制！';
  setTimeout(function(){{ el.style.background=''; el.textContent=text; }},1200);
}}
function showToast(msg,ms){{
  var t=document.getElementById('cmdToast');
  document.getElementById('toastContent').innerHTML=msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer=setTimeout(function(){{ t.classList.remove('show'); }},ms||3000);
}}

// ── Analysis Modal ──
function openAnalysis(title,bodyHtml){{
  document.getElementById('analysisTitle').textContent=title;
  document.getElementById('analysisBody').innerHTML=bodyHtml;
  document.getElementById('analysisOverlay').classList.add('active');
}}
function closeAnalysis(){{ document.getElementById('analysisOverlay').classList.remove('active'); }}

function analysisRow(cells,isHeader){{
  var tag=isHeader?'th':'td';
  var cls=isHeader?'ar-head':'';
  return '<tr class="'+cls+'">'+cells.map(function(c){{ return '<'+tag+'>'+c+'</'+tag+'>'; }}).join('')+'</tr>';
}}

function showCostAnalysis(){{
  var active=subs.filter(function(s){{ return s.status==='active'; }});
  if(active.length===0){{ openAnalysis('📊 成本分析','<p style="color:var(--text2)">暂无活跃订阅</p>'); return; }}
  var byCat={{}}, byCur={{}}, totalMonthly=0;
  active.forEach(function(s){{
    var p=getProduct(s.product_key)||{{}};
    var cat=catOf(p);
    var m=s.billing_cycle==='yearly'?s.price_paid/12:s.price_paid;
    var usd=toUsd(m,s.currency);
    byCat[cat]=(byCat[cat]||0)+usd;
    byCur[s.currency]=byCur[s.currency]||{{monthly:0,annual:0}};
    byCur[s.currency].monthly+=m;
    byCur[s.currency].annual+=s.billing_cycle==='yearly'?s.price_paid:m*12;
    totalMonthly+=usd;
  }});
  var h='<div class="an-section"><div class="an-title">💰 总支出</div>';
  h+='<div class="an-cards">';
  h+='<div class="an-card"><div class="an-card-label">月度支出</div><div class="an-card-value">'+fmtUsd(totalMonthly)+'</div></div>';
  h+='<div class="an-card"><div class="an-card-label">年度支出</div><div class="an-card-value">'+fmtUsd(totalMonthly*12)+'</div></div>';
  h+='<div class="an-card"><div class="an-card-label">活跃订阅</div><div class="an-card-value">'+active.length+'</div></div>';
  h+='</div></div>';

  h+='<div class="an-section"><div class="an-title">📂 按分类</div><table class="an-table">';
  h+=analysisRow(['分类','月度(USD)','占比'],true);
  Object.keys(byCat).forEach(function(cat){{
    var pct=Math.round(byCat[cat]/totalMonthly*100);
    h+=analysisRow([emojiOf(cat)+' '+catName(cat),fmtUsd(byCat[cat]),pct+'%']);
  }});
  h+='</table></div>';

  h+='<div class="an-section"><div class="an-title">💱 按币种</div><table class="an-table">';
  h+=analysisRow(['币种','月度','年度'],true);
  Object.keys(byCur).forEach(function(cur){{
    h+=analysisRow([cur,fmtPrice(byCur[cur].monthly,cur),fmtPrice(byCur[cur].annual,cur)]);
  }});
  h+='</table></div>';
  openAnalysis('📊 成本分析',h);
}}

function showRenewalCheck(){{
  var active=subs.filter(function(s){{ return s.status==='active'; }});
  if(active.length===0){{ openAnalysis('🔄 续费评估','<p style="color:var(--text2)">暂无活跃订阅</p>'); return; }}
  var sorted=active.slice().sort(function(a,b){{ return daysUntil(a.next_billing_date)-daysUntil(b.next_billing_date); }});
  var h='<div class="an-section"><table class="an-table">';
  h+=analysisRow(['产品','套餐','扣费日期','剩余天数','状态'],true);
  sorted.forEach(function(s){{
    var p=getProduct(s.product_key)||{{}};
    var d=daysUntil(s.next_billing_date);
    var status,icon;
    if(d<0){{ icon='🔴'; status='已过期 '+Math.abs(d)+'天'; }}
    else if(d<=3){{ icon='🔴'; status='紧急'; }}
    else if(d<=7){{ icon='🟠'; status='即将扣费'; }}
    else if(d<=14){{ icon='🟡'; status='留意'; }}
    else{{ icon='🟢'; status='正常'; }}
    h+=analysisRow([
      '<b>'+esc(p.display_name||s.product_key)+'</b>',
      esc(s.tier),
      s.next_billing_date,
      d+'天',
      icon+' '+status
    ]);
  }});
  h+='</table></div>';
  var urgent=sorted.filter(function(s){{ return daysUntil(s.next_billing_date)<=7; }});
  if(urgent.length>0){{
    h+='<div class="an-alert">⚠️ 未来7天有 <b>'+urgent.length+'</b> 条订阅即将扣费，请检查账户余额或确认是否续费。</div>';
  }} else {{
    h+='<div class="an-note">✅ 未来7天无即将扣费的订阅。</div>';
  }}
  openAnalysis('🔄 续费评估',h);
}}

function showPriceCompare(){{
  var active=subs.filter(function(s){{ return s.status==='active'; }});
  if(active.length===0){{ openAnalysis('💰 同类比价','<p style="color:var(--text2)">暂无活跃订阅，无法对比</p>'); return; }}
  var h='<div class="an-section"><table class="an-table">';
  h+=analysisRow(['你的订阅','月付(USD)','同类最低价','差价','建议'],true);
  active.forEach(function(s){{
    var p=getProduct(s.product_key); if(!p) return;
    var myMonthly=s.billing_cycle==='yearly'?s.price_paid/12:s.price_paid;
    var myUsd=toUsd(myMonthly,s.currency);
    var sameCat=PRODUCTS.filter(function(pp){{ return pp.category===p.category; }});
    var cheapest=null, cheapestUsd=Infinity;
    sameCat.forEach(function(pp){{
      (pp.plans||[]).forEach(function(plan){{
        if(plan.price!=null && plan.price>0){{
          var pu=toUsd(plan.price,plan.currency||'USD');
          if(pu<cheapestUsd){{ cheapestUsd=pu; cheapest=pp; cheapestTier=plan; }}
        }}
      }});
    }});
    var diff=myUsd-cheapestUsd;
    var advice;
    if(diff>5) advice='🔻 可考虑切换到'+(cheapest?cheapest.display_name:'')+(cheapestTier?' '+cheapestTier.tier:'');
    else if(diff<-5) advice='✅ 当前价格有优势';
    else advice='➖ 价格相近';
    h+=analysisRow([
      '<b>'+esc(p.display_name)+'</b> '+esc(s.tier),
      fmtUsd(myUsd),
      (cheapest?esc(cheapest.display_name)+' '+(cheapestTier?esc(cheapestTier.tier):''):'-')+'<br><span style="color:var(--success);font-weight:600">'+fmtUsd(cheapestUsd)+'</span>',
      diff>0?'+':''+fmtUsd(diff),
      advice
    ]);
  }});
  h+='</table></div>';
  openAnalysis('💰 同类比价',h);
}}

function showOverlap(){{
  var active=subs.filter(function(s){{ return s.status==='active'; }});
  if(active.length<2){{ openAnalysis('🔗 重叠检测','<p style="color:var(--text2)">至少需要2条活跃订阅才能检测重叠</p>'); return; }}
  var subProducts=active.map(function(s){{
    var p=getProduct(s.product_key);
    return {{ sub:s, product:p, tags:new Set((p&&p.tags)||[]) }};
  }}).filter(function(sp){{ return sp.product; }});
  var overlaps=[];
  for(var i=0;i<subProducts.length;i++){{
    for(var j=i+1;j<subProducts.length;j++){{
      var a=subProducts[i], b=subProducts[j];
      var shared=[];
      a.tags.forEach(function(t){{ if(b.tags.has(t)) shared.push(t); }});
      if(shared.length>0){{
        overlaps.push({{ a:a, b:b, shared:shared }});
      }}
    }}
  }}
  if(overlaps.length===0){{
    openAnalysis('🔗 重叠检测','<div class="an-note">✅ 当前订阅之间未发现功能重叠，组合合理。</div>');
    return;
  }}
  var h='<div class="an-section">';
  overlaps.forEach(function(o){{
    h+='<div class="an-overlap">';
    h+='<div class="an-overlap-pair"><b>'+esc(o.a.product.display_name)+'</b> ⚡ <b>'+esc(o.b.product.display_name)+'</b></div>';
    h+='<div class="an-overlap-tags">'+o.shared.map(function(t){{ return '<span class="tag">'+esc(t)+'</span>'; }}).join('')+'</div>';
    h+='</div>';
  }});
  h+='</div>';
  h+='<div class="an-alert">💡 以上订阅存在功能重叠，可根据实际使用频率考虑保留其一以节省开支。</div>';
  openAnalysis('🔗 重叠检测',h);
}}

// ── Modal ──
function openAdd(){{
  document.getElementById('editIdx').value=-1;
  document.getElementById('modalTitle').textContent='添加订阅';
  document.getElementById('submitBtn').textContent='添加';
  document.getElementById('subForm').reset();
  document.getElementById('fStartDate').value=todayStr();
  document.getElementById('fAutoRenew').classList.add('on');
  document.getElementById('fTier').innerHTML='<option value="">-- 先选择产品 --</option>';
  document.getElementById('modalOverlay').classList.add('active');
}}
function openEdit(idx){{
  var s=subs[idx]; if(!s) return;
  document.getElementById('editIdx').value=idx;
  document.getElementById('modalTitle').textContent='编辑订阅';
  document.getElementById('submitBtn').textContent='保存';
  // set product
  var ps=document.getElementById('fProduct');
  var found=false;
  for(var i=0;i<ps.options.length;i++){{
    if(ps.options[i].value===s.product_key){{ ps.selectedIndex=i; found=true; break; }}
  }}
  if(!found) ps.selectedIndex=0;
  onProductChange(s.tier,s.price_paid,s.currency,s.billing_cycle);
  document.getElementById('fStartDate').value=s.start_date||todayStr();
  document.getElementById('fNextBill').value=s.next_billing_date||'';
  document.getElementById('fPayment').value=s.payment_method||'';
  document.getElementById('fNotes').value=s.notes||'';
  var tg=document.getElementById('fAutoRenew');
  if(s.auto_renew) tg.classList.add('on'); else tg.classList.remove('on');
  document.getElementById('modalOverlay').classList.add('active');
}}
function closeModal(){{ document.getElementById('modalOverlay').classList.remove('active'); }}

function onProductChange(pTier,pPrice,pCur,pBill){{
  var pk=document.getElementById('fProduct').value;
  var ts=document.getElementById('fTier');
  ts.innerHTML='<option value="">-- 选择套餐 --</option>';
  if(!pk) return;
  var p=getProduct(pk); if(!p) return;
  p.plans.forEach(function(plan){{
    var o=document.createElement('option');
    var ps=plan.price!=null&&plan.price>0?(SYMBOLS[plan.currency]||plan.currency)+plan.price+'/月':'免费';
    o.value=plan.tier;
    o.textContent=plan.tier+' — '+ps;
    o.dataset.price=plan.price||0;
    o.dataset.currency=plan.currency||'USD';
    o.dataset.billing=plan.billing_cycle||'monthly';
    if(pTier&&plan.tier===pTier) o.selected=true;
    ts.appendChild(o);
  }});
  onTierChange(pPrice,pCur,pBill);
}}

function onTierChange(pPrice,pCur,pBill){{
  var ts=document.getElementById('fTier');
  var opt=ts.options[ts.selectedIndex];
  if(!opt||!opt.value) return;
  if(pPrice!==undefined&&pPrice!==null){{
    document.getElementById('fPrice').value=pPrice;
    document.getElementById('fCurrency').value=pCur||'USD';
    document.getElementById('fBilling').value=pBill||'monthly';
  }} else {{
    document.getElementById('fPrice').value=parseFloat(opt.dataset.price)||0;
    document.getElementById('fCurrency').value=opt.dataset.currency;
    document.getElementById('fBilling').value=opt.dataset.billing;
  }}
}}

function handleSubmit(e){{
  e.preventDefault();
  var idx=parseInt(document.getElementById('editIdx').value);
  var pk=document.getElementById('fProduct').value;
  var tier=document.getElementById('fTier').value;
  var price=parseFloat(document.getElementById('fPrice').value);
  var cur=document.getElementById('fCurrency').value;
  var bill=document.getElementById('fBilling').value;
  var sd=document.getElementById('fStartDate').value;
  var nb=document.getElementById('fNextBill').value;
  var pm=document.getElementById('fPayment').value||'信用卡';
  var notes=document.getElementById('fNotes').value;
  var ar=document.getElementById('fAutoRenew').classList.contains('on');
  if(!pk||!tier||isNaN(price)||!sd){{ alert('请填写所有必填项'); return false; }}
  if(!nb) nb=bill==='yearly'?addMonths(sd,12):addMonths(sd,1);
  var sub={{
    product_key:pk, tier:tier, price_paid:price, currency:cur,
    billing_cycle:bill, start_date:sd, next_billing_date:nb,
    payment_method:pm, notes:notes, auto_renew:ar, status:'active'
  }};
  if(idx>=0) subs[idx]=sub; else subs.push(sub);
  closeModal(); render();
  return false;
}}

// ── Delete ──
var delIdx=-1;
function confirmDel(idx){{
  delIdx=idx;
  var s=subs[idx]; var p=getProduct(s.product_key);
  var name=p?p.display_name:s.product_key;
  document.getElementById('confirmText').textContent=
    '确定删除「'+name+' '+s.tier+'」订阅？此操作不可撤销。';
  document.getElementById('confirmOverlay').classList.add('active');
  document.getElementById('confirmDelBtn').onclick=function(){{
    subs.splice(delIdx,1); closeConfirm(); render();
  }};
}}
function closeConfirm(){{ document.getElementById('confirmOverlay').classList.remove('active'); delIdx=-1; }}

// ── Export ──
function exportData(){{
  var blob=new Blob([JSON.stringify(subs,null,2)],{{type:'application/json'}});
  var a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download='subscriptions.json';
  a.click();
  URL.revokeObjectURL(a.href);
  showToast('📥 已导出 '+subs.length+' 条订阅数据');
}}

// ── Init ──
render();
</script>
</body>
</html>'''
    return html


if __name__ == '__main__':
    main()
