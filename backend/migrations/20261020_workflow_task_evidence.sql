alter table public.production_workflow_documents add column task_id text references public.production_job_tasks(id);
alter table public.production_workflow_documents add constraint task_documents_require_job check(task_id is null or production_order_id is not null);
create index workflow_documents_task on public.production_workflow_documents(task_id);
alter table public.production_dependency_exceptions add column dependency_ids jsonb not null default '[]';
