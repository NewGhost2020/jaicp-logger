# jaicp-logger

Сервис приёма, хранения и просмотра логов сессий JAICP-ботов. Заменяет webhook.site:
боты шлют батчи событий, сервис их хранит (SQLite) и отдаёт веб-UI с фильтрами и поиском.

- **Прод:** <https://labaicode.ru/> (UI, Basic Auth), `https://labaicode.ru/api/v1/events` (ingest)
- **Стек:** FastAPI + SQLAlchemy + SQLite + Jinja2, запуск через uvicorn под systemd
- **Размещение:** VPS `/opt/jaicp-logs`, systemd-юнит `jaicp-logs`, пользователь `jaicplogs`

## Эндпоинты

| Метод | Путь | Auth | Назначение |
|---|---|---|---|
| `POST` | `/api/v1/events` | `X-Bot-Token` | приём батча событий |
| `GET` | `/api/v1/health` | — | healthcheck |
| `GET` | `/api/v1/sessions` | Basic | список сессий (фильтры) |
| `GET` | `/api/v1/sessions/{id}` | Basic | сессия + все события |
| `GET` | `/` , `/session/{id}` | Basic | веб-UI |

## Мультибот

Каждый бот идентифицируется своим `bot_id` и шлёт события со **своим токеном**.
Токен жёстко привязан к `bot_id`: если в теле запроса `bot_id` не совпадает с тем, что
зашит за токеном, ingest отвечает `403` — подделать чужой `bot_id` нельзя.

Реестр ботов хранится в переменной `BOT_TOKENS` в `.env` (единый источник правды —
и токен, и отображаемое имя в одном месте):

```jsonc
BOT_TOKENS={"tema-bot": {"token": "<64-hex>", "name": "Тёма (Telematika)"}}
```

Допустима краткая форма `{"bot_id": "<token>"}` — тогда имя в UI = `bot_id`.

Имя бота используется в выпадашке фильтра и в колонке «Бот» веб-UI.

### Как добавить нового бота

1. **Сгенерировать токен:**
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Дописать запись в `BOT_TOKENS`** в `/opt/jaicp-logs/.env`. Поскольку строка — JSON,
   правьте через Python, чтобы не сломать кавычки/кириллицу:
   ```bash
   python3 - <<'PY'
   import json
   path = "/opt/jaicp-logs/.env"
   lines = open(path).read().splitlines()
   for i, ln in enumerate(lines):
       if ln.startswith("BOT_TOKENS="):
           reg = json.loads(ln[len("BOT_TOKENS="):])
           reg["shop-bot"] = {"token": "<новый-токен>", "name": "Магазин"}
           lines[i] = "BOT_TOKENS=" + json.dumps(reg, ensure_ascii=False)
           break
   open(path, "w").write("\n".join(lines) + "\n")
   print("OK")
   PY
   ```

3. **Перезапустить сервис:**
   ```bash
   systemctl restart jaicp-logs
   ```

4. **Прописать токен в скрипте бота** (`functions.js`):
   ```javascript
   var LOG_BOT_ID = 'shop-bot';
   var LOG_BOT_TOKEN = '<новый-токен>';
   ```

После первого батча бот появится в выпадашке UI под своим именем.

> `LOG_INGEST_TOKEN` — legacy-общий токен (wildcard, разрешает любой `bot_id`).
> Оставлять **пустым**: он отключает изоляцию и нужен только на время миграции.

## Локальный запуск

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # затем отредактировать (см. ниже)
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Тесты:
```bash
pip install -r requirements-dev.txt
pytest -q
```

## Переменные окружения (`.env`)

| Переменная | Назначение |
|---|---|
| `BOT_TOKENS` | JSON-реестр ботов `{bot_id: {token, name}}` (см. «Мультибот») |
| `LOG_INGEST_TOKEN` | legacy-wildcard токен, держать пустым |
| `BASIC_AUTH_USERS` | JSON `{логин: bcrypt-хэш}` для входа в UI |
| `BASIC_AUTH_USER` / `BASIC_AUTH_PASS_HASH` | одиночный пользователь (fallback, если `BASIC_AUTH_USERS` пуст) |
| `DATABASE_URL` | строка подключения SQLite |
| `TZ_DISPLAY` | таймзона отображения в UI (`Europe/Moscow`) |
| `SESSION_ABANDON_HOURS` | через сколько часов простоя сессия → `abandoned` |
| `RETENTION_DAYS` / `BATCHES_RETENTION_DAYS` | срок хранения сессий/событий и батчей |

Хэш пароля для UI:
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'ВАШ_ПАРОЛЬ', bcrypt.gensalt(12)).decode())"
```

## Деплой

VPS `/opt/jaicp-logs` — git-checkout этого репозитория:

```bash
git -C /opt/jaicp-logs pull
/opt/jaicp-logs/venv/bin/pip install -r /opt/jaicp-logs/requirements.txt   # при изменении зависимостей
systemctl restart jaicp-logs
journalctl -u jaicp-logs -f                                                 # логи
```
