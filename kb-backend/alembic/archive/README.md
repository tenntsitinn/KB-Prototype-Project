# Archived data migrations

These revisions were removed from the active Alembic chain before the first
production baseline. Their source remains available in Git history; this file
records why they must not be restored. They only transformed disposable
development/test data or inserted bootstrap data.

- `0004_migrate_existing_data.py`: generated knowledge points for legacy test data.
- `0005_add_education_roles.py`: inserted roles and permissions now managed by
  the idempotent `scripts/bootstrap.py` command.

Do not restore these files into `alembic/versions`. Existing disposable
databases stamped at `0004` or `0005` should be recreated or restamped at the
current head.
