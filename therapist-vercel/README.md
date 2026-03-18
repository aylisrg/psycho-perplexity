# 🧠 AI-Психотерапевт — Vercel + Telegram + Supabase

Приватный AI-психотерапевт на Vercel serverless. Текст + голос, долгосрочная память, переключение моделей.

## Архитектура

```
Вы (Telegram)
    ↓ webhook
Vercel (serverless functions)
    ├→ Claude / OpenAI / Custom API (думает)
    ├→ OpenAI Whisper (голос → текст)
    ├→ OpenAI TTS (текст → голос)
    └→ Supabase (память, сессии, знания)
```

GitHub push → Vercel автодеплой → бот обновляется.

---

## Установка за 15 минут

### Шаг 1: Telegram Bot

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`, дайте имя и username
3. Скопируйте токен (формат: `123456:ABC-DEF...`)
4. Узнайте свой Telegram ID — отправьте что-нибудь [@userinfobot](https://t.me/userinfobot)

### Шаг 2: Supabase

1. Зайдите на [supabase.com](https://supabase.com), создайте проект
2. Подождите ~2 минуты пока проект инициализируется
3. Откройте **SQL Editor** (иконка в левом меню)
4. Скопируйте содержимое файла `storage/schema.sql` → вставьте в редактор → нажмите **Run**
5. Перейдите в **Project Settings → API**:
   - Скопируйте **Project URL** (формат: `https://xxxxx.supabase.co`)
   - Скопируйте **service_role key** (длинный ключ, НЕ anon key)

### Шаг 3: API-ключи

- **Anthropic Claude**: [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key
- **OpenAI** (для голоса): [platform.openai.com](https://platform.openai.com) → API Keys → Create

### Шаг 4: GitHub репозиторий

1. Создайте **приватный** репозиторий на GitHub
2. Загрузите туда все файлы этого проекта:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USER/therapist-bot.git
git push -u origin main
```

### Шаг 5: Vercel

1. Зайдите в [vercel.com](https://vercel.com) → **Add New Project**
2. Импортируйте ваш GitHub-репо
3. **Framework Preset**: Other
4. Откройте **Settings → Environment Variables** и добавьте:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Токен из BotFather |
| `TELEGRAM_ALLOWED_USERS` | Ваш Telegram ID (число) |
| `SUPABASE_URL` | `https://xxxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Service role key из Supabase |
| `ANTHROPIC_API_KEY` | Ключ Claude |
| `OPENAI_API_KEY` | Ключ OpenAI |
| `WEBHOOK_SECRET` | Любая случайная строка (для защиты webhook) |

Необязательные:
| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_AI_PROVIDER` | `claude` | `claude`, `openai`, или `custom` |
| `CLAUDE_DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Модель Claude |
| `VOICE_ENABLED` | `true` | Включить голос |
| `TTS_VOICE` | `alloy` | Голос TTS: alloy, echo, fable, onyx, nova, shimmer |
| `CUSTOM_AI_API_KEY` | — | Ключ для OpenRouter/Groq/etc. |
| `CUSTOM_AI_BASE_URL` | — | URL API (напр. `https://openrouter.ai/api/v1`) |
| `CUSTOM_AI_NAME` | — | Название провайдера |
| `CUSTOM_AI_DEFAULT_MODEL` | — | Модель по умолчанию |
| `CUSTOM_AI_MODELS` | — | Список моделей через запятую |

5. Нажмите **Redeploy** (чтобы переменные применились)

### Шаг 6: Активация

Откройте в браузере:
```
https://your-project.vercel.app/api/setup
```

Вы увидите JSON с результатами:
- Webhook установлен
- Команды бота зарегистрированы
- База знаний загружена

### Шаг 7: Готово!

Откройте бота в Telegram и отправьте `/start` 🎉

---

## Как обновлять

1. Получите обновлённые файлы
2. Замените их в репозитории
3. `git add . && git commit -m "Update" && git push`
4. Vercel автоматически задеплоит новую версию (~30 сек)

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие |
| `/newsession` | Начать новую сессию |
| `/endsession` | Завершить сессию (с резюме) |
| `/model` | Выбрать AI-модель |
| `/voice` | Вкл/выкл голосовые ответы |
| `/memory` | Что бот помнит о вас |
| `/history` | История сессий |
| `/knowledge` | Управление базой знаний |
| `/help` | Справка |

## Добавление знаний

Отправьте боту текст в формате:
```
категория | заголовок | содержание | источник
```

Категории: `cbt`, `act`, `dbt`, `psychodynamic`, `mindfulness`, `crisis`, `general`, `techniques`, `exercises`

---

## Структура проекта

```
therapist-vercel/
├── api/
│   ├── webhook.py        ← Telegram webhook (основной endpoint)
│   ├── setup.py          ← Установка webhook + загрузка знаний
│   └── health.py         ← Health check
├── core/
│   ├── config.py         ← Конфигурация (env vars)
│   ├── therapist.py      ← Ядро психотерапевта
│   ├── ai_provider.py    ← Claude / OpenAI / Custom
│   ├── system_prompt.py  ← Терапевтический промпт + промпты памяти
│   └── voice.py          ← STT (Whisper) + TTS
├── storage/
│   ├── supabase_client.py ← Работа с Supabase
│   └── schema.sql        ← SQL-схема (выполнить в Supabase)
├── knowledge/
│   └── default_knowledge.py ← Начальная база знаний
├── vercel.json           ← Конфигурация Vercel
├── requirements.txt      ← Зависимости Python
└── README.md
```

## Проверка работоспособности

- Health check: `GET /api/health` — покажет статус всех подключений
- Webhook info: `GET /api/webhook` — подтверждение что endpoint работает
- Setup: `GET /api/setup` — переустановить webhook и перезагрузить знания

## Безопасность

- Приватный GitHub-репо (код не публичный)
- Ключи в Vercel Environment Variables (не в коде)
- `TELEGRAM_ALLOWED_USERS` — только ваш ID
- `WEBHOOK_SECRET` — защита endpoint от чужих запросов
- Supabase RLS включён
- Service Role Key даёт доступ только боту

## Дисклеймер

Это инструмент для самопознания и поддержки, **не замена профессиональной психотерапии**.
