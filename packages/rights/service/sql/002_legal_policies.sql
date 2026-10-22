-- ALDOL RIGHTS v0.3: isolated legal notices and data-subject request registers.
-- Stage after 001_rights.sql. Does not mutate shared ARAM Auth settings.
-- Bootstrap a specific verified operator with privileged SQL ONLY:
-- INSERT INTO public.rights_policy_admins(owner_id) VALUES ('<VERIFIED_AUTH_USER_UUID>');
-- Never grant admin based on email or user-editable metadata.

create table public.rights_policy_admins (
  owner_id uuid primary key references auth.users(id) on delete cascade
);
alter table public.rights_policy_admins enable row level security;
revoke all on public.rights_policy_admins from anon, authenticated;
grant select on public.rights_policy_admins to authenticated;
create policy rights_policy_admin_self on public.rights_policy_admins
  for select to authenticated using (owner_id = (select auth.uid()));

create table public.rights_legal_documents (
  doc_id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('privacy','terms')),
  version integer not null check (version >= 1),
  status text not null default 'draft' check (status in ('draft','published')),
  content text not null check (char_length(content) between 400 and 30000),
  effective_on date not null,
  revision integer not null default 1 check (revision >= 1),
  editor_id uuid not null references auth.users(id),
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(kind, version),
  constraint publication_time check ((status='draft' and published_at is null) or
                                      (status='published' and published_at is not null))
);
create index rights_legal_documents_kind_pub on public.rights_legal_documents(kind, status, version desc);
alter table public.rights_legal_documents enable row level security;
revoke all on public.rights_legal_documents from anon, authenticated;
grant select on public.rights_legal_documents to anon, authenticated;
grant insert(kind,version,status,content,effective_on,editor_id) on public.rights_legal_documents to authenticated;
grant update(content,effective_on,status,published_at) on public.rights_legal_documents to authenticated;

create policy rights_legal_public on public.rights_legal_documents
  for select to anon,authenticated using (status='published');
create policy rights_legal_admin_read on public.rights_legal_documents
  for select to authenticated using (exists (
    select 1 from public.rights_policy_admins p where p.owner_id=(select auth.uid())));
create policy rights_legal_admin_insert on public.rights_legal_documents
  for insert to authenticated with check (status='draft' and published_at is null
    and editor_id=(select auth.uid()) and exists (
    select 1 from public.rights_policy_admins p where p.owner_id=(select auth.uid())));
create policy rights_legal_admin_update on public.rights_legal_documents
  for update to authenticated using (status='draft' and exists (
    select 1 from public.rights_policy_admins p where p.owner_id=(select auth.uid())))
  with check (status in ('draft','published') and exists (
    select 1 from public.rights_policy_admins p where p.owner_id=(select auth.uid())));

create or replace function rights_private.legal_document_revision() returns trigger
language plpgsql set search_path = '' as $$
begin
  if old.status='published' then raise exception 'Published legal text is immutable'; end if;
  if new.doc_id<>old.doc_id or new.kind<>old.kind or new.version<>old.version
     or new.editor_id<>old.editor_id or new.created_at<>old.created_at
     or new.revision<>old.revision then
    raise exception 'Legal document identity/revision is immutable';
  end if;
  new.revision=old.revision+1;
  new.updated_at=now();
  return new;
end $$;
revoke all on function rights_private.legal_document_revision() from public,anon,authenticated;
create trigger rights_legal_revision before update on public.rights_legal_documents
for each row execute function rights_private.legal_document_revision();

create table public.rights_policy_acceptances (
  acceptance_id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  doc_id uuid not null references public.rights_legal_documents(doc_id),
  accepted_at timestamptz not null default now(),
  unique(owner_id,doc_id)
);
alter table public.rights_policy_acceptances enable row level security;
revoke all on public.rights_policy_acceptances from anon, authenticated;
grant select on public.rights_policy_acceptances to authenticated;
grant insert(owner_id,doc_id) on public.rights_policy_acceptances to authenticated;
create policy rights_acceptances_owner_read on public.rights_policy_acceptances
  for select to authenticated using (owner_id=(select auth.uid()));
create policy rights_acceptances_owner_create on public.rights_policy_acceptances
  for insert to authenticated with check (owner_id=(select auth.uid())
    and exists(select 1 from public.rights_legal_documents d
      where d.doc_id=rights_policy_acceptances.doc_id and d.kind='terms' and d.status='published'));
-- Never update/delete acceptance records through the Data API.

create table public.rights_privacy_requests (
  request_id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  request_type text not null check (request_type in ('access','rectification','erasure','restriction')),
  status text not null default 'received' check (status in ('received','reviewing','fulfilled','rejected')),
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);
create index rights_privacy_requests_owner on public.rights_privacy_requests(owner_id,created_at desc);
alter table public.rights_privacy_requests enable row level security;
revoke all on public.rights_privacy_requests from anon, authenticated;
grant select on public.rights_privacy_requests to authenticated;
grant insert(owner_id,request_type) on public.rights_privacy_requests to authenticated;
create policy rights_privacy_owner_read on public.rights_privacy_requests
  for select to authenticated using (owner_id=(select auth.uid()));
create policy rights_privacy_admin_read on public.rights_privacy_requests
  for select to authenticated using (exists (
    select 1 from public.rights_policy_admins p where p.owner_id=(select auth.uid())));
create policy rights_privacy_owner_create on public.rights_privacy_requests
  for insert to authenticated with check (owner_id=(select auth.uid()));
-- Resolution stays a privileged operator SQL workflow with independent identity verification.
-- REQUEST RECEIVED does not imply that erasure/rectification was performed.
