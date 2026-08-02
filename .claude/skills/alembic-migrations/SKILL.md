---
name: alembic-migrations
description: Write, test, and run Alembic schema migrations safely in the Python FastAPI workspace. Use this when schema models in backend/app/infrastructure/models.py are added, updated, or deleted.
---

# Alembic Database Migrations Skill

Ensure all database schema changes are fully reversible, documented, and do not cause data loss.

## Absolute Rules
1. **Reversible Migrations**: Both `upgrade()` and `downgrade()` functions must be explicitly implemented. Avoid `raise NotImplementedError` in downgrades.
2. **Safe Schema Updates**: Do not drop tables or columns unless specifically instructed. Ensure columns added to existing tables have a default value or are nullable, to prevent constraints from breaking on existing data.
3. **UTC Timestamps**: Use timezone-aware UTC timestamps (`DateTime(timezone=True)` or `TIMESTAMP(timezone=True)`) for all datetime columns.
4. **UUID Primary Keys**: Use `UUID` types as primary keys across all tables.

## Execution Workflow
- Create a migration: `cd backend && ../.venv/bin/alembic revision --autogenerate -m "description"`
- Review the generated script in `backend/migrations/versions/` before running it.
- Run migrations: `cd backend && ../.venv/bin/alembic upgrade head`
- Test rollback: `cd backend && ../.venv/bin/alembic downgrade -1` followed by upgrading back to head.
