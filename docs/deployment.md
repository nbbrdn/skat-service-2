# Развёртывание SKAT Service на Ubuntu 24.04 LTS

Caddy работает на хосте через systemd и принимает HTTP/HTTPS на портах 80 и 443. Gunicorn слушает внутри контейнера, Docker публикует его только на `127.0.0.1:18080`. PostgreSQL 17 подключён только к внутренней сети Compose и хранит данные в именованном томе. WhiteNoise отдаёт статику из образа.

На подготовленном сервере с настроенным доступом для `nb`, Docker Compose, UFW и HTTPS начните с раздела 4. Разделы 1–3 относятся к настройке новой ВМ.

## 1. Ubuntu, SSH и firewall

В первой SSH-сессии на ВМ выполните под исходным администратором:

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl gnupg git ufw dnsutils openssl
sudo adduser nb
sudo usermod -aG sudo nb
sudo install -d -m 0700 -o nb -g nb /home/nb/.ssh
sudoedit /home/nb/.ssh/authorized_keys
sudo chown nb:nb /home/nb/.ssh/authorized_keys
sudo chmod 0600 /home/nb/.ssh/authorized_keys
```

Вставьте публичный ключ своего компьютера в `authorized_keys`. С рабочего компьютера, сохраняя первую сессию открытой, проверьте отдельный вход и `sudo`. Замените `VM_IP` на публичный IPv4-адрес ВМ.

```bash
ssh nb@VM_IP
sudo -v
```

Дальнейшие команды на ВМ выполняются как `nb`. Для стандартного SSH-порта 22:

```bash
sudo tee /etc/ssh/sshd_config.d/00-skat-hardening.conf >/dev/null <<'CONFIG'
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
CONFIG
sudo sshd -t && sudo systemctl reload ssh
sudo sshd -T | awk '/^(permitrootlogin|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication) /'
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

При нестандартном SSH-порте замените 22 и в правилах ВМ, и в firewall провайдера. Откройте там также TCP 80 и 443. Снова проверьте отдельный вход по ключу, прежде чем закрывать первую сессию. Если обновления требуют перезагрузки, выполните `sudo reboot` после проверки доступа и подключитесь снова.

## 2. Docker Engine и Compose Plugin

На ВМ под `nb`, из любого каталога:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<CONFIG
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $VERSION_CODENAME
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
CONFIG
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

Используйте Docker Engine 28 или новее для ограничения опубликованного loopback-порта. Docker управляет собственными сетевыми правилами, поэтому проверяйте адрес публикации в Compose и доступность портов извне. Команды ниже используют `sudo docker`.

## 3. Caddy и DNS

Установите Caddy из официального стабильного APT-репозитория:

```bash
sudo install -d -m 0755 /usr/share/keyrings
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
sudo chmod a+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update
sudo apt-get install -y caddy
sudo systemctl enable --now caddy
```

У DNS-провайдера создайте A-запись `service.skatpower.ru` на публичный IPv4 ВМ. При наличии AAAA-записи проверьте, что соответствующий IPv6 также ведёт на эту ВМ и доступен на 80/443, либо удалите устаревшую запись. Проверьте ответы публичного DNS:

```bash
dig @1.1.1.1 +short A service.skatpower.ru
dig @1.1.1.1 +short AAAA service.skatpower.ru
```

## 4. Первый запуск приложения

Подключитесь по SSH как `nb`. Клонируйте репозиторий от root в новый каталог. Для закрытого репозитория настройте доступ на чтение для Git, запущенного через `sudo`.

```bash
sudo -H sh -c 'umask 022 && git clone --branch main https://github.com/nbbrdn/skat-service-2.git /opt/skat-service'
cd /opt/skat-service
sudo namei -l /opt/skat-service/deploy/backup-postgres.sh
sudo find /opt/skat-service \
    \( ! -user root -o ! -group root -o \( ! -type l -perm /022 \) \) -ls
```

У каталогов в цепочке пути и у скрипта ожидаются владелец и группа `root:root` и право записи только у владельца. Команда `find` должна завершиться успешно без вывода. Устраните расхождения перед запуском Compose или настройкой cron. Пользователь `nb` выполняет административные команды через `sudo`.

