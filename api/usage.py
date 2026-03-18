"""
Vercel Serverless Function — Дашборд потребления токенов.
GET /api/usage — красивая HTML-страница со статистикой.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.supabase_client import get_usage_stats


def _format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _build_html(stats: dict) -> str:
    total_cost = stats["total_cost_usd"]
    total_tokens = stats["total_tokens"]
    total_requests = stats["total_requests"]

    # По моделям — строки таблицы
    model_rows = ""
    for model, data in sorted(stats["by_model"].items(), key=lambda x: x[1]["cost_usd"], reverse=True):
        model_rows += f"""
        <tr>
            <td>{model}</td>
            <td>{data['requests']}</td>
            <td>{_format_number(data['input_tokens'])}</td>
            <td>{_format_number(data['output_tokens'])}</td>
            <td>${data['cost_usd']:.4f}</td>
        </tr>"""

    # По дням — строки таблицы
    day_rows = ""
    for day, data in list(stats["by_day"].items())[:14]:
        day_rows += f"""
        <tr>
            <td>{day}</td>
            <td>{data['requests']}</td>
            <td>{_format_number(data['tokens'])}</td>
            <td>${data['cost_usd']:.4f}</td>
        </tr>"""

    # Последние запросы
    recent_rows = ""
    for r in stats["recent"][:15]:
        ts = r.get("created_at", "")[:19].replace("T", " ")
        recent_rows += f"""
        <tr>
            <td>{ts}</td>
            <td>{r.get('model', '?')}</td>
            <td>{r.get('input_tokens', 0)}</td>
            <td>{r.get('output_tokens', 0)}</td>
            <td>${float(r.get('cost_usd', 0)):.4f}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Therapist — Usage</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            padding: 24px;
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 24px;
            color: #fff;
        }}
        h2 {{
            font-size: 16px;
            font-weight: 600;
            margin: 32px 0 12px;
            color: #aaa;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 8px;
        }}
        .card {{
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            padding: 20px;
        }}
        .card .label {{
            font-size: 13px;
            color: #888;
            margin-bottom: 4px;
        }}
        .card .value {{
            font-size: 28px;
            font-weight: 700;
            color: #fff;
        }}
        .card .value.cost {{
            color: #4ade80;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 8px;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #1a1a1a;
            font-size: 14px;
        }}
        th {{
            color: #888;
            font-weight: 500;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        tr:hover td {{
            background: #111;
        }}
        .empty {{
            color: #555;
            padding: 40px;
            text-align: center;
        }}
        .refresh {{
            display: inline-block;
            margin-top: 32px;
            padding: 10px 20px;
            background: #222;
            border: 1px solid #333;
            border-radius: 8px;
            color: #aaa;
            text-decoration: none;
            font-size: 14px;
        }}
        .refresh:hover {{
            background: #2a2a2a;
            color: #fff;
        }}
    </style>
</head>
<body>
    <h1>🧠 AI Therapist — Usage Dashboard</h1>

    <div class="cards">
        <div class="card">
            <div class="label">Всего запросов</div>
            <div class="value">{total_requests}</div>
        </div>
        <div class="card">
            <div class="label">Всего токенов</div>
            <div class="value">{_format_number(total_tokens)}</div>
        </div>
        <div class="card">
            <div class="label">Общий расход</div>
            <div class="value cost">${total_cost:.4f}</div>
        </div>
    </div>

    <h2>По моделям</h2>
    {"<table><thead><tr><th>Модель</th><th>Запросы</th><th>Input</th><th>Output</th><th>Стоимость</th></tr></thead><tbody>" + model_rows + "</tbody></table>" if model_rows else '<div class="empty">Нет данных</div>'}

    <h2>По дням</h2>
    {"<table><thead><tr><th>Дата</th><th>Запросы</th><th>Токены</th><th>Стоимость</th></tr></thead><tbody>" + day_rows + "</tbody></table>" if day_rows else '<div class="empty">Нет данных</div>'}

    <h2>Последние запросы</h2>
    {"<table><thead><tr><th>Время</th><th>Модель</th><th>Input</th><th>Output</th><th>Стоимость</th></tr></thead><tbody>" + recent_rows + "</tbody></table>" if recent_rows else '<div class="empty">Нет данных</div>'}

    <a href="/api/usage" class="refresh">🔄 Обновить</a>
</body>
</html>"""


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            stats = get_usage_stats()
            html = _build_html(stats)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
