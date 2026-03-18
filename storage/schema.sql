-- ============================================================
-- AI Психотерапевт — Схема базы данных Supabase
-- Запустить в Supabase SQL Editor
-- ============================================================

-- 1. Профили пользователей
CREATE TABLE IF NOT EXISTS user_profiles (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    display_name TEXT DEFAULT '',
    authenticated BOOLEAN DEFAULT FALSE,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_profiles_telegram_id ON user_profiles(telegram_id);

-- 2. Терапевтические сессии
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL REFERENCES user_profiles(telegram_id),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'closed', 'paused')),
    summary TEXT,
    mood_start TEXT,
    mood_end TEXT,
    topics JSONB DEFAULT '[]'
);

CREATE INDEX idx_sessions_telegram_id ON sessions(telegram_id);
CREATE INDEX idx_sessions_status ON sessions(status);

-- 3. Сообщения (история диалога)
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- 4. Долгосрочная память (факты о пользователе)
CREATE TABLE IF NOT EXISTS memory_facts (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL REFERENCES user_profiles(telegram_id),
    category TEXT NOT NULL CHECK (category IN (
        'emotions', 'relationships', 'goals', 'health',
        'beliefs', 'events', 'triggers', 'coping_strategies',
        'background', 'personality', 'preferences'
    )),
    fact TEXT NOT NULL,
    importance INTEGER DEFAULT 5 CHECK (importance BETWEEN 1 AND 10),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_memory_facts_telegram_id ON memory_facts(telegram_id);
CREATE INDEX idx_memory_facts_category ON memory_facts(category);
CREATE INDEX idx_memory_facts_active ON memory_facts(active);

-- 5. Обновляемая база знаний психотерапевта
CREATE TABLE IF NOT EXISTS knowledge_base (
    id BIGSERIAL PRIMARY KEY,
    category TEXT NOT NULL CHECK (category IN (
        'cbt', 'act', 'dbt', 'psychodynamic', 'mindfulness',
        'crisis', 'general', 'techniques', 'exercises'
    )),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_knowledge_base_category ON knowledge_base(category);
CREATE INDEX idx_knowledge_base_active ON knowledge_base(active);

-- 6. Автообновление updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_user_profiles_updated
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_memory_facts_updated
    BEFORE UPDATE ON memory_facts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_knowledge_base_updated
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 7. Row Level Security (приватность)
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;

-- Полный доступ через service_role (бот работает через service key)
CREATE POLICY "Service full access" ON user_profiles
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service full access" ON sessions
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service full access" ON messages
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service full access" ON memory_facts
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service full access" ON knowledge_base
    FOR ALL USING (true) WITH CHECK (true);
