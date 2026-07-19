# Telegram bot (legacy entry)

Рабочий бот по-прежнему запускается из корня:

```bash
python main.py
```

SaaS API/worker — отдельно (`docker compose up` или uvicorn + arq).

Связка с кабинетом: `core.compat.bot_bridge.create_telegram_link_code(tg_id)`.
