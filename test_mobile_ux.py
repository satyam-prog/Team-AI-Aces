"""
Automated Verification Suite for Mobile UX, SEO, & Institutional Compliance (Items 10-19)
Tests:
10. Mobile breakpoints
11. Sticky mobile CTA
12. Loading states
13. Form error states
14. Thank-you page
15. Privacy policy page
16. Terms page
17. Cookie banner
18. Analytics installed & endpoint
19. Real contact address
Plus strict redline checks (no em dashes, no purple gradients, no pill buttons, no emojis, no AI tags).
"""

import unittest
import urllib.request
import urllib.parse
import json
import os
import re

BASE_URL = "http://localhost:8000"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(REPO_DIR, "static")

class TestMobileUXAndCompliance(unittest.TestCase):

    # -------------------------------------------------------------
    # 10. Mobile Breakpoints
    # -------------------------------------------------------------
    def test_10_mobile_breakpoints_css(self):
        css_path = os.path.join(STATIC_DIR, "css", "style.css")
        self.assertTrue(os.path.isfile(css_path), "style.css must exist")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        # Verify key media queries exist
        self.assertIn("@media (max-width: 1024px)", css, "Missing 1024px tablet breakpoint")
        self.assertIn("@media (max-width: 768px)", css, "Missing 768px mobile breakpoint")
        self.assertIn("@media (max-width: 480px)", css, "Missing 480px small mobile breakpoint")

        # Verify responsive patterns
        self.assertIn(".nav-tabs-bar", css, "Missing nav-tabs-bar responsive rule")
        self.assertIn(".kpi-grid", css, "Missing responsive kpi grid handling")
        self.assertIn("overflow-x: auto", css, "Missing horizontal scroll for data tables or tabs on mobile")

    # -------------------------------------------------------------
    # 11. Sticky Mobile CTA
    # -------------------------------------------------------------
    def test_11_sticky_mobile_cta(self):
        html_path = os.path.join(STATIC_DIR, "index.html")
        css_path = os.path.join(STATIC_DIR, "css", "style.css")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn('id="sticky-mobile-cta"', html, "Missing #sticky-mobile-cta in index.html")
        self.assertIn(".sticky-mobile-cta", css, "Missing .sticky-mobile-cta class in style.css")
        self.assertIn("position: fixed", css, "Sticky mobile CTA must use fixed positioning")
        self.assertIn("bottom: 0", css, "Sticky mobile CTA must stick to bottom")
        
        # Verify hidden on desktop, visible on mobile
        self.assertIn("display: none", css, "Sticky mobile CTA should default to hidden on desktop")
        self.assertIn("display: flex", css, "Sticky mobile CTA should display flex on mobile breakpoint")

    # -------------------------------------------------------------
    # 12. Loading States
    # -------------------------------------------------------------
    def test_12_loading_states(self):
        html_path = os.path.join(STATIC_DIR, "index.html")
        css_path = os.path.join(STATIC_DIR, "css", "style.css")
        js_path = os.path.join(STATIC_DIR, "js", "app.js")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn('id="global-loader"', html, "Missing #global-loader progress bar element in index.html")
        self.assertIn("#global-loader", css, "Missing #global-loader CSS rules")
        self.assertIn(".btn.is-loading", css, "Missing .btn.is-loading CSS rules")
        self.assertIn(".btn-spinner", css, "Missing .btn-spinner CSS rules")
        self.assertIn(".skeleton-box", css, "Missing .skeleton-box animation CSS")
        self.assertIn("function showGlobalLoader", js, "Missing showGlobalLoader helper function in app.js")
        self.assertIn("function setBtnLoading", js, "Missing setBtnLoading helper function in app.js")

    # -------------------------------------------------------------
    # 13. Form Error States
    # -------------------------------------------------------------
    def test_13_form_error_states(self):
        css_path = os.path.join(STATIC_DIR, "css", "style.css")
        js_path = os.path.join(STATIC_DIR, "js", "app.js")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn(".form-control.has-error", css, "Missing .form-control.has-error in style.css")
        self.assertIn(".field-error-msg", css, "Missing .field-error-msg in style.css")
        self.assertIn("function setFieldError", js, "Missing setFieldError function in app.js")
        self.assertIn("function clearFieldError", js, "Missing clearFieldError function in app.js")

    # -------------------------------------------------------------
    # 14. Thank-You Page
    # -------------------------------------------------------------
    def test_14_thank_you_page(self):
        req = urllib.request.Request(f"{BASE_URL}/thank-you")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")

        self.assertIn("Institutional Request Confirmed", content)
        self.assertIn("Advisory Protocol &amp; Service Level Agreement", content)
        self.assertIn("Ref #", content)
        self.assertIn("Return to Gateway", content)
        self.assertIn("canonical", content)
        self.assertIn("og:image", content)

    # -------------------------------------------------------------
    # 15. Privacy Policy Page
    # -------------------------------------------------------------
    def test_15_privacy_policy_page(self):
        req = urllib.request.Request(f"{BASE_URL}/privacy")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")

        self.assertIn("FERPA", content)
        self.assertIn("Family Educational Rights and Privacy Act", content)
        self.assertIn("450 Technology Square", content)
        self.assertIn("privacy@edueagle.edu", content)

    # -------------------------------------------------------------
    # 16. Terms of Service Page
    # -------------------------------------------------------------
    def test_16_terms_of_service_page(self):
        req = urllib.request.Request(f"{BASE_URL}/terms")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")

        self.assertIn("Terms and Conditions of Institutional Service", content)
        self.assertIn("Non-Punitive", content)
        self.assertIn("Override", content)
        self.assertIn("450 Technology Square", content)

    # -------------------------------------------------------------
    # 17. Cookie Banner
    # -------------------------------------------------------------
    def test_17_cookie_banner(self):
        html_path = os.path.join(STATIC_DIR, "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('id="cookie-banner"', html, "Missing #cookie-banner element in index.html")
        self.assertIn("acceptCookieConsent('all')", html)
        self.assertIn("acceptCookieConsent('essential')", html)
        self.assertIn("edueagle_cookie_consent", html)

    # -------------------------------------------------------------
    # 18. Analytics Installed & Endpoint
    # -------------------------------------------------------------
    def test_18_analytics_installed_and_endpoint(self):
        pages = ["index.html", "privacy.html", "terms.html", "thank-you.html"]
        for p in pages:
            path = os.path.join(STATIC_DIR, p)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("/js/analytics.js", content, f"analytics.js missing from {p}")

        # Test telemetry POST endpoint without authentication token
        payload = json.dumps({"event": "page_view", "path": "/test-verification"}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/analytics/event",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"), "Telemetry event endpoint must return success=True")

    # -------------------------------------------------------------
    # 19. Real Contact Address
    # -------------------------------------------------------------
    def test_19_real_contact_address(self):
        pages = ["index.html", "privacy.html", "terms.html", "thank-you.html"]
        expected_address = "450 Technology Square"
        expected_phone = "+1 (617) 555-0198"

        for p in pages:
            path = os.path.join(STATIC_DIR, p)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn(expected_address, content, f"Physical address missing from {p}")
            self.assertIn(expected_phone, content, f"Phone helpline missing from {p}")

    # -------------------------------------------------------------
    # Strict Redlines Verification
    # -------------------------------------------------------------
    def test_redline_no_em_dashes(self):
        files_to_check = [
            "index.html", "privacy.html", "terms.html", "thank-you.html", "404.html",
            "css/style.css", "js/app.js", "js/analytics.js"
        ]
        bad_patterns = ["\u2014", "\u2013", "&mdash;", "&ndash;"]
        for rel in files_to_check:
            fp = os.path.join(STATIC_DIR, rel)
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
            for bp in bad_patterns:
                self.assertNotIn(bp, content, f"Found forbidden dash '{bp}' in {rel}")

    def test_redline_no_pill_buttons(self):
        css_path = os.path.join(STATIC_DIR, "css", "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        self.assertNotIn("border-radius: 9999px", css, "Vibe-coded pill buttons (9999px) forbidden")
        self.assertNotIn("border-radius: 50px", css, "Pill border radius (50px) forbidden")

    def test_redline_no_purple_gradients(self):
        css_path = os.path.join(STATIC_DIR, "css", "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read().lower()
        forbidden_purples = ["#8a2be2", "#9333ea", "#a855f7", "#c084fc", "#7e22ce"]
        for p in forbidden_purples:
            self.assertNotIn(p, css, f"Forbidden purple gradient color {p} detected in style.css")

    def test_redline_no_ai_tag(self):
        pages = ["index.html", "privacy.html", "terms.html", "thank-you.html", "404.html"]
        for p in pages:
            path = os.path.join(STATIC_DIR, p)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().lower()
            self.assertNotIn("made with ai", content, f"'made with ai' tag found in {p}")
            self.assertNotIn("built with ai", content, f"'built with ai' tag found in {p}")

if __name__ == "__main__":
    unittest.main()
