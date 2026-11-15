#!/bin/sh
set -eu

PGHOST="${PGHOST:-db}"
PGUSER="${PGUSER:-postgres}"
export PGPASSWORD="${PGPASSWORD:-postgres}"

echo "[init-db] ожидание postgres ($PGHOST)"
until pg_isready -h "$PGHOST" -U "$PGUSER" >/dev/null 2>&1; do
  sleep 2
done

create_db() {
  name="$1"
  exists="$(psql -h "$PGHOST" -U "$PGUSER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$name'")"
  if [ "$exists" != "1" ]; then
    echo "[init-db] создаю базу $name"
    psql -h "$PGHOST" -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $name"
  fi
}

create_db courses_for_bu
create_db rag
create_db app

has_courses="$(psql -h "$PGHOST" -U "$PGUSER" -d courses_for_bu -tAc "SELECT to_regclass('public.\"Courses\"') IS NOT NULL")"
if [ "$has_courses" != "t" ]; then
  if [ ! -f /data/alfa_course_hackathon.backup ]; then
    echo "[init-db] ОШИБКА: нет /data/alfa_course_hackathon.backup (положи дамп в ./data)" >&2
    exit 1
  fi
  echo "[init-db] восстановление courses_for_bu из дампа"
  pg_restore -h "$PGHOST" -U "$PGUSER" -d courses_for_bu \
    --no-owner --no-privileges --exit-on-error \
    /data/alfa_course_hackathon.backup
else
  echo "[init-db] courses_for_bu уже восстановлена"
fi

has_chats="$(psql -h "$PGHOST" -U "$PGUSER" -d app -tAc "SELECT to_regclass('public.chats') IS NOT NULL")"
if [ "$has_chats" != "t" ]; then
  echo "[init-db] применяю db/schema.sql в app"
  psql -h "$PGHOST" -U "$PGUSER" -d app -v ON_ERROR_STOP=1 -f /schema.sql >/dev/null
else
  echo "[init-db] схема app уже применена"
fi

echo "[init-db] готово"
