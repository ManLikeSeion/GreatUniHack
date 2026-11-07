"""Optional browser smoke test: pip install playwright; python this_file.py.
Uses installed Edge, or Playwright Chromium (playwright install chromium).
All API traffic uses an isolated temporary SQLite database, with no AI calls.
"""
import functools
import os
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'warwick-events')]
from BACKEND.workflow import create_workflow


def main():
    frontend = Path(__file__).resolve().parents[1]
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    handler = functools.partial(QuietHandler, directory=str(frontend))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as directory, sync_playwright() as playwright:
            app = FastAPI()
            app.include_router(create_workflow(Path(directory) / 'test.sqlite3'), prefix='/api')
            with TestClient(app) as api:
                edge = Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe'
                browser = playwright.chromium.launch(headless=True, **({'executable_path': str(edge)} if edge.exists() else {}))
                page = browser.new_page(viewport={'width': 390, 'height': 844})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                def intercept(route):
                    request = route.request
                    path = urlsplit(request.url).path
                    if path == '/api/updates':
                        route.abort()
                        return
                    response = api.request(request.method, path, headers=request.headers,
                                           content=request.post_data or None)
                    route.fulfill(status=response.status_code, content_type='application/json', body=response.content)
                page.route('**/api/**', intercept)
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.locator('[data-role="student"]').click()
                page.locator('#email').fill('onboarding-smoke@example.com')
                page.locator('#login-form button[type=submit]').click()
                expect(page.locator('#ob-heading')).to_have_text('About you')
                page.locator('#ob-next').click()
                expect(page.locator('#ob-error')).to_contain_text('Choose your course')
                page.locator('#ob-course-search').fill('Computer Science')
                page.locator('#ob-course').select_option(label='Computer Science BSc')
                options = page.locator('#ob-year option').all_text_contents()
                page.locator('#ob-year').select_option(label=options[2])
                page.locator('#ob-next').click()
                expect(page.locator('#ob-heading')).to_have_text('Your interests')
                page.get_by_role('button', name='Programming', exact=True).click()
                page.locator('#ob-back').click()
                expect(page.locator('#ob-course')).to_have_value('computer-science-bsc')
                page.locator('#ob-next').click()
                expect(page.get_by_role('button', name='Programming', exact=True)).to_have_attribute('aria-pressed', 'true')
                page.locator('#ob-next').click()
                expect(page.locator('#ob-heading')).to_have_text('Your societies')
                page.reload()
                expect(page.locator('#ob-heading')).to_have_text('Your societies')
                card = page.locator('#ob-content .society-grid').first.locator('article').filter(has=page.get_by_role('heading', name='Computing', exact=True))
                card.get_by_role('button', name='Follow society', exact=True).click()
                page.locator('#ob-next').click()
                expect(page.locator('#ob-heading')).to_have_text('Ready to explore')
                expect(page.locator('#ob-content')).to_contain_text('Following 1 societies')
                page.locator('#ob-next').click()
                expect(page.locator('#app-view')).to_be_visible()
                expect(page.locator('#onboarding-view')).to_be_hidden()
                page.reload()
                expect(page.locator('#app-view')).to_be_visible()
                expect(page.locator('#onboarding-view')).to_be_hidden()
                page.locator('[data-tab=settings]').click()
                page.locator('#edit-student-profile').click()
                expect(page.locator('#ob-heading')).to_have_text('About you')
                if errors:
                    raise AssertionError(errors)
                browser.close()
                print('PASS: first login, validation, Back, interest selection, refresh/resume, follow, completion, returning student, settings edit; no browser errors')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
