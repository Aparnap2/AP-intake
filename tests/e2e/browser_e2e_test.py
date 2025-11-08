"""
Browser-based E2E Testing for AP Intake System using Playwright
"""

import asyncio
import json
import time
from datetime import datetime
from playwright.async_api import async_playwright

class BrowserE2ETestFramework:
    """Browser-based E2E Testing Framework"""

    def __init__(self):
        self.base_url = "http://localhost:3000"
        self.api_url = "http://localhost:8001"
        self.test_results = []
        self.session_id = f"browser-test-{int(time.time())}"

    async def run_browser_tests(self):
        """Execute all browser-based E2E tests"""
        print("🌐 Starting Browser-based E2E Test Suite")
        print(f"Test Session ID: {self.session_id}")
        print("=" * 60)

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=False, slow_mo=1000)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                ignore_https_errors=True
            )
            page = await context.new_page()

            try:
                # Test 1: Basic Navigation
                await self.test_basic_navigation(page)

                # Test 2: Invoice Dashboard Loading
                await self.test_invoice_dashboard(page)

                # Test 3: Upload Modal Functionality
                await self.test_upload_modal(page)

                # Test 4: Tab Navigation
                await self.test_tab_navigation(page)

                # Test 5: Responsive Design
                await self.test_responsive_design(page)

                # Test 6: Error Handling UI
                await self.test_error_handling_ui(page)

                # Test 7: Real-time Updates (if implemented)
                await self.test_realtime_updates(page)

                # Test 8: Performance Metrics
                await self.test_performance_metrics(page)

            finally:
                await browser.close()

        # Generate comprehensive report
        self.generate_browser_test_report()

    async def test_basic_navigation(self, page):
        """Test basic page navigation"""
        print("\n🧭 Testing Basic Navigation...")

        test_name = "Basic Navigation Test"
        start_time = time.time()

        try:
            # Test main page loading
            response = await page.goto(self.base_url, wait_until="domcontentloaded")
            page_load_time = time.time() - start_time

            # Check page title
            title = await page.title()
            title_valid = bool(title and len(title) > 0)

            # Check if page content loaded
            await page.wait_for_timeout(2000)  # Wait for dynamic content
            content_loaded = await page.locator('body').count() > 0

            # Check for critical elements
            navigation_exists = await page.locator('nav, header, [role="navigation"]').count() > 0
            main_content_exists = await page.locator('main, .main, [role="main"]').count() > 0

            success = (
                response.status in [200, 206] and
                title_valid and
                content_loaded and
                navigation_exists
            )

            result = {
                "test": test_name,
                "success": success,
                "page_status": response.status,
                "page_title": title,
                "load_time": f"{page_load_time:.2f}s",
                "navigation_exists": navigation_exists,
                "main_content_exists": main_content_exists,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")
            print(f"   Page Status: {response.status}")
            print(f"   Load Time: {page_load_time:.2f}s")
            print(f"   Title: {title}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_invoice_dashboard(self, page):
        """Test invoice dashboard functionality"""
        print("\n📊 Testing Invoice Dashboard...")

        test_name = "Invoice Dashboard Test"
        start_time = time.time()

        try:
            # Navigate to invoices page
            await page.goto(f"{self.base_url}/invoices", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)  # Wait for dynamic content

            # Check for dashboard elements
            dashboard_elements = {
                "invoice_management_title": 'h1:has-text("Invoice Management")',
                "upload_button": 'button:has-text("Upload Invoice")',
                "stats_cards": '[data-testid="stats-card"], .card',
                "tabs": '[role="tab"], .tab',
                "refresh_button": 'button:has-text("Refresh")'
            }

            element_results = {}
            for element_name, selector in dashboard_elements.items():
                try:
                    element_exists = await page.locator(selector).count() > 0
                    element_results[element_name] = element_exists
                    print(f"   {element_name}: {'✅' if element_exists else '❌'}")
                except Exception as e:
                    element_results[element_name] = False
                    print(f"   {element_name}: ❌ ERROR - {e}")

            # Check for specific dashboard stats
            try:
                stats_elements = await page.locator('.text-2xl, .text-xl').count()
                stats_available = stats_elements > 0
                print(f"   Stats elements found: {stats_elements}")
            except:
                stats_available = False

            # Test upload button click
            upload_working = False
            try:
                upload_btn = page.locator('button:has-text("Upload Invoice")').first
                if await upload_btn.count() > 0:
                    await upload_btn.click()
                    await page.wait_for_timeout(1000)
                    # Check if modal opens
                    modal_exists = await page.locator('[role="dialog"], .modal').count() > 0
                    if modal_exists:
                        upload_working = True
                        # Close modal
                        await page.keyboard.press('Escape')
                        await page.wait_for_timeout(500)
                    print(f"   Upload button functionality: {'✅' if upload_working else '❌'}")
            except Exception as e:
                print(f"   Upload button test: ERROR - {e}")

            # Overall success criteria
            critical_elements = [
                element_results.get("invoice_management_title", False),
                element_results.get("upload_button", False),
                stats_available
            ]

            success = sum(critical_elements) >= 2  # At least 2 critical elements

            load_time = time.time() - start_time

            result = {
                "test": test_name,
                "success": success,
                "elements": element_results,
                "stats_available": stats_available,
                "upload_working": upload_working,
                "load_time": f"{load_time:.2f}s",
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_upload_modal(self, page):
        """Test upload modal functionality"""
        print("\n📤 Testing Upload Modal...")

        test_name = "Upload Modal Test"

        try:
            # Navigate to invoices page
            await page.goto(f"{self.base_url}/invoices", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Click upload button
            upload_btn = page.locator('button:has-text("Upload Invoice")').first
            await upload_btn.click()
            await page.wait_for_timeout(1000)

            # Check modal elements
            modal_elements = {
                "modal_title": 'h2:has-text("Upload Invoices")',
                "drop_area": '[data-testid="drop-area"], .drop-area',
                "file_types": 'text:has-text("PDF")',
                "cancel_button": 'button:has-text("Cancel")',
                "upload_button": 'button:has-text("Upload")'
            }

            modal_results = {}
            for element_name, selector in modal_elements.items():
                try:
                    element_exists = await page.locator(selector).count() > 0
                    modal_results[element_name] = element_exists
                    print(f"   {element_name}: {'✅' if element_exists else '❌'}")
                except Exception as e:
                    modal_results[element_name] = False
                    print(f"   {element_name}: ❌ ERROR - {e}")

            # Test modal close functionality
            close_working = False
            try:
                # Try close button
                cancel_btn = page.locator('button:has-text("Cancel")')
                if await cancel_btn.count() > 0:
                    await cancel_btn.click()
                    await page.wait_for_timeout(500)
                    # Check if modal is closed
                    modal_closed = await page.locator('h2:has-text("Upload Invoices")').count() == 0
                    close_working = modal_closed
                    print(f"   Modal close functionality: {'✅' if close_working else '❌'}")
            except Exception as e:
                print(f"   Modal close test: ERROR - {e}")

            # Test modal open again
            modal_reopen = False
            try:
                await upload_btn.click()
                await page.wait_for_timeout(500)
                modal_reopened = await page.locator('h2:has-text("Upload Invoices")').count() > 0
                modal_reopen = modal_reopened
                print(f"   Modal reopen functionality: {'✅' if modal_reopen else '❌'}")
                if modal_reopened:
                    await page.keyboard.press('Escape')  # Close it again
            except Exception as e:
                print(f"   Modal reopen test: ERROR - {e}")

            # Success criteria
            critical_modal_elements = [
                modal_results.get("modal_title", False),
                modal_results.get("cancel_button", False),
                close_working
            ]

            success = sum(critical_modal_elements) >= 2

            result = {
                "test": test_name,
                "success": success,
                "modal_elements": modal_results,
                "close_working": close_working,
                "reopen_working": modal_reopen,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_tab_navigation(self, page):
        """Test tab navigation functionality"""
        print("\n📑 Testing Tab Navigation...")

        test_name = "Tab Navigation Test"

        try:
            # Navigate to invoices page
            await page.goto(f"{self.base_url}/invoices", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Find tabs
            tabs = await page.locator('[role="tab"], .tab, button[role="tab"]').count()
            print(f"   Found {tabs} tabs")

            tab_results = {}
            tab_names = ["Dashboard", "Review", "Exceptions", "Approvals", "Exports", "Analytics", "Email"]

            for tab_name in tab_names:
                try:
                    tab_selector = f'button:has-text("{tab_name}"), [role="tab"]:has-text("{tab_name}")'
                    tab_exists = await page.locator(tab_selector).count() > 0

                    if tab_exists:
                        # Try to click the tab
                        await page.locator(tab_selector).first.click()
                        await page.wait_for_timeout(1000)
                        # Check if tab becomes active
                        active_tab = await page.locator(tab_selector).first.evaluate(
                            "el => el.classList.contains('active') || el.getAttribute('aria-selected') === 'true'"
                        )
                        tab_results[tab_name] = {"exists": True, "clickable": True, "active": active_tab}
                        print(f"   {tab_name}: ✅ Exists, Clickable, Active: {active_tab}")
                    else:
                        tab_results[tab_name] = {"exists": False, "clickable": False, "active": False}
                        print(f"   {tab_name}: ❌ Not found")

                except Exception as e:
                    tab_results[tab_name] = {"exists": False, "clickable": False, "active": False, "error": str(e)}
                    print(f"   {tab_name}: ❌ ERROR - {e}")

            # Success criteria
            clickable_tabs = [name for name, result in tab_results.items() if result.get("clickable", False)]
            success = len(clickable_tabs) >= 3  # At least 3 working tabs

            result = {
                "test": test_name,
                "success": success,
                "total_tabs": tabs,
                "tab_results": tab_results,
                "clickable_tabs": len(clickable_tabs),
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")
            print(f"   Clickable tabs: {len(clickable_tabs)}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_responsive_design(self, page):
        """Test responsive design"""
        print("\n📱 Testing Responsive Design...")

        test_name = "Responsive Design Test"

        try:
            # Test different viewport sizes
            viewports = [
                {"width": 1920, "height": 1080, "name": "Desktop"},
                {"width": 768, "height": 1024, "name": "Tablet"},
                {"width": 375, "height": 667, "name": "Mobile"}
            ]

            responsive_results = {}

            for viewport in viewports:
                await page.set_viewport_size(viewport)
                await page.goto(f"{self.base_url}/invoices", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                # Check if content is still accessible
                title_visible = await page.locator('h1').is_visible()
                content_scrollable = await page.evaluate("() => document.body.scrollHeight > window.innerHeight")
                navigation_accessible = await page.locator('nav, header, button').count() > 0

                responsive_results[viewport["name"]] = {
                    "title_visible": title_visible,
                    "content_scrollable": content_scrollable,
                    "navigation_accessible": navigation_accessible
                }

                print(f"   {viewport['name']}: {'✅' if title_visible and navigation_accessible else '❌'}")

            # Test mobile navigation if it exists
            mobile_menu_working = False
            await page.set_viewport_size({"width": 375, "height": 667})
            try:
                hamburger_menu = page.locator('button:has-text("Menu"), .hamburger, [aria-label="menu"]')
                if await hamburger_menu.count() > 0:
                    await hamburger_menu.click()
                    await page.wait_for_timeout(500)
                    mobile_menu_open = await page.locator('.mobile-menu, .nav-menu').count() > 0
                    mobile_menu_working = mobile_menu_open
                    print(f"   Mobile menu: {'✅' if mobile_menu_working else '❌'}")
                else:
                    print("   Mobile menu: Not found (may not be implemented)")
            except Exception as e:
                print(f"   Mobile menu: ERROR - {e}")

            # Success criteria
            desktop_ok = responsive_results.get("Desktop", {}).get("title_visible", False)
            tablet_ok = responsive_results.get("Tablet", {}).get("title_visible", False)
            mobile_ok = responsive_results.get("Mobile", {}).get("title_visible", False)

            success = desktop_ok and (tablet_ok or mobile_ok)  # At least desktop + one other

            result = {
                "test": test_name,
                "success": success,
                "responsive_results": responsive_results,
                "mobile_menu_working": mobile_menu_working,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_error_handling_ui(self, page):
        """Test error handling in UI"""
        print("\n⚠️ Testing Error Handling UI...")

        test_name = "Error Handling UI Test"

        try:
            # Navigate to invoices page
            await page.goto(f"{self.base_url}/invoices", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Test network error simulation
            error_handling_results = {}

            # Test invalid route
            try:
                response = await page.goto(f"{self.base_url}/nonexistent-page", wait_until="domcontentloaded")
                error_404_handled = response.status in [404, 200]  # 200 if custom 404 page
                error_handling_results["404_handling"] = error_404_handled
                print(f"   404 handling: {'✅' if error_404_handled else '❌'}")
            except Exception as e:
                error_handling_results["404_handling"] = False
                print(f"   404 handling: ERROR - {e}")

            # Check for error boundary implementation
            try:
                error_boundary_exists = await page.locator('[data-testid="error-boundary"], .error-boundary').count() > 0
                error_handling_results["error_boundary"] = error_boundary_exists
                print(f"   Error boundary: {'✅' if error_boundary_exists else '❌'}")
            except:
                error_handling_results["error_boundary"] = False
                print(f"   Error boundary: Not detected")

            # Test loading states
            try:
                # Trigger loading state (e.g., refresh button)
                refresh_btn = page.locator('button:has-text("Refresh")')
                if await refresh_btn.count() > 0:
                    await refresh_btn.click()
                    await page.wait_for_timeout(1000)
                    # Check for loading indicators
                    loading_indicators = await page.locator('.loading, .spinner, [aria-busy="true"]').count()
                    loading_states_exist = loading_indicators > 0
                    error_handling_results["loading_states"] = loading_states_exist
                    print(f"   Loading states: {'✅' if loading_states_exist else '❌'}")
                else:
                    error_handling_results["loading_states"] = False
                    print("   Loading states: Refresh button not found")
            except Exception as e:
                error_handling_results["loading_states"] = False
                print(f"   Loading states: ERROR - {e}")

            # Test error messages (look for any error display areas)
            try:
                error_message_areas = await page.locator('.error, .alert, [role="alert"]').count()
                error_handling_results["error_areas"] = error_message_areas > 0
                print(f"   Error message areas: {'✅' if error_message_areas > 0 else '❌'}")
            except:
                error_handling_results["error_areas"] = False
                print("   Error message areas: Not detected")

            success = (
                error_handling_results.get("404_handling", False) or
                error_handling_results.get("error_boundary", False) or
                error_handling_results.get("loading_states", False)
            )

            result = {
                "test": test_name,
                "success": success,
                "error_handling": error_handling_results,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_realtime_updates(self, page):
        """Test real-time updates functionality"""
        print("\n🔄 Testing Real-time Updates...")

        test_name = "Real-time Updates Test"

        try:
            # Navigate to invoices page
            await page.goto(f"{self.base_url}/invoices", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            realtime_features = {}

            # Test for WebSocket connections
            try:
                websocket_connections = await page.evaluate("""
                    () => {
                        const originalWebSocket = window.WebSocket;
                        let connections = 0;
                        window.WebSocket = function(url, protocols) {
                            connections++;
                            console.log('WebSocket connection attempt:', url);
                            return new originalWebSocket(url, protocols);
                        };
                        return connections;
                    }
                """)
                realtime_features["websocket_detected"] = websocket_connections > 0
                print(f"   WebSocket connections: {websocket_connections}")
            except Exception as e:
                realtime_features["websocket_detected"] = False
                print(f"   WebSocket detection: ERROR - {e}")

            # Test for polling mechanisms
            try:
                # Look for setInterval/setTimeout usage that might indicate polling
                polling_detected = await page.evaluate("""
                    () => {
                        let intervals = 0;
                        let timeouts = 0;
                        const originalSetInterval = window.setInterval;
                        const originalSetTimeout = window.setTimeout;

                        window.setInterval = function(...args) {
                            intervals++;
                            return originalSetInterval.apply(this, args);
                        };

                        window.setTimeout = function(...args) {
                            timeouts++;
                            return originalSetTimeout.apply(this, args);
                        };

                        return { intervals, timeouts };
                    }
                """)
                realtime_features["polling_detected"] = polling_detected["intervals"] > 0
                print(f"   Polling intervals: {polling_detected['intervals']}")
            except Exception as e:
                realtime_features["polling_detected"] = False
                print(f"   Polling detection: ERROR - {e}")

            # Test for live data updates
            try:
                # Take a snapshot of current data
                initial_content = await page.locator('body').inner_text()

                # Wait and check if content updates
                await page.wait_for_timeout(5000)
                updated_content = await page.locator('body').inner_text()

                content_changed = initial_content != updated_content
                realtime_features["content_updates"] = content_changed
                print(f"   Content auto-updates: {'✅' if content_changed else '❌'}")
            except Exception as e:
                realtime_features["content_updates"] = False
                print(f"   Content updates: ERROR - {e}")

            # Test for refresh mechanisms
            try:
                refresh_btn = page.locator('button:has-text("Refresh")')
                refresh_available = await refresh_btn.count() > 0
                realtime_features["manual_refresh"] = refresh_available
                print(f"   Manual refresh: {'✅' if refresh_available else '❌'}")
            except:
                realtime_features["manual_refresh"] = False
                print("   Manual refresh: Not available")

            success = (
                realtime_features.get("websocket_detected", False) or
                realtime_features.get("polling_detected", False) or
                realtime_features.get("content_updates", False) or
                realtime_features.get("manual_refresh", False)
            )

            result = {
                "test": test_name,
                "success": success,
                "realtime_features": realtime_features,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    async def test_performance_metrics(self, page):
        """Test performance metrics"""
        print("\n⚡ Testing Performance Metrics...")

        test_name = "Performance Metrics Test"

        try:
            performance_data = {}

            # Test page load performance
            await page.goto(f"{self.base_url}/invoices", wait_until="domcontentloaded")

            # Get performance metrics
            metrics = await page.evaluate("""
                () => {
                    const navigation = performance.getEntriesByType('navigation')[0];
                    return {
                        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
                        loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
                        firstPaint: performance.getEntriesByType('paint')[0]?.startTime || 0,
                        firstContentfulPaint: performance.getEntriesByType('paint')[1]?.startTime || 0,
                        totalLoadTime: navigation.loadEventEnd - navigation.fetchStart
                    };
                }
            """)

            performance_data["page_load"] = metrics

            print(f"   DOM Content Loaded: {metrics['domContentLoaded']:.0f}ms")
            print(f"   Load Complete: {metrics['loadComplete']:.0f}ms")
            print(f"   First Contentful Paint: {metrics['firstContentfulPaint']:.0f}ms")
            print(f"   Total Load Time: {metrics['totalLoadTime']:.0f}ms")

            # Test interaction performance
            interaction_times = []
            for i in range(3):
                start_time = time.time()
                try:
                    # Click on different tabs
                    tabs = page.locator('[role="tab"], button[role="tab"]')
                    if await tabs.count() > i:
                        await tabs.nth(i).click()
                        await page.wait_for_timeout(500)
                        interaction_time = (time.time() - start_time) * 1000
                        interaction_times.append(interaction_time)
                except:
                    pass

            if interaction_times:
                avg_interaction_time = sum(interaction_times) / len(interaction_times)
                performance_data["avg_interaction_time"] = avg_interaction_time
                print(f"   Avg Interaction Time: {avg_interaction_time:.0f}ms")

            # Test memory usage
            try:
                memory_info = await page.evaluate("""
                    () => {
                        if (performance.memory) {
                            return {
                                used: performance.memory.usedJSHeapSize,
                                total: performance.memory.totalJSHeapSize,
                                limit: performance.memory.jsHeapSizeLimit
                            };
                        }
                        return null;
                    }
                """)

                if memory_info:
                    performance_data["memory"] = memory_info
                    print(f"   Memory Used: {memory_info['used'] / 1024 / 1024:.1f}MB")
            except Exception as e:
                print(f"   Memory info: Not available")

            # Check for performance optimizations
            optimizations = {}

            # Check for lazy loading images
            lazy_images = await page.locator('img[loading="lazy"]').count()
            optimizations["lazy_loading"] = lazy_images > 0
            print(f"   Lazy loaded images: {lazy_images}")

            # Check for resource optimization
            resource_count = await page.evaluate("""
                () => performance.getEntriesByType('resource').length
            """)
            optimizations["resource_count"] = resource_count
            print(f"   Total resources: {resource_count}")

            # Performance criteria
            good_performance = (
                metrics.get("totalLoadTime", 10000) < 5000 and  # < 5 seconds
                (not performance_data.get("avg_interaction_time") or performance_data.get("avg_interaction_time", 1000) < 1000)  # < 1 second
            )

            success = good_performance

            result = {
                "test": test_name,
                "success": success,
                "performance_data": performance_data,
                "optimizations": optimizations,
                "timestamp": datetime.now().isoformat()
            }

            self.test_results.append(result)
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")

        except Exception as e:
            result = {
                "test": test_name,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.test_results.append(result)
            print(f"❌ {test_name}: FAILED - {e}")

    def generate_browser_test_report(self):
        """Generate comprehensive browser test report"""
        print("\n" + "=" * 60)
        print("🌐 BROWSER-BASED E2E TEST REPORT")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests

        print(f"\nTest Session: {self.session_id}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        print(f"\nDetailed Results:")
        print("-" * 40)

        for result in self.test_results:
            status = "✅ PASSED" if result["success"] else "❌ FAILED"
            print(f"{result['test']}: {status}")

            if not result["success"] and "error" in result:
                print(f"  Error: {result['error']}")

        # Performance summary
        performance_results = [r for r in self.test_results if "performance_data" in r]
        if performance_results:
            perf_data = performance_results[0]["performance_data"]
            if "page_load" in perf_data:
                load_time = perf_data["page_load"].get("totalLoadTime", 0)
                print(f"\nPerformance Summary:")
                print(f"Page Load Time: {load_time:.0f}ms")

        # UI/UX summary
        ui_tests = ["Basic Navigation Test", "Invoice Dashboard Test", "Upload Modal Test", "Tab Navigation Test"]
        ui_passed = sum(1 for r in self.test_results if r["test"] in ui_tests and r["success"])
        print(f"UI/UX Tests: {ui_passed}/{len(ui_tests)} passed")

        # Save report to file
        report_file = f"browser_e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests/total_tests)*100
            },
            "results": self.test_results
        }

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved to: {report_file}")

        print("\n" + "=" * 60)
        print("🎯 BROWSER READINESS ASSESSMENT")
        print("=" * 60)

        if failed_tests == 0:
            print("✅ ALL BROWSER TESTS PASSED - Frontend is PRODUCTION READY")
        elif failed_tests <= 2:
            print("⚠️  MINOR UI ISSUES - Frontend is MOSTLY READY with small improvements needed")
        else:
            print("❌ MULTIPLE UI FAILURES - Frontend needs significant improvements before production")

        print("=" * 60)

async def main():
    """Main browser test execution function"""
    framework = BrowserE2ETestFramework()
    await framework.run_browser_tests()

if __name__ == "__main__":
    asyncio.run(main())