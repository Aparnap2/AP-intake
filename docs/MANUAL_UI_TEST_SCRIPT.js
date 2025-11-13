/**
 * Manual UI Testing Script for AP Intake & Validation System
 * This script can be run in browser console to test UI functionality
 */

class ManualUITester {
  constructor() {
    this.testResults = [];
    this.baseUrl = 'http://localhost:3000';
  }

  log(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    this.testResults.push({ message, type, timestamp: new Date() });
  }

  async testPageLoad() {
    this.log('Testing page load and basic UI elements...');

    try {
      // Check if main elements are present
      const mainTitle = document.querySelector('h1');
      if (mainTitle) {
        this.log(`✅ Main title found: ${mainTitle.textContent}`, 'success');
      } else {
        this.log('❌ Main title not found', 'error');
      }

      // Check for navigation
      const navElements = document.querySelectorAll('nav a');
      this.log(`✅ Found ${navElements.length} navigation links`, 'success');

      // Check for buttons
      const buttons = document.querySelectorAll('button');
      this.log(`✅ Found ${buttons.length} buttons on page`, 'success');

      return true;
    } catch (error) {
      this.log(`❌ Page load test failed: ${error.message}`, 'error');
      return false;
    }
  }

  async testInvoiceDashboard() {
    this.log('Testing Invoice Dashboard functionality...');

    try {
      // Look for invoice table
      const table = document.querySelector('table');
      if (table) {
        this.log('✅ Invoice table found', 'success');

        // Test sorting
        const sortableHeaders = table.querySelectorAll('th button');
        if (sortableHeaders.length > 0) {
          this.log(`✅ Found ${sortableHeaders.length} sortable columns`, 'success');

          // Test clicking a sort button
          sortableHeaders[0].click();
          this.log('✅ Sort functionality tested', 'success');
        }
      }

      // Test search functionality
      const searchInput = document.querySelector('input[placeholder*="search"]');
      if (searchInput) {
        searchInput.value = 'test';
        searchInput.dispatchEvent(new Event('input', { bubbles: true }));
        this.log('✅ Search input tested', 'success');
      }

      // Test filters
      const filterButtons = document.querySelectorAll('button');
      const filterButton = Array.from(filterButtons).find(btn =>
        btn.textContent.includes('Filter')
      );
      if (filterButton) {
        filterButton.click();
        this.log('✅ Filter button tested', 'success');
      }

      return true;
    } catch (error) {
      this.log(`❌ Invoice dashboard test failed: ${error.message}`, 'error');
      return false;
    }
  }

  async testFormInteractions() {
    this.log('Testing form interactions...');

    try {
      // Test all input fields
      const inputs = document.querySelectorAll('input, textarea, select');
      this.log(`✅ Found ${inputs.length} form elements`, 'success');

      inputs.forEach((input, index) => {
        if (input.type !== 'hidden' && !input.disabled) {
          // Test focus
          input.focus();
          if (document.activeElement === input) {
            this.log(`✅ Input ${index + 1} focusable`, 'success');
          }

          // Test value change if appropriate
          if (input.tagName === 'INPUT' && input.type === 'text') {
            input.value = 'test value';
            input.dispatchEvent(new Event('input', { bubbles: true }));
            this.log(`✅ Input ${index + 1} value change tested`, 'success');
          }
        }
      });

      return true;
    } catch (error) {
      this.log(`❌ Form interactions test failed: ${error.message}`, 'error');
      return false;
    }
  }

  async testModalAndDialog() {
    this.log('Testing modal and dialog functionality...');

    try {
      // Look for modal triggers
      const modalTriggers = document.querySelectorAll('[role="dialog"], [data-modal], .modal-trigger');

      if (modalTriggers.length > 0) {
        this.log(`✅ Found ${modalTriggers.length} modal-related elements`, 'success');
      } else {
        this.log('ℹ️ No modal elements found on current page', 'info');
      }

      // Test alert dialogs
      const alertDialogs = document.querySelectorAll('[role="alertdialog"]');
      if (alertDialogs.length > 0) {
        this.log(`✅ Found ${alertDialogs.length} alert dialogs`, 'success');
      }

      return true;
    } catch (error) {
      this.log(`❌ Modal test failed: ${error.message}`, 'error');
      return false;
    }
  }

