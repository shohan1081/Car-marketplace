# Nory Backend — AWS EC2 Deployment Runbook

Complete, command-by-command deployment of the Django API **and** the
`car-video-agent` FastAPI service onto a single AWS EC2 instance, using Docker
Compose, with code pulled from GitLab.

Every command below says *what it does* and *why you are running it*. Run them
in order. Nothing is optional unless it says so.

---

## 0. What you are about to build

```
                    Internet
                       |
                  :80  |  :443
                       v
              +------------------+
              |      nginx       |   TLS, static + media files,
              |   (only public   |   upload size limits, routing
              |    container)    |
              +--------+---------+
                       |
        /ws/ ----------+----------> [ ws ]    daphne   — chat + notifications
        everything ----+----------> [ web ]   gunicorn — REST API + admin
                                       |
                    +------------------+------------------+
                    |                  |                  |
                 [ db ]            [ redis ]          [ agent ]
              PostgreSQL       channel layer       FastAPI AI video
                                 + cache          (fal.ai + OpenAI)
```

**Key design points, and why:**

| Decision | Reason |
|---|---|
| Only nginx publishes ports | PostgreSQL, Redis and the AI agent are unreachable from the internet. An attacker cannot even attempt to connect to them. |
| gunicorn and daphne split | A slow REST request can never stall live chat, and each side scales on its own. |
| Redis is mandatory | `messaging/views.py` pushes to WebSocket clients from an ordinary HTTP request. With gunicorn and daphne in separate processes, the old in-memory channel layer would silently deliver nothing. |
| nginx serves `/media/` | Video reels are streamed by the kernel, with byte-range support for seeking, instead of occupying a Python worker for every frame. |
| Agent has no public port | The AI service holds your fal.ai and OpenAI keys. Django talks to it at `http://agent:8000`, entirely inside the server. |

---

## 1. Before you touch AWS

Have these ready:

- An AWS account with billing set up.
- A domain name you control, e.g. `api.buysoloio.com`. **You cannot get an
  HTTPS certificate for a raw EC2 IP address.**
- Your GitLab repository: `gitlab.betopialimited.com/join-venture-ai/nory_video-based/backend`
- Your production secrets: fal.ai key, OpenAI key, Gmail app password,
  Firebase service-account JSON, Apple/Google IAP credentials.

---

## 2. Create the EC2 instance

### 2.1 Pick a region

In the AWS Console top-right region selector, choose the region closest to your
**users**, not to yourself. Latency is decided here and cannot be changed later
without rebuilding the instance.

Your users are in the United States, so select:

```
US East (N. Virginia)   us-east-1
```

Why this one:

- Most of the US population and most US internet peering sit on the East Coast,
  so a single instance here serves the whole country reasonably. Round trip is
  roughly 20 ms from New York and 70 ms from California.
- It is in AWS's cheapest pricing tier, alongside `us-east-2` and `us-west-2`.
- Every instance type and service is available here first.

Alternatives, only if they fit you better:

| Region | Choose it when |
|---|---|
| `us-east-2` (Ohio) | You want the same price with a slightly better outage record than `us-east-1`, and a more central position. A reasonable second choice. |
| `us-west-2` (Oregon) | Your client and users are specifically West Coast. |

> Do **not** pick a region near you in Bangladesh. You will connect over SSH a
> handful of times a day and 250 ms of lag there costs you nothing, while every
> API call your users make would cross the planet twice.

### 2.2 Launch the instance

Go to **EC2 → Instances → Launch instances** and set:

**Name and tags**
```
Name: nory-backend-prod
```
Add a second tag `Environment = production`. Tags are how you find things and
split the bill later, when there are more than three instances in the account.

**Application and OS Image (AMI)**
```
Ubuntu Server 24.04 LTS (HVM), SSD Volume Type
Architecture: 64-bit (x86)
```
Ubuntu LTS gets security updates until 2029 and every Docker instruction below
is written for it. Stay on **x86**, not ARM/Graviton — some Python wheels in
`requirements.txt` are slower or unavailable on ARM.

