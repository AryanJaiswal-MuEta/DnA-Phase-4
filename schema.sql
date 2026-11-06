DROP DATABASE IF EXISTS speedrun_phase4;
CREATE DATABASE speedrun_phase4 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE speedrun_phase4;

CREATE TABLE users (user_id VARCHAR(32) PRIMARY KEY, username VARCHAR(100) NOT NULL UNIQUE, display_name VARCHAR(150) NOT NULL, joined_at DATETIME NOT NULL, is_admin BOOLEAN NOT NULL DEFAULT FALSE, active BOOLEAN NOT NULL DEFAULT TRUE, country_code CHAR(2), region_name VARCHAR(100));
CREATE TABLE game (game_id VARCHAR(32) PRIMARY KEY, slug VARCHAR(80) NOT NULL UNIQUE, title_international VARCHAR(200) NOT NULL, title_local VARCHAR(200), release_year SMALLINT, source_url VARCHAR(500), active BOOLEAN NOT NULL DEFAULT TRUE);
CREATE TABLE category (category_id VARCHAR(32) PRIMARY KEY, name VARCHAR(150) NOT NULL, kind ENUM('full_game','per_level') NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE, game_id VARCHAR(32) NOT NULL, UNIQUE(game_id,name,kind), FOREIGN KEY(game_id) REFERENCES game(game_id) ON DELETE RESTRICT);
CREATE TABLE level (level_id VARCHAR(32) PRIMARY KEY, name VARCHAR(150) NOT NULL, display_order INT NOT NULL, game_id VARCHAR(32) NOT NULL, UNIQUE(game_id,name), UNIQUE(game_id,display_order), FOREIGN KEY(game_id) REFERENCES game(game_id) ON DELETE RESTRICT);
CREATE TABLE platform (platform_id VARCHAR(32) PRIMARY KEY, name VARCHAR(150) NOT NULL UNIQUE, manufacturer VARCHAR(100));
CREATE TABLE permission (permission_code VARCHAR(32) PRIMARY KEY, description VARCHAR(255) NOT NULL);
CREATE TABLE supports (game_id VARCHAR(32) NOT NULL, platform_id VARCHAR(32) NOT NULL, PRIMARY KEY(game_id,platform_id), FOREIGN KEY(game_id) REFERENCES game(game_id), FOREIGN KEY(platform_id) REFERENCES platform(platform_id));
CREATE TABLE related_to (source_game_id VARCHAR(32) NOT NULL, related_game_id VARCHAR(32) NOT NULL, PRIMARY KEY(source_game_id,related_game_id), FOREIGN KEY(source_game_id) REFERENCES game(game_id), FOREIGN KEY(related_game_id) REFERENCES game(game_id), CHECK(source_game_id<>related_game_id));
CREATE TABLE game_alternate_name (game_id VARCHAR(32) NOT NULL, alternate_name VARCHAR(200) NOT NULL, PRIMARY KEY(game_id,alternate_name), FOREIGN KEY(game_id) REFERENCES game(game_id));
CREATE TABLE user_social_profile (user_id VARCHAR(32) NOT NULL, service VARCHAR(40) NOT NULL, url VARCHAR(500) NOT NULL, PRIMARY KEY(user_id,service,url), FOREIGN KEY(user_id) REFERENCES users(user_id));
