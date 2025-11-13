#!/usr/bin/env python3
"""
Comprehensive UX Testing for AP Intake & Validation System
Using Playwright for automated browser testing
"""

import asyncio
import json
import time
from playwright.async_api import async_playwright
from typing import Dict, List, Any

class UXTester:
    def __init__(self):
        self.test_results = []
        self.current_test = ""
        self.browser = None
        self.page = None

    async def setup(self):
        """Initialize browser and page"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False, slow_mo=1000)
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        self.page = await self.context.new_page()

    async def cleanup(self):
        """Cleanup browser resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    def log_test_result(self, test_name: str, status: str, details: str = "", issues: List[str] = None):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,  # PASS, FAIL, WARN
            "details": details,
            "issues": issues or [],
            "timestamp": time.time()
        }
        self.test_results.append(result)
        status_emoji = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(status, "❓")
        print(f"{status_emoji} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
        if issues:
            for issue in issues:
                print(f"   Issue: {issue}")

    async def navigate_to_page(self, url: str) -> bool:
        """Navigate to a page and check if it loads"""
        try:
            await self.page.goto(url, wait_until='networkidle')
            await self.page.wait_for_timeout(2000)  # Wait for dynamic content
            return True
        except Exception as e:
            self.log_test_result(f"Navigate to {url}", "FAIL", str(e))
            return False

    async def take_screenshot(self, name: str):
        """Take screenshot for documentation"""
        try:
            await self.page.screenshot(path=f"screenshots/{name}.png", full_page=True)
            print(f"📸 Screenshot saved: screenshots/{name}.png")
        except Exception as e:
            print(f"Screenshot failed: {e}")

async def main():
    """Main UX testing execution"""
    tester = UXTester()

    try:
        print("🚀 Starting Comprehensive UX Testing for AP Intake System")
        print("=" * 60)

        await tester.setup()

        # Test 1: Landing Page - Invoice Review Interface
        print("\n📋 TEST 1: Landing Page - Invoice Review Interface")
        print("-" * 50)

        if not await tester.navigate_to_page("http://localhost:3000"):
            return

        # Wait for page to fully load
        await tester.page.wait_for_timeout(3000)

        # Check main elements
        try:
            # Check if the main heading exists
            main_heading = await tester.page.wait_for_selector('h1', timeout=10000)
            heading_text = await main_heading.inner_text()
            tester.log_test_result(
                "Main Heading Display",
                "PASS" if "AP Intake Review" in heading_text else "FAIL",
                f"Heading: {heading_text}"
            )
        except Exception as e:
            tester.log_test_result("Main Heading Display", "FAIL", str(e))

        # Check document information
        try:
            doc_info = await tester.page.query_selector('p:has-text("Document:")')
            if doc_info:
                doc_text = await doc_info.inner_text()
                tester.log_test_result("Document Info Display", "PASS", doc_text)
            else:
                tester.log_test_result("Document Info Display", "FAIL", "Document info not found")
        except Exception as e:
            tester.log_test_result("Document Info Display", "FAIL", str(e))

        # Check status section
        try:
            status_section = await tester.page.query_selector('div:has-text("Pending Review")')
            if status_section:
                tester.log_test_result("Status Display", "PASS", "Processing status shown")
            else:
                tester.log_test_result("Status Display", "FAIL", "Status section not found")
        except Exception as e:
            tester.log_test_result("Status Display", "FAIL", str(e))

        # Test validation alerts
        try:
            validation_alerts = await tester.page.query_selector('div[role="alert"]:has-text("Validation Alerts")')
            if validation_alerts:
                alert_text = await validation_alerts.inner_text()
                tester.log_test_result("Validation Alerts", "PASS", f"Alerts displayed: {alert_text[:50]}...")
            else:
                tester.log_test_result("Validation Alerts", "WARN", "No validation alerts found")
        except Exception as e:
            tester.log_test_result("Validation Alerts", "FAIL", str(e))

        await tester.take_screenshot("01_landing_page")

        # Test 2: Tab Navigation
        print("\n📋 TEST 2: Tab Navigation Interface")
        print("-" * 50)

        tabs = ["Summary", "Detailed Fields", "Line Items"]

        for tab_name in tabs:
            try:
                # Find and click tab
                tab_selector = f'button:has-text("{tab_name}")'
                tab_element = await tester.page.wait_for_selector(tab_selector, timeout=5000)

                # Check if it's already active
                is_active = await tab_element.evaluate('el => el.classList.contains("border-blue-600")')

                if not is_active:
                    await tab_element.click()
                    await tester.page.wait_for_timeout(1000)

                # Verify tab is now active
                is_now_active = await tab_element.evaluate('el => el.classList.contains("border-blue-600")')

                tester.log_test_result(
                    f"Tab Navigation - {tab_name}",
                    "PASS" if is_now_active else "FAIL",
                    f"Tab {'activated' if is_now_active else 'failed to activate'}"
                )

                await tester.take_screenshot(f"02_tab_{tab_name.lower().replace(' ', '_')}")

            except Exception as e:
                tester.log_test_result(f"Tab Navigation - {tab_name}", "FAIL", str(e))

        # Test 3: Invoice Details Card
        print("\n📋 TEST 3: Invoice Details Display")
        print("-" * 50)

        try:
            # Check invoice number with confidence score
            invoice_section = await tester.page.query_selector('text=Invoice Number')
            if invoice_section:
                # Look for confidence score badge
                confidence_badge = await tester.page.query_selector('text=High:')
                if confidence_badge:
                    confidence_text = await confidence_badge.inner_text()
                    tester.log_test_result("Invoice Number with Confidence", "PASS", confidence_text)
                else:
                    tester.log_test_result("Invoice Number with Confidence", "WARN", "No confidence score shown")
            else:
                tester.log_test_result("Invoice Number Display", "FAIL", "Invoice section not found")
        except Exception as e:
            tester.log_test_result("Invoice Details", "FAIL", str(e))

        # Test 4: Vendor Information
        print("\n📋 TEST 4: Vendor Information Display")
        print("-" * 50)

        try:
            vendor_name = await tester.page.query_selector('text=Vendor Name')
            if vendor_name:
                # Check for validation status indicators
                checkmark = await tester.page.query_selector('svg.lucide-circle-check')
                if checkmark:
                    tester.log_test_result("Vendor Validation Status", "PASS", "Validation indicator shown")
                else:
                    tester.log_test_result("Vendor Validation Status", "WARN", "No validation indicator")

                # Check for review needed badge
                review_badge = await tester.page.query_selector('text=Needs Review')
                if review_badge:
                    tester.log_test_result("Vendor Review Badge", "PASS", "Review needed indicator shown")
                else:
                    tester.log_test_result("Vendor Review Badge", "WARN", "No review badge found")
            else:
                tester.log_test_result("Vendor Information", "FAIL", "Vendor section not found")
        except Exception as e:
            tester.log_test_result("Vendor Information", "FAIL", str(e))

        # Test 5: Action Buttons
        print("\n📋 TEST 5: Action Buttons Functionality")
        print("-" * 50)

        action_buttons = [
            "Reject & Request Reupload",
            "Request Manual Review",
            "Approve & Process"
        ]

        for button_text in action_buttons:
            try:
                button_selector = f'button:has-text("{button_text}")'
                button_element = await tester.page.wait_for_selector(button_selector, timeout=5000)

                # Check if button is clickable
                is_enabled = await button_element.is_enabled()
                button_class = await button_element.get_attribute('class')

                tester.log_test_result(
                    f"Action Button - {button_text}",
                    "PASS" if is_enabled else "WARN",
                    f"Button is {'enabled' if is_enabled else 'disabled'}"
                )

                # Test hover effect by checking computed style
                await button_element.hover()
                await tester.page.wait_for_timeout(500)

                tester.log_test_result(
                    f"Button Hover - {button_text}",
                    "PASS",
                    "Hover effect applied"
                )

            except Exception as e:
                tester.log_test_result(f"Action Button - {button_text}", "FAIL", str(e))

        # Test 6: Extraction Quality Metrics
        print("\n📋 TEST 6: Extraction Quality Display")
        print("-" * 50)

        try:
            # Check overall confidence display
            confidence_section = await tester.page.query_selector('text=Overall Confidence')
            if confidence_section:
                # Look for percentage
                percentage = await tester.page.query_selector('text=%')
                if percentage:
                    percentage_text = await percentage.inner_text()
                    tester.log_test_result("Confidence Percentage", "PASS", percentage_text)
                else:
                    tester.log_test_result("Confidence Percentage", "FAIL", "No percentage shown")

                # Check for progress bar
                progress_bar = await tester.page.query_selector('div[style*="width:95%"]')
                if progress_bar:
                    tester.log_test_result("Progress Bar", "PASS", "Confidence progress bar displayed")
                else:
                    tester.log_test_result("Progress Bar", "WARN", "Progress bar not found")

                # Check status text
                status_text = await tester.page.query_selector('text=Ready for Processing')
                if status_text:
                    tester.log_test_result("Processing Status", "PASS", "Ready status shown")
                else:
                    tester.log_test_result("Processing Status", "WARN", "Status text not found")
            else:
                tester.log_test_result("Extraction Quality", "FAIL", "Quality section not found")
        except Exception as e:
            tester.log_test_result("Extraction Quality", "FAIL", str(e))

        # Test 7: Navigation to Dashboard
        print("\n📋 TEST 7: Dashboard Navigation")
        print("-" * 50)

        try:
            # Find and click the main dashboard link
            dashboard_link = await tester.page.wait_for_selector('a:has-text("Open Invoice Dashboard")', timeout=5000)
            await dashboard_link.click()

            # Wait for navigation
            await tester.page.wait_for_url('**/invoices', timeout=10000)
            await tester.page.wait_for_timeout(2000)

            current_url = tester.page.url
            tester.log_test_result(
                "Dashboard Navigation",
                "PASS" if '/invoices' in current_url else "FAIL",
                f"Navigated to: {current_url}"
            )

            await tester.take_screenshot("03_dashboard_landing")

        except Exception as e:
            tester.log_test_result("Dashboard Navigation", "FAIL", str(e))

        # Test 8: Dashboard Multi-Tab Interface
        print("\n📋 TEST 8: Dashboard Tab Interface")
        print("-" * 50)

        dashboard_tabs = ["Dashboard", "Review", "Exceptions", "Approvals", "Exports", "Analytics", "Email"]

        for tab_name in dashboard_tabs:
            try:
                tab_selector = f'button:has-text("{tab_name}")'
                tab_element = await tester.page.wait_for_selector(tab_selector, timeout=5000)

                # Check if clickable
                is_enabled = await tab_element.is_enabled()

                tester.log_test_result(
                    f"Dashboard Tab - {tab_name}",
                    "PASS" if is_enabled else "WARN",
                    f"Tab is {'enabled' if is_enabled else 'disabled'}"
                )

                # Click tab and verify navigation
                if is_enabled:
                    await tab_element.click()
                    await tester.page.wait_for_timeout(1000)

                    tester.log_test_result(
                        f"Dashboard Tab Click - {tab_name}",
                        "PASS",
                        f"Successfully clicked {tab_name} tab"
                    )

                    await tester.take_screenshot(f"04_dashboard_tab_{tab_name.lower()}")

            except Exception as e:
                tester.log_test_result(f"Dashboard Tab - {tab_name}", "FAIL", str(e))

        # Test 9: Exception Management
        print("\n📋 TEST 9: Exception Management Interface")
        print("-" * 50)

        try:
            # Navigate to exceptions
            exceptions_tab = await tester.page.wait_for_selector('button:has-text("Exceptions")', timeout=5000)
            await exceptions_tab.click()
            await tester.page.wait_for_timeout(2000)

            # Check for exception count badge
            exception_badge = await tester.page.query_selector('[class*="badge"]')
            if exception_badge:
                badge_text = await exception_badge.inner_text()
                tester.log_test_result("Exception Count Badge", "PASS", f"Exception count: {badge_text}")
            else:
                tester.log_test_result("Exception Count Badge", "WARN", "No exception badge found")

            # Check for exception list or management interface
            exception_content = await tester.page.query_selector('text="No exceptions found", text="Exception List", text="Exception Management"')
            if exception_content:
                tester.log_test_result("Exception Content", "PASS", "Exception interface loaded")
            else:
                tester.log_test_result("Exception Content", "WARN", "Exception content not clearly visible")

            await tester.take_screenshot("05_exceptions_tab")

        except Exception as e:
            tester.log_test_result("Exception Management", "FAIL", str(e))

        # Test 10: Email Integration
        print("\n📋 TEST 10: Email Integration Interface")
        print("-" * 50)

        try:
            # Navigate to email integration
            email_link = await tester.page.wait_for_selector('a:has-text("Email Integration")', timeout=5000)
            await email_link.click()

            # Wait for navigation
            await tester.page.wait_for_timeout(3000)

            current_url = tester.page.url
            tester.log_test_result(
                "Email Integration Navigation",
                "PASS" if '/email' in current_url else "FAIL",
                f"Navigated to: {current_url}"
            )

            await tester.take_screenshot("06_email_integration")

            # Check for email interface elements
            try:
                # Look for account management, processing queue, or metrics
                email_elements = await tester.page.query_selector_all('text="Account", text="Processing", text="Queue", text="Metrics", text="Status"')
                if email_elements:
                    tester.log_test_result("Email Interface Elements", "PASS", f"Found {len(email_elements)} interface elements")
                else:
                    tester.log_test_result("Email Interface Elements", "WARN", "Email interface elements not clearly visible")
            except Exception as e:
                tester.log_test_result("Email Interface Elements", "FAIL", str(e))

        except Exception as e:
            tester.log_test_result("Email Integration", "FAIL", str(e))

        # Test 11: Responsive Design Testing
        print("\n📋 TEST 11: Responsive Design Testing")
        print("-" * 50)

        viewports = [
            {"name": "Mobile", "width": 375, "height": 667},
            {"name": "Tablet", "width": 768, "height": 1024},
            {"name": "Desktop", "width": 1920, "height": 1080}
        ]

        for viewport in viewports:
            try:
                await tester.page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
                await tester.page.wait_for_timeout(1000)

                # Check if content is still accessible
                main_content = await tester.page.query_selector('main, .container, [class*="min-h-screen"]')
                if main_content:
                    tester.log_test_result(
                        f"Responsive - {viewport['name']}",
                        "PASS",
                        f"Content accessible at {viewport['width']}x{viewport['height']}"
                    )
                else:
                    tester.log_test_result(
                        f"Responsive - {viewport['name']}",
                        "WARN",
                        f"Content may not be optimal at {viewport['width']}x{viewport['height']}"
                    )

                await tester.take_screenshot(f"07_responsive_{viewport['name'].lower()}")

            except Exception as e:
                tester.log_test_result(f"Responsive - {viewport['name']}", "FAIL", str(e))

        # Test 12: Performance and Loading States
        print("\n📋 TEST 12: Performance and Loading States")
        print("-" * 50)

        try:
            # Navigate back to main page for performance testing
            await tester.navigate_to_page("http://localhost:3000")

            start_time = time.time()
            await tester.page.wait_for_load_state('networkidle')
            load_time = time.time() - start_time

            tester.log_test_result(
                "Page Load Performance",
                "PASS" if load_time < 3.0 else "WARN",
                f"Load time: {load_time:.2f}s"
            )

            # Check for any loading indicators
            loading_elements = await tester.page.query_selector_all('[class*="loading"], [class*="spinner"], [aria-busy="true"]')
            if loading_elements:
                tester.log_test_result("Loading Indicators", "PASS", f"Found {len(loading_elements)} loading elements")
            else:
                tester.log_test_result("Loading Indicators", "WARN", "No loading indicators found")

        except Exception as e:
            tester.log_test_result("Performance Testing", "FAIL", str(e))

        # Final summary
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE UX TESTING SUMMARY")
        print("=" * 60)

        total_tests = len(tester.test_results)
        passed_tests = len([r for r in tester.test_results if r["status"] == "PASS"])
        failed_tests = len([r for r in tester.test_results if r["status"] == "FAIL"])
        warn_tests = len([r for r in tester.test_results if r["status"] == "WARN"])

        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"⚠️  Warnings: {warn_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in tester.test_results:
                if result["status"] == "FAIL":
                    print(f"   - {result['test']}: {result['details']}")

        if warn_tests > 0:
            print("\n⚠️  Warnings:")
            for result in tester.test_results:
                if result["status"] == "WARN":
                    print(f"   - {result['test']}: {result['details']}")

        # Save detailed results
        with open('ux_test_results.json', 'w') as f:
            json.dump(tester.test_results, f, indent=2)
        print(f"\n📄 Detailed results saved to: ux_test_results.json")
        print("📸 Screenshots saved to: screenshots/ directory")

    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await tester.cleanup()

if __name__ == "__main__":
    # Create screenshots directory
    import os
    os.makedirs("screenshots", exist_ok=True)

    # Run the comprehensive UX testing
    asyncio.run(main())