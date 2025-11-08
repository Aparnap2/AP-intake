-- Test script to validate the PostgreSQL index syntax
-- This simulates the fixed migration syntax

-- Create a test exceptions table (similar to the model)
CREATE TABLE IF NOT EXISTS test_exceptions (
    id UUID PRIMARY KEY,
    invoice_id UUID NOT NULL,
    reason_code VARCHAR(50) NOT NULL,
    details_json JSONB NOT NULL,
    resolved_by VARCHAR(255),
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Enable pg_trgm extension for advanced text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Test 1: B-tree indexes on extracted text fields (for exact equality)
CREATE INDEX idx_test_exception_category
ON test_exceptions USING btree ((details_json->>'category'));

CREATE INDEX idx_test_exception_severity
ON test_exceptions USING btree ((details_json->>'severity'));

CREATE INDEX idx_test_exception_status
ON test_exceptions USING btree ((details_json->>'status'));

-- Test 2: GIN index with jsonb_path_ops (for JSON containment queries)
CREATE INDEX idx_test_exception_details_gin
ON test_exceptions USING gin (details_json jsonb_path_ops);

-- Test 3: Optional trigram index for advanced text search
CREATE INDEX idx_test_exception_category_trgm
ON test_exceptions USING gin ((details_json->>'category') gin_trgm_ops);

-- Insert test data to verify indexes work
INSERT INTO test_exceptions (id, invoice_id, reason_code, details_json) VALUES
('550e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440000', 'VALIDATION_FAILED',
 '{"category": "data_quality", "severity": "high", "status": "open", "message": "Invalid amount"}'),
('550e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440003', 'MISSING_FIELD',
 '{"category": "validation", "severity": "medium", "status": "in_review", "message": "Vendor not found"}');

-- Test queries to verify indexes are being used
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM test_exceptions WHERE details_json->>'category' = 'data_quality';

EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM test_exceptions WHERE details_json @> '{"severity": "high"}';

EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM test_exceptions WHERE details_json->>'category' LIKE '%data%';

-- Show all indexes on the test table
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'test_exceptions';

-- Cleanup
DROP TABLE IF EXISTS test_exceptions;