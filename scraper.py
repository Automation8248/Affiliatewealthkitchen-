import os
import random
import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION (NO AI API REQUIRED) ---
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") 
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

COOLDOWN_DAYS = 5
HISTORY_FILE = "history.json"
LINKS_FILE = "links.txt"

# --- 100+ USER AGENTS TO PREVENT BLOCKING ---
base_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.90 Mobile Safari/537.36"
]
generated_agents = [f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(100, 122)}.0.{random.randint(1000, 9999)}.0 Safari/537.36" for _ in range(95)]
USER_AGENTS = base_agents + generated_agents

def clean_text(text):
    """Stars (*) aur Hashtags (#) ko strictly remove karta hai"""
    if not text: return ""
    return re.sub(r'[*#]', '', text).strip()

def smart_truncate_title(raw_title):
    """Smart Logic: Amazon title ko comma (,) ya dash (-) se pehle cut karke clean title banata hai"""
    clean_title = re.split(r'[,|\-\(]', raw_title)[0].strip()
    return clean_text(clean_title[:80])

def smart_truncate_desc(raw_desc, max_len=200):
    """Smart Logic: Description ko exactly 200 characters tak limit karta hai, bina kisi word ko tode"""
    if len(raw_desc) <= max_len:
        return clean_text(raw_desc)
    truncated = raw_desc[:max_len]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return clean_text(truncated) + "..."

def process_and_post():
    if not os.path.exists(LINKS_FILE): return
    with open(LINKS_FILE, "r") as f:
        all_links = [l.strip() for l in f.readlines() if l.strip()]
    
    history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f: history = json.load(f)
        except: history = {}

    now = datetime.now()
    available = [l for l in all_links if l not in history or (now - datetime.fromisoformat(history[l])) >= timedelta(days=COOLDOWN_DAYS)]
    
    if not available: 
        print(f"Sabhi links {COOLDOWN_DAYS} din ke cooldown par hain.")
        return
        
    affiliate_link = random.choice(available)
    print(f"Processing Link: {affiliate_link}")

    try:
        # 1. Scrape Amazon Data
        res = requests.get(affiliate_link, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        
        title_node = soup.find("span", {"id": "productTitle"})
        if not title_node: 
            print("❌ Amazon ne block kiya (Captcha). Skipping...")
            return
        
        raw_title = title_node.get_text(strip=True)
        img_url = soup.find("img", {"id": "landingImage"})['src']
        bullets = soup.find("div", {"id": "feature-bullets"})
        raw_desc = " ".join([li.get_text(strip=True) for li in bullets.find_all("li")]) if bullets else "Great quality kitchen and home find on Amazon."
        
        # Scrape Category
        category_node = soup.select_one('#wayfinding-breadcrumbs_container ul li:first-child a')
        category = category_node.get_text(strip=True) if category_node else "General"

        # 2. Smart Formatting (No AI API used)
        f_title = smart_truncate_title(raw_title)
        f_desc = smart_truncate_desc(raw_desc, 200)

        # 3. Telegram Post (Strictly Image, Title, Link Only)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            clean_token = str(TELEGRAM_BOT_TOKEN).split(']')[-1].strip().replace('[', '').replace(']', '')
            t_url = f"https://api.telegram.org/bot{clean_token}/sendPhoto"
            
            # Sirf Title aur Link, Description hata diya gaya hai
            caption = f"🔥 <b>{f_title}</b>\n\n🛒 <b>Product Link:</b> {affiliate_link}"
            requests.post(t_url, data={"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": caption, "parse_mode": "HTML"})
            print("✅ Telegram par bhej diya gaya.")

        # 4. Webhook Post (Includes Category and max 200 char Description)
        if WEBHOOK_URL:
            requests.post(WEBHOOK_URL, json={
                "title": f_title, 
                "image": img_url, 
                "link": affiliate_link, 
                "desc": f_desc,
                "category": category
            })
            print("✅ Webhook par bhej diya gaya.")

        # Save History
        history[affiliate_link] = now.isoformat()
        with open(HISTORY_FILE, "w") as f: json.dump(history, f, indent=4)
        print("✅ Automation Successful!")

    except Exception as e:
        print(f"System Error: {e}")

if __name__ == "__main__":
    process_and_post()
