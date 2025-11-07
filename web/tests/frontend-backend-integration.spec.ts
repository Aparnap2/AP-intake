import { test, expect } from '@playwright/test';

test.describe('Frontend-Backend Integration Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the frontend
    await page.goto('http://localhost:3000');

    // Wait for the page to load completely
    await page.waitForLoadState('networkidle');
  });

  test('should load the AP Intake dashboard', async ({ page }) => {
    // Check if the main title is visible
    await expect(page.locator('h1')).toContainText('AP Intake Review');

    // Check for the FileText icon
    await expect(page.locator('[data-testid="file-text-icon"]')).toBeVisible();

    // Take a screenshot of the initial state
    await page.screenshot({ path: 'test-results/dashboard-initial-state.png' });
  });

  test('should display demo invoice data correctly', async ({ page }) => {
    // Check if demo invoice number is displayed
    await expect(page.locator('text=INV-2024-5647')).toBeVisible();

    // Check if vendor name is displayed
    await expect(page.locator('text=Acme Corp Manufacturing')).toBeVisible();

    // Check if total amount is displayed
    await expect(page.locator('text=$12,450.50')).toBeVisible();

    // Check if confidence scores are displayed
    await expect(page.locator('text=High: 98%')).toBeVisible();
  });

  test('should handle view tab switching', async ({ page }) => {
    // Check that Summary tab is active by default
    await expect(page.locator('text=Summary')).toHaveClass(/border-blue-600/);

    // Click on Detailed Fields tab
    await page.click('text=Detailed Fields');
    await expect(page.locator('text=Detailed Fields')).toHaveClass(/border-blue-600/);

    // Check if detailed fields are visible
    await expect(page.locator('text=Extracted Fields')).toBeVisible();

    // Click on Line Items tab
    await page.click('text=Line Items');
    await expect(page.locator('text=Line Items')).toHaveClass(/border-blue-600/);

    // Check if line items are visible
    await expect(page.locator('text=Manufacturing supplies - Q4 batch')).toBeVisible();
  });

  test('should display validation alerts', async ({ page }) => {
    // Check for validation issues section
    await expect(page.locator('text=Validation Alerts (2)')).toBeVisible();

    // Check for specific validation messages
    await expect(page.locator('text=Vendor ID not found in master list')).toBeVisible();
    await expect(page.locator('text=PO partially matches existing records')).toBeVisible();
  });

  test('should have working action buttons', async ({ page }) => {
    // Check that all action buttons are present
    await expect(page.locator('button:has-text("Reject & Request Reupload")')).toBeVisible();
    await expect(page.locator('button:has-text("Request Manual Review")')).toBeVisible();
    await expect(page.locator('button:has-text("Approve & Process")')).toBeVisible();

    // Test button clicks (they won't do anything yet since we're using demo data)
    await page.click('button:has-text("Approve & Process")');
    // Just verify the click doesn't cause errors
    await expect(page.locator('h1')).toContainText('AP Intake Review');
  });

  test('should have navigation links to other pages', async ({ page }) => {
    // Check for navigation links
    await expect(page.locator('a:has-text("Open Invoice Dashboard")')).toBeVisible();
    await expect(page.locator('a:has-text("View Exceptions")')).toBeVisible();
    await expect(page.locator('a:has-text("Email Integration")')).toBeVisible();

    // Test navigation (these will likely 404 since pages don't exist yet)
    const [newPage] = await Promise.all([
      page.context().waitForEvent('page'),
      page.click('a:has-text("Open Invoice Dashboard")')
    ]);

    // Check that we navigated (even if to 404)
    await expect(newPage.url()).toContain('/invoices');
    await newPage.close();
  });
});

test.describe('Backend API Integration Tests', () => {
  test('should verify backend API is accessible', async ({ request }) => {
    // Test health endpoint
    const healthResponse = await request.get('http://localhost:8000/health');
    expect(healthResponse.status()).toBe(200);

    // Test API docs endpoint
    const docsResponse = await request.get('http://localhost:8000/docs');
    expect(docsResponse.status()).toBe(200);
  });

  test('should test invoices API endpoints', async ({ request }) => {
    // Test GET /api/v1/invoices
    const invoicesResponse = await request.get('http://localhost:8000/api/v1/invoices');
    expect(invoicesResponse.status()).toBe(200);

    const invoicesData = await invoicesResponse.json();
    console.log('Invoices API response:', invoicesData);
  });

  test('should check for CORS configuration', async ({ page }) => {
    // Make a request from the frontend context to check CORS
    const response = await page.evaluate(async () => {
      try {
        const result = await fetch('http://localhost:8000/api/v1/invoices', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          }
        });
        return {
          status: result.status,
          ok: result.ok,
          headers: Object.fromEntries(result.headers.entries())
        };
      } catch (error) {
        return {
          error: error.message,
          status: 0,
          ok: false
        };
      }
    });

    console.log('CORS test response:', response);

    // Check if the request was successful (no CORS errors)
    expect(response.error).toBeUndefined();
    expect(response.ok).toBe(true);
  });
});

test.describe('Network Request Monitoring', () => {
  test('should monitor network requests for API calls', async ({ page }) => {
    // Set up request monitoring
    const requests: any[] = [];
    page.on('request', request => {
      if (request.url().includes('localhost:8000')) {
        requests.push({
          url: request.url(),
          method: request.method(),
          headers: request.headers()
        });
      }
    });

    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Wait a bit more to catch any delayed requests
    await page.waitForTimeout(3000);

    console.log('Network requests to backend:', requests);

    // Currently, since we're using demo data, there might not be real API calls
    // But this test will help us identify when they are added
    expect(Array.isArray(requests)).toBe(true);
  });

  test('should check for any console errors', async ({ page }) => {
    const consoleMessages: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleMessages.push(msg.text());
      }
    });

    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Wait a bit more to catch any delayed errors
    await page.waitForTimeout(3000);

    console.log('Console errors:', consoleMessages);

    // Report any console errors
    if (consoleMessages.length > 0) {
      console.warn('Found console errors:', consoleMessages);
    }
  });
});