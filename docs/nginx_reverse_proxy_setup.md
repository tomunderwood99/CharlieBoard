# nginx Reverse Proxy Setup

Set up nginx so you can access the web interface at `http://hostname.local` instead of `http://hostname.local:8000`.

## Installation

### 1. Install nginx

```bash
sudo apt update
sudo apt install nginx -y
```

### 2. Create Configuration

```bash
sudo nano /etc/nginx/sites-available/mbta-display
```

Add:
```nginx
server {
    listen 80;
    listen [::]:80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### 3. Enable Configuration

```bash
sudo ln -s /etc/nginx/sites-available/mbta-display /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
```

Should show "syntax is ok" and "test is successful".

### 4. Start nginx

```bash
sudo systemctl enable nginx
sudo systemctl restart nginx
sudo systemctl status nginx
```

### 5. Verify

Access your display at `http://hostname.local` (no port needed).

## Optional: Pi Zero 2W Optimization

```bash
sudo nano /etc/nginx/nginx.conf
```

Set `worker_processes 1;` and add to `http` block:
```nginx
keepalive_timeout 15;
keepalive_requests 100;
client_body_buffer_size 10K;
client_header_buffer_size 1k;
client_max_body_size 8m;
large_client_header_buffers 2 1k;
```

Then: `sudo systemctl restart nginx`

## Coexistence with the headless WiFi helper

If you also installed [`tomunderwood99/headless_wifi_helper`](https://github.com/tomunderwood99/headless_wifi_helper)
via `setup_mbta_controller.sh --with-wifi-helper`, both services want port 80,
but on a normal boot they don't actually fight over it:

- The helper's captive portal binds to `192.168.4.1:80` (the AP gateway IP),
  not `0.0.0.0`, and only when `wifi_configurator.service` decides to bring
  the AP up because no known WiFi is in range.
- `wifi_configurator.service` is `Before=network-online.target`, and nginx
  effectively starts after `network-online.target` is reached. So while the
  captive portal is up, nginx is *not* running yet — no conflict.
- Once WiFi is up, the helper exits, the AP comes down, and nginx then binds
  port 80 on `0.0.0.0` (which includes wlan0's normal client IP).

The one case where they collide is if you manually start
`wifi_configurator.service` after the system is already up (e.g., for testing
the portal). nginx will already own port 80 on `0.0.0.0`, which includes
`192.168.4.1` once the AP comes up, and the portal will fail to bind with an
`OSError: [Errno 98] Address already in use` in `journalctl -u wifi_configurator`.
If you need to test the portal manually, stop nginx first:

```bash
sudo systemctl stop nginx
sudo systemctl start wifi_configurator.service
# When done:
sudo systemctl stop wifi_configurator.service
sudo systemctl start nginx
```

This is a manual-testing-only edge case; the normal boot path is conflict-free.

## Troubleshooting

| Problem | Check |
|---------|-------|
| nginx won't start | `sudo tail -f /var/log/nginx/error.log` |
| Can't access web | Is Flask running? `sudo netstat -tlnp \| grep 8000` |
| Port 80 in use | `sudo rm /etc/nginx/sites-enabled/default` |
| Config test fails | `sudo nginx -t` shows which line has error |
| `wifi_configurator` won't bind 80 | nginx already owns it — see [Coexistence](#coexistence-with-the-headless-wifi-helper) |

## Useful Commands

```bash
sudo systemctl restart nginx    # Restart
sudo systemctl reload nginx     # Reload config without downtime
sudo nginx -t                   # Test configuration
sudo tail -f /var/log/nginx/error.log   # View errors
sudo tail -f /var/log/nginx/access.log  # View access log
```

## Uninstalling

```bash
sudo systemctl stop nginx
sudo systemctl disable nginx
sudo apt remove nginx nginx-common -y
sudo apt autoremove -y
```
