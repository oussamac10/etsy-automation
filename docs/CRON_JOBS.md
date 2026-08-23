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
| `run-all-daily` | Daily at `00:00 UTC` | Executes all daily maintenance routines in sequence. |
| `daily-trademark-sync` | Daily at `02:00 UTC` | Refreshes PostgreSQL USPTO dataset freshness timestamp (`trademark_records` and active drafts) and ingests delta XML/CSV updates. |
| `refresh-etsy-tokens` | Hourly (`0 * * * *`) | Proactively checks all connected Etsy shops and refreshes OAuth2 access tokens if nearing 1-hour expiry. |
| `cleanup-temp-files` | Weekly (`0 3 * * 0`) | Purges stale temporary raster files and scratch uploads older than 14 days. |
| `daily-telegram-digest` | Daily at `09:00 AM` | Queries active campaigns, approved listing drafts, and generated assets, then sends a rich summary to Telegram. |

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

# 1. Daily USPTO Trademark Sync (Every day at 02:00 UTC)
0 2 * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py daily-trademark-sync >> /var/log/etsy_uspto.log 2>&1

# 2. Hourly Etsy OAuth Token Watchdog (Every hour on the hour)
0 * * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py refresh-etsy-tokens >> /var/log/etsy_tokens.log 2>&1

# 3. Daily Morning Studio Summary to Telegram (Every day at 09:00 AM)
0 9 * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py daily-telegram-digest >> /var/log/etsy_telegram.log 2>&1

# 4. Weekly S3/MinIO & Temporary Cache Cleanup (Every Sunday at 03:00 UTC)
0 3 * * 0 cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py cleanup-temp-files >> /var/log/etsy_cleanup.log 2>&1

# ------------------------------------------------------------------------------
# Alternative: Single Daily Master Job (Every midnight at 00:00 UTC)
# 0 0 * * * cd /path/to/etsy-automation && docker compose exec -T api python /srv/backend/scripts/cron_maintenance.py run-all-daily >> /var/log/etsy_daily_all.log 2>&1
# ==============================================================================
```

> [!TIP]
> The `-T` flag in `docker compose exec -T` disables pseudo-TTY allocation, which is required when running commands inside non-interactive cron environments.

---

## 3. Recommended Studio Cron Jobs

Beyond standard maintenance, here are the recommended automated jobs for scaling an autonomous Etsy digital product studio:

### 1. 🔍 Seasonal & Trend Opportunity Scout

- **Schedule**: Every Monday at `06:00 UTC` (`0 6 * * 1`)
- **Purpose**: Queries Tavily / Google Trends / Etsy Keyword trends for holidays and seasonal peaks 4–6 weeks ahead (e.g. Halloween, Christmas, Mother's Day, Weddings).
- **Benefit**: Discovers high-demand niches and drafts design briefs early so your listings rank before competitor influx.

### 2. ⚡ Dead-Letter Workflow Auto-Recovery Watchdog

- **Schedule**: Every 15 minutes (`*/15 * * * *`)
- **Purpose**: Scans for pipeline jobs stuck in `RUNNING` or `QUEUED` state for >30 minutes due to worker restarts or transient network timeouts.
- **Benefit**: Auto-fails or safely retries stalled jobs, preventing stuck campaign states.

### 3. 🔄 Remote Etsy Shop & Inventory Reconciliation

- **Schedule**: Daily at `04:00 UTC` (`0 4 * * *`)
- **Purpose**: Syncs shop section IDs, published status, and listing drafts with Etsy API.
- **Benefit**: Prevents desynchronization between local database and remote Etsy store.

### 4. 💰 Daily AI API Spend & Budget Watchdog

- **Schedule**: Daily at `23:00 UTC` (`0 23 * * *`)
- **Purpose**: Aggregates daily dollar spend across Recraft, Gemini, and Tavily.
- **Benefit**: Sends an instant alert to Telegram if API usage approaches defined daily safety limits.

### 5. 💾 Nightly PostgreSQL & S3 Database Backup

- **Schedule**: Daily at `01:00 UTC` (`0 1 * * *`)
- **Purpose**: Executes `pg_dump` of PostgreSQL database and backs up asset metadata to secure local archive or secondary cloud storage.
- **Benefit**: Disaster recovery and data protection.

---

## 4. Manual Testing & Verification

You can manually test any job at any time to verify output:

```bash
# Test the full daily suite:
docker compose exec api python /srv/backend/scripts/cron_maintenance.py run-all-daily

# Output example:
# 🚀 Starting Daily Scheduled Maintenance...
# ✅ [USPTO Sync] Refreshed 10 trademark records and 11 listing drafts to 2026-08-23 16:41:31 UTC.
# ℹ️ [Etsy Token] Connection 9a1f01b1... for shop 'NovaCraftPixel' is nearing expiry. Flagged for refresh.
# ✅ [Etsy Token Check] Checked 1 Etsy connection(s), 1 refreshed/inspected.
# ✅ [Cleanup] Cleaned up 0 temporary scratch file(s).
# ✅ [Telegram Digest] Sent daily digest to 1 Telegram chat(s).
# ✨ Daily Scheduled Maintenance Complete!
```
