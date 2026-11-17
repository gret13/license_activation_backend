# License Activation Backend

Сервис активации программных лицензий для работы во внутренней сети.

Backend принимает запросы от CLI-приложения, проверяет лицензии и характеристики устройств, контролирует количество активаций и сохраняет результаты в PostgreSQL.

## Архитектура

Сервис состоит из трёх Docker-контейнеров:

| Компонент | Назначение |
|---|---|
| **FastAPI** | HTTP API и логика активации лицензий |
| **PostgreSQL** | Хранение лицензий и активаций |
| **Redis** | Ограничение частоты запросов |

```text
License Activation CLI
          |
          | HTTP
          v
    FastAPI Backend
          |
          +------ Redis
          |
          +------ PostgreSQL
          |
          
```

PostgreSQL и Redis доступны только внутри Docker-сети. На хост публикуется только порт API.

## 1. Получение проекта из GitHub

Для установки необходимы Docker и Docker Compose.

Склонируйте репозиторий Backend с GitHub или скачайте его через **Code → Download ZIP**.

После загрузки структура проекта будет следующей:

```text
license_activation_backend/
├── app/
├── scripts/
│   └── init_db.py
├── tests/
├── Dockerfile
├── compose.yaml
├── compose.build.yaml
├── .env.example
└── pyproject.toml
```

Перейдите в корневую директорию проекта.

Все необходимые файлы Docker Compose и конфигурации уже находятся в репозитории.

## 2. Настройка окружения

Создайте `.env` из `.env.example`.

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**Linux:**

```bash
cp .env.example .env
```

Откройте `.env` и проверьте основные параметры:

```dotenv
BACKEND_IMAGE=ghcr.io/gret13/license_activation_backend:main

API_BIND_IP=127.0.0.1
API_PORT=55000

POSTGRES_DB=licenses
POSTGRES_USER=licenses_app
POSTGRES_PASSWORD=REPLACE_WITH_STRONG_PASSWORD

LOG_HMAC_SECRET=REPLACE_WITH_RANDOM_SECRET_MIN_32_CHARACTERS

APP_ENV=production
```

Обязательно замените `POSTGRES_PASSWORD` и `LOG_HMAC_SECRET` собственными секретными значениями.

`BACKEND_IMAGE` указывает на готовый Docker-образ, опубликованный через GitHub Actions.

По умолчанию API доступен только на Docker-хосте. Для подключения из локальной сети укажите в `API_BIND_IP` локальный IP-адрес сервера и настройте межсетевой экран.

## 3. Запуск Backend

Предусмотрены два способа запуска. **По умолчанию рекомендуется использовать готовый Docker-образ из GitHub Container Registry.**

### Способ 1. Готовый образ из GitHub (рекомендуется)

Docker-образ автоматически собирается и публикуется в GitHub Container Registry после успешного прохождения CI.

Выполните из корня проекта:

```bash
docker compose up -d --pull always
```

Docker Compose автоматически:

1. Скачает готовый Backend из GHCR.
2. Скачает PostgreSQL и Redis.
3. Создаст Docker-сеть и тома.
4. Запустит PostgreSQL и Redis.
5. Запустит Backend с автоматической инициализацией базы данных.

**Никакая локальная сборка Backend не требуется.**

Если Docker-образ приватный, необходимо предварительно авторизоваться в GHCR с правами на чтение пакета.

### Способ 2. Самостоятельная сборка из исходников

Если необходимо собрать Backend самостоятельно, используйте исходный код из того же репозитория.

Для этого предусмотрен файл `compose.build.yaml`, который дополняет основной `compose.yaml` и задаёт локальную сборку Backend через `Dockerfile`.

Выполните:

```bash
docker compose -f compose.yaml -f compose.build.yaml up -d --build
```

Docker Compose автоматически:

1. Соберёт Backend из локального `Dockerfile`.
2. Создаст образ `license-activation-backend:local`.
3. Запустит PostgreSQL и Redis.
4. Запустит Backend с автоматической инициализацией базы данных.

**Готовый Backend из GHCR при этом не используется.**

Оба способа используют одинаковую конфигурацию `.env` и Docker Compose для PostgreSQL и Redis.

## 4. Проверка работы

После запуска любым способом проверьте контейнеры:

```bash
docker compose ps
```

Просмотрите логи Backend:

```bash
docker compose logs --tail=100 api
```

При успешном запуске API доступен по адресу:

```text
http://127.0.0.1:55000
```

Инициализация PostgreSQL выполняется автоматически при запуске контейнера. Отдельно запускать `scripts/init_db.py` не требуется.

## 5. Обновление Backend

### Готовый образ из GitHub

Чтобы загрузить актуальную версию из GHCR:

```bash
docker compose up -d --pull always
```

### Самостоятельная сборка

После обновления исходного кода пересоберите Backend:

```bash
docker compose -f compose.yaml -f compose.build.yaml up -d --build
```

Данные PostgreSQL сохраняются в Docker volume.

## 6. Управление контейнерами

| Команда | Назначение |
|---|---|
| `docker compose ps` | Состояние контейнеров |
| `docker compose logs -f api` | Просмотр логов Backend |
| `docker compose restart api` | Перезапуск Backend |
| `docker compose down` | Остановка без удаления данных |

Данные PostgreSQL хранятся в Docker volume `postgres_data`.

Логи приложения и служебные файлы лицензирования размещаются в каталогах `logs/` и `secrets/`.

## 7. CI и публикация Docker-образов

GitHub Actions автоматически запускается при `push` и Pull Request в ветку `main`.

CI состоит из четырёх последовательных этапов:

| Этап | Назначение |
|---|---|
| **Ruff** | Статический анализ качества Python-кода |
| **mypy** | Проверка типизации |
| **pytest** | Модульные и интеграционные тесты |
| **Docker** | Сборка и публикация образа в GHCR |

После успешного `push` в `main` публикуются образы:

```text
ghcr.io/gret13/license_activation_backend:main
ghcr.io/gret13/license_activation_backend:sha-xxxxxxx
```

Автоматическое развёртывание Backend на сервере не предусмотрено.

## 8. Ограничения MVP

- Сервис предназначен для внутренней сети.
- HTTP используется без TLS.
- PostgreSQL и Redis не публикуются за пределами Docker-сети.
- Административный веб-интерфейс отсутствует.
- Автоматические миграции схемы PostgreSQL не предусмотрены.
- Автоматическое развёртывание на сервере отсутствует.
