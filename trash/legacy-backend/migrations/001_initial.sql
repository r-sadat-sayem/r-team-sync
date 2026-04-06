-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sessions table for conversation continuity
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_key VARCHAR(255) UNIQUE NOT NULL,
    mode VARCHAR(50) DEFAULT 'analyze',
    status VARCHAR(50) DEFAULT 'active',
    context_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Messages table for conversation history
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    action VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PRD Documents table
CREATE TABLE prd_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    markdown_content TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    quality_score INTEGER,
    grade VARCHAR(5),
    test_case_count INTEGER,
    sections_detected JSONB,
    missing_sections JSONB,
    status VARCHAR(50) DEFAULT 'generated',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email deliveries table
CREATE TABLE email_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prd_id UUID REFERENCES prd_documents(id) ON DELETE CASCADE,
    recipient_name VARCHAR(255),
    recipient_email VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    sent_at TIMESTAMP,
    error_message TEXT
);

-- JIRA tickets table
CREATE TABLE jira_tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prd_id UUID REFERENCES prd_documents(id) ON DELETE CASCADE,
    epic_key VARCHAR(50),
    epic_title VARCHAR(500),
    task_key VARCHAR(50),
    task_title VARCHAR(500),
    subtask_key VARCHAR(50),
    subtask_title VARCHAR(500),
    project_id VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_prd_session_id ON prd_documents(session_id);
CREATE INDEX idx_sessions_key ON sessions(session_key);
CREATE INDEX idx_email_prd_id ON email_deliveries(prd_id);
CREATE INDEX idx_jira_prd_id ON jira_tickets(prd_id);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();