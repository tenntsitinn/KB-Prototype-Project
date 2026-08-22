-- 知识库管理平台 — 数据库初始化脚本
-- 在 PostgreSQL 容器首次启动时自动执行

-- 知识单元主表
CREATE TABLE IF NOT EXISTS knowledge_units (
    id VARCHAR(32) PRIMARY KEY,
    unit_code VARCHAR(64) UNIQUE NOT NULL,
    title VARCHAR(512) NOT NULL,
    content TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    category VARCHAR(128) DEFAULT '',
    source_file_name VARCHAR(512) DEFAULT '',
    file_type VARCHAR(16) DEFAULT '',
    file_size INTEGER DEFAULT 0,
    file_md5 VARCHAR(64) DEFAULT '',
    minio_path VARCHAR(1024) DEFAULT '',
    status VARCHAR(16) DEFAULT 'draft',
    creator_id VARCHAR(32) DEFAULT '',
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 知识单元数据权限表
CREATE TABLE IF NOT EXISTS unit_permissions (
    id VARCHAR(32) PRIMARY KEY,
    unit_id VARCHAR(32) NOT NULL REFERENCES knowledge_units(id) ON DELETE CASCADE,
    target_type VARCHAR(16) NOT NULL,
    target_id VARCHAR(64) DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 问答访问日志表
CREATE TABLE IF NOT EXISTS qa_access_logs (
    id VARCHAR(32) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(32) NOT NULL,
    question TEXT DEFAULT '',
    answer TEXT DEFAULT '',
    recalled_unit_ids_json TEXT DEFAULT '[]',
    authorized_unit_ids_json TEXT DEFAULT '[]',
    unauthorized_unit_ids_json TEXT DEFAULT '[]',
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    response_time_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- FAQ 表
CREATE TABLE IF NOT EXISTS faqs (
    id VARCHAR(32) PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT DEFAULT '',
    related_unit_id VARCHAR(32) DEFAULT '',
    source_type VARCHAR(16) DEFAULT 'manual',
    status VARCHAR(16) DEFAULT 'pending_review',
    hit_count INTEGER DEFAULT 0,
    reviewer_id VARCHAR(32) DEFAULT '',
    reviewed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 知识切片表（向量化断点续跑依据）
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    unit_id VARCHAR(32) NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (unit_id, chunk_index)
);

-- 标签表
CREATE TABLE IF NOT EXISTS tags (
    id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) UNIQUE NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 题库表
CREATE TABLE IF NOT EXISTS quiz_questions (
    id VARCHAR(32) PRIMARY KEY,
    question TEXT NOT NULL,
    reference_answer TEXT DEFAULT '',
    category VARCHAR(128) DEFAULT '',
    source_unit_id VARCHAR(32) DEFAULT '',
    source_type VARCHAR(16) DEFAULT 'ai_generated',
    status VARCHAR(16) DEFAULT 'pending_review',
    usage_count INTEGER DEFAULT 0,
    reviewer_id VARCHAR(32) DEFAULT '',
    reviewed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 答题记录表
CREATE TABLE IF NOT EXISTS quiz_answers (
    id VARCHAR(32) PRIMARY KEY,
    question_id VARCHAR(32) NOT NULL,
    user_id VARCHAR(32) NOT NULL,
    answer_text TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    feedback TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 知识缺口表
CREATE TABLE IF NOT EXISTS knowledge_gaps (
    id VARCHAR(32) PRIMARY KEY,
    question_pattern TEXT DEFAULT '',
    sample_questions_json TEXT DEFAULT '[]',
    ask_count INTEGER DEFAULT 0,
    last_asked_at TIMESTAMP NULL,
    status VARCHAR(16) DEFAULT 'unresolved',
    resolved_unit_id VARCHAR(32) DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(32) PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    display_name VARCHAR(128) DEFAULT '',
    email VARCHAR(128) DEFAULT '',
    department_id VARCHAR(32) DEFAULT '',
    status VARCHAR(16) DEFAULT 'active',
    is_superuser BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 部门表
CREATE TABLE IF NOT EXISTS departments (
    id VARCHAR(32) PRIMARY KEY,
    parent_id VARCHAR(32) DEFAULT NULL,
    name VARCHAR(128) NOT NULL,
    leader_id VARCHAR(32) DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 角色表
CREATE TABLE IF NOT EXISTS roles (
    id VARCHAR(32) PRIMARY KEY,
    role_name VARCHAR(64) NOT NULL,
    role_code VARCHAR(64) UNIQUE NOT NULL,
    description VARCHAR(256) DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 用户-角色关联表
CREATE TABLE IF NOT EXISTS user_roles (
    id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id VARCHAR(32) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 角色权限表
CREATE TABLE IF NOT EXISTS role_permissions (
    id VARCHAR(32) PRIMARY KEY,
    role_id VARCHAR(32) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_code VARCHAR(64) NOT NULL,
    permission_type VARCHAR(16) DEFAULT 'operation',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_ku_status ON knowledge_units(status);
CREATE INDEX IF NOT EXISTS idx_ku_category ON knowledge_units(category);
CREATE INDEX IF NOT EXISTS idx_ku_creator ON knowledge_units(creator_id);
CREATE INDEX IF NOT EXISTS idx_up_unit_id ON unit_permissions(unit_id);
CREATE INDEX IF NOT EXISTS idx_up_target ON unit_permissions(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_qa_user_id ON qa_access_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_qa_session ON qa_access_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_qa_created ON qa_access_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_faq_status ON faqs(status);
CREATE INDEX IF NOT EXISTS idx_gap_status ON knowledge_gaps(status);
CREATE INDEX IF NOT EXISTS idx_quiz_status ON quiz_questions(status);
CREATE INDEX IF NOT EXISTS idx_quiz_category ON quiz_questions(category);
CREATE INDEX IF NOT EXISTS idx_quiz_answer_question ON quiz_answers(question_id);
CREATE INDEX IF NOT EXISTS idx_quiz_answer_user ON quiz_answers(user_id);