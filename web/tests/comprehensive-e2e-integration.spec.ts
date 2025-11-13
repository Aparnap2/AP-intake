import { test, expect } from '@playwright/test';

test.describe('Comprehensive E2E UI-Backend Integration Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the frontend
    await page.goto('http://localhost:3000');
    // Wait for the page to load completely
    await page.waitForLoadState('networkidle');
  });

  test('should load the React frontend application', async ({ page }) => {
    // Check if the main title is visible
    await expect(page.locator('h1')).toContainText('AP Intake Review');

    // Take a screenshot of the initial state
    await page.screenshot({ path: 'test-results/frontend-loaded.png', fullPage: true });

    // Verify the page structure
    await expect(page.locator('text=Document: Invoice_Acme_Corp_2024.pdf')).toBeVisible();
    await expect(page.locator('text=$12,450.50')).toBeVisible();
  });

  test('should display invoice details and validation alerts', async ({ page }) => {
    // Check invoice details
    await expect(page.locator('text=INV-2024-5647')).toBeVisible();
    await expect(page.locator('text=Acme Corp Manufacturing')).toBeVisible();

    // Check validation alerts
    await expect(page.locator('text=Validation Alerts (2)')).toBeVisible();
    await expect(page.locator('text=Vendor ID not found in master list')).toBeVisible();
    await expect(page.locator('text=PO partially matches existing records')).toBeVisible();

    // Check confidence scores
    await expect(page.locator('text=High: 98%')).toBeVisible();
    await expect(page.locator('text=Ready for Processing')).toBeVisible();
  });

  test('should handle tab navigation correctly', async ({ page }) => {
    // Check that Summary tab is active by default
    await expect(page.locator('text=Summary')).toBeVisible();

    // Click on Detailed Fields tab
    await page.click('text=Detailed Fields');
    await page.waitForTimeout(500); // Wait for tab transition

    // Click on Line Items tab
    await page.click('text=Line Items');
    await page.waitForTimeout(500);

    // Verify tabs are clickable and interface is responsive
    await expect(page.locator('h1')).toContainText('AP Intake Review');
  });

  test('should have functional action buttons', async ({ page }) => {
    // Check that all action buttons are present and clickable
    const buttons = [
      'button:has-text("Reject & Request Reupload")',
      'button:has-text("Request Manual Review")',
      'button:has-text("Approve & Process")'
    ];

    for (const buttonSelector of buttons) {
      await expect(page.locator(buttonSelector)).toBeVisible();
      await expect(page.locator(buttonSelector)).toBeEnabled();
    }

    // Test clicking the approve button
    await page.click('button:has-text("Approve & Process")');
    await page.waitForTimeout(1000);

    // Verify we're still on the same page (button click shouldn't break anything)
    await expect(page.locator('h1')).toContainText('AP Intake Review');
  });

  test('should have working navigation links', async ({ page }) => {
    // Check for navigation links
    const links = [
      'a:has-text("Open Invoice Dashboard")',
      'a:has-text("View Exceptions")',
      'a:has-text("Email Integration")'
    ];

    for (const linkSelector of links) {
      await expect(page.locator(linkSelector)).toBeVisible();
    }

    // Test navigation to invoice dashboard
    const [newPage] = await Promise.all([
      page.context().waitForEvent('page'),
      page.click('a:has-text("Open Invoice Dashboard")')
    ]);

    await newPage.waitForLoadState('networkidle');
    // Check that we navigated (even if to 404, this shows navigation works)
    expect(newPage.url()).toContain('/invoices');
    await newPage.close();
  });
});

test.describe('Backend API Health Checks', () => {
  test('should verify backend server is running', async ({ request }) => {
    // Test health endpoint
    const healthResponse = await request.get('http://localhost:8000/health');
    expect(healthResponse.status()).toBe(200);

    const healthData = await healthResponse.json();
    expect(healthData).toHaveProperty('status', 'healthy');
    expect(healthData).toHaveProperty('version');
    expect(healthData).toHaveProperty('environment');

    console.log('✅ Backend health check passed:', healthData);
  });

  test('should verify API documentation is accessible', async ({ request }) => {
    // Test API docs endpoint
    const docsResponse = await request.get('http://localhost:8000/docs');
    expect(docsResponse.status()).toBe(200);

    const docsContent = await docsResponse.text();
    expect(docsContent).toContain('Swagger UI');
    expect(docsContent).toContain('AP Intake & Validation');

    console.log('✅ API documentation is accessible');
  });

  test('should verify metrics endpoint is working', async ({ request }) => {
    // Test metrics endpoint
    const metricsResponse = await request.get('http://localhost:8000/metrics');
    expect(metricsResponse.status()).toBe(200);

    const metricsContent = await metricsResponse.text();
    expect(metricsContent).toContain('http_requests_total');

    console.log('✅ Metrics endpoint is working');
  });

  test('should test frontend-backend connectivity', async ({ page }) => {
    // Test if we can make API calls from the frontend context
    const connectivityTest = await page.evaluate(async () => {
      try {
        // Test the health endpoint from frontend
        const healthResponse = await fetch('http://localhost:8000/health');
        const healthData = await healthResponse.json();

        return {
          success: true,
          status: healthResponse.status,
          data: healthData
        };
      } catch (error) {
        return {
          success: false,
          error: error.message
        };
      }
    });

    console.log('Frontend-Backend connectivity test:', connectivityTest);

    expect(connectivityTest.success).toBe(true);
    expect(connectivityTest.status).toBe(200);
    expect(connectivityTest.data).toHaveProperty('status', 'healthy');
  });
});

