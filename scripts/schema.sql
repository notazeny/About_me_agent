-- About_Me_Agent 的 MySQL 表结构（从 SQLite 迁移）
-- 学习点：严格类型 / 显式索引 / InnoDB 引擎 / utf8mb4

CREATE DATABASE IF NOT EXISTS about_me_agent
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE about_me_agent;

CREATE TABLE IF NOT EXISTS sessions (
    id         CHAR(32)     PRIMARY KEY,              -- uuid hex 固定 32 位 → 定长 CHAR
    title      VARCHAR(255) NOT NULL DEFAULT '',
    created_at DATETIME     NOT NULL,
    updated_at DATETIME     NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS messages (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    session_id CHAR(32)     NOT NULL,
    role       VARCHAR(16)  NOT NULL,                 -- 'user' | 'assistant'
    content    TEXT         NOT NULL,
    sources    TEXT         NULL,                     -- JSON 串：只存取不查内部，用 TEXT
    created_at DATETIME     NOT NULL,
    INDEX idx_session_id (session_id),                -- 最高频查询列，显式建索引
    CONSTRAINT fk_messages_session
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS users (
    id            INT          AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     NOT NULL,
    UNIQUE KEY uq_username (username)          -- 用户名唯一：防重名 + 加速登录查询
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
