-- Migration 008: Add caching for translations and tafsir
-- This migration creates tables to cache API responses to reduce external API calls

-- Cache for translations (by page and language)
CREATE TABLE IF NOT EXISTS translation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_number INTEGER NOT NULL,
    language TEXT NOT NULL,
    data TEXT NOT NULL,  -- JSON string of translation data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(page_number, language)
);

-- Cache for tafsir (by page and edition)
CREATE TABLE IF NOT EXISTS tafsir_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_number INTEGER NOT NULL,
    edition TEXT NOT NULL,
    data TEXT NOT NULL,  -- JSON string of tafsir data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(page_number, edition)
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_translation_cache_lookup ON translation_cache(page_number, language);
CREATE INDEX IF NOT EXISTS idx_tafsir_cache_lookup ON tafsir_cache(page_number, edition);
