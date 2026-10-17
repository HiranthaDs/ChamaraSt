"""Apply additive feature migrations, once each. Never prints connection credentials.

Run from orbit-erp: python -m backend.migrate --apply
Without --apply, only lists pending migrations.
"""
import argparse
import hashlib
from pathlib import Path
from backend.app.db.postgres import get_connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        with get_connection() as db:
            db.execute('select pg_advisory_xact_lock(2026101702)')
            db.execute('create table if not exists public.erp_schema_migrations(name text primary key, checksum text not null, applied_at timestamptz not null default now())')
            db.execute('alter table public.erp_schema_migrations enable row level security')
            migration_order = {
                '20261017_sales_tracking.sql': 0,
                '20261017_gate_passes.sql': 1,
                '20261018_sales_mobile_dashboard.sql': 2,
                '20261017_enterprise_traceability.sql': 3,
                '20261018_audit_location_redaction.sql': 4,
                '20261018_notification_audit.sql': 5,
                '20261018_shipment_tracking.sql': 6,
                '20261018_partial_delivery_support.sql': 7,
            }
            for path in sorted((Path(__file__).parent / 'migrations').glob('*.sql'), key=lambda p: (migration_order.get(p.name, 10), p.name)):
                content = path.read_text(encoding='utf-8')
                checksum = hashlib.sha256(content.encode()).hexdigest()
                previous = db.execute('select checksum from public.erp_schema_migrations where name=%s', (path.name,)).fetchone()
                if previous:
                    if previous['checksum'] != checksum:
                        raise RuntimeError('Applied migration changed: '+path.name)
                    print('Already applied:', path.name)
                    continue
                print('Applying:' if args.apply else 'Pending:', path.name)
                if args.apply:
                    db.execute(content, prepare=False)
                    db.execute('insert into public.erp_schema_migrations(name,checksum) values(%s,%s)', (path.name,checksum))
            if not args.apply:
                db.rollback()
        print('Migrations committed.' if args.apply else 'Preview only; use --apply to commit.')
    except Exception as exc:
        print('Migration failed; transaction rolled back:', type(exc).__name__)
        if isinstance(exc, RuntimeError):
            print(str(exc))
        elif exc.__cause__:
            print('Database error:', type(exc.__cause__).__name__, 'SQLSTATE:', getattr(exc.__cause__, 'sqlstate', None))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
