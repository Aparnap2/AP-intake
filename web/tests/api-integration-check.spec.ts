import { test, expect } from '@playwright/test';

test.describe('API Integration Analysis', () => {
  test('should analyze current frontend for API integration points', async ({ page }) => {
    await page.goto('http://localhost:3000');

    // Check if there are any fetch calls in the page source
    const hasApiCalls = await page.evaluate(() => {
      const scripts = Array.from(document.querySelectorAll('script'));
      const pageContent = scripts.map(script => script.textContent || script.innerHTML).join(' ');

      // Look for common API patterns
      const apiPatterns = [
        /fetch\s*\(/,
        /axios\./,
        /api\//,
        /localhost:8000/,
        /\/api\/v1\//,
        /useEffect.*fetch/,
        /useSWR/,
        /react-query/,
        /@tanstack\/react-query/
      ];

      return apiPatterns.some(pattern => pattern.test(pageContent));
    });

    console.log('Frontend has API integration patterns:', hasApiCalls);

    // Take screenshot for visual verification
    await page.screenshot({ path: 'test-results/frontend-screenshot.png', fullPage: true });
  });

  test('should check for React hooks that might fetch data', async ({ page }) => {
    const reactHooksCheck = await page.evaluate(() => {
      // Look for React hooks usage in the page
      const scripts = Array.from(document.querySelectorAll('script'));
      const pageContent = scripts.map(script => script.textContent || script.innerHTML).join(' ');

      const hooksFound = {
        useEffect: /useEffect/.test(pageContent),
        useState: /useState/.test(pageContent),
        useFetch: /useFetch|useSWR|useQuery/.test(pageContent),
        hasDataFetching: false
      };

      // Check for data fetching patterns
      hooksFound.hasDataFetching = /fetch|axios|request/.test(pageContent);

      return hooksFound;
    });

    console.log('React hooks analysis:', reactHooksCheck);
  });

  test('should test direct API communication from frontend', async ({ page }) => {
    // Test if we can make API calls from the frontend context
    const apiTestResult = await page.evaluate(async () => {
      try {
        // Test the health endpoint
        const healthResponse = await fetch('http://localhost:8000/health');
        const healthData = await healthResponse.json();

        // Test the invoices endpoint
        const invoicesResponse = await fetch('http://localhost:8000/api/v1/invoices');

        return {
          healthEndpoint: {
            status: healthResponse.status,
            ok: healthResponse.ok,
            data: healthData
          },
          invoicesEndpoint: {
            status: invoicesResponse.status,
            ok: invoicesResponse.ok,
            hasData: invoicesResponse.headers.get('content-type')?.includes('application/json')
          }
        };
      } catch (error) {
        return {
          error: error.message,
          stack: error.stack
        };
      }
    });

    console.log('Direct API test results:', apiTestResult);

    // Verify API communication works
    expect(apiTestResult.error).toBeUndefined();
    expect(apiTestResult.healthEndpoint.ok).toBe(true);
    expect(apiTestResult.invoicesEndpoint.ok).toBe(true);
  });

  test('should check what backend endpoints are available', async ({ request }) => {
    const endpoints = [
      '/health',
      '/api/v1/invoices',
      '/docs',
      '/metrics',
      '/openapi.json'
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

        // Get sample data for some endpoints
        if (endpoint === '/api/v1/invoices' && response.ok()) {
          try {
            results[endpoint].data = await response.json();
          } catch (e) {
            results[endpoint].dataError = 'Failed to parse JSON';
          }
        }
      } catch (error) {
        results[endpoint] = {
          error: error.message
        };
      }
    }

    console.log('Available backend endpoints:', JSON.stringify(results, null, 2));

    // Save endpoint information for reference
    await page.evaluate((data) => {
      console.log('Backend API Analysis:', data);
    }, results);
  });

  test('should create a proof-of-concept API integration', async ({ page }) => {
    // Inject a simple API integration test into the page
    const integrationTest = await page.evaluate(async () => {
      // Create a simple function to test API integration
      async function testBackendIntegration() {
        const results = {
          healthCheck: false,
          invoicesData: null,
          error: null
        };

        try {
          // Test health endpoint
          const healthResponse = await fetch('http://localhost:8000/health');
          if (healthResponse.ok) {
            results.healthCheck = true;
            const healthData = await healthResponse.json();
            console.log('Health check passed:', healthData);
          }

          // Test invoices endpoint
          const invoicesResponse = await fetch('http://localhost:8000/api/v1/invoices');
          if (invoicesResponse.ok) {
            const invoicesData = await invoicesResponse.json();
            results.invoicesData = invoicesData;
            console.log('Invoices data:', invoicesData);
          }

        } catch (error) {
          results.error = error.message;
          console.error('API integration test failed:', error);
        }

        return results;
      }

      // Run the test
      return await testBackendIntegration();
    });

    console.log('Proof-of-concept API integration:', integrationTest);

    // Verify the integration works
    expect(integrationTest.healthCheck).toBe(true);
    expect(integrationTest.error).toBeNull();
  });
});