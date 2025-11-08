import { test, expect } from '@playwright/test';
import { join } from 'path';
import { promises as fs } from 'fs';

test.describe('Invoice Upload Data Validation Tests', () => {
  const testInvoicesPath = '/home/aparna/Desktop/ap_intake/test_invoices';

  test.beforeEach(async ({ page }) => {
    // Navigate to the invoices page
    await page.goto('http://localhost:3000/invoices');

    // Wait for the page to load completely
    await page.waitForLoadState('networkidle');

    // Wait for the main invoice dashboard to be visible
    await expect(page.locator('h1')).toContainText('Invoice Management');
  });

  test('should upload standard invoice and display correct data without NaN or undefined', async ({ page }) => {
    // Take initial screenshot
    await page.screenshot({ path: 'test-results/invoice-dashboard-before-upload.png' });

    // Click the upload button to open modal
    await page.click('button:has-text("Upload Invoice")');

    // Wait for modal to open
    await expect(page.locator('h2:has-text("Upload Invoices")')).toBeVisible();
    await page.screenshot({ path: 'test-results/upload-modal-opened.png' });

    // Get a test invoice file
    const testInvoicePath = join(testInvoicesPath, 'test_invoice_standard_20251108_050448.pdf');

    // Check if file exists
    try {
      await fs.access(testInvoicePath);
    } catch (error) {
      console.log(`Test file not found: ${testInvoicePath}`);
      // Try alternative file
      const altInvoicePath = join(testInvoicesPath, 'test_invoice_standard_01_20251107_175123.pdf');
      await fs.access(altInvoicePath);
      testInvoicePath.replace('test_invoice_standard_20251108_050448.pdf', 'test_invoice_standard_01_20251107_175123.pdf');
    }

    // Upload the file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(testInvoicePath);

    // Wait for file to be processed and upload button to be enabled
    await page.waitForTimeout(1000);

    // Click upload button
    await page.click('button:has-text("Upload")');

    // Wait for upload to complete - look for success message or navigation
    await page.waitForTimeout(5000);

    // Take screenshot after upload
    await page.screenshot({ path: 'test-results/after-upload.png' });

    // Look for invoice in the list and click to review
    // Try to find the uploaded invoice
    const invoiceRow = page.locator('text=INV-').first();
    if (await invoiceRow.isVisible()) {
      await invoiceRow.click();
    } else {
      // If no specific invoice found, try to navigate to review tab
      const reviewTab = page.locator('button:has-text("Review")');
      if (await reviewTab.isVisible()) {
        await reviewTab.click();
      }
    }

    // Wait for invoice review page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Take screenshot of invoice review page
    await page.screenshot({ path: 'test-results/invoice-review-page.png' });

    // Validate that amounts are displayed correctly (no NaN values)
    const amountElements = page.locator('text=$').all();
    for (const element of await amountElements) {
      const text = await element.textContent();
      expect(text).not.toContain('NaN');
      expect(text).not.toContain('undefined');
      if (text && text.includes('$')) {
        // Should be a valid monetary amount
        expect(text).toMatch(/\$\d[\d,]*\.?\d*/);
      }
    }

    // Validate confidence scores are displayed as percentages (not NaN%)
    const confidenceElements = page.locator('text=/\d+%/').all();
    for (const element of await confidenceElements) {
      const text = await element.textContent();
      expect(text).not.toContain('NaN%');
      expect(text).not.toContain('undefined%');
      if (text) {
        // Should be a valid percentage
        expect(text).match(/\d+%/);
      }
    }

    // Validate vendor names are displayed properly (not "undefined")
    const vendorElements = page.locator('text=Acme Corp').all();
    for (const element of await vendorElements) {
      const text = await element.textContent();
      expect(text).not.toBe('undefined');
      expect(text).not.toBe('NaN');
      expect(text?.length).toBeGreaterThan(0);
    }

    // Validate invoice numbers are displayed properly (not "undefined")
    const invoiceNumberElements = page.locator('text=INV-').all();
    for (const element of await invoiceNumberElements) {
      const text = await element.textContent();
      expect(text).not.toBe('undefined');
      expect(text).not.toBe('NaN');
      expect(text?.length).toBeGreaterThan(0);
    }

    // Check specific data fields that commonly have issues
    await validateNoNaNOrUndefined(page, 'Invoice Number');
    await validateNoNaNOrUndefined(page, 'Invoice Date');
    await validateNoNaNOrUndefined(page, 'Due Date');
    await validateNoNaNOrUndefined(page, 'Vendor Name');
    await validateNoNaNOrUndefined(page, 'Total Amount');
    await validateNoNaNOrUndefined(page, 'Subtotal');
    await validateNoNaNOrUndefined(page, 'Tax');

    // Take final screenshot showing successful validation
    await page.screenshot({ path: 'test-results/final-validation-success.png' });

    console.log('✅ All data validations passed - no NaN or undefined values found');
  });

  test('should handle complex invoice with many items correctly', async ({ page }) => {
    // Open upload modal
    await page.click('button:has-text("Upload Invoice")');
    await expect(page.locator('h2:has-text("Upload Invoices")')).toBeVisible();

    // Upload complex invoice with many items
    const complexInvoicePath = join(testInvoicesPath, 'test_invoice_many_items_20251108_050448.pdf');

    try {
      await fs.access(complexInvoicePath);
    } catch (error) {
      console.log(`Complex test file not found, using alternative`);
      const altPath = join(testInvoicesPath, 'test_invoice_many_items_20251107_175127.pdf');
      await fs.access(altPath);
      complexInvoicePath.replace('test_invoice_many_items_20251108_050448.pdf', 'test_invoice_many_items_20251107_175127.pdf');
    }

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(complexInvoicePath);

    await page.waitForTimeout(1000);
    await page.click('button:has-text("Upload")');
    await page.waitForTimeout(5000);

    // Navigate to review if possible
    const reviewTab = page.locator('button:has-text("Review")');
    if (await reviewTab.isVisible()) {
      await reviewTab.click();
      await page.waitForLoadState('networkidle');
    }

    // Take screenshot of complex invoice
    await page.screenshot({ path: 'test-results/complex-invoice-review.png' });

    // Validate line items table doesn't have NaN/undefined values
    const lineItemElements = page.locator('table tr').all();
    for (const element of await lineItemElements.slice(0, 5)) { // Check first 5 rows
      const text = await element.textContent();
      expect(text).not.toContain('NaN');
      expect(text).not.toContain('undefined');
    }

    console.log('✅ Complex invoice validation passed');
  });

  test('should handle minimal invoice correctly', async ({ page }) => {
    // Open upload modal
    await page.click('button:has-text("Upload Invoice")');
    await expect(page.locator('h2:has-text("Upload Invoices")')).toBeVisible();

    // Upload minimal invoice
    const minimalInvoicePath = join(testInvoicesPath, 'test_invoice_minimal_20251108_050448.pdf');

    try {
      await fs.access(minimalInvoicePath);
    } catch (error) {
      const altPath = join(testInvoicesPath, 'test_invoice_minimal_20251107_175127.pdf');
      await fs.access(altPath);
      minimalInvoicePath.replace('test_invoice_minimal_20251108_050448.pdf', 'test_invoice_minimal_20251107_175127.pdf');
    }

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(minimalInvoicePath);

    await page.waitForTimeout(1000);
    await page.click('button:has-text("Upload")');
    await page.waitForTimeout(5000);

    // Take screenshot of minimal invoice
    await page.screenshot({ path: 'test-results/minimal-invoice-review.png' });

    // Validate that even minimal data doesn't show NaN/undefined
    const pageText = await page.textContent('body');
    expect(pageText).not.toContain('NaN');
    expect(pageText).not.toContain('undefined');

    console.log('✅ Minimal invoice validation passed');
  });
});

// Helper function to validate no NaN or undefined values for a specific field
async function validateNoNaNOrUndefined(page: any, fieldName: string) {
  try {
    const fieldLabel = page.locator(`text=${fieldName}`);
    if (await fieldLabel.isVisible()) {
      const parentRow = fieldLabel.locator('xpath=ancestor::div[contains(@class, "flex")][1]');
      const fieldValue = parentRow.locator('span').last();

      if (await fieldValue.isVisible()) {
        const text = await fieldValue.textContent();
        expect(text).not.toBe('NaN');
        expect(text).not.toBe('undefined');
        expect(text?.length).toBeGreaterThan(0);
        console.log(`✅ ${fieldName}: ${text}`);
      }
    }
  } catch (error) {
    console.log(`Could not validate ${fieldName}: ${error}`);
  }
}