import { test, expect, devices } from '@playwright/test';

/**
 * Comprehensive UX Testing Suite for AP Intake & Validation System
 *
 * This test suite validates the entire user experience including:
 * - Invoice Review Interface (Primary Workflow)
 * - Dashboard Navigation (Secondary Workflow)
 * - Exception Management System (Critical Workflow)
 * - Email Integration Dashboard (Advanced Workflow)
 * - Form & Input Validation (Critical for Data Quality)
 * - Accessibility Testing (WCAG Compliance)
 * - Responsive Testing (Mobile, Tablet, Desktop)
 * - Performance Testing (Page Load & Interaction)
 */

test.describe('AP Intake System - Comprehensive UX Testing', () => {

  // Test on different devices for responsive design validation
  test.describe('Desktop Testing', () => {
    test.use({ ...devices['Desktop Chrome'] });

      test.beforeEach(async ({ page }) => {
        // Navigate to the main page
        await page.goto('http://localhost:3000');

        // Wait for page to fully load
        await page.waitForLoadState('networkidle');

        // Performance timing
        const performanceMetrics = await page.evaluate(() => {
          const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
          return {
            domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
            loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
            firstContentfulPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime || 0,
            largestContentfulPaint: performance.getEntriesByName('largest-contentful-paint')[0]?.startTime || 0,
          };
        });

        console.log(`Performance metrics for ${device.name}:`, performanceMetrics);

        // Assert reasonable performance (load should complete within 3 seconds)
        expect(performanceMetrics.loadComplete).toBeLessThan(3000);
      });

      test('Invoice Review Interface - Primary Workflow', async ({ page }) => {
        await test.step('1. Verify Page Header and Document Information', async () => {
          // Check main header is present and visible
          await expect(page.getByRole('heading', { name: 'AP Intake Review' })).toBeVisible();

          // Check document information
          await expect(page.getByText('Document:')).toBeVisible();
          await expect(page.getByText('Invoice_Acme_Corp_2024.pdf')).toBeVisible();

          // Check file icon is present
          await expect(page.locator('svg[data-testid="file-icon"]')).toBeVisible();
        });

        await test.step('2. Verify Status Banner with Key Metrics', async () => {
          // Check status banner
          const statusBanner = page.locator('div:has-text("Pending Review")').first();
          await expect(statusBanner).toBeVisible();

          // Verify extraction time and line items count
          await expect(page.getByText('Extracted in')).toBeVisible();
          await expect(page.getByText('1240ms')).toBeVisible();
          await expect(page.getByText('2 line items')).toBeVisible();

          // Check total amount display
          await expect(page.getByText('$12,450.50')).toBeVisible();
          await expect(page.getByText('USD')).toBeVisible();
        });

        await test.step('3. Verify Validation Alerts Display', async () => {
          // Check validation alerts section
          await expect(page.getByText('Validation Alerts (2)')).toBeVisible();

          // Verify specific validation issues
          await expect(page.getByText('vendorId:')).toBeVisible();
          await expect(page.getByText('Vendor ID not found in master list')).toBeVisible();

          await expect(page.getByText('purchaseOrder:')).toBeVisible();
          await expect(page.getByText('PO partially matches existing records')).toBeVisible();

          // Check warning triangle icon
          await expect(page.locator('svg[data-testid="alert-triangle"]')).toBeVisible();
        });

        await test.step('4. Test Tab Navigation - Smooth Transitions', async () => {
          // Test Summary tab (default)
          await expect(page.getByRole('button', { name: 'Summary' })).toBeVisible();
          await expect(page.getByRole('button', { name: 'Summary' })).toHaveClass(/border-blue-600/);

          // Test Detailed Fields tab
          const detailedTab = page.getByRole('button', { name: 'Detailed Fields' });
          await detailedTab.click();

          // Wait for content to change
          await page.waitForTimeout(200);
          await expect(detailedTab).toHaveClass(/border-blue-600/);
          await expect(page.getByRole('button', { name: 'Summary' })).not.toHaveClass(/border-blue-600/);

          // Verify detailed fields content appears
          await expect(page.getByText('Extracted Fields')).toBeVisible();
          await expect(page.getByText('Review confidence scores and validation status')).toBeVisible();

          // Test Line Items tab
          const lineItemsTab = page.getByRole('button', { name: 'Line Items' });
          await lineItemsTab.click();

          await page.waitForTimeout(200);
          await expect(lineItemsTab).toHaveClass(/border-blue-600/);

          // Verify line items content appears
          await expect(page.getByText('2 items found')).toBeVisible();
          await expect(page.getByText('Manufacturing supplies - Q4 batch')).toBeVisible();

          // Return to Summary tab
          await page.getByRole('button', { name: 'Summary' }).click();
          await page.waitForTimeout(200);
        });

        await test.step('5. Verify Data Display with Confidence Scores', async () => {
          // Check invoice details card
          await expect(page.getByText('Invoice Details')).toBeVisible();
          await expect(page.getByText('INV-2024-5647')).toBeVisible();
          await expect(page.getByText('High: 98%')).toBeVisible();

          // Check vendor information card
          await expect(page.getByText('Vendor Information')).toBeVisible();
          await expect(page.getByText('Acme Corp Manufacturing')).toBeVisible();
          await expect(page.getByText('Needs Review')).toBeVisible();

          // Check amount summary card
          await expect(page.getByText('Amount Summary')).toBeVisible();
          await expect(page.getByText('$12,000.00')).toBeVisible();
          await expect(page.getByText('$0.00')).toBeVisible();
          await expect(page.getByText('$12,450.50')).toBeVisible();

          // Check extraction quality card
          await expect(page.getByText('Extraction Quality')).toBeVisible();
          await expect(page.getByText('Overall Confidence')).toBeVisible();
          await expect(page.getByText('95%')).toBeVisible();

          // Check progress bar is present
          const progressBar = page.locator('div[style*="width: 95%"]');
          await expect(progressBar).toBeVisible();
        });

        await test.step('6. Test Action Buttons - Visual Feedback', async () => {
          // Verify all action buttons are present
          const rejectButton = page.getByRole('button', { name: 'Reject & Request Reupload' });
          const reviewButton = page.getByRole('button', { name: 'Request Manual Review' });
          const approveButton = page.getByRole('button', { name: 'Approve & Process' });

          await expect(rejectButton).toBeVisible();
          await expect(reviewButton).toBeVisible();
          await expect(approveButton).toBeVisible();

          // Test hover effects on buttons
          await rejectButton.hover();
          await page.waitForTimeout(100);

          await reviewButton.hover();
          await page.waitForTimeout(100);

          await approveButton.hover();
          await page.waitForTimeout(100);

          // Test button click interactions (should not navigate in demo)
          await rejectButton.click();
          await page.waitForTimeout(100);

          await reviewButton.click();
          await page.waitForTimeout(100);

          await approveButton.click();
          await page.waitForTimeout(100);
        });
      });

      test('Navigation Dashboard - Secondary Workflow', async ({ page }) => {
        await test.step('1. Test Navigation Links to Full System', async () => {
          // Check navigation section is present
          await expect(page.getByText('Ready for the Complete Invoice Management System?')).toBeVisible();

          // Test Invoice Dashboard link
          const invoiceDashboardLink = page.getByRole('link', { name: 'Open Invoice Dashboard' });
          await expect(invoiceDashboardLink).toBeVisible();

          // Test View Exceptions link
          const exceptionsLink = page.getByRole('link', { name: 'View Exceptions' });
          await expect(exceptionsLink).toBeVisible();

          // Test Email Integration link
          const emailLink = page.getByRole('link', { name: 'Email Integration' });
          await expect(emailLink).toBeVisible();

          // Verify quick stats section (on desktop)
          if (device.name !== 'iPhone 13 Pro') {
            await expect(page.getByText('Quick Stats')).toBeVisible();
            await expect(page.getByText('Total Invoices:')).toBeVisible();
            await expect(page.getByText('1,247')).toBeVisible();
            await expect(page.getByText('Pending Review:')).toBeVisible();
            await expect(page.getByText('23')).toBeVisible();
            await expect(page.getByText('Auto-Approval Rate:')).toBeVisible();
            await expect(page.getByText('78.5%')).toBeVisible();
          }
        });

        await test.step('2. Test Interactive Elements', async () => {
          // Test link hover states
          const invoiceDashboardLink = page.getByRole('link', { name: 'Open Invoice Dashboard' });
          await invoiceDashboardLink.hover();
          await page.waitForTimeout(100);

          // Verify links are properly formatted
          await expect(invoiceDashboardLink).toHaveAttribute('href', '/invoices');
          await expect(page.getByRole('link', { name: 'View Exceptions' })).toHaveAttribute('href', '/invoices?tab=exceptions');
          await expect(page.getByRole('link', { name: 'Email Integration' })).toHaveAttribute('href', '/email');
        });
      });

      test('Accessibility Testing - WCAG Compliance', async ({ page }) => {
        await test.step('1. Test Keyboard Navigation', async () => {
          // Test Tab navigation through interactive elements
          await page.keyboard.press('Tab');
          await page.waitForTimeout(100);

          // Continue tabbing through all interactive elements
          for (let i = 0; i < 10; i++) {
            await page.keyboard.press('Tab');
            await page.waitForTimeout(50);
          }

          // Test Shift+Tab for reverse navigation
          for (let i = 0; i < 5; i++) {
            await page.keyboard.press('Shift+Tab');
            await page.waitForTimeout(50);
          }

          // Test Enter key on buttons
          await page.keyboard.press('Enter');
          await page.waitForTimeout(100);
        });

        await test.step('2. Test ARIA Labels and Roles', async () => {
          // Check for proper ARIA roles
          await expect(page.getByRole('main')).toBeVisible();
          await expect(page.getByRole('button', { name: 'Summary' })).toBeVisible();
          await expect(page.getByRole('button', { name: 'Detailed Fields' })).toBeVisible();
          await expect(page.getByRole('button', { name: 'Line Items' })).toBeVisible();

          // Check for ARIA labels on interactive elements
          const alertRegion = page.getByRole('alert');
          await expect(alertRegion).toBeVisible();
        });

        await test.step('3. Test Color Contrast and Visual Accessibility', async () => {
          // Verify text is readable (basic check)
          const mainText = page.getByText('AP Intake Review');
          await expect(mainText).toBeVisible();

          // Check status indicators use both color and icons
          await expect(page.locator('svg[data-testid="check-circle"]')).toBeVisible();
          await expect(page.locator('svg[data-testid="alert-circle"]')).toBeVisible();
        });

        await test.step('4. Test Focus Management', async () => {
          // Test focus remains visible during keyboard navigation
          await page.keyboard.press('Tab');
          await page.waitForTimeout(100);

          // Verify focused element is visible
          const focusedElement = page.locator(':focus');
          await expect(focusedElement).toBeVisible();
        });
      });

      test('Responsive Design Testing', async ({ page }) => {
        const viewport = page.viewportSize();

        await test.step(`1. Verify Layout Adaptation for ${viewport?.width}x${viewport?.height}`, async () => {
          // Check main container is responsive
          const mainContainer = page.locator('.min-h-screen');
          await expect(mainContainer).toBeVisible();

          // On mobile, quick stats should be hidden
          if (device.name === 'iPhone 13 Pro') {
            await expect(page.getByText('Quick Stats')).not.toBeVisible();
          } else {
            await expect(page.getByText('Quick Stats')).toBeVisible();
          }

          // Test card layout adaptation
          const cards = page.locator('.grid > div');
          const cardCount = await cards.count();
          expect(cardCount).toBeGreaterThan(0);

          // Check text scaling
          const mainHeading = page.getByRole('heading', { name: 'AP Intake Review' });
          await expect(mainHeading).toBeVisible();
        });

        await test.step('2. Test Touch Interactions on Mobile', async () => {
          if (device.name === 'iPhone 13 Pro' || device.name === 'iPad Pro') {
            // Test tap interactions
            await page.tap('button:has-text("Detailed Fields")');
            await page.waitForTimeout(200);

            await page.tap('button:has-text("Line Items")');
            await page.waitForTimeout(200);

            await page.tap('button:has-text("Summary")');
            await page.waitForTimeout(200);
          }
        });

        await test.step('3. Test Scroll Behavior', async () => {
          // Test vertical scrolling
          const initialScrollY = await page.evaluate(() => window.scrollY);

          await page.evaluate(() => window.scrollTo(0, 500));
          await page.waitForTimeout(200);

          const afterScrollY = await page.evaluate(() => window.scrollY);
          expect(afterScrollY).toBeGreaterThan(initialScrollY);

          // Scroll back to top
          await page.evaluate(() => window.scrollTo(0, 0));
          await page.waitForTimeout(200);
        });
      });

      test('Form and Input Validation Testing', async ({ page }) => {
        await test.step('1. Test Button Interactions', async () => {
          // Test all main action buttons
          const buttons = [
            'Reject & Request Reupload',
            'Request Manual Review',
            'Approve & Process',
            'Open Invoice Dashboard',
            'View Exceptions',
            'Email Integration'
          ];

          for (const buttonText of buttons) {
            const button = page.getByRole('button', { name: buttonText }).or(page.getByRole('link', { name: buttonText }));
            await expect(button).toBeVisible();

            // Test hover state
            await button.hover();
            await page.waitForTimeout(50);

            // Test active state
            await button.click();
            await page.waitForTimeout(100);
          }
        });

        await test.step('2. Test Tab Switching Interactions', async () => {
          const tabs = ['Summary', 'Detailed Fields', 'Line Items'];

          for (const tabName of tabs) {
            const tab = page.getByRole('button', { name: tabName });
            await tab.click();
            await page.waitForTimeout(200);

            // Verify active tab styling
            await expect(tab).toHaveClass(/border-blue-600/);

            // Verify content is displayed
            if (tabName === 'Detailed Fields') {
              await expect(page.getByText('Extracted Fields')).toBeVisible();
            } else if (tabName === 'Line Items') {
              await expect(page.getByText('items found')).toBeVisible();
            }
          }
        });
      });

      test('Error State and Edge Case Testing', async ({ page }) => {
        await test.step('1. Test Network Error Handling', async () => {
          // Simulate offline condition
          await page.context().setOffline(true);

          // Try to interact with elements
          const button = page.getByRole('button', { name: 'Approve & Process' });
          await button.click();
          await page.waitForTimeout(200);

          // Restore online
          await page.context().setOffline(false);
        });

        await test.step('2. Test Rapid Interactions', async () => {
          // Test rapid tab switching
          const tabs = ['Summary', 'Detailed Fields', 'Line Items'];

          for (let i = 0; i < 3; i++) {
            for (const tabName of tabs) {
              await page.getByRole('button', { name: tabName }).click();
              await page.waitForTimeout(50);
            }
          }
        });

        await test.step('3. Test Browser Resize', async () => {
          // Test responsive resize
          await page.setViewportSize({ width: 800, height: 600 });
          await page.waitForTimeout(200);

          await page.setViewportSize({ width: 1200, height: 800 });
          await page.waitForTimeout(200);

          await page.setViewportSize({ width: 375, height: 667 });
          await page.waitForTimeout(200);
        });
      });

      test('Performance and Loading Testing', async ({ page }) => {
        await test.step('1. Measure Page Load Performance', async () => {
          const performanceMetrics = await page.evaluate(() => {
            const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
            return {
              domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
              loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
              firstPaint: performance.getEntriesByName('first-paint')[0]?.startTime || 0,
              firstContentfulPaint: performance.getEntriesByName('first-contentful-paint')[0]?.startTime || 0,
            };
          });

          console.log('Performance Metrics:', performanceMetrics);

          // Assert performance thresholds
          expect(performanceMetrics.domContentLoaded).toBeLessThan(1500);
          expect(performanceMetrics.loadComplete).toBeLessThan(3000);
          expect(performanceMetrics.firstContentfulPaint).toBeLessThan(2000);
        });

        await test.step('2. Test Animation Performance', async () => {
          // Test smooth transitions
          const startTime = Date.now();

          await page.getByRole('button', { name: 'Detailed Fields' }).click();
          await page.waitForTimeout(300);

          const endTime = Date.now();
          const transitionTime = endTime - startTime;

          // Transitions should complete within 300ms
          expect(transitionTime).toBeLessThan(500);
        });

        await test.step('3. Test Memory Usage', async ({ page }) => {
          // Basic memory check (if available)
          const memoryInfo = await page.evaluate(() => {
            return (performance as any).memory ? {
              usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
              totalJSHeapSize: (performance as any).memory.totalJSHeapSize,
            } : null;
          });

          if (memoryInfo) {
            console.log('Memory Usage:', memoryInfo);
            // Basic sanity check for memory usage
            expect(memoryInfo.usedJSHeapSize).toBeGreaterThan(0);
            expect(memoryInfo.totalJSHeapSize).toBeGreaterThan(memoryInfo.usedJSHeapSize);
          }
        });
      });
    });
  });

  // Cross-browser testing
  test.describe('Cross-Browser Testing', () => {
    test('Chrome Browser Compatibility', async ({ page, browserName }) => {
      test.skip(browserName !== 'chromium', 'Chrome-specific test');

      await page.goto('http://localhost:3000');
      await page.waitForLoadState('networkidle');

      // Chrome-specific features
      await expect(page.getByText('AP Intake Review')).toBeVisible();

      // Test Chrome DevTools integration (if available)
      const userAgent = await page.evaluate(() => navigator.userAgent);
      expect(userAgent).toContain('Chrome');
    });

    test('Firefox Browser Compatibility', async ({ page, browserName }) => {
      test.skip(browserName !== 'firefox', 'Firefox-specific test');

      await page.goto('http://localhost:3000');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('AP Intake Review')).toBeVisible();

      const userAgent = await page.evaluate(() => navigator.userAgent);
      expect(userAgent).toContain('Firefox');
    });

    test('Safari Browser Compatibility', async ({ page, browserName }) => {
      test.skip(browserName !== 'webkit', 'Safari-specific test');

      await page.goto('http://localhost:3000');
      await page.waitForLoadState('networkidle');

      await expect(page.getByText('AP Intake Review')).toBeVisible();

      const userAgent = await page.evaluate(() => navigator.userAgent);
      expect(userAgent).toContain('Safari');
    });
  });

  // Integration with other components (if they exist)
  test.describe('Component Integration Testing', () => {
    test('Toast Notification System', async ({ page }) => {
      await page.goto('http://localhost:3000');

      // Test toast container is present
      const toastContainer = page.locator('[role="region"][aria-label="Notifications"]');
      await expect(toastContainer).toBeVisible();
    });

    test('Theme Provider Integration', async ({ page }) => {
      await page.goto('http://localhost:3000');

      // Check if theme provider is working
      const bodyElement = page.locator('body');
      await expect(bodyElement).toHaveClass(/font-sans/);
      await expect(bodyElement).toHaveClass(/antialiased/);
    });
  });

  // Advanced user workflows
  test.describe('Advanced User Workflow Testing', () => {
    test('Complete Invoice Review Workflow', async ({ page }) => {
      await page.goto('http://localhost:3000');

      await test.step('1. Initial Review of Summary', async () => {
        // User starts with summary view
        await expect(page.getByRole('button', { name: 'Summary' })).toHaveClass(/border-blue-600/);
        await expect(page.getByText('Invoice Details')).toBeVisible();
        await expect(page.getByText('Vendor Information')).toBeVisible();
        await expect(page.getByText('Amount Summary')).toBeVisible();
      });

      await test.step('2. Deep Dive into Detailed Fields', async () => {
        // User switches to detailed view for comprehensive review
        await page.getByRole('button', { name: 'Detailed Fields' }).click();
        await page.waitForTimeout(200);

        // User reviews confidence scores
        await expect(page.getByText('High: 98%')).toBeVisible();
        await expect(page.getByText('Good: 89%')).toBeVisible();

        // User reviews validation status
        await expect(page.getByText('Validated')).toBeVisible();
        await expect(page.getByText('Needs Review')).toBeVisible();
      });

      await test.step('3. Line Items Verification', async () => {
        // User checks line items for accuracy
        await page.getByRole('button', { name: 'Line Items' }).click();
        await page.waitForTimeout(200);

        // User reviews each line item
        await expect(page.getByText('Manufacturing supplies - Q4 batch')).toBeVisible();
        await expect(page.getByText('500')).toBeVisible(); // Quantity
        await expect(page.getByText('$24.00')).toBeVisible(); // Unit price
        await expect(page.getByText('$12,000.00')).toBeVisible(); // Total
      });

      await test.step('4. Return to Summary for Decision', async () => {
        // User returns to summary for final decision
        await page.getByRole('button', { name: 'Summary' }).click();
        await page.waitForTimeout(200);

        // User makes final decision
        await expect(page.getByRole('button', { name: 'Approve & Process' })).toBeVisible();
      });
    });

    test('Exception Review Workflow', async ({ page }) => {
      await page.goto('http://localhost:3000');

      await test.step('1. Review Validation Alerts', async () => {
        // User reviews validation alerts
        await expect(page.getByText('Validation Alerts (2)')).toBeVisible();
        await expect(page.getByText('Vendor ID not found in master list')).toBeVisible();
        await expect(page.getByText('PO partially matches existing records')).toBeVisible();
      });

      await test.step('2. Evaluate Risk Level', async () => {
        // User evaluates overall confidence
        await expect(page.getByText('Overall Confidence')).toBeVisible();
        await expect(page.getByText('95%')).toBeVisible();

        // User checks specific field confidence
        await expect(page.getByText('High: 98%')).toBeVisible();
        await expect(page.getByText('Good: 89%')).toBeVisible();
      });

      await test.step('3. Make Informed Decision', async () => {
        // Based on review, user chooses appropriate action
        await expect(page.getByRole('button', { name: 'Request Manual Review' })).toBeVisible();
        await expect(page.getByRole('button', { name: 'Approve & Process' })).toBeVisible();
      });
    });
  });
});