-- Simple Database Initialization Script for AP Intake System
-- This script creates the essential tables needed for basic functionality

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core Enums
DO $$ BEGIN
    CREATE TYPE invoice_status AS ENUM (
        'received', 'parsed', 'validated', 'exception', 'ready', 'staged', 'done'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE export_format AS ENUM ('csv', 'json');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE export_status AS ENUM ('prepared', 'sent', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE ingestion_status AS ENUM (
        'pending', 'processing', 'completed', 'failed', 'duplicate_detected', 'require_review'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE deduplication_strategy AS ENUM (
        'file_hash', 'business_rules', 'temporal', 'fuzzy_matching', 'composite', 'working_capital'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE duplicate_resolution AS ENUM (
        'auto_ignore', 'auto_merge', 'manual_review', 'replace_existing', 'archive_existing'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE idempotency_operation_type AS ENUM (
        'invoice_upload', 'invoice_process', 'export_stage', 'export_post',
        'exception_resolve', 'batch_operation'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE idempotency_status AS ENUM (
        'pending', 'in_progress', 'completed', 'failed', 'cancelled'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE dlq_status AS ENUM (
        'pending', 'processing', 'redriving', 'completed', 'failed_permanently', 'archived'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE dlq_category AS ENUM (
        'processing_error', 'validation_error', 'network_error', 'database_error',
        'timeout_error', 'business_rule_error', 'system_error', 'unknown_error'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE dlq_priority AS ENUM ('low', 'normal', 'high', 'critical');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Vendors table (reference data)
CREATE TABLE IF NOT EXISTS vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    tax_id VARCHAR(50) UNIQUE,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    active BOOLEAN NOT NULL DEFAULT true,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    payment_terms_days VARCHAR(10),
    credit_limit VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Invoices table (main entity)
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID REFERENCES vendors(id),
    file_url TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size VARCHAR(20) NOT NULL,
    status invoice_status NOT NULL DEFAULT 'received',
    workflow_state VARCHAR(50),
    workflow_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Invoice extractions table
CREATE TABLE IF NOT EXISTS invoice_extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    header_json JSONB NOT NULL,
    lines_json JSONB NOT NULL,
    confidence_json JSONB NOT NULL,
    parser_version VARCHAR(50) NOT NULL,
    processing_time_ms VARCHAR(20),
    page_count VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Validations table
CREATE TABLE IF NOT EXISTS validations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    passed BOOLEAN NOT NULL DEFAULT false,
    checks_json JSONB NOT NULL,
    rules_version VARCHAR(50) NOT NULL,
    validator_version VARCHAR(50) NOT NULL,
    processing_time_ms VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Exceptions table
CREATE TABLE IF NOT EXISTS exceptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    reason_code VARCHAR(50) NOT NULL,
    details_json JSONB NOT NULL,
    resolved_by VARCHAR(255),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Staged exports table
CREATE TABLE IF NOT EXISTS staged_exports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    payload_json JSONB NOT NULL,
    format export_format NOT NULL,
    status export_status NOT NULL DEFAULT 'prepared',
    destination VARCHAR(255) NOT NULL,
    export_job_id VARCHAR(100),
    file_name VARCHAR(255),
    file_size VARCHAR(20),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ingestion jobs table
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_filename VARCHAR(500) NOT NULL,
    file_extension VARCHAR(10) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    file_hash_sha256 VARCHAR(64) UNIQUE NOT NULL,
    mime_type VARCHAR(100),
    storage_path TEXT NOT NULL,
    storage_backend VARCHAR(50) NOT NULL DEFAULT 'local',
    signed_url TEXT,
    signed_url_expiry TIMESTAMP WITH TIME ZONE,
    status ingestion_status NOT NULL DEFAULT 'pending',
    extracted_metadata JSONB,
    vendor_id UUID REFERENCES vendors(id),
    processing_priority INTEGER NOT NULL DEFAULT 5,
    deduplication_strategy deduplication_strategy NOT NULL DEFAULT 'composite',
    duplicate_group_id UUID,
    is_duplicate BOOLEAN NOT NULL DEFAULT false,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    processing_duration_ms INTEGER,
    error_message TEXT,
    error_code VARCHAR(50),
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    source_type VARCHAR(50) NOT NULL DEFAULT 'upload',
    source_reference VARCHAR(500),
    uploaded_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dead letter queue table
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id VARCHAR(255) UNIQUE NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    task_args JSONB,
    task_kwargs JSONB,
    original_task_data JSONB,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_stack_trace TEXT,
    error_category dlq_category NOT NULL DEFAULT 'unknown_error',
    retry_count INTEGER DEFAULT 0 NOT NULL,
    max_retries INTEGER DEFAULT 3 NOT NULL,
    last_retry_at TIMESTAMP WITH TIME ZONE,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    dlq_status dlq_status NOT NULL DEFAULT 'pending',
    priority dlq_priority NOT NULL DEFAULT 'normal',
    idempotency_key VARCHAR(255),
    invoice_id UUID REFERENCES invoices(id),
    worker_name VARCHAR(255),
    queue_name VARCHAR(100),
    execution_time INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    redrive_history JSONB,
    manual_intervention BOOLEAN NOT NULL DEFAULT false,
    intervention_reason TEXT
);

-- Idempotency records table
CREATE TABLE IF NOT EXISTS idempotency_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    operation_type idempotency_operation_type NOT NULL,
    operation_status idempotency_status NOT NULL DEFAULT 'pending',
    invoice_id UUID REFERENCES invoices(id),
    ingestion_job_id UUID REFERENCES ingestion_jobs(id),
    operation_data JSONB NOT NULL,
    result_data JSONB,
    error_data JSONB,
    execution_count INTEGER NOT NULL DEFAULT 0,
    max_executions INTEGER NOT NULL DEFAULT 1,
    first_attempt_at TIMESTAMP WITH TIME ZONE,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    ttl_seconds INTEGER,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    client_ip VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Basic indexes for performance
CREATE INDEX IF NOT EXISTS idx_invoices_vendor_id ON invoices(vendor_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_file_hash ON invoices(file_hash);
CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON invoices(created_at);

CREATE INDEX IF NOT EXISTS idx_invoice_extractions_invoice_id ON invoice_extractions(invoice_id);
CREATE INDEX IF NOT EXISTS idx_validations_invoice_id ON validations(invoice_id);
CREATE INDEX IF NOT EXISTS idx_validations_passed ON validations(passed);
CREATE INDEX IF NOT EXISTS idx_exceptions_invoice_id ON exceptions(invoice_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_reason_code ON exceptions(reason_code);
CREATE INDEX IF NOT EXISTS idx_staged_exports_invoice_id ON staged_exports(invoice_id);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_file_hash ON ingestion_jobs(file_hash_sha256);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_vendor_id ON ingestion_jobs(vendor_id);

CREATE INDEX IF NOT EXISTS idx_dlq_status ON dead_letter_queue(dlq_status);
CREATE INDEX IF NOT EXISTS idx_dlq_created_at ON dead_letter_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_dlq_task_name ON dead_letter_queue(task_name);
CREATE INDEX IF NOT EXISTS idx_dlq_next_retry ON dead_letter_queue(next_retry_at);

CREATE INDEX IF NOT EXISTS idx_idempotency_records_key ON idempotency_records(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_idempotency_records_status ON idempotency_records(operation_status);
CREATE INDEX IF NOT EXISTS idx_idempotency_records_invoice_id ON idempotency_records(invoice_id);

-- Insert some basic vendor data for testing
INSERT INTO vendors (name, currency, email, active, status) VALUES
('Test Vendor 1', 'USD', 'test1@example.com', true, 'active'),
('Test Vendor 2', 'USD', 'test2@example.com', true, 'active'),
('Test Vendor 3', 'USD', 'test3@example.com', true, 'active')
ON CONFLICT DO NOTHING;

-- Print success message
DO $$
BEGIN
    RAISE NOTICE 'Database tables created successfully!';
    RAISE NOTICE 'Core tables: vendors, invoices, invoice_extractions, validations, exceptions, staged_exports';
    RAISE NOTICE 'Supporting tables: ingestion_jobs, dead_letter_queue, idempotency_records';
    RAISE NOTICE 'Sample vendor data inserted for testing';
END $$;