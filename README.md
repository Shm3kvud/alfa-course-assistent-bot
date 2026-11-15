# Alfa Course Assistant Bot

Telegram-бот-консультант с RAG по материалам платформы «Альфа Курсы»: подбирает курсы, уроки, статьи, шаблоны, вебинары, подкасты и калькуляторы под сферу, опыт и цель пользователя.

Проект для хакатона **Hack & Change 2026**.

**В разработке участвовали:** TamerlanIkaev — A (Telegram-бот и история диалогов), Shm3kvud — B (RAG-инфраструктура и PGVector), Alinux228 — C (RAG-пайплайн, LLM, подготовка базы знаний).

---

## Быстрый старт

[Запуск через Docker (одна команда)](#docker) · [Ручной запуск](#manual) · [Как это работает](#how-it-works)

### Что нужно заранее

- Docker Engine или Docker Desktop с Compose.
- Файл `.env` — скопируйте `.env.example` и заполните `BOT_TOKEN` и `GIGACHAT_API_KEY`.
- Файл `data/alfa_course_hackathon.backup` (~19 МБ) — дамп платформы, выдаётся организаторами. В git он не хранится.

### Одна команда

```bash
docker compose up --build
```

Что произойдёт: поднимется Postgres, восстановятся исходные данные, создадутся базы `courses_for_bu`, `app`, `rag`, выполнятся индексация 1887 документов и запуск Telegram-бота.

- Первый запуск: 5–15 минут (сборка образа ~3 ГБ + модель).
- Повторный запуск: секунды, индексация пропускается.
- Остановить: `Ctrl+C` или `docker compose down`.
- Полный сброс с пересозданием базы и индекса: `docker compose down -v`.

Подробная инструкция: [Запуск через Docker](#docker).

---

## О проекте

### Проблема

На платформе «Альфа Курсы» много разнородных материалов, и новичку сложно быстро понять, с чего начать. Начинающий предприниматель (например, 18-летний пользователь, который хочет открыть табачный магазин) теряется среди десятков курсов, сотен статей и шаблонов. А уверенный предприниматель не всегда найдет время на скроллинг сайта и самостоятельный подбор материалов. Им нужен помощник, который задаст уточняющие вопросы и порекомендует подходящие материалы.

### Решение

Telegram-бот-консультант с RAG-системой. Бот общается с пользователем, задаёт уточняющие вопросы, учитывает цель, опыт и сферу бизнеса, а затем рекомендует подходящие материалы на основе базы знаний платформы. Ответ конкретный и объяснимый: бот не просто даёт ссылку, а объясняет, почему материал подходит и что делать дальше.

### Для кого

- Новички — начинающие предприниматели, которые только хотят открыть бизнес.
- Продвинутые — предприниматели с опытом, которым нужно развитие или масштабирование.
- Самые продвинутые — опытные предприниматели, которым нужны узкие и продвинутые темы.

### Гипотеза

Если помочь пользователю подобрать обучение через Telegram-бота за короткое время, ему будет комфортнее выбирать материалы, а платформа получит больше целевых переходов и продаж курсов. Бот даёт более точные рекомендации, чем обычный каталог, потому что учитывает потребности пользователя и работает с неполными данными.

### Что умеет бот

- Может задать уточняющий вопрос, если запрос расплывчатый — через промпт, без отдельного профиля пользователя.
- Рекомендует материалы на основе запроса и базы знаний.
- Объясняет, почему рекомендует именно этот материал, и предлагает следующий шаг.
- Даёт ссылки только из базы знаний, без выдуманных URL.
- Сохраняет историю диалогов, позволяет переключаться между чатами и очищать историю.
- Работает с разными типами материалов: курсы, уроки, статьи, шаблоны, вебинары, подкасты, калькуляторы.

### Пример сценария

1. Пользователь: «Хочу открыть табачный магазин, с чего начать?»
2. Если запрос расплывчатый, бот может задать уточняющий вопрос.
3. Бот находит подходящие курсы, статьи и шаблоны, объясняет, почему они подходят.
4. Бот даёт реальные ссылки из базы знаний и предлагает следующий шаг.

---

<a id="how-it-works"></a>
## Как это работает

### Архитектура

```
Telegram
   |
   v
bot/handlers/*  (aiogram 3)
   |
   v
rag/pipeline.answer
   |            \
   v             v
rag/retriever  memory/session (история для LLM, 5 пар)
   |
   v
vector_db/vectorstore.search
   |
   v
Postgres + pgvector  (база rag, коллекция knowledge)
   |
   v
llm/client.generate  ->  GigaChat-2-Max  ->  ответ + ссылки
```

### Индексация (офлайн, CLI)

```
courses_for_bu
  -> db/db_loader.py        читает материалы, собирает Document (текст + metadata)
  -> rag/embeddings.py      текст -> вектор (e5, префиксы passage:/query:, L2-нормализация)
  -> vector_db/vectorstore.py  запись в PGVector батчами (upsert по стабильному id)
```

### Ответ на вопрос (онлайн)

```
вопрос
  -> rag/retriever.py       эмбеддинг запроса -> top-k по косинусу -> порог SCORE_THRESHOLD
  -> rag/pipeline.py        контекст + факты из metadata + история диалога + промпт
  -> llm/client.py          GigaChat-2-Max
  -> ответ пользователю
```

### История диалогов

- `db/history.py` — чаты и сообщения в Postgres (база `app`): список, открытие, очистка. Работает через `asyncpg` и переменные `DB_*`.
- `memory/session.py` — последние 5 пар «вопрос-ответ», которые передаются LLM. При открытии чата контекст восстанавливается из его сообщений; при новом чате и очистке истории сбрасывается.
- После рестарта контекст LLM пуст, пока пользователь не откроет сохранённый чат; история в интерфейсе при этом остаётся в Postgres.
- При открытии чата показываются последние 3 сообщения.

---

## База знаний

Источник — дамп платформы, восстановленный в Postgres (база `courses_for_bu`).
Векторная база — Postgres + pgvector (база `rag`, коллекция `knowledge`).

| Категория | Документов |
|---|---:|
| Курсы | 37 |
| Уроки | 512 |
| Доп. информация о курсах | 185 |
| Частые вопросы о курсах | 22 |
| Статьи | 855 |
| Шаблоны | 247 |
| Вебинары | 13 |
| Подкасты | 8 |
| Калькуляторы | 7 |
| Подписки | 1 |
| **Итого** | **1887** |

- Один материал = один `Document`: `page_content` (текст) + `metadata` (`id`, `url`, `source_type` и специфичные поля).
- `id` стабильный и уникальный (`course:…`, `article:…`, `lesson:{lesson_id}_{course_id}` и т.п.), поэтому повторная индексация не плодит дубликаты.
- Векторная размерность — 384 (`intfloat/multilingual-e5-small`).

---

## Стек

- Python 3.12, пакетный менеджер [uv](https://docs.astral.sh/uv/)
- **aiogram 3** — Telegram-бот, `telegramify-markdown` для форматирования
- **sentence-transformers**, модель `intfloat/multilingual-e5-small` (fallback `e5-large`): префиксы `query:` / `passage:`, L2-нормализация, 384 измерения
- **Postgres 17 + pgvector** (`pgvector/pgvector:pg17`), базы `courses_for_bu`, `app`, `rag`
- **PGVector** (`langchain-postgres`) + **psycopg** — векторный поиск
- **asyncpg** — история чатов бота
- **GigaChat-2-Max** (`langchain-gigachat`) — текстовая модель
- **pydantic-settings** — единые настройки из `.env`
- **Docker / Docker Compose** — запуск одной командой

---

## Структура проекта

Роли: A — TamerlanIkaev, B — Shm3kvud, C — Alinux228.

```text
alpha-course-assistent-bot/
├── main.py                 # A: точка входа Telegram-бота
├── config.py               # B: настройки из .env
├── Dockerfile              # B: образ приложения (python:3.12-slim + uv)
├── docker-compose.yml      # B: db + init-db + init-rag + app
├── README.md               # B: документация и запуск
├── pyproject.toml          # B
├── uv.lock                 # B
├── .env.example            # B
├── .python-version         # B
├── .dockerignore           # B
├── .gitattributes          # B
├── test_rag.py             # A: локальная проверка RAG без Telegram
│
├── bot/                    # A: Telegram-бот
│   ├── handlers/
│   │   ├── start.py        # A: /start, главное меню
│   │   └── chat.py         # A: вопросы, ответы, история, очистка
│   └── keyboards/
│       └── keyboards.py    # A
│
├── db/                     # C: чтение исходной БД, A: история
│   ├── db_loader.py        # C: courses_for_bu -> Document
│   ├── history.py          # A: история чатов в Postgres (asyncpg)
│   ├── schema.sql          # A: таблицы chats/messages
│   └── check_db.py         # A: dev-скрипт проверки подключения
│
├── vector_db/
│   └── vectorstore.py      # B: PGVector: коллекция, upsert, поиск
│
├── rag/
│   ├── embeddings.py       # B: e5, префиксы, нормализация, fallback
│   ├── retriever.py        # B: retrieve / aretrieve + порог
│   ├── ingest.py           # B: офлайн-индексация: fetch -> embed -> upsert
│   └── pipeline.py         # C: RAG-ответ: retrieve -> промпт -> LLM
│
├── llm/
│   ├── client.py           # C: GigaChat
│   └── prompts.py          # C: системный промпт
│
├── memory/
│   └── session.py          # C: история для LLM (in-memory, 5 пар)
│
├── scripts/
│   ├── init_db.sh          # B: базы, restore дампа, схема app
│   └── init_rag.py         # B: проверка коллекции и ingest при необходимости
│
└── data/                   # общие данные (дамп, в git не попадает)
```

> `.env`, `data/`, `.venv/`, `data_extracted.json` — в `.gitignore`.
> `test_rag.py` — локальный dev-скрипт для проверки retrieval/ответа без Telegram.

---

<a id="docker"></a>
## Запуск через Docker

### 1. Подготовка

```bash
cp .env.example .env
```

Заполните в `.env`:

- `BOT_TOKEN` — токен бота от [@BotFather](https://t.me/BotFather);
- `GIGACHAT_API_KEY` — ключ GigaChat.

Остальные значения можно оставить как в `.env.example`: для Docker compose сам переопределяет адреса БД на хост `db`.

Положите дамп в `data/`:

```
data/alfa_course_hackathon.backup
```

### 2. Запуск

```bash
docker compose up --build
```

Или в фоне:

```bash
docker compose up -d --build
docker compose logs -f app
```

### 3. Что происходит

| Сервис | Назначение |
|---|---|
| `db` | Postgres 17 + pgvector, том `pgdata`, порт `127.0.0.1:5432` |
| `init-db` | Создаёт `courses_for_bu`, `app`, `rag`; восстанавливает дамп; применяет `db/schema.sql` |
| `init-rag` | Если коллекция пуста — запускает `python -m rag.ingest`, иначе пропускает |
| `app` | Запускает `python main.py` (Telegram-бот) |

Порядок: `db` (healthy) → `init-db` (завершился) → `init-rag` (завершился) → `app`.
`init-db` и `init-rag` идемпотентны: повторный `docker compose up` не перезаписывает данные и не переиндексирует.

### 4. Проверка

```bash
docker compose ps
docker compose logs init-db
docker compose logs init-rag
docker compose logs -f app
```

Проверить количество документов в векторной базе:

```bash
docker compose exec -T db psql -U postgres -d rag -c "SELECT count(*) FROM langchain_pg_embedding;"
```

Ожидаемо: `1887`.

Проверить распределение по типам:

```bash
docker compose exec -T db psql -U postgres -d rag -c "SELECT cmetadata->>'source_type' AS type, count(*) FROM langchain_pg_embedding GROUP BY 1 ORDER BY 2 DESC;"
```

### 5. Остановка и сброс

```bash
docker compose down        # остановить, данные сохраняются
docker compose down -v     # удалить том с БД; следующий up восстановит дамп и переиндексирует
```

### 6. Смена модели эмбеддингов

В образ заранее скачивается `intfloat/multilingual-e5-small`, а в compose включён `HF_HUB_OFFLINE=1`. Поэтому:

- чтобы использовать другую модель, поменяйте строку предзагрузки в `Dockerfile` и пересоберите образ (`docker compose build`);
- либо уберите `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` в `docker-compose.yml`, чтобы модель скачалась при первом старте;
- при смене размерности (384 → 1024) обязателен `docker compose down -v`: тип колонки `vector(384)` не меняется автоматически.

---

<a id="manual"></a>
## Ручной запуск

Вариант без Docker для приложения, но с Postgres в Docker. Команды для PowerShell (Windows); на Linux/macOS аналогично.

### 1. Зависимости

Нужны Python 3.12, [uv](https://docs.astral.sh/uv/) и Docker.

```powershell
uv sync
```

### 2. Настройки

```powershell
Copy-Item .env.example .env
```

Заполните `BOT_TOKEN` и `GIGACHAT_API_KEY`. Адреса БД в `.env` указывают на `localhost:5432` — это подходит для ручного запуска (`db`-контейнер пробрасывает порт).

Важно: `SOURCE_DATABASE_URL` и `APP_DATABASE_URL` используют обычную схему `postgresql://` (psycopg), а `VECTOR_DATABASE_URL` — `postgresql+psycopg://` (SQLAlchemy/langchain-postgres).

### 3. Postgres

```powershell
docker compose up -d db
docker compose ps        # ждём healthy
```

### 4. Базы, дамп и схема истории

```powershell
docker compose run --rm init-db
```

Скрипт создаст базы `courses_for_bu`, `app`, `rag`, восстановит `data/alfa_course_hackathon.backup` и применит `db/schema.sql` в `app`.

### 5. Индексация

```powershell
uv run python -m rag.ingest
```

Ожидаемо: счётчики по категориям, прогресс батчей (`200/1887`, …), итог.
Первый запуск скачивает модель e5-small (~470 МБ). Если модель уже в кэше и сеть нестабильна:

```powershell
$env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"
uv run python -m rag.ingest
```

Проверка:

```powershell
docker compose exec -T db psql -U postgres -d rag -c "SELECT count(*) FROM langchain_pg_embedding;"
```

### 6. Запуск бота

```powershell
uv run python main.py
```

Не запускайте одновременно локального бота и Docker-контейнер `app` с тем же `BOT_TOKEN`: Telegram разрешает только один polling, второй получит `409 Conflict`.

### 7. Проверка без Telegram

```powershell
uv run python test_rag.py
```

Скрипт прогоняет несколько запросов через retrieval и один полный ответ через GigaChat.

Только поиск, без LLM:

```powershell
uv run python -c "import asyncio; from rag.retriever import aretrieve; docs=asyncio.run(aretrieve('хочу открыть табачный магазин', 5)); print('найдено:', len(docs)); [print(d.metadata.get('id'), d.metadata.get('source_type')) for d in docs]"
```

### 8. Переиндексация

`ingest` каждый раз пересоздаёт коллекцию (`pre_delete=True`), поэтому повторный запуск безопасен: дублей не будет, коллекция перезапишется.

---

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `BOT_TOKEN` | — | Токен Telegram-бота |
| `GIGACHAT_API_KEY` | — | Ключ GigaChat |
| `GIGACHAT_MODEL` | `GigaChat-2-Max` | Текстовая модель |
| `GIGACHAT_SCOPE` | `GIGACHAT_API_PERS` | Scope доступа |
| `SOURCE_DATABASE_URL` | — | Исходная база `courses_for_bu` (psycopg, `postgresql://`) |
| `APP_DATABASE_URL` | — | База приложения (зарезервирована) |
| `VECTOR_DATABASE_URL` | — | Векторная база `rag` (SQLAlchemy, `postgresql+psycopg://`) |
| `COLLECTION_NAME` | `knowledge` | Имя коллекции в pgvector |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Модель эмбеддингов |
| `EMBEDDING_FALLBACK_MODEL` | `intfloat/multilingual-e5-large` | Fallback при ошибке загрузки |
| `EMBEDDING_BATCH_SIZE` | `16` | Батч инференса эмбеддингов |
| `EMBEDDING_DEVICE` | `cpu` | Устройство инференса |
| `TOP_K` | `5` | Сколько документов брать из поиска |
| `SCORE_THRESHOLD` | `0.84` | Минимальная cosine similarity |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `localhost` / `5432` / `app` / `postgres` / `postgres` | Подключение истории чатов (`asyncpg`) |

В Docker compose адреса БД и `DB_HOST` переопределяются на `db`.

---

## Диагностика

Полезные строки в логах:

```
vector store: db=localhost:5432/rag collection=knowledge dim=384
retrieval: '...' -> 15 docs, types=article,calculator,document
```

- `vector store` показывает, к какой базе/коллекции подключился процесс и какая размерность.
- `retrieval` показывает, сколько документов прошло порог и какие типы материалов попали в контекст.

Если бот отвечает «не нашёл», а материал в базе есть:

1. Проверьте `count(*)` — должно быть `1887`.
2. Проверьте `types=...` в логе retrieval.
3. Проверьте порог `SCORE_THRESHOLD` (для другой модели эмбеддингов его нужно калибровать заново).

---

## Известные ограничения

- **Тонкий контекст:** индексируются название, рубрика и краткое описание материала, а не полные тела статей/уроков. Это ограничивает глубину ответов.
- Нет метрик качества (recall@k), reranker и гибридного поиска.
- Порог `0.84` подобран под e5-small; для другой модели его нужно калибровать.
- Fallback на e5-large меняет размерность (384 → 1024); без переиндексации поиск сломается. На fallback лучше не рассчитывать в проде.
- Контекст диалога для LLM живёт в памяти процесса; после рестарта он пуст, пока не открыть сохранённый чат (тогда восстанавливается из БД).
- Уточняющие вопросы не оформлены как отдельный сценарий или профиль пользователя — зависят от промпта и истории.
- Один `BOT_TOKEN` — один polling-процесс. Локальный бот и Docker-бот одновременно работать не будут.
- Docker-образ ~3 ГБ (CPU-торч + модель в образе). Первая сборка требует сети.

---

## Частые проблемы

- **Нет `.env`** — `docker compose` падает на `env_file`. Скопируйте `.env.example` в `.env`.
- **Пустые значения в `.env`** — pydantic не сможет разобрать числа (`SCORE_THRESHOLD=""`). Оставьте значения из `.env.example`.
- **Нет `data/alfa_course_hackathon.backup`** — `init-db` завершится с понятной ошибкой. Положите дамп в `data/`.
- **Порт 5432 занят** — поменяйте проброс в `docker-compose.yml` (например, `127.0.0.1:5433:5432`). Для ручного запуска дополнительно поправьте порт в URL и `DB_PORT` в `.env`; внутри Docker-сети адрес остаётся `db:5432`.
- **`connection refused`** — не поднят `courses-db`; проверьте `docker compose ps`.
- **`ModuleNotFoundError`** — запускайте из корня репозитория и через `uv run ...`, либо выполните `uv sync`.
- **Долгий старт модели** — первый запуск скачивает e5-small; при нестабильной сети используйте `HF_HUB_OFFLINE=1`, когда модель уже в кэше.
- **`409 Conflict` в логах бота** — запущен второй экземпляр с тем же `BOT_TOKEN`.
- **Кракозябры в консоли Windows** — это кодировка, не данные: `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` и `$env:PYTHONIOENCODING="utf-8"`.
- **Мало места на диске** — очистите кэш сборки: `docker builder prune -af`.

---

## Лицензия

MIT, 2026. См. [LICENSE](LICENSE).