**Instance type**
```
t3.medium   (2 vCPU, 4 GB RAM)   <- recommended
```
Why not smaller: you are running PostgreSQL, Redis, three gunicorn workers,
daphne, two uvicorn workers and nginx on one box, and `ffmpeg` briefly spikes
memory when validating an uploaded reel. `t3.small` (2 GB) will run but will
struggle during a Docker build. `t2.micro` (free tier, 1 GB) will not work.

**Key pair (login)**
1. Click **Create new key pair**.
2. Name: `nory-prod-key`
3. Type: **ED25519** (shorter and stronger than RSA).
4. Format: **.pem**
5. Download it. **This is the only copy AWS will ever give you.** Store it
   somewhere safe — losing it means losing SSH access to the instance.

**Network settings** → click **Edit**
```
VPC:               default VPC
Subnet:            any public subnet (e.g. us-east-1a)
Auto-assign public IP:  Enable
Firewall (security groups): Create security group
  Name:        nory-backend-sg
  Description: HTTP, HTTPS from anywhere; SSH from my IP only
```

Set the inbound rules exactly as follows — details in section 3.

**Configure storage**
```
1x  50 GiB  gp3  Root volume
    Delete on termination: Yes
    Encrypted: Yes  (use the default aws/ebs KMS key)
```
Why 50 GB: the two Docker images are roughly 2 GB, PostgreSQL and Redis are
small, but uploaded reels and AI-generated videos accumulate in the media
volume forever. 8 GB (the default) fills within weeks. gp3 is cheaper and
faster than gp2 — there is no reason to pick gp2.

**Advanced details** (scroll down)
```
Termination protection: Enable
```
This makes it impossible to delete the instance with a single misclick. You
can turn it off deliberately when you actually mean to destroy it.

Leave everything else at its default and click **Launch instance**.

### 2.3 Allocate an Elastic IP

A default EC2 public IP **changes every time the instance stops and starts**,
which would break your DNS record and your TLS certificate. An Elastic IP is
permanent.

1. **EC2 → Elastic IPs → Allocate Elastic IP address → Allocate**
2. Select the new address → **Actions → Associate Elastic IP address**
3. Resource type: **Instance** → choose `nory-backend-prod` → **Associate**

> An Elastic IP is free while it is attached to a running instance, and billed
> hourly when it is left unattached. Do not allocate spares.

Write the address down. Everything below calls it `<ELASTIC_IP>`.

### 2.4 Point your domain at it

In your DNS provider (Route 53, Cloudflare, Namecheap…):

```
Type: A     Name: api     Value: <ELASTIC_IP>     TTL: 300
```

If you use Cloudflare, set the record to **DNS only** (grey cloud) for now.
The orange-cloud proxy interferes with the Let's Encrypt HTTP-01 challenge in
section 8; you can turn it on afterwards.

Verify from your own machine before continuing — the certificate step in
section 8 will fail if this is not resolving:

```bash
nslookup api.buysoloio.com
```

---

## 3. Security group rules

**EC2 → Security Groups → `nory-backend-sg` → Inbound rules → Edit**

| Type | Protocol | Port | Source | Why |
|---|---|---|---|---|
| SSH | TCP | 22 | **My IP** | Only you can attempt to log in. Never `0.0.0.0/0` — bots hammer port 22 continuously. |
| HTTP | TCP | 80 | `0.0.0.0/0` | Public traffic, and required for Let's Encrypt domain validation. |
| HTTP | TCP | 80 | `::/0` | Same, for IPv6 clients. |
| HTTPS | TCP | 443 | `0.0.0.0/0` | The real traffic. |
| HTTPS | TCP | 443 | `::/0` | Same, for IPv6. |

**Outbound rules:** leave the default `All traffic → 0.0.0.0/0`. The server
must reach fal.ai, OpenAI, Gmail SMTP, Docker Hub and GitLab.

### What must NOT be here

Do not open **8000**, **5432** (PostgreSQL), or **6379** (Redis). Those
services listen only on the private Docker network. An open 5432 with a
guessable password is one of the most common ways a small production database
is stolen.

> **If your home IP changes**, SSH will stop working. Come back here and update
> the "My IP" rule. For a fixed alternative, use AWS Systems Manager Session
> Manager instead of SSH — then you can close port 22 entirely.

