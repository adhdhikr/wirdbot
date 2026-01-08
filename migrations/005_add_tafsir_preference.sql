-- Add tafsir_preference column to users table
ALTER TABLE users ADD COLUMN tafsir_preference TEXT DEFAULT 'ar-tafsir-ibn-kathir';