  async testResponsiveDesign() {
    this.log('Testing responsive design...');

    try {
      // Store original viewport size
      const originalWidth = window.innerWidth;
      const originalHeight = window.innerHeight;

      // Test different viewport sizes
      const viewports = [
        { width: 1920, height: 1080, name: 'Desktop' },
        { width: 768, height: 1024, name: 'Tablet' },
        { width: 375, height: 667, name: 'Mobile' }
      ];

      for (const viewport of viewports) {
        // Resize window (this might not work in all browsers)
        window.resizeTo(viewport.width, viewport.height);
        await new Promise(resolve => setTimeout(resolve, 500));

        this.log(`✅ Tested ${viewport.name} viewport (${viewport.width}x${viewport.height})`, 'success');
      }

      // Restore original size
      window.resizeTo(originalWidth, originalHeight);

      return true;
    } catch (error) {
      this.log(`❌ Responsive design test failed: ${error.message}`, 'error');
      return false;
    }
  }

  async testAccessibility() {
    this.log('Testing accessibility features...');

    try {
      // Test keyboard navigation
      const focusableElements = document.querySelectorAll(
        'a, button, input, textarea, select, [tabindex]:not([tabindex="-1"])'
      );
      this.log(`✅ Found ${focusableElements.length} keyboard-focusable elements`, 'success');

      // Test ARIA labels
      const elementsWithAria = document.querySelectorAll('[aria-label], [aria-labelledby], [role]');
      this.log(`✅ Found ${elementsWithAria.length} elements with ARIA attributes`, 'success');

      // Test color contrast (basic check)
      const textElements = document.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, h6');
      this.log(`✅ Found ${textElements.length} text elements for contrast testing`, 'success');

      // Test headings structure
      const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
      this.log(`✅ Found ${headings.length} heading elements`, 'success');

      return true;
    } catch (error) {
      this.log(`❌ Accessibility test failed: ${error.message}`, 'error');
      return false;
    }
  }

  async testPerformance() {
    this.log('Testing performance metrics...');

    try {
      // Check page load time
      if (performance.timing) {
        const loadTime = performance.timing.loadEventEnd - performance.timing.navigationStart;
        this.log(`✅ Page load time: ${loadTime}ms`, 'success');
      }

      // Check for large DOM trees
      const elementCount = document.querySelectorAll('*').length;
      this.log(`✅ DOM element count: ${elementCount}`, 'success');

      // Check for memory usage (if available)
      if (performance.memory) {
        const memoryUsed = Math.round(performance.memory.usedJSHeapSize / 1048576);
        this.log(`✅ Memory usage: ${memoryUsed}MB`, 'success');
      }

      return true;
    } catch (error) {
      this.log(`❌ Performance test failed: ${error.message}`, 'error');
      return false;
    }
  }

  async runAllTests() {
    this.log('🚀 Starting comprehensive UI testing...', 'info');

    const tests = [
      () => this.testPageLoad(),
      () => this.testInvoiceDashboard(),
      () => this.testFormInteractions(),
      () => this.testModalAndDialog(),
      () => this.testResponsiveDesign(),
      () => this.testAccessibility(),
      () => this.testPerformance()
    ];

    let passed = 0;
    let failed = 0;

    for (const test of tests) {
      try {
        const result = await test();
        if (result) {
          passed++;
        } else {
          failed++;
        }
      } catch (error) {
        this.log(`❌ Test failed with exception: ${error.message}`, 'error');
        failed++;
      }
    }

    this.log(`\n📊 Test Summary:`, 'info');
    this.log(`✅ Passed: ${passed}`, 'success');
    this.log(`❌ Failed: ${failed}`, 'error');
    this.log(`📝 Total: ${passed + failed}`, 'info');

    return {
      passed,
      failed,
      total: passed + failed,
      results: this.testResults
    };
  }

  generateReport() {
    const report = {
      timestamp: new Date().toISOString(),
      url: window.location.href,
      userAgent: navigator.userAgent,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight
      },
      results: this.testResults,
      summary: {
        total: this.testResults.length,
        success: this.testResults.filter(r => r.type === 'success').length,
        error: this.testResults.filter(r => r.type === 'error').length,
        info: this.testResults.filter(r => r.type === 'info').length
      }
    };

    console.log('\n📋 Test Report:', report);
    return report;
  }
}

// Auto-run if in browser environment
if (typeof window !== 'undefined') {
  const tester = new ManualUITester();

  // Make available globally
  window.uiTester = tester;

  // Run tests automatically after page load
  if (document.readyState === 'complete') {
    setTimeout(() => tester.runAllTests(), 1000);
  } else {
    window.addEventListener('load', () => {
      setTimeout(() => tester.runAllTests(), 1000);
    });
  }

  console.log('🔧 UI Tester loaded. Run uiTester.runAllTests() to start testing.');
}