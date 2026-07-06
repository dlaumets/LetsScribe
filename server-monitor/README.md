# Server Monitor

Отдельный Telegram-бот для мониторинга VPS. **Не входит** в Docker Compose LetsScribe.

## Что мониторит

- Сервер: CPU load, RAM, swap, диск
- Docker-контейнеры (в т.ч. LetsScribe)
- CPV Bot (systemd)
- VPN (awg0)

## Установка на VPS

```bash
cd server-monitor
cp .env.example /opt/server-monitor/.env   # или отредактируй существующий
# пропиши MONITOR_BOT_TOKEN и MONITOR_ALLOWED_IDS
sudo bash setup.sh
```

Сервис: `systemctl status server-monitor`  
Файлы: `/opt/server-monitor/`

## Команды бота

| Команда | Описание |
|---------|----------|
| `/status` | Текст + графики (PNG) |
| `/graphs` | Только графики |
| `/server` | Сервер |
| `/scribe` | LetsScribe |
| `/transcriber` | LetsScribe (alias) |
| `/docker` | Docker |
| `/cpv` | CPV Bot |
| `/vpn` | VPN |

## Обновление

```bash
cd /opt/letsscribe/server-monitor   # или где лежит репозиторий
git pull
sudo bash setup.sh
```

`.env` на сервере при этом не перезаписывается.
