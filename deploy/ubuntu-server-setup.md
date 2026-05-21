## Ubuntu/Debian server setup (2.27.123.28 + ninavpn.store)

### 1) DNS
- Set `A` record: `ninavpn.store` → `2.27.123.28`

Wait until it resolves:

```bash
dig +short ninavpn.store
```

### 2) Install nginx + certbot

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 3) Issue TLS certificate (Let’s Encrypt)

When DNS is correct:

```bash
sudo certbot --nginx -d ninavpn.store
```

### 4) Install nginx vhost for the bot HTTP app

```bash
cd /opt/ninavpn-bot
sudo cp deploy/nginx/ninavpn.store.conf /etc/nginx/sites-available/ninavpn.store
sudo ln -sf /etc/nginx/sites-available/ninavpn.store /etc/nginx/sites-enabled/ninavpn.store
sudo nginx -t && sudo systemctl reload nginx
```

Checks:
- `curl -I https://ninavpn.store/payment/success` (should return 200/30x after bot is running)
- `curl -I https://ninavpn.store/miniapp/` (should return 200/404 depending on webapp presence; after bot is running it should serve files from `webapp/`)

