## systemd setup (ninavpn-bot)

The repository already contains `ninavpn-bot.service` expecting:
- code in `/opt/ninavpn-bot`
- venv at `/opt/ninavpn-bot/venv`

### Install / enable / start

```bash
sudo cp /opt/ninavpn-bot/ninavpn-bot.service /etc/systemd/system/ninavpn-bot.service
sudo systemctl daemon-reload
sudo systemctl enable ninavpn-bot
sudo systemctl start ninavpn-bot
sudo systemctl --no-pager status ninavpn-bot
```

### Logs

```bash
sudo journalctl -u ninavpn-bot -f
```

### Quick smoke checks

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/payment/success
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/miniapp/api/plans
```

