-- Basic test schema for database testing
-- This creates the essential tables needed for testing

-- Create vendors table
CREATE TABLE IF NOT EXISTS vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    tax_id VARCHAR(50) UNIQUE,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    payment_terms_days VARCHAR(10) DEFAULT '30',
    credit_limit VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for vendors
CREATE INDEX IF NOT EXISTS idx_vendor_active_status ON vendors(active, status);
CREATE INDEX IF NOT EXISTS idx_vendor_name_active ON vendors(name, active);
CREATE INDEX IF NOT EXISTS idx_vendors_tax_id ON vendors(tax_id) WHERE tax_id IS NOT NULL;

-- Create invoices table
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID REFERENCES vendors(id) ON DELETE SET NULL,
    file_url TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'received',
    workflow_state VARCHAR(50),
    workflow_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for invoices
CREATE INDEX IF NOT EXISTS idx_invoices_vendor_id ON invoices(vendor_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_file_hash ON invoices(file_hash);
CREATE INDEX IF NOT EXISTS idx_invoices_created_status ON invoices(created_at, status);
CREATE INDEX IF NOT EXISTS idx_invoices_workflow_state ON invoices(workflow_state, status);

-- Create invoice_extractions table
CREATE TABLE IF NOT EXISTS invoice_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- Create validations table
CREATE TABLE IF NOT EXISTS validations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    passed BOOLEAN NOT NULL DEFAULT FALSE,
    checks_json JSONB NOT NULL,
    rules_version VARCHAR(50) NOT NULL,
    validator_version VARCHAR(50) NOT NULL,
    processing_time_ms VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create exceptions table
CREATE TABLE IF NOT EXISTS exceptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    reason_code VARCHAR(50) NOT NULL,
    details_json JSONB NOT NULL,
    resolved_by VARCHAR(255),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create staged_exports table
CREATE TABLE IF NOT EXISTS staged_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    payload_json JSONB NOT NULL,
    format VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'prepared',
    destination VARCHAR(255) NOT NULL,
    export_job_id VARCHAR(100),
    file_name VARCHAR(255),
    file_size VARCHAR(20),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create purchase_orders table
CREATE TABLE IF NOT EXISTS purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_no VARCHAR(100) UNIQUE NOT NULL,
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE RESTRICT,
    lines_json JSONB NOT NULL,
    total_amount VARCHAR(20) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    order_date TIMESTAMP WITH TIME ZONE,
    expected_date TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(255),
    approved_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create goods_receipt_notes table
CREATE TABLE IF NOT EXISTS goods_receipt_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grn_no VARCHAR(100) UNIQUE NOT NULL,
    po_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE RESTRICT,
    lines_json JSONB NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL,
    carrier VARCHAR(255),
    tracking_no VARCHAR(100),
    received_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add some basic constraints
ALTER TABLE vendors ADD CONSTRAINT check_vendor_name_not_empty CHECK (name <> '');
ALTER TABLE vendors ADD CONSTRAINT check_currency_format CHECK (currency ~ '^[A-Z]{3}$');

ALTER TABLE invoices ADD CONSTRAINT check_file_size_not_empty CHECK (file_size <> '');
ALTER TABLE invoices ADD CONSTRAINT check_file_name_not_empty CHECK (file_name <> '');

ALTER TABLE purchase_orders ADD CONSTRAINT check_po_no_not_empty CHECK (po_no <> '');
ALTER TABLE purchase_orders ADD CONSTRAINT check_total_amount_not_empty CHECK (total_amount <> '');

ALTER TABLE goods_receipt_notes ADD CONSTRAINT check_grn_no_not_empty CHECK (grn_no <> '');
ALTER TABLE goods_receipt_notes ADD CONSTRAINT check_received_by_not_empty CHECK (received_by <> '');

-- Insert some sample data for testing
INSERT INTO vendors (id, name, currency, active, status) VALUES
('550e8400-e29b-41d4-a716-446655440001', 'Test Vendor 1', 'USD', true, 'active'),
('550e8400-e29b-41d4-a716-446655440002', 'Test Vendor 2', 'EUR', true, 'active'),
('550e8400-e29b-41d4-a716-446655440003', 'Test Vendor 3', 'USD', false, 'inactive')
ON CONFLICT (id) DO NOTHING;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_vendors_updated_at BEFORE UPDATE ON vendors FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_invoices_updated_at BEFORE UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_invoice_extractions_updated_at BEFORE UPDATE ON invoice_extractions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_validations_updated_at BEFORE UPDATE ON validations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_exceptions_updated_at BEFORE UPDATE ON exceptions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_staged_exports_updated_at BEFORE UPDATE ON staged_exports FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_purchase_orders_updated_at BEFORE UPDATE ON purchase_orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_goods_receipt_notes_updated_at BEFORE UPDATE ON goods_receipt_notes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();