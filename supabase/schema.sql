-- MedQuiz cross-device sync schema.
-- Run this once in the Supabase dashboard: SQL Editor -> New query -> paste -> Run.

create table if not exists public.progress (
  user_id uuid references auth.users not null,
  id text not null,
  data jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, id)
);

create table if not exists public.anki_cards (
  user_id uuid references auth.users not null,
  id text not null,
  data jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, id)
);

create table if not exists public.bookmarks (
  user_id uuid references auth.users not null,
  id text not null,
  data jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, id)
);

create table if not exists public.settings (
  user_id uuid references auth.users not null,
  key text not null,
  data jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, key)
);

-- Row Level Security: every user can only ever see/write their own rows.
alter table public.progress enable row level security;
alter table public.anki_cards enable row level security;
alter table public.bookmarks enable row level security;
alter table public.settings enable row level security;

create policy "own progress" on public.progress
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own anki_cards" on public.anki_cards
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own bookmarks" on public.bookmarks
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own settings" on public.settings
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Keep updated_at current on every write (used for last-write-wins merge).
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger touch_progress before update on public.progress
  for each row execute function public.touch_updated_at();
create trigger touch_anki_cards before update on public.anki_cards
  for each row execute function public.touch_updated_at();
create trigger touch_bookmarks before update on public.bookmarks
  for each row execute function public.touch_updated_at();
create trigger touch_settings before update on public.settings
  for each row execute function public.touch_updated_at();
