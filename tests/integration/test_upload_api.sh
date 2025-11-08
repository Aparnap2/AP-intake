#!/bin/bash
# Get project root
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$(readlink -f "$0")")")")"

#!/bin/bash

# Comprehensive File Upload API Test Script
# Tests the /api/v1/invoices/upload endpoint with various scenarios

set -e

# Configuration
API_BASE_URL="http://localhost:8000"
API_ENDPOINT="${API_BASE_URL}/api/v1/invoices/upload"
TEST_INVOICE_PATH="$PROJECT_ROOT/test_invoices/test_invoice_standard_20251107_175127.pdf"
REPORT_DIR="$PROJECT_ROOT/test_reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="${REPORT_DIR}/upload_api_test_report_${TIMESTAMP}.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
ERROR_TESTS=0

# Create report directory
mkdir -p "$REPORT_DIR"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$REPORT_FILE"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1" | tee -a "$REPORT_FILE"
}

log_failure() {
    echo -e "${RED}[FAIL]${NC} $1" | tee -a "$REPORT_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$REPORT_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$REPORT_FILE"
}

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_status="$3"
    local description="$4"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    log_info "Running Test: $test_name"
    log_info "Description: $description"
    log_info "Command: $test_command"

    # Measure response time
    start_time=$(date +%s%N)

    # Execute test and capture response
    if response=$(eval "$test_command" 2>&1); then
        http_status=$(echo "$response" | grep -o 'HTTP/[0-9.]* [0-9]*' | awk '{print $2}' | tail -1)
        if [ -z "$http_status" ]; then
            # Try to get status from curl if available
            http_status=$(echo "$response" | grep -o '"status":[^,}]*' | cut -d'"' -f4 | head -1)
        fi
    else
        http_status="000"
    fi

    end_time=$(date +%s%N)
    response_time=$(( (end_time - start_time) / 1000000 )) # Convert to milliseconds

    log_info "HTTP Status: $http_status"
    log_info "Response Time: ${response_time}ms"

    # Check if test passed
    if [ "$http_status" = "$expected_status" ]; then
        log_success "$test_name: PASSED (Status: $http_status, Time: ${response_time}ms)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        log_failure "$test_name: FAILED (Expected: $expected_status, Got: $http_status)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi

    # Save response details
    echo "Response details:" | tee -a "$REPORT_FILE"
    echo "$response" | head -20 | tee -a "$REPORT_FILE"
    echo "---" | tee -a "$REPORT_FILE"
    echo "" | tee -a "$REPORT_FILE"
}

# Function to test API health
check_api_health() {
    log_info "Checking API health..."

    if curl -s "${API_BASE_URL}/health" | grep -q '"status":"healthy"'; then
        log_success "API is healthy and responding"
        return 0
    else
        log_error "API is not responding correctly"
        return 1
    fi
}

# Function to create test files
create_test_files() {
    log_info "Creating test files..."

    # Create a text file (invalid type)
    echo "This is a text file, not a PDF" > /tmp/test.txt

    # Create an empty file
    touch /tmp/empty.pdf

    # Create a corrupted PDF
    echo "%PDF-1.4
This is not a valid PDF structure
%%EOF" > /tmp/corrupted.pdf

    # Create a large file (30MB)
    dd if=/dev/zero of=/tmp/large.pdf bs=1M count=30 2>/dev/null

    # Create minimal image files with correct headers
    # JPEG header
    printf '\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00' > /tmp/test.jpg
    # PNG header
    printf '\x89PNG\r\n\x1a\n' > /tmp/test.png

    log_info "Test files created"
}

# Function to cleanup test files
cleanup_test_files() {
    log_info "Cleaning up test files..."
    rm -f /tmp/test.txt /tmp/empty.pdf /tmp/corrupted.pdf /tmp/large.pdf /tmp/test.jpg /tmp/test.png
}

# Initialize report
echo "=================================================" | tee "$REPORT_FILE"
echo "COMPREHENSIVE FILE UPLOAD API TEST REPORT" | tee -a "$REPORT_FILE"
echo "=================================================" | tee -a "$REPORT_FILE"
echo "Date: $(date)" | tee -a "$REPORT_FILE"
echo "API Endpoint: $API_ENDPOINT" | tee -a "$REPORT_FILE"
echo "Test Invoice: $TEST_INVOICE_PATH" | tee -a "$REPORT_FILE"
echo "" | tee -a "$REPORT_FILE"

# Check if API is running
if ! check_api_health; then
    log_error "API is not healthy. Exiting tests."
    exit 1
fi

# Check if test invoice exists
if [ ! -f "$TEST_INVOICE_PATH" ]; then
    log_error "Test invoice file not found: $TEST_INVOICE_PATH"
    exit 1
fi

# Create test files
create_test_files

# Run comprehensive tests
log_info "Starting comprehensive file upload API tests..."

# Test 1: Valid PDF upload
run_test "Valid PDF Upload" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@$TEST_INVOICE_PATH' '$API_ENDPOINT'" \
    "200" \
    "Upload a valid PDF invoice file"

# Test 2: Missing file
run_test "Missing File" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST '$API_ENDPOINT'" \
    "422" \
    "Request without any file"

# Test 3: Invalid file type (text file)
run_test "Invalid File Type" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@/tmp/test.txt' '$API_ENDPOINT'" \
    "400" \
    "Upload a text file (should be rejected)"

# Test 4: Large file (exceeds 25MB limit)
run_test "Large File Upload" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@/tmp/large.pdf' '$API_ENDPOINT'" \
    "400" \
    "Upload a 30MB file (should exceed limit)"

