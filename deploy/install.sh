#!/bin/bash
# Деплой jaicp-logger на VPS Beget (31.129.102.58)
# Запускать от root: bash deploy/install.sh
set -euo pipefail

APP_DIR=/opt/jaicp-logs
REPO=https://github.com/NewGhost2020/jaicp-logger.git
SERVICE=jaicp-logs
USER=jaicplogs

echo "=== 1. Системный пользователь ==="
id "$USER" &>/dev/null || useradd -r -s /sbin/nologin "$USER"

echo "=== 2. Клонирование/обновление репозитория ==="
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull
else
    git clone "$REPO" "$APP_DIR"
fi

echo "=== 3. Виртуальное окружение ==="
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "=== 4. Директория данных ==="
mkdir -p "$APP_DIR/data"
chown -R "$USER:$USER" "$APP_DIR"
chmod 750 "$APP_DIR"

echo "=== 5. Файл .env ==="
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "ВАЖНО: отредактируй $APP_DIR/.env — задай LOG_INGEST_TOKEN и BASIC_AUTH_PASS_HASH"
    echo "       Сгенерировать хэш пароля:"
    echo "       $APP_DIR/venv/bin/python -c \"from passlib.hash import bcrypt; print(bcrypt.hash('ВАШ_ПАРОЛЬ'))\""
fi

echo "=== 6. Alembic миграции ==="
(cd "$APP_DIR" && "$APP_DIR/venv/bin/alembic" upgrade head)

echo "=== 7. Systemd сервис ==="
cp "$APP_DIR/deploy/jaicp-logs.service" /etc/systemd/system/"$SERVICE".service
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
systemctl status "$SERVICE" --no-pager

echo "=== 8. Nginx конфиг ==="
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/"$SERVICE"
ln -sf /etc/nginx/sites-available/"$SERVICE" /etc/nginx/sites-enabled/"$SERVICE"
nginx -t && systemctl reload nginx

echo ""
echo "=== Готово! ==="
echo "Сервис: http://31.129.102.58/"
echo "Health: http://31.129.102.58/api/v1/health"
echo "Логи:   journalctl -u $SERVICE -f"
