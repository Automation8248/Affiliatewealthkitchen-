import os
import random
import requests
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION FROM GITHUB SECRETS ---
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") 
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

COOLDOWN_DAYS = 5
HISTORY_FILE = "history.json"
LINKS_FILE = "links.txt"

# --- 100+ USER AGENTS TO PREVENT AMAZON CAPTCHA BLOCKING ---
base_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.90 Mobile Safari/537.36",
]
# Dynamically generate 95 more agents for safety
generated_agents = [f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(100, 122)}.0.{random.randint(1000, 9999)}.0 Safari/537.36" for _ in range(95)]
USER_AGENTS = base_agents + generated_agents

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
            except: return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def process_and_post():
    if not os.path.exists(LINKS_FILE): 
        print(f"Error: {LINKS_FILE} nahi mila.")
        return
        
    with open(LINKS_FILE, "r") as f:
        all_links = [l.strip() for l in f.readlines() if l.strip()]
    
    history = load_history()
    now = datetime.now()
    
    # Check 5 days cooldown
    available = [l for l in all_links if l not in history or (now - datetime.fromisoformat(history[l])) >= timedelta(days=COOLDOWN_DAYS)]
    
    if not available:
        print(f"Sabhi links {COOLDOWN_DAYS} din ke cooldown par hain.")
        return

    affiliate_link = random.choice(available)
    print(f"Processing: {affiliate_link}")

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }

    try:
        res = requests.get(affiliate_link, headers=headers, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Scrape Title
        title_node = soup.find("span", {"id": "productTitle"})
        if not title_node: 
            print("❌ Amazon block (Captcha). Code safely skipping.")
            return
        
        # Keep title up to 150 chars max to keep it clean
        title = title_node.get_text(strip=True)[:150] 

        # Scrape Image
        img_node = soup.find("img", {"id": "landingImage"})
        img_url = img_node['src'] if img_node else ""
        
        # Scrape Description and strictly limit to 700 chars
        bullets = soup.find("div", {"id": "feature-bullets"})
        description = " ".join([li.get_text(strip=True) for li in bullets.find_all("li")]) if bullets else "Best quality product."
        
        if len(description) > 700:
            description = description[:697] + "..."

        # 1. Telegram Post
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            t_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            caption = f"🔥 **{title}**\n\n✨ {description}\n\n🛒 **Buy Here:** {affiliate_link}"
            t_res = requests.post(t_url, data={"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": caption, "parse_mode": "Markdown"})
            if t_res.status_code == 200: 
                print("✅ Telegram Post Success")
            else:
                print(f"❌ Telegram Error: {t_res.text}")

        # 2. Webhook Post
        if WEBHOOK_URL:
            w_res = requests.post(WEBHOOK_URL, json={
                "title": title, 
                "image_url": img_url, 
                "link": affiliate_link, 
                "desc": description
            })
            if w_res.status_code == 200: 
                print("✅ Webhook Post Success")
            else:
                print(f"❌ Webhook Error: {w_res.status_code}")

        # Update History
        history[affiliate_link] = now.isoformat()
        save_history(history)
        print("✅ Data successfully sent and history updated!")

    except Exception as e:
        print(f"Error occurred during scraping/posting: {e}")

if __name__ == "__main__":
    process_and_post()
