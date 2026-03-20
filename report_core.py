"""Общая логика: Telegram — только координаты со ссылками на карты (server.py и Vercel api/report)."""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.parse
import urllib.request


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


def telegram_send_message(
    token: str, chat_id: str, text: str, *, parse_mode: str | None = None
) -> None:
    token = normalize_telegram_token(token)
    chat_id = normalize_telegram_chat_id(chat_id)
    if not token or ":" not in token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN пустой или неверного формата (нужен вид 123456789:AAH… из @BotFather)."
        )
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID пустой.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    msg: dict = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        msg["parse_mode"] = parse_mode
    body = json.dumps(msg).encode("utf-8")
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


def _fmt_coord(n: float) -> str:
    s = f"{n:.8f}"
    return s.rstrip("0").rstrip(".")


def format_coordinates_telegram_html(lat: float, lon: float) -> str:
    """
    Короткое HTML для Telegram: координаты — ссылка на Google Maps;
    отдельные ссылки на Яндекс, Apple Maps, 2ГИС (по нажатию открывается карта с точкой, адрес виден в приложении карт).
    """
    lat_s = _fmt_coord(lat)
    lon_s = _fmt_coord(lon)
    label = f"{lat_s}, {lon_s}"
    query = urllib.parse.quote(f"{lat},{lon}")
    google = f"https://www.google.com/maps/search/?api=1&query={query}"
    yandex = f"https://yandex.ru/maps/?pt={lon},{lat}&z=16&l=map"
    apple = f"https://maps.apple.com/?ll={lat},{lon}"
    gis2 = f"https://2gis.ru/geo/{lon}%2C{lat}"

    def href(u: str) -> str:
        return html.escape(u, quote=True)

    label_e = html.escape(label, quote=False)
    return (
        f'📍 <a href="{href(google)}">{label_e}</a>\n'
        f'<a href="{href(yandex)}">Яндекс.Карты</a> · '
        f'<a href="{href(apple)}">Apple Maps</a> · '
        f'<a href="{href(gis2)}">2ГИС</a>'
    )


def send_telegram_report(token: str, chat_id: str, payload: dict) -> None:
    """Одно сообщение в Telegram: только координаты и ссылки на карты."""
    g = payload.get("geolocation") or {}
    lat, lon = g.get("latitude"), g.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        raise RuntimeError(
            "Нет координат: в запросе должны быть числовые geolocation.latitude и geolocation.longitude."
        )
    text = format_coordinates_telegram_html(float(lat), float(lon))
    telegram_send_message(token, chat_id, text, parse_mode="HTML")