Из `/opt/skat-service` один раз создайте `.env` с двумя независимыми секретами. Сначала убедитесь, что `git check-ignore` выводит `.env`.

```bash
sudo git check-ignore -- .env
sudo python3 - <<'PY'
import os
import secrets
from pathlib import Path

os.umask(0o077)
template = Path("deploy/.env.prod.example").read_text()
for name in ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD"):
    template = template.replace(f"{name}=\n", f"{name}={secrets.token_urlsafe(64)}\n")
with Path(".env").open("x") as env_file:
    env_file.write(template)
PY
sudo test -s .env
sudo stat -c '%U:%G %a %n' .env
```

Ожидаемые владелец и права для `.env` — `root:root 600`. Для редактирования используйте `sudoedit /opt/skat-service/.env`.

```bash
sudo docker compose -f compose.prod.yaml config --quiet
sudo docker compose -f compose.prod.yaml up -d --wait db
sudo docker compose -f compose.prod.yaml build web
sudo docker compose -f compose.prod.yaml run --rm web python manage.py check --deploy --fail-level ERROR
sudo docker compose -f compose.prod.yaml run --rm web python manage.py migrate --noinput
sudo docker compose -f compose.prod.yaml up -d --build
sudo docker compose -f compose.prod.yaml exec web python manage.py createsuperuser
sudo docker compose -f compose.prod.yaml ps
```

При ошибке команды остановитесь и устраните причину, прежде чем переходить к следующей. Используйте `config --quiet`, чтобы не выводить интерполированные секреты. Храните `.env` с правами 0600. Замена `POSTGRES_PASSWORD` в файле после первого запуска требует отдельной смены пароля роли в существующем PostgreSQL. Проверка Django может вывести два ожидаемых предупреждения `security.W005` и `security.W021`: HSTS применяется к текущему домену, preload выключен. Compose фиксирует `DJANGO_DEBUG=0`, запускает Gunicorn без миграций и собирает статику при сборке образа. Значение `GUNICORN_GRACEFUL_TIMEOUT` должно быть меньше `stop_grace_period` в Compose (60 секунд по умолчанию).

## 5. HTTPS и приёмка

В существующей конфигурации Caddy добавьте или обновите блок `service.skatpower.ru` по образцу `deploy/Caddyfile.example`, сохранив остальные сайты и настройки. На новой ВМ без других сайтов можно установить образец командой `sudo install -m 0644 deploy/Caddyfile.example /etc/caddy/Caddyfile` из `/opt/skat-service`.

```bash
cd /opt/skat-service
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
sudo journalctl -u caddy -b -n 100 --no-pager
sudo docker compose -f compose.prod.yaml logs --tail=100 web db
```

Caddy получает сертификат после применения конфигурации и сам его продлевает. С внешнего компьютера:

```bash
curl -sSI http://service.skatpower.ru/health/
curl -fsS https://service.skatpower.ru/health/
curl -fsSI https://service.skatpower.ru/admin/login/
openssl s_client -connect service.skatpower.ru:443 -servername service.skatpower.ru -verify_hostname service.skatpower.ru -verify_return_error </dev/null
openssl s_client -connect service.skatpower.ru:443 -servername service.skatpower.ru </dev/null 2>/dev/null | openssl x509 -noout -issuer -subject -dates
```

Ожидайте перенаправление на HTTPS, ответ `ok` и валидный сертификат. Для контроля продления на ВМ проверяйте журнал командой `sudo journalctl -u caddy --since '30 days ago' --no-pager` и сравнивайте срок сертификата тем же запросом OpenSSL после очередного продления. Начальный HSTS составляет один час и относится к текущему домену. После проверки HTTPS увеличьте `DJANGO_HSTS_SECONDS` до `31536000` через `sudoedit /opt/skat-service/.env` и пересоздайте web командой `sudo docker compose -f compose.prod.yaml up -d --no-build web`. Caddy заменяет `X-Forwarded-Proto` значением, полученным из соединения. Сохраняйте доступ к Gunicorn через loopback и допускайте в сеть БД только доверенные контейнеры.

