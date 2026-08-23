# ⏰ Automated Scheduled Jobs & Cron Maintenance Guide

This document details the scheduled maintenance jobs, cron configurations, and background automation tasks for **Marketplace Studio**.

---

## 1. Unified Maintenance Engine (`cron_maintenance.py`)

All scheduled routines are centralized in [`backend/scripts/cron_maintenance.py`](file:///Users/oussama/Desktop/etsy%20automation/backend/scripts/cron_maintenance.py).

```bash
# General syntax
python backend/scripts/cron_maintenance.py <command> [--quiet]

# Inside Docker
docker compose exec api python /srv/backend/scripts/cron_maintenance.py <command> [--quiet]
```

### Available Commands

| Command | Recommended Schedule | Description |
| :--- | :--- | :--- |
| `run-all-daily` | Daily at `00:00 UTC` | Executes all standard daily maintenance and audit routines in sequence. |
| `daily-trademark-sync` | Daily at `02:00 UTC` | Refreshes PostgreSQL USPTO dataset freshness timestamp (`trademark_records` and active drafts) and ingests delta XML/CSV updates. |
| `refresh-etsy-tokens` | Hourly (`0 * * * *`) | Proactively checks all connected Etsy shops and refreshes OAuth2 access tokens if nearing 1-hour expiry. |
| `cleanup-temp-files` | Weekly (`0 3 * * 0`) | Purges stale temporary raster files and scratch uploads older than 14 days. |
| `daily-telegram-digest` | Daily at `09:00 AM` | Queries active campaigns, approved listing drafts, and generated assets, then sends a rich summary to Telegram. |
| `scout-seasonal-trends` | Weekly Mondays (`0 6 * * 1`) | Evaluates forward-looking calendar retail windows (4–6 weeks ahead) and drafts seasonal opportunity niches. |
| `recover-deadletter-workflows` | Every 15 min (`*/15 * * * *`) | Scans for jobs stuck in transient executing states for >30m and safely auto-recovers them to their previous review checkpoint. |
| `reconcile-etsy-inventory` | Daily at `04:00 UTC` (`0 4 * * *`) | Syncs shop section IDs, published status, and listing drafts with remote Etsy store. |
| `audit-ai-spend` | Daily at `23:00 UTC` (`0 23 * * *`) | Audits 24h AI API consumption against owner daily budgets and alerts Telegram if usage exceeds 80%. |
| `backup-database` | Daily at `01:00 UTC` (`0 1 * * *`) | Exports a snapshot of database tables and metrics to `/tmp/backups/`, keeping the 7 most recent backups. |

---

## 2. Production Crontab Setup

To configure automated execution on your host machine or deployment server, edit crontab:

```bash
crontab -e
```

### Complete Crontab Template

```bash
# ==============================================================================
# MARKETPLACE STUDIO — AUTOMATED PRODUCTION & MAINTENANCE CRONTAB
# ==============================================================================
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# 1. 15-Minute Dead-Letter Workflow Auto-Recovery Watchdog
*/15 * * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py recover-deadletter-workflows >> /var/log/etsy_recovery.log 2>&1

# 2. Hourly Etsy OAuth Token Watchdog (Every hour on the hour)
0 * * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py refresh-etsy-tokens >> /var/log/etsy_tokens.log 2>&1

# 3. Daily Database Snapshot & Retention (Every day at 01:00 UTC)
0 1 * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py backup-database >> /var/log/etsy_backup.log 2>&1

# 4. Daily USPTO Trademark Sync (Every day at 02:00 UTC)
0 2 * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py daily-trademark-sync >> /var/log/etsy_uspto.log 2>&1

# 5. Daily Remote Etsy Shop & Inventory Reconciliation (Every day at 04:00 UTC)
0 4 * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py reconcile-etsy-inventory >> /var/log/etsy_etsy_sync.log 2>&1

# 6. Weekly Seasonal Opportunity Scout (Every Monday at 06:00 UTC)
0 6 * * 1 cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py scout-seasonal-trends >> /var/log/etsy_trends.log 2>&1

# 7. Daily Morning Studio Summary to Telegram (Every day at 09:00 AM)
0 9 * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py daily-telegram-digest >> /var/log/etsy_telegram.log 2>&1

# 8. Daily AI API Spend & Budget Watchdog (Every day at 23:00 UTC)
0 23 * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py audit-ai-spend >> /var/log/etsy_spend.log 2>&1

# 9. Weekly Scratch & Temporary Cache Cleanup (Every Sunday at 03:00 UTC)
0 3 * * 0 cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py cleanup-temp-files >> /var/log/etsy_cleanup.log 2>&1

# ------------------------------------------------------------------------------
# Alternative: Single Daily Master Job (Every midnight at 00:00 UTC)
# 0 0 * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py run-all-daily >> /var/log/etsy_daily_all.log 2>&1
# ==============================================================================
```

> [!TIP]
> The `-T` flag in `docker compose exec -T` disables pseudo-TTY allocation, which is required when running commands inside non-interactive cron environments.

---

## 3. Manual Testing & Verification

You can manually test any job at any time to verify output:

```bash
# Test individual jobs:
docker compose exec api python /srv/backend/scripts/cron_maintenance.py scout-seasonal-trends
docker compose exec api python /srv/backend/scripts/cron_maintenance.py recover-deadletter-workflows
docker compose exec api python /srv/backend/scripts/cron_maintenance.py reconcile-etsy-inventory
docker compose exec api python /srv/backend/scripts/cron_maintenance.py audit-ai-spend
docker compose exec api python /srv/backend/scripts/cron_maintenance.py backup-database

# Test the master daily suite:
docker compose exec api python /srv/backend/scripts/cron_maintenance.py run-all-daily
```