---

## 4. Connect over SSH

### 4.1 Fix the key file permissions

SSH refuses to use a private key that other users can read.

**Windows (PowerShell), from the folder containing the key:**
```powershell
icacls.exe nory-prod-key.pem /reset
icacls.exe nory-prod-key.pem /grant:r "$($env:USERNAME):(R)"
icacls.exe nory-prod-key.pem /inheritance:r
```
This resets the file's permissions, grants read access to you alone, and stops
it inheriting permissions from the parent folder.

**macOS / Linux:**
```bash
chmod 400 nory-prod-key.pem
```

### 4.2 Log in

```bash
ssh -i nory-prod-key.pem ubuntu@<ELASTIC_IP>
```

`ubuntu` is the default user on the Ubuntu AMI. On first connection you will be
asked to accept the host fingerprint — type `yes`.

Everything from here runs **on the server**.

---

## 5. Prepare the server

### 5.1 Update the system

```bash
sudo apt-get update && sudo apt-get upgrade -y
```
Downloads the current package index, then installs all pending security
updates. A freshly launched AMI is usually a few weeks behind.

If it tells you a reboot is required:
```bash
sudo reboot
```
Wait about 30 seconds, then SSH back in.

### 5.2 Set the timezone

```bash
sudo timedatectl set-timezone UTC
timedatectl
```
Keep servers on UTC. Django is already configured with `TIME_ZONE = 'UTC'`, and
matching them means log timestamps and database timestamps line up.

### 5.3 Add swap space

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

Line by line:
- `fallocate` reserves a 2 GB file on disk.
- `chmod 600` makes it readable only by root — it will hold memory contents.
- `mkswap` formats it as swap.
- `swapon` activates it immediately.
- The `/etc/fstab` line re-activates it automatically after a reboot.
- `free -h` should now show 2 GB under `Swap`.

Why this matters: `pip install` compiling packages during the Docker build is
the single most memory-hungry moment in this deployment. Without swap, a 4 GB
instance can hit the out-of-memory killer mid-build and fail with a confusing
`Killed` message.

### 5.4 Enable automatic security updates

```bash
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```
Choose **Yes**. Ubuntu will now install kernel and OpenSSL security patches on
its own, which is the single highest-value thing you can do for a server you
will not log into every day.

### 5.5 Protect SSH from brute force

```bash
sudo apt-get install -y fail2ban
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```
`fail2ban` watches the auth log and temporarily blocks IPs that fail to log in
repeatedly. Your security group already limits port 22 to your own IP, so this
is defence in depth — cheap, and it costs you nothing.

> **A note on `ufw`:** do not bother. Docker writes its own `iptables` rules for
> published ports, which bypass `ufw` entirely — you would get a firewall that
> looks active but does not filter your application traffic. The AWS security
> group is the real firewall here, and it works at the network level, before
> packets ever reach the instance.

---

## 6. Install Docker

Use Docker's official repository, not `apt install docker.io`. The Ubuntu
package is old and does not ship the Compose v2 plugin this project needs.

### 6.1 Add Docker's package repository