С внешнего компьютера проверьте, что `curl --connect-timeout 3 http://VM_IP:18080/health/` и `nc -vz -w 3 VM_IP 5432` не подключаются. В браузере войдите в Admin по HTTPS и проверьте стили, создайте обычную учётную запись и тестовую позицию с остатком. Войдите обычной учётной записью и проверьте каталог, корзину, оформление тестового заказа и его появление в истории. Проверьте наличие `Secure` у `sessionid` и `csrftoken`, `HttpOnly` у `sessionid` и отсутствие запросов к CDN в панели Network. Для проверки CSRF отправьте POST без токена и ожидайте 403:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST https://service.skatpower.ru/login/
```

`/health/` проверяет обработку запроса приложением. Для контроля БД проверяйте статус `db` в выводе `sudo docker compose -f compose.prod.yaml ps` и выполняйте функциональные проверки отдельно.

## 6. Резервное копирование и проверка восстановления

`pg_dump` снимает согласованную копию работающей базы. Скрипт использует локальный Unix-сокет PostgreSQL внутри контейнера с аутентификацией стандартного образа, проверяет успешность выгрузки и читаемость оглавления архива. Скрипт определяет каталог проекта по своему расположению. При запуске от root готовые копии принадлежат root и имеют права `0600`. Именованный том хранит рабочие данные. Для защиты при потере ВМ храните копии также на независимом хранилище.

На ВМ под `nb`:

```bash
sudo install -d -m 0700 -o root -g root /var/backups/skat-service
sudo env BACKUP_DIR=/var/backups/skat-service BACKUP_RETENTION_DAYS=14 /usr/bin/bash /opt/skat-service/deploy/backup-postgres.sh
sudo stat -c '%U:%G %a %n' /var/backups/skat-service
sudo ls -l /var/backups/skat-service
```

Для ежедневного запуска добавьте cron-задание. Перед установкой задания повторите проверку владельца и прав рабочей копии из раздела 4. Задание работает от root для доступа к Docker. Время 03:17 относится к часовому поясу ВМ.

```bash
sudo systemctl enable --now cron
sudo tee /etc/cron.d/skat-service-backup >/dev/null <<'CONFIG'
PATH=/usr/sbin:/usr/bin:/sbin:/bin
BACKUP_DIR=/var/backups/skat-service
BACKUP_RETENTION_DAYS=14
17 3 * * * root /usr/bin/bash -o pipefail -c '/usr/bin/bash /opt/skat-service/deploy/backup-postgres.sh 2>&1 | /usr/bin/logger -t skat-service-backup'
CONFIG
sudo chown root:root /etc/cron.d/skat-service-backup
sudo chmod 0644 /etc/cron.d/skat-service-backup
sudo stat -c '%U:%G %a %n' /etc/cron.d/skat-service-backup
sudo journalctl -t skat-service-backup --since today
```

Для пробного восстановления выберите имя файла из списка. Блок создаёт новую базу с уникальным именем в том же экземпляре PostgreSQL. Восстановление выполняется одной транзакцией. После успешного просмотра таблиц пробная база удаляется. При ошибке база остаётся для диагностики.

```bash
cd /opt/skat-service
(
    set -euo pipefail
    read -r -p 'Имя файла копии (skat-postgres-….dump): ' backup_file
    [[ "$backup_file" == skat-postgres-*.dump && "$backup_file" != */* ]]
    backup="/var/backups/skat-service/$backup_file"
    test_db="skat_restore_$(date +%s)_$$"
    compose=(sudo docker compose -f compose.prod.yaml)
    "${compose[@]}" exec -T db sh -ec 'createdb -w -U "$POSTGRES_USER" -T template0 "$1"' sh "$test_db"
    sudo cat -- "$backup" | "${compose[@]}" exec -T db sh -ec '
        pg_restore -w --single-transaction --exit-on-error -U "$POSTGRES_USER" -d "$1"
    ' sh "$test_db"
    "${compose[@]}" exec -T db sh -ec 'psql -w -U "$POSTGRES_USER" -d "$1" -c "\dt"' sh "$test_db"
    "${compose[@]}" exec -T db sh -ec 'dropdb -w -U "$POSTGRES_USER" "$1"' sh "$test_db"
)
```

Для аварийного восстановления остановите web командой `sudo docker compose -f compose.prod.yaml stop web`. Выберите копию, соответствующую версии приложения. Повторите блок с новой базой, пропустив последнюю команду `dropdb`, и запишите её имя. Сохраните старую базу и укажите имя восстановленной базы в `POSTGRES_DB` через `sudoedit /opt/skat-service/.env`. Запустите приложение командой `sudo docker compose -f compose.prod.yaml up -d --no-build` на версии кода, совместимой со схемой копии. Повторите приёмку. Если утрачена вся ВМ, сначала выполните начальную настройку до запуска здорового PostgreSQL. Снимок содержит данные одной БД, поэтому восстановите также используемую роль и пароль через настройку нового экземпляра и сохранённый `.env`.

## 7. Обновление из GitHub и восстановление после ошибки

Работайте из каталога репозитория и запланируйте окно обслуживания. Сначала проверьте чистоту рабочей копии и посмотрите входящие изменения.

```bash
cd /opt/skat-service
sudo git status --short
sudo -H git fetch origin main
sudo git log --oneline HEAD..origin/main
sudo git diff --stat HEAD..origin/main
old_rev=$(sudo git rev-parse HEAD)
sudo docker image tag skat-service-web:prod "skat-service-web:rollback-$old_rev"
printf 'Предыдущий коммит %s\n' "$old_rev"
```

Проверьте требования миграций и изменения в Compose, Caddy и примере окружения. Блок ниже останавливается при ошибке. Web останавливается перед финальной копией, чтобы в неё попали все записи, сделанные до обновления.

```bash
(
    set -eu
    umask 022
    sudo git merge --ff-only --no-overwrite-ignore origin/main
    sudo git check-ignore -- .env
    unexpected=$(sudo find /opt/skat-service \
        \( ! -user root -o ! -group root -o \( ! -type l -perm /022 \) \) -print -quit)
    test -z "$unexpected"
    test "$(sudo stat -c '%U:%G %a' .env)" = 'root:root 600'
    sudo docker compose -f compose.prod.yaml config --quiet
    sudo docker compose -f compose.prod.yaml build web
    sudo docker compose -f compose.prod.yaml stop web
    sudo /usr/bin/bash /opt/skat-service/deploy/backup-postgres.sh
    sudo docker compose -f compose.prod.yaml run --rm web python manage.py migrate --plan
    sudo docker compose -f compose.prod.yaml run --rm web python manage.py migrate --noinput
    sudo docker compose -f compose.prod.yaml up -d --no-build
    curl -fsS https://service.skatpower.ru/health/
)
```

Повторите приёмку. Если требуется обновление Caddyfile, сначала сохраните копию текущего файла, затем повторите установку, проверку и reload из раздела HTTPS.

При сбое проверьте `sudo docker compose -f compose.prod.yaml logs --tail=100 web db` и состояние миграций командой `sudo docker compose -f compose.prod.yaml run --rm web python manage.py showmigrations`. Если схема подтверждённо совместима со старым кодом, остановите web и верните прежние конфигурацию, образ и код. В той же оболочке, где задана переменная `old_rev`:

```bash
sudo docker compose -f compose.prod.yaml stop web
sudo git switch --no-overwrite-ignore --detach "$old_rev"
sudo docker image tag "skat-service-web:rollback-$old_rev" skat-service-web:prod
sudo docker compose -f compose.prod.yaml up -d --no-build
```

Перед следующим обновлением вернитесь на `main` командой `sudo git switch --no-overwrite-ignore main` и убедитесь, что причина сбоя исправлена в целевом коммите. Если схема несовместима, выберите исправление вперёд либо восстановите предмиграционную копию в новую БД по предыдущему разделу и запустите совместимую версию приложения. Оцените потери записей после момента копии и сохраните текущее состояние для диагностики. Избегайте автоматического отката миграций: часть операций над схемой и данными может быть необратимой. Не удаляйте именованный том во время обновления или диагностики.
