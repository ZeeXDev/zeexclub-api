-- backend/database/migrations.sql

-- Scripts SQL d'initialisation pour Supabase
-- À exécuter dans l'éditeur SQL Supabase
---

-- =====================================================
-- EXTENSIONS NÉCESSAIRES
-- =====================================================

-- Pour la recherche full-text et similarité
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS uuid-ossp;

-- =====================================================
-- TABLES PRINCIPALES
-- =====================================================

-- Table des dossiers (films/séries/saisons)
CREATE TABLE IF NOT EXISTS folders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    folder_name TEXT NOT NULL,
    parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    
    -- Champs d'enrichissement TMDB
    tmdb_id INTEGER,
    title TEXT,
    description TEXT,
    poster_url TEXT,
    poster_url_small TEXT,
    backdrop_url TEXT,
    year INTEGER,
    rating DECIMAL(3,1),
    genres TEXT[] DEFAULT '{}',
    media_type TEXT CHECK (media_type IN ('movie', 'tv')),
    tmdb_updated_at TIMESTAMP WITH TIME ZONE,
    
    -- Pour séries (sous-dossiers saisons)
    season_number INTEGER,
    season_overview TEXT,
    season_poster TEXT,
    episode_count INTEGER
);

-- Table des vidéos (films ou épisodes)
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    
    -- Numérotation
    episode_number INTEGER,
    season_number INTEGER,
    
    -- Sources vidéo
    file_id TEXT NOT NULL UNIQUE,
    zeex_url TEXT NOT NULL,
    filemoon_url TEXT,
    
    -- Métadonnées fichier
    caption TEXT,
    file_size BIGINT,
    duration INTEGER,
    width INTEGER,
    height INTEGER,
    mime_type TEXT,
    
    -- Métadonnées TMDB
    poster_url TEXT,
    year INTEGER,
    genre TEXT[] DEFAULT '{}',
    rating DECIMAL(3,1),
    tmdb_episode_id INTEGER,
    still_path TEXT,
    air_date DATE,
    
    -- Statistiques
    views_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Table des mappings de streaming
CREATE TABLE IF NOT EXISTS stream_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    unique_id TEXT NOT NULL UNIQUE,
    file_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Table des commentaires
CREATE TABLE IF NOT EXISTS comments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    comment_text TEXT NOT NULL CHECK (char_length(comment_text) <= 1000),
    likes INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

-- Table de la liste de l'utilisateur
CREATE TABLE IF NOT EXISTS watchlist (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    UNIQUE(user_id, video_id)
);

-- Table de l'historique de visionnage
CREATE TABLE IF NOT EXISTS watch_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    progress INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT FALSE,
    last_watched TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW()),
    UNIQUE(user_id, video_id)
);

-- =====================================================
-- INDEX POUR PERFORMANCE
-- =====================================================

-- Index sur folders
CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);
CREATE INDEX IF NOT EXISTS idx_folders_name ON folders(folder_name);
CREATE INDEX IF NOT EXISTS idx_folders_tmdb_id ON folders(tmdb_id) WHERE tmdb_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_folders_year ON folders(year) WHERE year IS NOT NULL;

-- Index sur videos
CREATE INDEX IF NOT EXISTS idx_videos_folder ON videos(folder_id);
CREATE INDEX IF NOT EXISTS idx_videos_file_id ON videos(file_id);
CREATE INDEX IF NOT EXISTS idx_videos_episode ON videos(season_number, episode_number);
CREATE INDEX IF NOT EXISTS idx_videos_created ON videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_genre ON videos USING GIN(genre);
CREATE INDEX IF NOT EXISTS idx_videos_year ON videos(year) WHERE year IS NOT NULL;

