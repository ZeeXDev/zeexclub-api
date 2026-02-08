# backend/database/queries.py
"""
Requêtes SQL complexes pour Supabase
Utilisées pour des opérations avancées non couvertes par l'API simple
"""

# Requête pour obtenir les statistiques globales
STATS_QUERY = """
SELECT 
    (SELECT COUNT(*) FROM folders WHERE parent_id IS NULL) as total_root_folders,
    (SELECT COUNT(*) FROM folders WHERE parent_id IS NOT NULL) as total_subfolders,
    (SELECT COUNT(*) FROM videos) as total_videos,
    (SELECT SUM(file_size) FROM videos) as total_storage_used,
    (SELECT COUNT(DISTINCT user_id) FROM watch_history WHERE last_watched > NOW() - INTERVAL '30 days') as active_users_30d,
    (SELECT COUNT(*) FROM comments WHERE created_at > NOW() - INTERVAL '7 days') as recent_comments;
"""

# Requête pour les tendances (vidéos les plus vues)
TRENDING_VIDEOS_QUERY = """
SELECT 
    v.*,
    f.folder_name,
    COUNT(wh.id) as watch_count
FROM videos v
JOIN folders f ON v.folder_id = f.id
LEFT JOIN watch_history wh ON v.id = wh.video_id 
    AND wh.last_watched > NOW() - INTERVAL '7 days'
GROUP BY v.id, f.folder_name
ORDER BY watch_count DESC, v.views_count DESC
LIMIT 10;
"""

# Requête pour les recommandations (basées sur l'historique)
RECOMMENDATIONS_QUERY = """
WITH user_genres AS (
    SELECT UNNEST(v.genre) as genre, COUNT(*) as count
    FROM watch_history wh
    JOIN videos v ON wh.video_id = v.id
    WHERE wh.user_id = %s AND wh.completed = true
    GROUP BY genre
    ORDER BY count DESC
    LIMIT 3
)
SELECT DISTINCT v.*, f.folder_name
FROM videos v
JOIN folders f ON v.folder_id = f.id
WHERE v.id NOT IN (
    SELECT video_id FROM watch_history WHERE user_id = %s
)
AND v.genre && (SELECT ARRAY_AGG(genre) FROM user_genres)
ORDER BY v.rating DESC, v.views_count DESC
LIMIT 12;
"""

# Requête pour la recherche full-text (nécessite extension pg_trgm)
SEARCH_VIDEOS_QUERY = """
SELECT 
    v.*,
    f.folder_name,
    similarity(v.title, %s) as title_sim,
    similarity(COALESCE(v.description, ''), %s) as desc_sim
FROM videos v
JOIN folders f ON v.folder_id = f.id
WHERE 
    v.title %% %s 
    OR v.description %% %s
    OR v.title ILIKE %s
ORDER BY title_sim DESC, desc_sim DESC, v.views_count DESC
LIMIT 20;
"""

# Requête pour les nouveautés par période
NEW_RELEASES_QUERY = """
SELECT 
    v.*,
    f.folder_name
FROM videos v
JOIN folders f ON v.folder_id = f.id
WHERE v.created_at > NOW() - INTERVAL '%s days'
ORDER BY v.created_at DESC
LIMIT %s;
"""

# Requête pour les statistiques d'un dossier
FOLDER_STATS_QUERY = """
SELECT 
    f.*,
    COUNT(v.id) as video_count,
    SUM(v.file_size) as total_size,
    SUM(v.duration) as total_duration,
    AVG(v.rating) as avg_rating,
    ARRAY_AGG(DISTINCT UNNEST(v.genre)) as all_genres
FROM folders f
LEFT JOIN videos v ON f.id = v.folder_id
WHERE f.id = %s
GROUP BY f.id;
"""