# Test 5: Empty file
run_test "Empty File Upload" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@/tmp/empty.pdf' '$API_ENDPOINT'" \
    "200" \
    "Upload an empty PDF file"

# Test 6: Corrupted PDF
run_test "Corrupted PDF Upload" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@/tmp/corrupted.pdf' '$API_ENDPOINT'" \
    "200" \
    "Upload a corrupted PDF file (API should accept but processing may fail)"

# Test 7: Duplicate file upload
log_info "Running duplicate file test (2 uploads)..."
run_test "Duplicate File Upload - First" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@$TEST_INVOICE_PATH' '$API_ENDPOINT'" \
    "200" \
    "First upload of the PDF file"

run_test "Duplicate File Upload - Second" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@$TEST_INVOICE_PATH' '$API_ENDPOINT'" \
    "409" \
    "Second upload of same PDF (should detect duplicate)"

# Test 8: Image file uploads (JPEG and PNG)
run_test "JPEG Upload" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@/tmp/test.jpg' '$API_ENDPOINT'" \
    "200" \
    "Upload a JPEG image file"

run_test "PNG Upload" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@/tmp/test.png' '$API_ENDPOINT'" \
    "200" \
    "Upload a PNG image file"

# Test 9: File with special characters in name
cp "$TEST_INVOICE_PATH" "/tmp/test file (special).pdf"
run_test "Special Characters in Filename" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@/tmp/test file (special).pdf' '$API_ENDPOINT'" \
    "200" \
    "Upload file with special characters in name"

# Test 10: Test different content types
run_test "Wrong Content Type" \
    "curl -s -w 'HTTP Status: %{http_code}\n' -X POST -F 'file=@$TEST_INVOICE_PATH;type=text/plain' '$API_ENDPOINT'" \
    "200" \
    "Upload PDF with wrong content type (should still work)"

# Test 11: Performance test with multiple concurrent uploads
log_info "Running performance test with 5 concurrent uploads..."
start_time=$(date +%s%N)
for i in {1..5}; do
    curl -s -X POST -F "file=@$TEST_INVOICE_PATH" "$API_ENDPOINT" > "/tmp/concurrent_test_$i.json" 2>/dev/null &
done
wait
end_time=$(date +%s%N)
total_time=$(( (end_time - start_time) / 1000000 ))
avg_time=$((total_time / 5))

log_info "Performance Test Results:"
log_info "Total time for 5 concurrent uploads: ${total_time}ms"
log_info "Average time per upload: ${avg_time}ms"

# Count successful concurrent uploads
successful_concurrent=0
for i in {1..5}; do
    if grep -q '"id"' "/tmp/concurrent_test_$i.json" 2>/dev/null; then
        successful_concurrent=$((successful_concurrent + 1))
    fi
    rm -f "/tmp/concurrent_test_$i.json"
done

if [ "$successful_concurrent" -eq 5 ]; then
    log_success "Performance Test: All 5 concurrent uploads succeeded"
else
    log_failure "Performance Test: Only $successful_concurrent/5 concurrent uploads succeeded"
fi

# Cleanup test files
cleanup_test_files

# Generate final report
echo "" | tee -a "$REPORT_FILE"
echo "=================================================" | tee -a "$REPORT_FILE"
echo "FINAL TEST SUMMARY" | tee -a "$REPORT_FILE"
echo "=================================================" | tee -a "$REPORT_FILE"
echo "Total Tests: $TOTAL_TESTS" | tee -a "$REPORT_FILE"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}" | tee -a "$REPORT_FILE"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}" | tee -a "$REPORT_FILE"
echo -e "Errors: ${RED}$ERROR_TESTS${NC}" | tee -a "$REPORT_FILE"

if [ $TOTAL_TESTS -gt 0 ]; then
    success_rate=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
    echo "Success Rate: ${success_rate}%" | tee -a "$REPORT_FILE"
else
    echo "Success Rate: N/A (no tests run)" | tee -a "$REPORT_FILE"
fi

echo "" | tee -a "$REPORT_FILE"
echo "RECOMMENDATIONS:" | tee -a "$REPORT_FILE"

if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo "✅ All tests passed! The file upload API is working correctly." | tee -a "$REPORT_FILE"
else
    echo "❌ Some tests failed. Review the failed scenarios above." | tee -a "$REPORT_FILE"
fi

if [ $FAILED_TESTS -gt 0 ]; then
    echo "⚠️  Check API error handling and validation logic." | tee -a "$REPORT_FILE"
fi

if [ "$avg_time" -gt 5000 ]; then
    echo "⚠️  Average response time is high (${avg_time}ms). Consider optimizing performance." | tee -a "$REPORT_FILE"
fi

# Test database integration
log_info "Testing database integration..."
if response=$(curl -s "${API_BASE_URL}/api/v1/invoices?limit=5" 2>/dev/null); then
    if echo "$response" | grep -q '"invoices"'; then
        invoice_count=$(echo "$response" | grep -o '"total":[0-9]*' | cut -d':' -f2)
        log_success "Database integration working. Found $invoice_count invoices in system."
    else
        log_warning "Database integration test inconclusive."
    fi
else
    log_error "Could not test database integration."
fi

echo "" | tee -a "$REPORT_FILE"
echo "Report saved to: $REPORT_FILE" | tee -a "$REPORT_FILE"
echo "=================================================" | tee -a "$REPORT_FILE"

# Exit with error code if any tests failed
if [ $FAILED_TESTS -gt 0 ] || [ $ERROR_TESTS -gt 0 ]; then
    exit 1
else
    exit 0
fi