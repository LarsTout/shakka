-- WP-22 (A-16): the notification channel of M1 was dropped; remove its unused column.
alter table public.profiles drop constraint if exists profiles_telegram_chat_id_format;
alter table public.profiles drop column if exists telegram_chat_id;
