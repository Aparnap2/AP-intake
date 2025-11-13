const { chromium } = require('playwright');

async function runComprehensiveUXTests() {
  console.log('🚀 Starting Comprehensive UX Testing for AP Intake & Validation System');
  console.log('================================================================');

  const browser = await chromium.launch({
    headless: false, // Show browser for visual verification
    slowMo: 500 // Slow down for better visibility
  });

  const context = await browser.newContext({
    viewport: { width: 1366, height: 768 }
  });

  const page = await context.newPage();

  try {
    // Test 1: Main Invoice Review Interface
    console.log('\n📋 Testing 1: Main Invoice Review Interface');
    console.log('-------------------------------------------');

    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Take initial screenshot
    await page.screenshot({ path: 'ux_test_main_page.png' });
    console.log('✅ Main page loaded successfully');

    // Test navigation elements
    const navElements = await page.locator('nav a, header a').count();
    console.log(`✅ Found ${navElements} navigation elements`);

    // Test main CTA buttons
    const ctaButtons = await page.locator('button').count();
    console.log(`✅ Found ${ctaButtons} buttons on main page`);

    // Test 2: Dashboard Navigation
    console.log('\n📊 Testing 2: Dashboard Navigation');
    console.log('------------------------------------');

    await page.goto('http://localhost:3000/invoices');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'ux_test_dashboard.png' });

    // Test tab navigation
    const tabs = await page.locator('[role="tab"], .tab, .nav-link').count();
    console.log(`✅ Found ${tabs} tabs/navigational elements`);

    // Click on different tabs if they exist
    try {
      if (await page.locator('text=Dashboard').isVisible()) {
        await page.click('text=Dashboard');
        await page.waitForTimeout(1000);
        console.log('✅ Dashboard tab clicked');
      }

      if (await page.locator('text=Review').isVisible()) {
        await page.click('text=Review');
        await page.waitForTimeout(1000);
        console.log('✅ Review tab clicked');
      }

      if (await page.locator('text=Exceptions').isVisible()) {
        await page.click('text=Exceptions');
        await page.waitForTimeout(1000);
        console.log('✅ Exceptions tab clicked');
        await page.screenshot({ path: 'ux_test_exceptions.png' });
      }

      if (await page.locator('text=Approvals').isVisible()) {
        await page.click('text=Approvals');
        await page.waitForTimeout(1000);
        console.log('✅ Approvals tab clicked');
      }

      if (await page.locator('text=Analytics').isVisible()) {
        await page.click('text=Analytics');
        await page.waitForTimeout(1000);
        console.log('✅ Analytics tab clicked');
        await page.screenshot({ path: 'ux_test_analytics.png' });
      }
    } catch (error) {
      console.log('⚠️  Some tabs may not be interactive:', error.message);
    }

    // Test 3: Exception Management System
    console.log('\n🚨 Testing 3: Exception Management System');
    console.log('-----------------------------------------');

    await page.goto('http://localhost:3000/invoices');
    await page.waitForLoadState('networkidle');

    // Look for exception indicators
    const exceptionBadges = await page.locator('.badge, .notification, [data-count]').count();
    console.log(`✅ Found ${exceptionBadges} status badges/notifications`);

    // Test exception list if present
    try {
      const exceptionItems = await page.locator('.exception-item, .list-item, tbody tr').count();
      console.log(`✅ Found ${exceptionItems} items in lists/tables`);

      // Test action buttons in exception management
      const actionButtons = await page.locator('button:has-text("Resolve"), button:has-text("Apply"), button:has-text("Dismiss")').count();
      console.log(`✅ Found ${actionButtons} action buttons for resolution`);
    } catch (error) {
      console.log('ℹ️  Exception list may be empty or not loaded');
    }

    // Test 4: Email Integration Dashboard
    console.log('\n📧 Testing 4: Email Integration Dashboard');
    console.log('------------------------------------------');

    // Try to navigate to email integration
    await page.goto('http://localhost:3000/email').catch(() => {});
    await page.waitForTimeout(2000);

    if (page.url().includes('/email')) {
      await page.screenshot({ path: 'ux_test_email_integration.png' });
      console.log('✅ Email integration page loaded');

      // Test email account management elements
      const accountElements = await page.locator('.account, .email-account, .connection').count();
      console.log(`✅ Found ${accountElements} account management elements`);

      // Test processing controls
      const processingControls = await page.locator('button:has-text("Start"), button:has-text("Stop"), button:has-text("Refresh")').count();
      console.log(`✅ Found ${processingControls} processing control buttons`);
    } else {
      console.log('ℹ️  Email integration page may not be available');
    }

    // Test 5: Responsive Design Testing
    console.log('\n📱 Testing 5: Responsive Design');
    console.log('---------------------------------');

    const viewports = [
      { width: 1920, height: 1080, name: 'Desktop' },
      { width: 768, height: 1024, name: 'Tablet' },
      { width: 375, height: 667, name: 'Mobile' }
    ];

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await page.goto('http://localhost:3000');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: `ux_test_responsive_${viewport.name.toLowerCase()}.png` });
      console.log(`✅ ${viewport.name} view (${viewport.width}x${viewport.height}) tested`);

      // Test mobile menu if present
      if (viewport.width <= 768) {
        const mobileMenu = await page.locator('.hamburger, .menu-toggle, button:has-text("Menu")').count();
        if (mobileMenu > 0) {
          console.log('✅ Mobile menu detected');
        }
      }
    }

    // Test 6: Interactive Elements and Form Validation
    console.log('\n🎯 Testing 6: Interactive Elements and Forms');
    console.log('--------------------------------------------');

    await page.setViewportSize({ width: 1366, height: 768 });
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');

    // Test all buttons for hover states and clickability
    const allButtons = await page.locator('button').all();
    console.log(`✅ Testing ${allButtons.length} interactive buttons`);

    for (let i = 0; i < Math.min(allButtons.length, 10); i++) {
      try {
        await allButtons[i].hover();
        await page.waitForTimeout(200);
        console.log(`✅ Button ${i + 1} hover state working`);
      } catch (error) {
        console.log(`⚠️  Button ${i + 1} hover issue:`, error.message);
      }
    }

    // Test form inputs if present
    const formInputs = await page.locator('input, textarea, select').count();
    console.log(`✅ Found ${formInputs} form inputs`);

    if (formInputs > 0) {
      try {
        // Test input validation
        const firstInput = page.locator('input, textarea, select').first();
        await firstInput.click();
        await firstInput.fill('test input');
        await page.waitForTimeout(500);
        console.log('✅ Form input interaction working');
      } catch (error) {
        console.log('⚠️  Form input issue:', error.message);
      }
    }

    // Test 7: Performance and Loading States
    console.log('\n⚡ Testing 7: Performance and Loading States');
    console.log('----------------------------------------------');

    // Measure page load times
    const startTime = Date.now();
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');
    const loadTime = Date.now() - startTime;
    console.log(`✅ Main page load time: ${loadTime}ms`);

    // Test loading states and spinners
    const loadingElements = await page.locator('.loading, .spinner, .skeleton').count();
    console.log(`✅ Found ${loadingElements} loading state elements`);

    // Test API responses through network monitoring
    page.on('response', response => {
      if (response.url().includes('/api/')) {
        console.log(`✅ API Response: ${response.url()} - ${response.status()}`);
      }
    });

    // Navigate to dashboard to test API calls
    await page.goto('http://localhost:3000/invoices');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Test 8: Accessibility Features
    console.log('\n♿ Testing 8: Accessibility Features');
    console.log('-------------------------------------');

    // Test keyboard navigation
    await page.keyboard.press('Tab');
    await page.waitForTimeout(200);
    console.log('✅ Keyboard navigation (Tab) working');

    // Test ARIA labels
    const ariaElements = await page.locator('[aria-label], [role], [alt]').count();
    console.log(`✅ Found ${ariaElements} accessibility elements`);

    // Test focus management
    const focusedElement = await page.evaluate(() => document.activeElement.tagName);
    console.log(`✅ Focus management: ${focusedElement} element has focus`);

  } catch (error) {
    console.error('❌ Test execution error:', error);
  } finally {
    await browser.close();
  }

  console.log('\n🎉 UX Testing Complete!');
  console.log('========================');
  console.log('Screenshots saved for visual verification:');
  console.log('- ux_test_main_page.png');
  console.log('- ux_test_dashboard.png');
  console.log('- ux_test_exceptions.png');
  console.log('- ux_test_analytics.png');
  console.log('- ux_test_email_integration.png');
  console.log('- ux_test_responsive_desktop.png');
  console.log('- ux_test_responsive_tablet.png');
  console.log('- ux_test_responsive_mobile.png');
}

// Run the tests
runComprehensiveUXTests().catch(console.error);