```bash
sudo apt-get install -y ca-certificates curl gnupg
```
Tools needed to fetch and verify the repository's signing key.

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
     -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```
Downloads Docker's GPG public key. `apt` will use it to verify that every
Docker package really came from Docker and was not tampered with in transit.

```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```
Adds the repository, automatically filling in your CPU architecture (`amd64`)
and Ubuntu release name (`noble` for 24.04).

```bash
sudo apt-get update
```

### 6.2 Install the packages

```bash
sudo apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin
```

What each one is:
- `docker-ce` — the daemon that actually runs containers.
- `docker-ce-cli` — the `docker` command.
- `containerd.io` — the lower-level container runtime Docker sits on.
- `docker-buildx-plugin` — the modern build engine, which gives you the layer
  caching that makes redeploys fast.
- `docker-compose-plugin` — provides `docker compose` (two words). The old
  standalone `docker-compose` is deprecated.

### 6.3 Run Docker without `sudo`

```bash
sudo usermod -aG docker ubuntu
```
Adds your user to the `docker` group.

```bash
exit
```
**Log out and back in.** Group membership is only applied at login, so this
step does not take effect until you reconnect.

```bash
ssh -i nory-prod-key.pem ubuntu@<ELASTIC_IP>
```

### 6.4 Verify

```bash
docker --version
docker compose version
docker run --rm hello-world
```
The last command pulls a tiny test image and runs it. If it prints "Hello from
Docker!" without `sudo`, everything is correct.

```bash
sudo systemctl enable docker
```
Ensures Docker starts automatically after a reboot, so your stack comes back up
on its own.

---

## 7. Get the code from GitLab

### 7.1 Create a deploy key

The server needs read access to your GitLab repository without carrying your
personal credentials.

```bash
ssh-keygen -t ed25519 -C "nory-ec2-deploy" -f ~/.ssh/gitlab_deploy -N ""
```
- `-t ed25519` — modern, short, fast key type.
- `-f ~/.ssh/gitlab_deploy` — where to write it.
- `-N ""` — no passphrase, because an unattended `git pull` cannot type one.

```bash
cat ~/.ssh/gitlab_deploy.pub
```
Copy the whole line that prints.

Now in GitLab: **your project → Settings → Repository → Deploy keys → Add new key**
```
Title:  nory-ec2-prod
Key:    (paste)
Write access allowed:  LEAVE UNCHECKED
```
Read-only is deliberate. The server only ever pulls. If the instance is
compromised, the attacker cannot push malicious code back into your repository.

### 7.2 Tell SSH to use that key for GitLab

```bash
cat >> ~/.ssh/config <<'EOF'
Host gitlab.betopialimited.com
    HostName gitlab.betopialimited.com
    User git
    IdentityFile ~/.ssh/gitlab_deploy
    IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```
Without this, SSH offers every key it can find and GitLab may reject you before
reaching the right one.

```bash
ssh -T git@gitlab.betopialimited.com
```
Expect `Welcome to GitLab, @...`. Accept the host fingerprint if asked.

> **If SSH to GitLab is blocked** (some self-hosted instances only expose
> HTTPS), use a **Deploy Token** instead: GitLab → Settings → Repository →
> Deploy tokens → create one with the `read_repository` scope, then clone with
> `git clone https://<token-username>:<token>@gitlab.betopialimited.com/join-venture-ai/nory_video-based/backend.git nory-backend`.
> Never use your own account password here.

### 7.3 Clone

```bash
cd ~
git clone git@gitlab.betopialimited.com:join-venture-ai/nory_video-based/backend.git nory-backend
cd nory-backend
```

From now on, **every command assumes you are in `~/nory-backend`.**

```bash
ls -la
```
You should see `docker-compose.yml`, `Dockerfile`, `deploy.sh`,
`.env.production.example` and the `docker/` directory.

---

## 8. Configure the environment

### 8.1 Generate your secrets

Run these and keep the output in front of you — you need four distinct values:

```bash
echo "SECRET_KEY:              $(openssl rand -base64 48 | tr -d '\n/+=' )"
echo "POSTGRES_PASSWORD:       $(openssl rand -hex 32)"
echo "AI_VIDEO_WEBHOOK_TOKEN:  $(openssl rand -hex 32)"
```
`openssl rand` reads the kernel's cryptographic random source. The `tr` strips
characters that would confuse Docker Compose's variable substitution.

> **Never** reuse the `SECRET_KEY` from your development `.env`. It also signs
> every JWT in this project, so a leaked key lets anyone forge a login.

### 8.2 Django environment

```bash
cp .env.production.example .env
nano .env
```

Fill in every `CHANGE_ME`. The values that must be right or nothing works:

```ini
DOMAIN=api.buysoloio.com
NGINX_CONF=app.http.conf

POSTGRES_DB=nory
POSTGRES_USER=nory
POSTGRES_PASSWORD=<the hex string you generated>
DATABASE_URL=postgres://nory:<same password>@db:5432/nory

REDIS_URL=redis://redis:6379/0

DEBUG=False
SECRET_KEY=<the base64 string you generated>

# Include the raw Elastic IP for now, so you can test before DNS propagates.
DJANGO_ALLOWED_HOSTS=api.buysoloio.com,<ELASTIC_IP>,web,ws,localhost,127.0.0.1

# Leave the HTTPS switches OFF until section 10.
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SECURE_COOKIES=False
DJANGO_SECURE_HSTS_SECONDS=0

AI_VIDEO_SERVICE_URL=http://agent:8000
AI_VIDEO_WEBHOOK_TOKEN=<the third hex string>
```

Three things people get wrong here:

1. **The database host is `db`, not `localhost`.** Inside Docker, every service
   reaches the others by their compose service name.
2. **`web` and `ws` must stay in `DJANGO_ALLOWED_HOSTS`.** The AI agent calls
   Django back at `http://web:8000/...`, and the container healthchecks use
   `127.0.0.1`. Remove them and both silently break with `400 Bad Request`.
3. **No `$` characters in any value.** Compose reads this file for variable
   substitution and will mangle them.

Save with `Ctrl+O`, `Enter`, then exit with `Ctrl+X`.

```bash
chmod 600 .env
```
Only your user can read the file that holds every production secret.

### 8.3 AI agent environment

```bash
cp car-video-agent/car-video-agent/.env.example car-video-agent/car-video-agent/.env
nano car-video-agent/car-video-agent/.env
```

```ini
FAL_KEY=<your fal.ai key>
OPENAI_API_KEY=<your OpenAI key>
BACKEND_WEBHOOK_URL=http://web:8000/api/vehicles/ai-video/webhook/?token=<AI_VIDEO_WEBHOOK_TOKEN>
```

The token at the end **must be byte-identical** to `AI_VIDEO_WEBHOOK_TOKEN` in
the Django `.env`. If they differ, videos generate successfully but Django
rejects the callback with `401` and the job sits at `processing` forever.

```bash
chmod 600 car-video-agent/car-video-agent/.env
```

### 8.4 Service-account files

From **your own machine** (not the server), upload the JSON credentials:

```bash
scp -i nory-prod-key.pem firebase.json ubuntu@<ELASTIC_IP>:~/nory-backend/secrets/
scp -i nory-prod-key.pem google-play.json ubuntu@<ELASTIC_IP>:~/nory-backend/secrets/
```

Back on the server:
```bash
chmod 600 ~/nory-backend/secrets/*.json
ls -l ~/nory-backend/secrets/
```
Docker mounts this directory read-only at `/run/secrets` inside the containers,
which is where `FIREBASE_CREDENTIALS_PATH` and `GOOGLE_SERVICE_ACCOUNT_JSON`
point. Skip whichever file you do not use, and leave the matching variable in
`.env` blank.

---

## 9. First launch (HTTP)

### 9.1 Build the images

```bash
docker compose build
```

This takes **5–15 minutes the first time**. It downloads the Python base image,
compiles the dependency tree in a builder stage, then copies only the finished
packages into a clean runtime image. Later builds reuse cached layers and
finish in seconds unless `requirements.txt` changed.

### 9.2 Start everything

```bash
docker compose up -d
```
`-d` detaches, so the stack keeps running after you close SSH. On first start:

1. PostgreSQL initialises the database and Redis comes up.
2. `web` waits for the database, applies all migrations, runs
   `collectstatic`, then starts gunicorn.
3. `ws` starts daphne, `agent` starts uvicorn, `nginx` starts last.

### 9.3 Confirm it is healthy

```bash
docker compose ps
```
Every service should show `running`, and `web`, `ws` and `agent` should reach
`healthy` within a minute.

```bash
docker compose logs -f web
```
Watch for `[entrypoint] applying database migrations...` followed by gunicorn's
`Listening at: http://0.0.0.0:8000`. Press `Ctrl+C` to stop following — that
stops the log view, not the container.

### 9.4 Test from outside

From **your own machine**:
```bash
curl -i http://<ELASTIC_IP>/healthz/
```
Expect `HTTP/1.1 200 OK` and `{"status": "ok"}`.

```bash
curl -i http://api.buysoloio.com/healthz/
```
Same result once DNS has propagated.

