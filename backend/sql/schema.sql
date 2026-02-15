-- ============================================
-- ZeeXClub - Schéma Base de Données Supabase
-- ============================================

-- Activer l'extension UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABLE: shows (Films & Séries)
-- ============================================
CREATE TABLE shows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tmdb_id INTEGER UNIQUE NOT NULL,
    title TEXT NOT NULL,
    original_title TEXT,
    type TEXT CHECK (type IN ('movie', 'series')) NOT NULL,
    overview TEXT,
    poster_path TEXT,
    backdrop_path TEXT,
    release_date DATE,
    genres TEXT[] DEFAULT '{}',
    runtime INTEGER, -- en minutes
    rating DECIMAL(3,1),
    language TEXT DEFAULT 'fr',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'pending')),
    views INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index pour performances
CREATE INDEX idx_shows_type ON shows(type);
CREATE INDEX idx_shows_status ON shows(status);
CREATE INDEX idx_shows_tmdb_id ON shows(tmdb_id);
CREATE INDEX idx_shows_created_at ON shows(created_at DESC);
CREATE INDEX idx_shows_views ON shows(views DESC);

-- Trigger pour updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_shows_updated_at BEFORE UPDATE ON shows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- TABLE: seasons (Saisons pour séries)
-- ============================================
CREATE TABLE seasons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    show_id UUID NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    season_number INTEGER NOT NULL,
    name TEXT,
    overview TEXT,
    poster TEXT,
    air_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(show_id, season_number)
);

CREATE INDEX idx_seasons_show_id ON seasons(show_id);
CREATE INDEX idx_seasons_number ON seasons(season_number);

-- ============================================
-- TABLE: episodes
-- ============================================
CREATE TABLE episodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    season_id UUID NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    episode_number INTEGER NOT NULL,
    title TEXT,
    overview TEXT,
    thumbnail TEXT,
    air_date DATE,
    runtime INTEGER, -- en minutes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(season_id, episode_number)
);

CREATE INDEX idx_episodes_season_id ON episodes(season_id);
CREATE INDEX idx_episodes_number ON episodes(episode_number);

-- ============================================
-- TABLE: video_sources (Liens streaming)
-- ============================================
CREATE TABLE video_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    episode_id UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    server_name TEXT CHECK (server_name IN ('filemoon', 'telegram')) NOT NULL,
    link TEXT NOT NULL,
    file_id TEXT, -- Pour Telegram
    filemoon_code TEXT, -- Pour Filemoon
    quality TEXT DEFAULT 'HD' CHECK (quality IN ('SD', 'HD', 'FHD', '4K')),
    language TEXT DEFAULT 'FR',
    is_active BOOLEAN DEFAULT TRUE,
    file_size BIGINT, -- en bytes
    duration INTEGER, -- en secondes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_video_sources_episode ON video_sources(episode_id);
CREATE INDEX idx_video_sources_server ON video_sources(server_name);
CREATE INDEX idx_video_sources_active ON video_sources(is_active);

-- ============================================
-- TABLE: bot_sessions (Sessions admin bot)
-- ============================================
CREATE TABLE bot_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id BIGINT NOT NULL UNIQUE,
    current_show_id UUID REFERENCES shows(id),
    current_season_id UUID REFERENCES seasons(id),
    state TEXT DEFAULT 'idle',
    temp_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_bot_sessions_admin ON bot_sessions(admin_id);

-- ============================================
-- TABLE: upload_tasks (Tâches Filemoon)
-- ============================================
CREATE TABLE upload_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    episode_id UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL, -- Telegram file_id
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'uploading', 'processing', 'completed', 'failed')),
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    filemoon_code TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_upload_tasks_status ON upload_tasks(status);
CREATE INDEX idx_upload_tasks_episode ON upload_tasks(episode_id);

-- Trigger pour updated_at
CREATE TRIGGER update_upload_tasks_updated_at BEFORE UPDATE ON upload_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VUES POUR STATISTIQUES
-- ============================================

-- Vue des shows avec nombre de saisons/épisodes
CREATE VIEW show_stats AS
SELECT 
    s.*,
    COUNT(DISTINCT sea.id) as seasons_count,
    COUNT(DISTINCT e.id) as episodes_count,
    COUNT(DISTINCT vs.id) as sources_count
FROM shows s
LEFT JOIN seasons sea ON sea.show_id = s.id
LEFT JOIN episodes e ON e.season_id = sea.id
LEFT JOIN video_sources vs ON vs.episode_id = e.id
GROUP BY s.id;

-- ============================================
-- POLITIQUES DE SÉCURITÉ (RLS)
-- ============================================

-- Activer RLS sur toutes les tables
ALTER TABLE shows ENABLE ROW LEVEL SECURITY;
ALTER TABLE seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_sources ENABLE ROW LEVEL SECURITY;

-- Politique: Lecture publique pour les shows actifs
CREATE POLICY "Shows visibles publiquement" ON shows
    FOR SELECT USING (status = 'active');

CREATE POLICY "Saisons visibles publiquement" ON seasons
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM shows WHERE id = seasons.show_id AND status = 'active')
    );

CREATE POLICY "Épisodes visibles publiquement" ON episodes
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM seasons s 
            JOIN shows sh ON sh.id = s.show_id 
            WHERE s.id = episodes.season_id AND sh.status = 'active'
        )
    );

CREATE POLICY "Sources visibles publiquement" ON video_sources
    FOR SELECT USING (is_active = TRUE);

-- Politique: Modification uniquement par le bot (service role)
-- À configurer côté Supabase Dashboard avec les clés de service

-- ============================================
-- FONCTIONS UTILITAIRES
-- ============================================

-- Fonction de recherche full-text
CREATE OR REPLACE FUNCTION search_shows(search_query TEXT)
RETURNS SETOF shows AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM shows
    WHERE status = 'active'
    AND (
        title ILIKE '%' || search_query || '%'
        OR original_title ILIKE '%' || search_query || '%'
        OR overview ILIKE '%' || search_query || '%'
    )
    ORDER BY views DESC;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour incrémenter les vues
CREATE OR REPLACE FUNCTION increment_show_views(show_uuid UUID)
RETURNS void AS $$
BEGIN
    UPDATE shows 
    SET views = views + 1,
        updated_at = NOW()
    WHERE id = show_uuid;
END;
$$ LANGUAGE plpgsql;
