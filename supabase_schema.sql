-- Schema Supabase pour Optiflow Best Solution
-- A executer dans Supabase Studio > SQL Editor (voir SETUP_SUPABASE.md).
-- Idempotent : peut etre relance sans casser l'existant.

-- 1) Catalogue produits (verres)
create table if not exists public.products (
    id              uuid primary key default gen_random_uuid(),
    advantage       text,
    family          text check (family in ('simple_foyer', 'eyezen', 'varilux')),
    lens_type       text not null,
    index           text,
    treatment       text,
    transition      text,
    geometry        text,
    recommended_for text,
    created_at      timestamptz not null default now()
);

create index if not exists products_family_idx on public.products (family);

-- Migration des bases existantes (renommage des champs + suppression du prix).
-- Idempotent : ne renomme que si l'ancienne colonne existe encore.
do $$
begin
    if exists (select 1 from information_schema.columns
               where table_schema = 'public' and table_name = 'products'
                 and column_name = 'reference') then
        alter table public.products rename column reference to advantage;
    end if;
    if exists (select 1 from information_schema.columns
               where table_schema = 'public' and table_name = 'products'
                 and column_name = 'notes') then
        alter table public.products rename column notes to recommended_for;
    end if;
end $$;

alter table public.products drop column if exists price;

-- 2) Annotations expert : une note + un statut de verification par question
create table if not exists public.expert_annotations (
    id          uuid primary key default gen_random_uuid(),
    field       text not null,          -- cle de la question (ex: 'age', 'main_need')
    question    text,                   -- libelle de la question au moment de l'annotation
    note        text,
    verified    boolean not null default false,
    author      text,
    created_at  timestamptz not null default now()
);

create index if not exists expert_annotations_field_idx on public.expert_annotations (field);

-- 3) Journal des recommandations (optionnel, pour analyse / amelioration)
create table if not exists public.recommendation_logs (
    id          uuid primary key default gen_random_uuid(),
    family      text,
    profile     jsonb,
    reco        jsonb,
    created_at  timestamptz not null default now()
);

-- 4) Validation de la recommandation finale (1 = correct, 0 = incorrect).
--    geometry_ok reste NULL si le type n'est pas un Varilux.
create table if not exists public.evaluations (
    id            uuid primary key default gen_random_uuid(),
    family        text,
    lens_type     text,
    reco          jsonb,
    type_ok       smallint check (type_ok in (0, 1)),
    treatment_ok  smallint check (treatment_ok in (0, 1)),
    index_ok      smallint check (index_ok in (0, 1)),
    transition_ok smallint check (transition_ok in (0, 1)),
    geometry_ok   smallint check (geometry_ok in (0, 1)),
    author        text,
    created_at    timestamptz not null default now()
);

-- Row Level Security.
-- Pour demarrer simplement avec la cle "anon" en lecture/ecriture, on active
-- RLS puis on ouvre une policy permissive. RESTREINDRE plus tard si besoin
-- (ex: ecriture reservee a un role authentifie expert).
alter table public.products            enable row level security;
alter table public.expert_annotations  enable row level security;
alter table public.recommendation_logs enable row level security;
alter table public.evaluations         enable row level security;

drop policy if exists "anon_all_products" on public.products;
create policy "anon_all_products" on public.products
    for all using (true) with check (true);

drop policy if exists "anon_all_annotations" on public.expert_annotations;
create policy "anon_all_annotations" on public.expert_annotations
    for all using (true) with check (true);

drop policy if exists "anon_all_logs" on public.recommendation_logs;
create policy "anon_all_logs" on public.recommendation_logs
    for all using (true) with check (true);

drop policy if exists "anon_all_evaluations" on public.evaluations;
create policy "anon_all_evaluations" on public.evaluations
    for all using (true) with check (true);