> `400 Bad Request` here means the Host you used is not in
> `DJANGO_ALLOWED_HOSTS`. Fix `.env`, then `docker compose up -d web ws`.

### 9.5 Create your admin user

```bash
docker compose exec web python manage.py createsuperuser
```
`docker compose exec` runs a command inside the already-running `web`
container, so it uses the same database and settings as the live app.

Open `http://api.buysoloio.com/admin/` and log in. The page should be fully
styled — if it looks like unstyled plain text, `collectstatic` did not run;
see the troubleshooting section.

---

## 10. Enable HTTPS

Do not skip this. Without TLS, every JWT and password crosses the internet in
plain text.

### 10.1 Check the domain resolves to this server

```bash
curl -s http://api.buysoloio.com/healthz/
```
This must already work over plain HTTP. Let's Encrypt proves you own the domain
by fetching a file over port 80 — if the domain does not point here yet, the
next step fails.

### 10.2 Dry run first

```bash
docker compose run --rm --entrypoint certbot certbot certonly \
    --webroot -w /var/www/certbot \
    -d api.buysoloio.com \
    --email <your-email@example.com> \
    --agree-tos --no-eff-email \
    --dry-run
```

What this does: certbot writes a challenge file into the shared
`certbot_www` volume; nginx serves it at
`/.well-known/acme-challenge/`; Let's Encrypt fetches it and confirms you
control the domain.

`--dry-run` runs the whole exchange against the staging server without issuing
a real certificate. Use it, because the production endpoint allows only **5
failures per hour per domain** and it is easy to burn through that while
debugging DNS.

Expect: `The dry run was successful.`

### 10.3 Issue the real certificate

Remove `--dry-run` and run it again:

```bash
docker compose run --rm --entrypoint certbot certbot certonly \
    --webroot -w /var/www/certbot \
    -d api.buysoloio.com \
    --email <your-email@example.com> \
    --agree-tos --no-eff-email
```

Expect `Successfully received certificate` and a path under
`/etc/letsencrypt/live/api.buysoloio.com/`.

The `certbot` container in the stack already loops every 12 hours calling
`certbot renew`, so renewal is automatic from here. Certificates last 90 days
and renew inside the final 30.

### 10.4 Switch nginx to the TLS config

```bash
nano .env
```
Change one line:
```ini
NGINX_CONF=app.https.conf
```

```bash
docker compose up -d nginx
```
Compose sees the changed mount and recreates only nginx. The API stays up.

```bash
docker compose logs nginx | tail -20
```
Look for `Configuration complete; ready for start up`. An error mentioning
`cannot load certificate` means the domain in `DOMAIN` does not match the name
you passed to `-d` in step 10.3.

### 10.5 Verify

From your own machine:
```bash
curl -I https://api.buysoloio.com/healthz/
curl -I http://api.buysoloio.com/healthz/
```
The first returns `200`. The second returns `301` redirecting to `https://`.

### 10.6 Turn on Django's HTTPS hardening

Only now, with HTTPS confirmed working:

```bash
nano .env
```
```ini
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_COOKIES=True
DJANGO_CSRF_TRUSTED_ORIGINS=https://api.buysoloio.com
DJANGO_SECURE_HSTS_SECONDS=3600
```

```bash
docker compose up -d web ws
```

Leave `HSTS` at `3600` (one hour) for a day. Once you are confident nothing is
broken, raise it to `31536000` (one year) and restart again. HSTS is cached by
browsers for its full duration and **cannot be revoked**, which is exactly why
you raise it in stages.

Finally, tighten `DJANGO_ALLOWED_HOSTS` by removing the raw Elastic IP:
```ini
DJANGO_ALLOWED_HOSTS=api.buysoloio.com,web,ws,localhost,127.0.0.1
```

---

## 11. Verify the whole system

### 11.1 The AI video pipeline

This is the integration most likely to be misconfigured, because it depends on
two `.env` files agreeing.

Check Django can see the agent:
```bash
docker compose exec web python -c "import httpx; print(httpx.get('http://agent:8000/health').json())"
```
Expect `{'status': 'ok'}`. A connection error means the `agent` container is
not running — check `docker compose logs agent`.