-- Index full-text pour recherche (nécessite pg_trgm)
CREATE INDEX IF NOT EXISTS idx_videos_title_trgm ON videos USING gin(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_videos_desc_trgm ON videos USING gin(description gin_trgm_ops);

-- Index sur les tables relationnelles
CREATE INDEX IF NOT EXISTS idx_comments_video ON comments(video_id);
CREATE INDEX IF NOT EXISTS idx_comments_user ON comments(user_id);
CREATE INDEX IF NOT EXISTS idx_comments_created ON comments(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_video ON watchlist(video_id);

CREATE INDEX IF NOT EXISTS idx_history_user ON watch_history(user_id);
CREATE INDEX IF NOT EXISTS idx_history_video ON watch_history(video_id);
CREATE INDEX IF NOT EXISTS idx_history_last_watched ON watch_history(last_watched DESC);

-- =====================================================
-- TRIGGERS POUR MISES À JOUR AUTOMATIQUES
-- =====================================================

-- Fonction de mise à jour automatique de updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers pour updated_at
DROP TRIGGER IF EXISTS update_folders_updated_at ON folders;
CREATE TRIGGER update_folders_updated_at
    BEFORE UPDATE ON folders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_comments_updated_at ON comments;
CREATE TRIGGER update_comments_updated_at
    BEFORE UPDATE ON comments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger pour mettre à jour last_watched automatiquement
CREATE OR REPLACE FUNCTION update_last_watched_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_watched = TIMEZONE('utc', NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_history_last_watched ON watch_history;
CREATE TRIGGER update_history_last_watched
    BEFORE UPDATE ON watch_history
    FOR EACH ROW
    EXECUTE FUNCTION update_last_watched_column();

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Activer RLS sur toutes les tables sensibles
ALTER TABLE comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_history ENABLE ROW LEVEL SECURITY;

-- Politiques pour comments
DROP POLICY IF EXISTS "Anyone can view comments" ON comments;
CREATE POLICY "Anyone can view comments"
    ON comments FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Users can create comments" ON comments;
CREATE POLICY "Users can create comments"
    ON comments FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own comments" ON comments;
CREATE POLICY "Users can update their own comments"
    ON comments FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own comments" ON comments;
CREATE POLICY "Users can delete their own comments"
    ON comments FOR DELETE
    USING (auth.uid() = user_id);

-- Politiques pour watchlist
DROP POLICY IF EXISTS "Users can view their own watchlist" ON watchlist;
CREATE POLICY "Users can view their own watchlist"
    ON watchlist FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can add to their watchlist" ON watchlist;
CREATE POLICY "Users can add to their watchlist"
    ON watchlist FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can remove from their watchlist" ON watchlist;
CREATE POLICY "Users can remove from their watchlist"
    ON watchlist FOR DELETE
    USING (auth.uid() = user_id);

-- Politiques pour watch_history
DROP POLICY IF EXISTS "Users can view their own history" ON watch_history;
CREATE POLICY "Users can view their own history"
    ON watch_history FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can manage their history" ON watch_history;
CREATE POLICY "Users can manage their history"
    ON watch_history FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Désactiver RLS pour folders et videos (lecture publique)
ALTER TABLE folders DISABLE ROW LEVEL SECURITY;
ALTER TABLE videos DISABLE ROW LEVEL SECURITY;
ALTER TABLE stream_mappings DISABLE ROW LEVEL SECURITY;

-- =====================================================
-- FONCTIONS UTILITAIRES
-- =====================================================

-- Fonction pour rechercher des vidéos
CREATE OR REPLACE FUNCTION search_videos(search_query TEXT)
RETURNS TABLE (
    id UUID,
    title TEXT,
    description TEXT,
    similarity_score REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.id,
        v.title,
        v.description,
        GREATEST(
            similarity(v.title, search_query),
            similarity(COALESCE(v.description, ''), search_query)
        ) as similarity_score
    FROM videos v
    WHERE 
        v.title % search_query
        OR v.description % search_query
        OR v.title ILIKE '%' || search_query || '%'
    ORDER BY similarity_score DESC;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour obtenir les statistiques d'un dossier
CREATE OR REPLACE FUNCTION get_folder_stats(folder_uuid UUID)
RETURNS TABLE (
    video_count BIGINT,
    total_size BIGINT,
    total_duration BIGINT,
    avg_rating NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(v.id),
        COALESCE(SUM(v.file_size), 0),
        COALESCE(SUM(v.duration), 0),
        COALESCE(AVG(v.rating), 0)
    FROM videos v
    WHERE v.folder_id = folder_uuid;
END;
$$ LANGUAGE plpgsql;
