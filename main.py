import os
import random
import time
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# --- SECRETS & CONFIGURATION ---
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") 
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

COOLDOWN_DAYS = 7 
HISTORY_FILE = "history.json"
LINKS_FILE = "links.txt"
TITLES_FILE = "titles.txt"
TAGS_FILE = "tags.txt"
TEMP_IMAGE_FILE = "temp_image.jpg"

# --- AAPKI PROXY DETAILS ---
# Format: http://username:password@ip:port
MY_PROXY = "http://oxulhyvs:ukzzq3m862fa@31.59.20.176:6754/"

# --- 50+ RANDOM USER AGENTS ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

# --- CATBOX UPLOAD (10 TRIES) ---
def upload_to_catbox(file_path, retries=10):
    url = "https://catbox.moe/user/api.php"
    for i in range(retries):
        try:
            with open(file_path, 'rb') as f:
                data = {'reqtype': 'fileupload'}
                files = {'fileToUpload': f}
                response = requests.post(url, data=data, files=files, timeout=30)
                if response.status_code == 200 and "catbox.moe" in response.text:
                    return response.text.strip()
        except: pass
        time.sleep(2)
    return None

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f: json.dump(history, f, indent=4)

def get_available_link():
    if not os.path.exists(LINKS_FILE): return None
    with open(LINKS_FILE, "r") as f:
        all_links = [l.strip() for l in f.readlines() if l.strip()]
    history = load_history()
    now = datetime.now()
    available = [l for l in all_links if l not in history or (now - datetime.fromisoformat(history[l]) >= timedelta(days=COOLDOWN_DAYS))]
    return (random.choice(available), history) if available else None

def get_random_title():
    with open(TITLES_FILE, "r", encoding="utf-8") as f:
        titles = [l.strip() for l in f.readlines() if l.strip()]
    return random.choice(titles) if titles else "Awesome Find! 🔥"

def get_random_tags():
    with open(TAGS_FILE, "r", encoding="utf-8") as f:
        tags = [l.strip().replace("#", "") for l in f.readlines() if l.strip()]
    return " ".join([f"#{t}" for t in random.sample(tags, min(9, len(tags)))]) if tags else ""

def process_and_post():
    result = get_available_link()
    if not result: return
    link, history = result
    
    image_url = ""
    description = ""
    
    with sync_playwright() as p:
        # Aapki Proxy yahan use ho rahi hai
        browser = p.chromium.launch(headless=True, proxy={"server": MY_PROXY})
        context = browser.new_context(user_agent=random.choice(USER_AGENTS))
        page = context.new_page()
        
        try:
            page.goto(link, timeout=60000)
            
            # 1. CONTINUE SHOPPING BYPASS (HUMAN CLICK)
            continue_btn = page.locator("text=/Continue shopping/i")
            if continue_btn.count() > 0:
                continue_btn.first.hover()
                time.sleep(2)
                continue_btn.first.click(delay=random.randint(200, 500))
                time.sleep(6)
            
            # 2. HUMAN WAIT & SCROLL
            time.sleep(random.uniform(5, 7))
            page.mouse.wheel(0, 800)
            time.sleep(3)
            page.mouse.wheel(0, -400)
            
            # 3. EXTRACT
            page.wait_for_selector("#landingImage", timeout=15000)
            image_url = page.locator("#landingImage").get_attribute("src")
            description = " ".join(page.locator("#feature-bullets li").all_inner_texts())

        except Exception as e:
            print(f"Browser Error: {e}")
            browser.close()
            return
        browser.close()

    # DOWNLOAD & POST
    image_downloaded = False
    if image_url:
        img_res = requests.get(image_url)
        if img_res.status_code == 200:
            with open(TEMP_IMAGE_FILE, 'wb') as f: f.write(img_res.content)
            image_downloaded = True

    # CATBOX & FILES
    catbox_link = upload_to_catbox(TEMP_IMAGE_FILE) if image_downloaded else image_url
    final_title = get_random_title()
    final_tags = get_random_tags()

    # POSTING
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto", 
                      data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"**{final_title}**\n\n{link}", "parse_mode": "Markdown"},
                      files={"photo": open(TEMP_IMAGE_FILE, 'rb')} if image_downloaded else None)

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={
            "title": final_title, "description": description[:290]+"...", 
            "affiliate_link": link, "tags": final_tags, "image_url": catbox_link
        })

    history[link] = datetime.now().isoformat()
    save_history(history)
    if os.path.exists(TEMP_IMAGE_FILE): os.remove(TEMP_IMAGE_FILE)

if __name__ == "__main__":
    process_and_post()