Confirm the shared token matches on both sides:
```bash
grep AI_VIDEO_WEBHOOK_TOKEN .env
grep BACKEND_WEBHOOK_URL car-video-agent/car-video-agent/.env
```
The value after `token=` in the second must equal the first exactly.

Then trigger a real generation from the mobile app or Postman
(`POST /api/vehicles/ai-video/generate/` with images) and watch both sides:
```bash
docker compose logs -f agent web
```
You should see the agent log the detected car, then fal.ai queue updates, and
finally Django receiving the webhook and downloading the video.

### 11.2 WebSockets

```bash
docker compose logs ws | tail -20
```
Look for `ASGI application loading with JWTAuthMiddleware...` and
`Listening on TCP address 0.0.0.0:8000`.

Connect from a client to `wss://api.buysoloio.com/ws/notifications/` with a
valid JWT. If the handshake succeeds and stays open, nginx, daphne and Redis
are all wired correctly.

### 11.3 Media upload and playback

Upload a reel through the app, then confirm nginx is serving it directly:
```bash
curl -I https://api.buysoloio.com/media/reels/<filename>.mp4
```
Expect `200`, a `Content-Type: video/mp4`, and `Accept-Ranges: bytes`. That
last header is what lets the mobile player seek without downloading the whole
file.

### 11.4 Django's own production checklist

```bash
docker compose exec web python manage.py check --deploy
```
Reports anything Django considers unsafe for production. After section 10 it
should be clean, or mention only settings you have deliberately chosen.

---

## 12. Moving your existing development data (optional)

Only if you want the current SQLite contents in production.

On **your own machine**, with the development environment active:
```bash
python manage.py dumpdata \
    --natural-foreign --natural-primary \
    --exclude contenttypes --exclude auth.permission \
    --indent 2 -o dev_data.json
```
`contenttypes` and `auth.permission` are excluded because Django recreates them
during `migrate`; importing them causes primary-key collisions.

Upload and load it:
```bash
scp -i nory-prod-key.pem dev_data.json ubuntu@<ELASTIC_IP>:~/nory-backend/
```
```bash
docker compose exec -T web python manage.py loaddata dev_data.json
```

For the uploaded files, copy the whole media tree into the volume:
```bash
scp -i nory-prod-key.pem -r media ubuntu@<ELASTIC_IP>:~/media-upload
docker compose cp ~/media-upload/. web:/app/media/
docker compose exec web ls /app/media
```

---

## 13. Day-to-day operations

### Deploying a code change

```bash
cd ~/nory-backend
./deploy.sh
```

The script pulls from GitLab, rebuilds changed images, restarts the stack and
prunes old image layers. Migrations and `collectstatic` run automatically in
the `web` container's entrypoint.

Make it executable the first time:
```bash
chmod +x deploy.sh backup.sh
```

The manual equivalent, if you prefer to see each step:
```bash
git pull --ff-only          # refuse to auto-merge; stop if the server has edits
docker compose build        # rebuild only layers whose inputs changed
docker compose up -d        # recreate only containers whose config changed
docker image prune -f       # delete the now-untagged old layers
```

### Reading logs

```bash
docker compose logs -f web          # follow the API
docker compose logs --tail=100 ws   # last 100 WebSocket lines
docker compose logs agent           # AI video service
docker compose logs nginx           # access log + errors
docker compose logs                 # everything, interleaved
```

### Running Django management commands

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell
```

### Restarting

```bash
docker compose restart web       # one service
docker compose restart           # all of them
docker compose down              # stop and remove containers (volumes survive)
docker compose up -d             # bring it all back
```

`docker compose down` never deletes your data — the database, media and
certificates live in named volumes. Only `docker compose down -v` destroys
them, and there is no undo.

### Backups

```bash
./backup.sh
```
Writes a compressed database dump and a media archive into `./backups`, keeping
14 days.

Schedule it nightly at 03:00:
```bash
crontab -e
```
Add:
```
0 3 * * * cd /home/ubuntu/nory-backend && ./backup.sh >> backups/backup.log 2>&1
```

> A backup stored on the same instance survives a bad migration, not a lost
> instance. Copy the archives to S3 as well — attach an IAM role with
> `s3:PutObject` to the instance and add an `aws s3 cp` line to the script.

### Restoring the database

```bash
gunzip -c backups/db_2026-09-10_03-00.sql.gz \
    | docker compose exec -T db psql -U nory -d nory
