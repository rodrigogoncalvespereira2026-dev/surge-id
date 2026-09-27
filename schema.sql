-- Surge ID — esquema de base de dados (compatível com PostgreSQL e SQLite)
-- 3 tabelas: utilizadores, jogos e progresso por utilizador/jogo.

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  email         TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  surge_id      TEXT NOT NULL UNIQUE,
  display_name  TEXT,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users (LOWER(email));
CREATE INDEX IF NOT EXISTS idx_users_surge_id ON users (surge_id);

CREATE TABLE IF NOT EXISTS games (
  slug       TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_games (
  user_id    TEXT NOT NULL,
  game_slug  TEXT NOT NULL,
  progress   JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, game_slug),
  FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
  FOREIGN KEY (game_slug) REFERENCES games (slug) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_games_user ON user_games (user_id);
