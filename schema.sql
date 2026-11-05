DROP DATABASE IF EXISTS speedrun_phase4;
CREATE DATABASE speedrun_phase4 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE speedrun_phase4;

CREATE TABLE users (user_id VARCHAR(32) PRIMARY KEY, username VARCHAR(100) NOT NULL UNIQUE, display_name VARCHAR(150) NOT NULL, joined_at DATETIME NOT NULL, is_admin BOOLEAN NOT NULL DEFAULT FALSE, active BOOLEAN NOT NULL DEFAULT TRUE, country_code CHAR(2), region_name VARCHAR(100));
CREATE TABLE game (game_id VARCHAR(32) PRIMARY KEY, slug VARCHAR(80) NOT NULL UNIQUE, title_international VARCHAR(200) NOT NULL, title_local VARCHAR(200), release_year SMALLINT, source_url VARCHAR(500), active BOOLEAN NOT NULL DEFAULT TRUE);
CREATE TABLE category (category_id VARCHAR(32) PRIMARY KEY, name VARCHAR(150) NOT NULL, kind ENUM('full_game','per_level') NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE, game_id VARCHAR(32) NOT NULL, UNIQUE(game_id,name,kind), FOREIGN KEY(game_id) REFERENCES game(game_id) ON DELETE RESTRICT);
CREATE TABLE level (level_id VARCHAR(32) PRIMARY KEY, name VARCHAR(150) NOT NULL, display_order INT NOT NULL, game_id VARCHAR(32) NOT NULL, UNIQUE(game_id,name), UNIQUE(game_id,display_order), FOREIGN KEY(game_id) REFERENCES game(game_id) ON DELETE RESTRICT);
