-- Additive namespace only. No existing ARAM policy or Auth settings change.
create table public.rights_assets (
 asset_id uuid primary key, owner_id uuid not null references auth.users(id) on delete cascade,
 title text not null check(char_length(title) between 1 and 300), kind text not null check(kind in ('image','audio','video','font','3d','code','text','other')),
 license_id text not null check(char_length(license_id)<=50), creator text not null default '' check(char_length(creator)<=512),
 rights_holder text not null default '' check(char_length(rights_holder)<=512),
 source_url text not null default '' check(char_length(source_url)<=2048), license_url text not null default '' check(char_length(license_url)<=2048), evidence_url text not null default '' check(char_length(evidence_url)<=2048),
 project text not null default '' check(char_length(project)<=120), notes text not null default '' check(char_length(notes)<=4096), usage jsonb not null default '{}',
 source_path text not null default '', evidence_path text not null default '',
 archived boolean not null default false, revision integer not null default 1,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 check(source_path='' or source_path like owner_id::text||'/'||asset_id::text||'/%'),
 check(evidence_path='' or evidence_path like owner_id::text||'/'||asset_id::text||'/%')
);
create index rights_assets_owner on public.rights_assets(owner_id,created_at desc);
alter table public.rights_assets enable row level security;
create policy rights_assets_select on public.rights_assets for select to authenticated using ((select auth.uid())=owner_id);
create policy rights_assets_insert on public.rights_assets for insert to authenticated with check ((select auth.uid())=owner_id);
create policy rights_assets_update on public.rights_assets for update to authenticated using ((select auth.uid())=owner_id) with check ((select auth.uid())=owner_id);
revoke all on public.rights_assets from authenticated;
grant select, insert on public.rights_assets to authenticated;
grant update(title,kind,license_id,creator,rights_holder,source_url,license_url,evidence_url,project,notes,usage,source_path,evidence_path,archived) on public.rights_assets to authenticated;
revoke all on public.rights_assets from anon;

create table public.rights_checks (
 check_id uuid primary key, owner_id uuid not null references auth.users(id) on delete cascade,
 asset_id uuid not null references public.rights_assets(asset_id), asset_revision integer not null,
 asset_snapshot jsonb not null, usage jsonb not null, result jsonb not null, created_at timestamptz not null default now()
);
create index rights_checks_owner on public.rights_checks(owner_id,created_at desc);
alter table public.rights_checks enable row level security;
create policy rights_checks_select on public.rights_checks for select to authenticated using ((select auth.uid())=owner_id);
create policy rights_checks_insert on public.rights_checks for insert to authenticated with check ((select auth.uid())=owner_id and exists(select 1 from public.rights_assets a where a.asset_id=rights_checks.asset_id and a.owner_id=(select auth.uid()) and a.revision=rights_checks.asset_revision));
revoke all on public.rights_checks from authenticated;
grant select,insert on public.rights_checks to authenticated;
revoke all on public.rights_checks from anon;

create table public.rights_connection_keys (
 key_id uuid primary key, owner_id uuid not null references auth.users(id) on delete cascade,
 label text not null check(char_length(label) between 1 and 80), token_hash text not null unique check(token_hash ~ '^[0-9a-f]{64}$'),
 resource text not null default 'aldol-rights-v02' check(resource='aldol-rights-v02'),
 scope text not null default 'rights:read' check(scope='rights:read'),
 expires_at timestamptz not null check(expires_at<=created_at+interval '90 days'),
 revoked boolean not null default false, created_at timestamptz not null default now()
);
create index rights_keys_owner on public.rights_connection_keys(owner_id);
alter table public.rights_connection_keys enable row level security;
create policy rights_keys_select on public.rights_connection_keys for select to authenticated using ((select auth.uid())=owner_id);
create policy rights_keys_insert on public.rights_connection_keys for insert to authenticated with check ((select auth.uid())=owner_id and expires_at>now() and expires_at<=now()+interval '90 days');
create policy rights_keys_revoke on public.rights_connection_keys for update to authenticated using ((select auth.uid())=owner_id) with check ((select auth.uid())=owner_id and revoked=true);
revoke all on public.rights_connection_keys from authenticated;
grant select,insert on public.rights_connection_keys to authenticated;
grant update(revoked) on public.rights_connection_keys to authenticated;
revoke all on public.rights_connection_keys from anon;

create schema if not exists rights_private;
revoke all on schema rights_private from public,anon,authenticated;
create function rights_private.bump_revision() returns trigger language plpgsql set search_path='' as $$
begin new.revision=old.revision+1; new.updated_at=now(); new.owner_id=old.owner_id; new.created_at=old.created_at; return new; end $$;
create trigger rights_revision before update on public.rights_assets for each row execute function rights_private.bump_revision();

-- The sole intentional SECURITY DEFINER: opaque-key authentication, read-only,
-- fixed actions, explicit owner predicates. No arbitrary SQL, writes or Storage access.
create function public.rights_mcp_read(p_token text,p_action text default 'identity',p_ids uuid[] default null)
returns jsonb language plpgsql security definer set search_path='' as $$
declare k public.rights_connection_keys; output jsonb; n integer;
begin
 if length(p_token)<40 or length(p_token)>160 then raise exception 'invalid connection key' using errcode='28000'; end if;
 select * into k from public.rights_connection_keys where token_hash=encode(extensions.digest(p_token,'sha256'),'hex') and not revoked and expires_at>now() and scope='rights:read' and resource='aldol-rights-v02';
 if not found then raise exception 'invalid connection key' using errcode='28000'; end if;
 if p_action='identity' then return jsonb_build_object('owner_id',k.owner_id,'key_id',k.key_id,'scope',k.scope,'expires_at',k.expires_at); end if;
 if p_ids is not null and cardinality(p_ids)>500 then raise exception 'selection exceeds 500'; end if;
 if p_action='assets' then
  select count(*) into n from public.rights_assets where owner_id=k.owner_id and not archived and (p_ids is null or asset_id=any(p_ids));
  if n>500 then raise exception 'More than 500 assets; select explicit IDs'; end if;
  if p_ids is not null and n<>cardinality(p_ids) then raise exception 'asset not found'; end if;
  select coalesce(jsonb_agg(to_jsonb(a) order by a.created_at desc),'[]'::jsonb) into output from public.rights_assets a where a.owner_id=k.owner_id and not a.archived and (p_ids is null or a.asset_id=any(p_ids));
  return output;
 elsif p_action='checks' then
  select coalesce(jsonb_agg(x),'[]'::jsonb) into output from (select check_id,asset_id,asset_revision,result,created_at from public.rights_checks where owner_id=k.owner_id order by created_at desc limit 100) x; return output;
 else raise exception 'unsupported read action'; end if;
end $$;
revoke all on function public.rights_mcp_read(text,text,uuid[]) from public;
grant execute on function public.rights_mcp_read(text,text,uuid[]) to anon,authenticated;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types) values
('rights-private','rights-private',false,10485760,array['image/png','image/jpeg','image/webp','audio/mpeg','audio/wav','video/mp4','font/ttf','font/otf','font/woff','font/woff2','application/pdf','text/plain','application/json','model/gltf-binary']);
create policy rights_files_select on storage.objects for select to authenticated using (bucket_id='rights-private' and (storage.foldername(name))[1]=(select auth.uid())::text);
create policy rights_files_insert on storage.objects for insert to authenticated with check (bucket_id='rights-private' and (storage.foldername(name))[1]=(select auth.uid())::text);
