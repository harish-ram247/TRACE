# Deploying TRACE on one small AWS server

The whole stack (PostgreSQL + pgvector, API, worker, Streamlit demo, Caddy for HTTPS) runs with Docker
Compose on a single EC2 instance. The same containers are built and started in CI on every push (the
`docker` job), so the setup is tested before it reaches the server.

```
Internet ──443──> Caddy ──> ui  (Streamlit demo, /)
                        └─> api (FastAPI, /api/...) ──> db (PostgreSQL + pgvector)
                                                   └─> Gemini API (outbound HTTPS)
                    worker (ingest jobs) ──> db
```

## 0. Before you start

- **Cost.** Check your AWS account's Free Tier / credit status in the Billing console first; terms
  changed in 2025 and differ per account. Create a **budget alarm** before anything else
  (Billing → Budgets → "Zero spend budget" or a small monthly amount, email alert).
- **Memory.** The API holds two small ONNX models (embeddings ~67 MB, entailment ~87 MB) plus PostgreSQL
  and Streamlit: plan for **2 GB RAM**. A 1 GB instance will be too small without swap. Pick the smallest
  2 GB type your plan allows (for example t3.small; ARM t4g.small also works, the images are multi-arch).
- **Region.** Any; one close to you keeps latency down.
- **What you do yourself:** create the AWS account, create the instance and key pair, and type any
  passwords. Never paste keys or passwords into chat.

## 1. Create the server (AWS console)

1. EC2 → Launch instance: **Ubuntu Server 24.04 LTS**, the 2 GB type chosen above, 20 GB gp3 disk.
2. Key pair: create one, download the `.pem`, keep it private.
3. Security group (firewall), inbound rules:
   - SSH (22) from **My IP** only
   - HTTP (80) and HTTPS (443) from anywhere
4. Launch, then allocate an **Elastic IP** and associate it with the instance (the address stays the same
   across reboots; an unattached Elastic IP is billed, so release it when you tear down).
5. Hostname for HTTPS: without buying a domain, use `<ip-with-dashes>.sslip.io`, for example
   `203-0-113-7.sslip.io` for IP 203.0.113.7. It resolves to your IP and Caddy can get a certificate for it.

## 2. Prepare the server (SSH)

```bash
ssh -i your-key.pem ubuntu@<elastic-ip>

# Docker Engine + Compose plugin (official convenience script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit        # log out and back in for the group to apply

# 2 GB swap as a safety net on a small instance
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

git clone https://github.com/harish-ram247/TRACE.git && cd TRACE
```

## 3. Configure

Create `.env` on the server (never commit it):

```bash
cp .env.example .env && chmod 600 .env && nano .env
```

Set at least:

| Variable | Value |
|---|---|
| `POSTGRES_PASSWORD` | a long random value (`openssl rand -base64 24`) |
| `TRACE_DOMAIN` | the sslip.io hostname from step 1 |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | same as your local `.env` (consider a separate Gemini key for the server) |
| `LLM_REQUESTS_PER_MINUTE` | 12 |
| `RATE_LIMIT_PER_MIN` | e.g. 10, to protect the free quota from public traffic |
| `ADMIN_TOKEN` | leave empty unless you need `/api/ingest` |

Leave `DATABASE_URL` as it is; Compose overrides it inside the containers.

## 4. Load the data

Restoring a dump of the evaluated database is faster and more exact than re-ingesting on the server.

On your laptop (local database running):

```bash
python -m scripts.db_dump                 # writes data/trace.dump (~8 MB)
scp -i your-key.pem data/trace.dump ubuntu@<elastic-ip>:~/TRACE/
```

On the server:

```bash
docker compose -f docker-compose.prod.yml up -d db
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U trace -d trace --no-owner --clean --if-exists < trace.dump
```

## 5. Start everything

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps          # all services "running" / "healthy"
curl https://<TRACE_DOMAIN>/api/health/db             # {"status":"ok"}
```

Open `https://<TRACE_DOMAIN>/` for the demo. The first question downloads the two models (~150 MB) into
the `appdata` volume, so it takes longer once.

## 6. Operate

| Task | Command |
|---|---|
| Logs | `docker compose -f docker-compose.prod.yml logs -f api` |
| Update to the latest code | `git pull && docker compose -f docker-compose.prod.yml up -d --build` |
| Back up the database | `docker compose -f docker-compose.prod.yml exec -T db pg_dump -U trace -Fc trace > backup.dump` |
| Stop (keeps data) | `docker compose -f docker-compose.prod.yml down` |

## 7. Tear down (stop all charges)

1. On the server: `docker compose -f docker-compose.prod.yml down -v` (deletes the data volumes).
2. EC2 console: terminate the instance, **release the Elastic IP**, delete the volume if it was kept,
   delete the security group and key pair.
3. Check the Billing console the next day.

Keep the demo video and screenshots so the project stays showable after the server is gone.

## Security notes

- Only ports 80/443 are public; SSH is limited to your IP; the database and API are not exposed.
- Admin endpoints are disabled unless `ADMIN_TOKEN` is set.
- `/ask` is rate limited per client; Caddy sets `X-Forwarded-For`, which the limiter uses. Requests made by
  the Streamlit UI all come from the UI container, so the UI shares one bucket.
- Containers run as a non-root user; HTTPS certificates renew automatically.
