"""E2E browser (opsional): pip install playwright && playwright install chromium.
Jalankan server dulu (python app.py), lalu: python tests/e2e_playwright.py
Screenshot disimpan di results/e2e_*.png"""
import asyncio, sys, glob
from playwright.async_api import async_playwright

import os
URL = os.environ.get("WM_URL", "http://127.0.0.1:5000/")
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--no-proxy-server"])
        ctx = await b.new_context(viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append("PAGEERR " + str(e)))
        page.on("console", lambda m: errs.append("CONSOLE " + m.text) if m.type == "error" and "fonts" not in m.text and "ERR_" not in m.text else None)
        await page.route("**/fonts.g*/**", lambda r: r.abort())
        await page.goto(URL, wait_until="domcontentloaded")
        await page.wait_for_selector(".hero")
        await page.screenshot(path="results/e2e_1_home.png")

        # Embed
        await page.click("#nav a[data-key=sisip]")
        await page.set_input_files("input[type=file] >> nth=0", glob.glob("dataset/original/astronaut.png")[0])
        await page.click("text=Sisipkan watermark")
        await page.wait_for_selector("text=Perbandingan visual", timeout=20000)
        await page.screenshot(path="results/e2e_2_embed.png", full_page=True)

        # Attack
        await page.click("text=Uji ketahanan")
        await page.wait_for_selector(".stage img")
        await page.check("text=Pemotongan (cropping)")
        await page.click("text=25% di pojok")
        await page.click("text=Terapkan serangan")
        await page.wait_for_selector("text=Hasil serangan", timeout=20000)
        await page.click("text=Uji semua serangan otomatis")
        await page.wait_for_selector(".barrow", timeout=30000)
        await page.screenshot(path="results/e2e_3_attack.png", full_page=True)

        # Extract from history (latest attack item is not embed... select first option)
        await page.click("#nav a[data-key=ekstraksi]")
        await page.click("text=Ekstrak watermark")
        await page.wait_for_selector("text=Evaluasi kinerja", timeout=20000)
        await page.screenshot(path="results/e2e_4_extract.png", full_page=True)

        # History
        await page.click("#nav a[data-key=riwayat]")
        await page.wait_for_selector(".hcard")
        await page.screenshot(path="results/e2e_5_history.png", full_page=True)
        await page.click(".hcard .thumb >> nth=0")
        await page.wait_for_selector("dialog[open]")
        await page.screenshot(path="results/e2e_6_dialog.png")
        await page.keyboard.press("Escape")

        # Home stats + mobile
        await page.click("#nav a[data-key=beranda]")
        await page.wait_for_selector(".stat")
        await page.screenshot(path="results/e2e_7_home_stats.png", full_page=True)
        m = await b.new_context(viewport={"width": 390, "height": 800})
        mp = await m.new_page()
        await mp.route("**/fonts.g*/**", lambda r: r.abort())
        await mp.goto(URL, wait_until="domcontentloaded")
        await mp.wait_for_selector(".hero")
        await mp.screenshot(path="results/e2e_8_mobile.png")
        print("ERRORS:", errs or "none")
        await b.close()
asyncio.run(main())
