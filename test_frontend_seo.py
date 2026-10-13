"""
EduEagle Verification Suite: 9 Frontend, SEO, Metadata & Accessibility Requirements
Tests:
1. Custom 404 page
2. CTA above the fold
3. Meta title per page
4. Meta description per page
5. Open Graph image
6. Favicon set
7. robots.txt
8. sitemap.xml
9. Alt text on every image
"""

import urllib.request
import urllib.error
import json
import re
import sys
import os

BASE_URL = "http://127.0.0.1:8000"

passed = 0
failed = 0

def test(name, condition, details=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {name}")
    else:
        failed += 1
        print(f"FAIL: {name} - {details}")

def get_url(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read(), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, e.read(), {k.lower(): v for k, v in e.headers.items()}

print("\n" + "=" * 65)
print("RUNNING 9-POINT FRONTEND, SEO & METADATA VERIFICATION SUITE")
print("=" * 65)

# -------------------------------------------------------------
# 1. CUSTOM 404 PAGE
# -------------------------------------------------------------
print("\n--- 1. Custom 404 Page ---")
status_rnd, body_rnd, hdrs_rnd = get_url("/non-existent-student-record-404")
body_rnd_str = body_rnd.decode("utf-8", errors="ignore")
test("Non-existent URL returns HTTP 404 status", status_rnd == 404, f"status={status_rnd}")
test("Non-existent URL serves custom HTML 404 page", "Academic Record Not Found" in body_rnd_str and "error-card" in body_rnd_str)
test("404 page provides link back to Institutional Gateway", 'href="/"' in body_rnd_str)

status_direct, body_direct, _ = get_url("/404")
test("Direct /404 path returns HTTP 404 status and custom content", status_direct == 404 and "Academic Record Not Found" in body_direct.decode("utf-8", errors="ignore"))

# -------------------------------------------------------------
# 2. CTA ABOVE THE FOLD
# -------------------------------------------------------------
print("\n--- 2. CTA Above the Fold ---")
status_idx, body_idx, _ = get_url("/")
idx_html = body_idx.decode("utf-8", errors="ignore")
test("Landing hero features primary CTA button above the fold", "Access Institutional Portal" in idx_html and "hero-cta-banner" in idx_html)
test("Landing hero features secondary live console CTA above the fold", "Launch Live Advisory Console" in idx_html)
test("Sign-in form interactive CTAs visible above the fold", "Request Verification Code" in idx_html and "persona-chip-grid" in idx_html)

# -------------------------------------------------------------
# 3. META TITLE PER PAGE
# -------------------------------------------------------------
print("\n--- 3. Meta Title Per Page ---")
test("Index page has descriptive title", "<title>EduEagle | Institutional Student Success &amp; Early Warning System</title>" in idx_html or "<title>EduEagle | Institutional Student Success & Early Warning System</title>" in idx_html)

_, body_priv, _ = get_url("/privacy")
priv_html = body_priv.decode("utf-8", errors="ignore")
test("Privacy policy has unique meta title", "<title>Institutional Privacy Policy &amp; FERPA Compliance | EduEagle</title>" in priv_html or "<title>Institutional Privacy Policy & FERPA Compliance | EduEagle</title>" in priv_html)

_, body_terms, _ = get_url("/terms")
terms_html = body_terms.decode("utf-8", errors="ignore")
test("Terms of Service has unique meta title", "<title>Terms and Conditions of Institutional Service | EduEagle</title>" in terms_html)

test("404 page has unique meta title", "<title>404 Resource Not Found | EduEagle</title>" in body_rnd_str)

# Verify JavaScript VIEW_METADATA catalog exists for SPA view transitions
with open("static/js/app.js", "r", encoding="utf-8") as f:
    app_js = f.read()
test("SPA app.js contains VIEW_METADATA catalog for dynamic titles", "VIEW_METADATA" in app_js and "updatePageMetadata" in app_js)

# -------------------------------------------------------------
# 4. META DESCRIPTION PER PAGE
# -------------------------------------------------------------
print("\n--- 4. Meta Description Per Page ---")
idx_desc_match = re.search(r'<meta\s+name=["\']description["\']\s+id=["\']page-meta-description["\']\s+content=["\'](.*?)["\']', idx_html)
test("Index page has custom meta description", idx_desc_match is not None and len(idx_desc_match.group(1)) > 30)

priv_desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', priv_html)
test("Privacy page has dedicated meta description", priv_desc_match is not None and "FERPA" in priv_desc_match.group(1))

terms_desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', terms_html)
test("Terms of Service has dedicated meta description", terms_desc_match is not None and "non-punitive" in terms_desc_match.group(1).lower())

error_desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', body_rnd_str)
test("404 page has dedicated meta description", error_desc_match is not None and len(error_desc_match.group(1)) > 20)

# -------------------------------------------------------------
# 5. OPEN GRAPH IMAGE & TAGS
# -------------------------------------------------------------
print("\n--- 5. Open Graph Image & Tags ---")
test("Open Graph og:image meta tag present in index.html", '<meta property="og:image" content="https://edueagle.edu/images/og-image.png">' in idx_html)
test("Open Graph width and height specified (1200x630)", '<meta property="og:image:width" content="1200">' in idx_html and '<meta property="og:image:height" content="630">' in idx_html)
test("Twitter Card summary_large_image tag present", '<meta name="twitter:card" content="summary_large_image">' in idx_html)

status_og, body_og, hdrs_og = get_url("/images/og-image.png")
test("Open Graph PNG image accessible with HTTP 200", status_og == 200 and hdrs_og.get("content-type") == "image/png")
test("Open Graph PNG has valid PNG header and significant binary size", body_og.startswith(b"\x89PNG\r\n\x1a\n") and len(body_og) > 5000, f"size={len(body_og)}")

status_og_svg, body_og_svg, hdrs_og_svg = get_url("/images/og-image.svg")
test("Open Graph vector SVG image accessible with HTTP 200", status_og_svg == 200 and "svg" in hdrs_og_svg.get("content-type", ""))

# -------------------------------------------------------------
# 6. FAVICON SET
# -------------------------------------------------------------
print("\n--- 6. Complete Favicon Set ---")
status_ico, body_ico, hdrs_ico = get_url("/favicon.ico")
test("favicon.ico returns HTTP 200 with image/x-icon", status_ico == 200 and hdrs_ico.get("content-type") == "image/x-icon")

status_svg, body_svg, hdrs_svg = get_url("/favicon.svg")
test("favicon.svg returns HTTP 200 with image/svg+xml", status_svg == 200 and "svg" in hdrs_svg.get("content-type", ""))

status_16, body_16, hdrs_16 = get_url("/favicon-16x16.png")
test("favicon-16x16.png returns HTTP 200 with image/png", status_16 == 200 and hdrs_16.get("content-type") == "image/png")

status_32, body_32, hdrs_32 = get_url("/favicon-32x32.png")
test("favicon-32x32.png returns HTTP 200 with image/png", status_32 == 200 and hdrs_32.get("content-type") == "image/png")

status_apple, body_apple, hdrs_apple = get_url("/apple-touch-icon.png")
test("apple-touch-icon.png (180x180) returns HTTP 200 with image/png", status_apple == 200 and hdrs_apple.get("content-type") == "image/png")

status_man, body_man, hdrs_man = get_url("/site.webmanifest")
test("site.webmanifest returns HTTP 200 with manifest mime type", status_man == 200 and "manifest" in hdrs_man.get("content-type", ""))
manifest_json = json.loads(body_man.decode("utf-8"))
test("site.webmanifest includes all configured icon resolutions", len(manifest_json.get("icons", [])) >= 4)

# -------------------------------------------------------------
# 7. ROBOTS.TXT
# -------------------------------------------------------------
print("\n--- 7. robots.txt ---")
status_rob, body_rob, hdrs_rob = get_url("/robots.txt")
rob_text = body_rob.decode("utf-8", errors="ignore")
test("robots.txt returns HTTP 200 with text/plain", status_rob == 200 and "text/plain" in hdrs_rob.get("content-type", ""))
test("robots.txt contains User-agent directive", "User-agent: *" in rob_text)
test("robots.txt allows root and public legal pages", "Allow: /" in rob_text and "Allow: /privacy" in rob_text)
test("robots.txt disallows private APIs and storage", "Disallow: /api/" in rob_text and "Disallow: /private_storage/" in rob_text)
test("robots.txt links to XML sitemap", "Sitemap: https://edueagle.edu/sitemap.xml" in rob_text)

# -------------------------------------------------------------
# 8. SITEMAP.XML
# -------------------------------------------------------------
print("\n--- 8. sitemap.xml ---")
status_map, body_map, hdrs_map = get_url("/sitemap.xml")
map_text = body_map.decode("utf-8", errors="ignore")
test("sitemap.xml returns HTTP 200 with application/xml", status_map == 200 and "xml" in hdrs_map.get("content-type", ""))
test("sitemap.xml contains urlset xmlns specification", 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' in map_text)
test("sitemap.xml includes index page URL with high priority", "<loc>https://edueagle.edu/</loc>" in map_text and "<priority>1.0</priority>" in map_text)
test("sitemap.xml includes privacy and terms legal URLs", "<loc>https://edueagle.edu/privacy</loc>" in map_text and "<loc>https://edueagle.edu/terms</loc>" in map_text)

# -------------------------------------------------------------
# 9. ALT TEXT ON EVERY IMAGE
# -------------------------------------------------------------
print("\n--- 9. Alt Text on Every Image ---")
all_html_files = [
    "static/index.html",
    "static/404.html",
    "static/privacy.html",
    "static/terms.html"
]

all_img_tags = []
missing_alt_imgs = []

for hf in all_html_files:
    with open(hf, "r", encoding="utf-8") as f:
        content = f.read()
    imgs = re.findall(r'<img[^>]*>', content)
    for img in imgs:
        all_img_tags.append((hf, img))
        alt_match = re.search(r'alt=["\']([^"\']+)["\']', img)
        if not alt_match or not alt_match.group(1).strip():
            missing_alt_imgs.append((hf, img))

test("Image tags detected across institutional HTML pages", len(all_img_tags) > 0, f"found={len(all_img_tags)}")
test("Every image tag has non-empty, descriptive alt attribute (0 missing)", len(missing_alt_imgs) == 0, f"violations={missing_alt_imgs}")

print("\n" + "=" * 65)
print(f"SUITE COMPLETE: {passed} PASSED, {failed} FAILED")
print("=" * 65)

if failed > 0:
    sys.exit(1)
sys.exit(0)