```
`-T` disables TTY allocation, which would otherwise corrupt the piped SQL.

### Watching disk space

```bash
df -h /                 # root volume usage
docker system df        # what Docker is using
du -sh ~/nory-backend/backups
```
When Docker's reclaimable space grows large:
```bash
docker system prune -a -f
```
This deletes every image not currently used by a running container. Safe, but
your next `docker compose up` rebuilds from scratch.

### Resource usage

```bash
docker stats --no-stream
free -h
```
If `web` is consistently near its memory ceiling, lower `GUNICORN_WORKERS` in
`.env`, or move up to a larger instance type.

---

## 14. Troubleshooting

**`400 Bad Request` on every request**
The `Host` header is not in `DJANGO_ALLOWED_HOSTS`. Check the domain, the
Elastic IP, and that `web`, `ws` and `127.0.0.1` are still listed.
```bash
grep DJANGO_ALLOWED_HOSTS .env && docker compose up -d web ws
```

**`502 Bad Gateway`**
nginx is up but gunicorn is not answering.
```bash
docker compose ps          # is web running?
docker compose logs web    # what did it crash on?
```
Usually a missing environment variable or a failed migration.

**`413 Request Entity Too Large` when uploading a reel**
The file exceeds nginx's `client_max_body_size` (200 MB). Raise it in
`docker/nginx/nginx.conf`, then `docker compose up -d nginx`.

**Admin page has no styling**
`collectstatic` did not run, or nginx cannot read the volume.
```bash
docker compose exec web python manage.py collectstatic --noinput
docker compose exec nginx ls /var/www/static/admin
docker compose restart nginx
```

**WebSockets connect then immediately drop**
Almost always Redis. Confirm `REDIS_URL` is set and reachable:
```bash
docker compose exec web python -c "import os;print(os.environ.get('REDIS_URL'))"
docker compose exec redis redis-cli ping
```

**AI videos stay at `processing` forever**
The agent finished but Django rejected the callback. Compare the tokens
(section 11.1) and check for a `401` in:
```bash
docker compose logs agent | tail -40
```

**`Permission denied` writing to `/app/media`**
The volume was created before the image set ownership. Fix it once:
```bash
docker compose exec -u root web chown -R appuser:appuser /app/media
docker compose restart web ws
```

**Certificate renewal failing**
```bash
docker compose logs certbot | tail -40
docker compose run --rm --entrypoint certbot certbot renew --dry-run
```
The usual cause is that port 80 stopped serving
`/.well-known/acme-challenge/` — confirm nginx is running and that the
security group still allows port 80.

**Instance unreachable after a stop/start**
The public IP changed because no Elastic IP is attached. Redo section 2.3.

---

## 15. Hardening checklist

Work through this before you announce the API to real users.

- [ ] `DEBUG=False` in `.env`, confirmed by `manage.py check --deploy`
- [ ] `SECRET_KEY` is new, never used in development, never committed
- [ ] `DJANGO_ALLOWED_HOSTS` no longer contains the raw Elastic IP
- [ ] HTTPS works and HTTP redirects to it
- [ ] `DJANGO_SECURE_SSL_REDIRECT` and `DJANGO_SECURE_COOKIES` are `True`
- [ ] `DJANGO_SECURE_HSTS_SECONDS` raised to `31536000`
- [ ] SSH port 22 restricted to your IP only
- [ ] Ports 5432, 6379 and 8000 are **not** in the security group
- [ ] `.env` files are `chmod 600` and absent from git
- [ ] Termination protection enabled on the instance
- [ ] `backup.sh` is in cron and you have restored from a backup at least once
- [ ] `unattended-upgrades` is active
- [ ] Automatic certificate renewal verified with `certbot renew --dry-run`
- [ ] A CloudWatch alarm on CPU and on the root volume's free space