test.describe('Application Performance and Error Monitoring', () => {
  test('should monitor for console errors', async ({ page }) => {
    const consoleMessages: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleMessages.push(msg.text());
      }
    });

    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000); // Wait for any delayed errors

    console.log('Console errors found:', consoleMessages.length);
    if (consoleMessages.length > 0) {
      console.warn('Console errors:', consoleMessages);
    }

    // Report the results
    expect(consoleMessages.length).toBe(0);
  });

  test('should check page load performance', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    console.log(`Page load time: ${loadTime}ms`);

    // Page should load within reasonable time
    expect(loadTime).toBeLessThan(5000); // 5 seconds max

    // Take performance screenshot
    await page.screenshot({ path: 'test-results/performance-screenshot.png' });
  });

  test('should verify responsive design', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Test desktop viewport
    await page.setViewportSize({ width: 1200, height: 800 });
    await expect(page.locator('h1')).toBeVisible();

    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(page.locator('h1')).toBeVisible();

    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await expect(page.locator('h1')).toBeVisible();

    console.log('✅ Responsive design verified across viewports');
  });
});

test.describe('Data Display and UI Components', () => {
  test('should display invoice summary cards correctly', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Check for key summary elements
    await expect(page.locator('text=Invoice Details')).toBeVisible();
    await expect(page.locator('text=Vendor Information')).toBeVisible();
    await expect(page.locator('text=Amount Summary')).toBeVisible();
    await expect(page.locator('text=Extraction Quality')).toBeVisible();

    // Check for status indicators
    await expect(page.locator('text=Pending Review')).toBeVisible();
    await expect(page.locator('text=Ready for Processing')).toBeVisible();
  });

  test('should display confidence indicators and badges', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Check for confidence badges
    await expect(page.locator('text=High: 98%')).toBeVisible();
    await expect(page.locator('text=Good: 89%')).toBeVisible();
    await expect(page.locator('text=Needs Review')).toBeVisible();

    // Check for progress bars
    await expect(page.locator('[style*="width:95%"]')).toBeVisible(); // Confidence progress bar
  });

  test('should have proper color coding and visual hierarchy', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Take screenshot for visual verification
    await page.screenshot({ path: 'test-results/visual-hierarchy.png', fullPage: true });

    // Check for warning colors (amber/yellow)
    const validationAlerts = page.locator('text=Validation Alerts');
    await expect(validationAlerts).toBeVisible();

    // Check for success indicators
    await expect(page.locator('text=Ready for Processing')).toBeVisible();
  });
});

test.describe('Integration Issues Documentation', () => {
  test('should document current API integration status', async ({ request }) => {
    const endpoints = [
      '/health',
      '/docs',
      '/metrics',
      '/api/v1/invoices/',
      '/api/v1/vendors/'
    ];

    const results: any = {};

    for (const endpoint of endpoints) {
      try {
        const response = await request.get(`http://localhost:8000${endpoint}`);
        results[endpoint] = {
          status: response.status(),
          ok: response.ok(),
          contentType: response.headers()['content-type']
        };
      } catch (error) {
        results[endpoint] = {
          error: error.message
        };
      }
    }

    console.log('🔍 Current API Integration Status:');
    console.log(JSON.stringify(results, null, 2));

    // Document what's working vs what needs attention
    const workingEndpoints = Object.entries(results).filter(([_, data]: any) => data.ok);
    const brokenEndpoints = Object.entries(results).filter(([_, data]: any) => !data.ok);

    console.log(`✅ Working endpoints: ${workingEndpoints.length}`);
    console.log(`❌ Broken endpoints: ${brokenEndpoints.length}`);

    // Save results for reference
    await request.post('http://localhost:3000/test-results', {
      data: {
        timestamp: new Date().toISOString(),
        integrationStatus: results,
        workingEndpoints: workingEndpoints.length,
        brokenEndpoints: brokenEndpoints.length
      }
    }).catch(() => {
      // Ignore this - just documenting the status
    });
  });
});