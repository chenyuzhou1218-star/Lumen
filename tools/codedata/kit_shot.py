"""Pictures of a page with the browser already on this computer (Edge or Chrome), so that nothing has to be downloaded."""
from __future__ import annotations

from pathlib import Path


def shots(html_path: Path, pictures: list) -> dict:
    """pictures: (file, width, height). Returns {'errors': [...]} or raises RuntimeError in words."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError('看不了图：这个 Python 里没有 playwright') from e
    errors: list = []
    with sync_playwright() as pw:
        browser = None
        for channel in ('msedge', 'chrome', None):
            try:
                browser = pw.chromium.launch(channel=channel, headless=True) if channel else pw.chromium.launch(headless=True)
                break
            except Exception:  # noqa: BLE001 (that browser is not here: try the next one)
                continue
        if browser is None:
            raise RuntimeError('看不了图：没有找到 Edge 或 Chrome')
        try:
            for path, width, height in pictures:
                page = browser.new_page(viewport={'width': width, 'height': height})
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
                page.goto(Path(html_path).resolve().as_uri())
                page.wait_for_timeout(300)
                overflow = page.evaluate('document.documentElement.scrollWidth > window.innerWidth + 1')
                if overflow:
                    errors.append(f'宽度 {width} 时页面左右超出屏幕')
                page.screenshot(path=str(path), full_page=True)
                page.close()
        finally:
            browser.close()
    return {'errors': list(dict.fromkeys(errors))[:20]}
