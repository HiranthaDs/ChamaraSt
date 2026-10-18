-- Notification creation, reading and acknowledgement are changes too; capture them
-- through the same append-only ledger and keep the event in the same transaction.
drop trigger if exists erp_row_change_audit on public.erp_notifications;
create trigger erp_row_change_audit
after insert or update or delete on public.erp_notifications
for each row execute function public.capture_erp_row_change();
