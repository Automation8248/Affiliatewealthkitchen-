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
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

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

def clean_text(text):
    """Removes stars and hashtags strictly"""
    return text.replace('*', '').replace('#', '').strip()

def process_with_openrouter(raw_title, raw_desc):
    """OpenRouter API call logic"""
    if not OPENROUTER_API_KEY:
        return None, None, "No API Key"

    prompt = f"""
    Product Title: {raw_title}
    Features: {raw_desc}

    Task:
    1. Create a short, catchy title (max 8 words).
    2. Write an engaging hook followed by a short product description.
    3. The description length MUST be exactly around 300-400 characters, maximum 400.
    4. STRICT RULE: DO NOT use any hashtags or asterisks anywhere.
    
    Output strictly in JSON format with two keys: "title" and "description".
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "google/gemini-2.5-flash", # Aap yahan OpenRouter ka koi bhi model daal sakte hain
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=20)
        res.raise_for_status()
        
        ai_text = res.json()['choices'][0]['message']['content'].strip()
        
        # Parse JSON safely
        if ai_text.startswith("```"):
            ai_text = ai_text.strip("`").replace("json", "", 1).strip()
            
        result = json.loads(ai_text)
        
        # Clean tags and symbols
        title = clean_text(result.get("title", ""))
        desc = clean_text(result.get("description", ""))
        
        # Strict 400 character limit enforcement
        if len(desc) > 400:
            desc = desc[:397] + "..."
            
        return title, desc, None
        
    except Exception as e:
        return None, None, str(e)

def process_and_post():
    if not os.path.exists(LINKS_FILE): 
        print(f"Error: {LINKS_FILE} nahi mila.")
        return
        
    with open(LINKS_FILE, "r") as f:
        all_links = [l.strip() for l in f.readlines() if l.strip()]
    
    history = load_history()
    now = datetime.now()
    
    available = [l for l in all_links if l not in history or (now - datetime.fromisoformat(history[l])) >= timedelta(days=COOLDOWN_DAYS)]
    
    if not available:
        print(f"Sabhi links {COOLDOWN_DAYS} din ke cooldown par hain.")
        return

    affiliate_link = random.choice(available)
    print(f"Processing: {affiliate_link}")

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "[https://www.google.com/](https://www.google.com/)"
    }

    try:
        res = requests.get(affiliate_link, headers=headers, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(res.content, "html.parser")
        
        # Scrape default elements
        title_node = soup.find("span", {"id": "productTitle"})
        if not title_node: 
            print("❌ Amazon block (Captcha). Code safely skipping.")
            return
            
        raw_title = title_node.get_text(strip=True)
        img_node = soup.find("img", {"id": "landingImage"})
        img_url = img_node['src'] if img_node else ""
        
        bullets = soup.find("div", {"id": "feature-bullets"})
        raw_desc = " ".join([li.get_text(strip=True) for li in bullets.find_all("li")]) if bullets else "High quality kitchen product."

        # Attempt AI Generation
        final_title, final_desc, ai_error = process_with_openrouter(raw_title, raw_desc)
        
        alert_message = ""
        
        # Fallback Logic if AI fails or limit is reached
        if ai_error:
            print(f"⚠️ OpenRouter failed ({ai_error}). Using default system.")
            final_title = clean_text(raw_title[:100])
            
            clean_raw_desc = clean_text(raw_desc)
            if len(clean_raw_desc) > 400:
                final_desc = clean_raw_desc[:397] + "..."
            else:
                final_desc = clean_raw_desc
                
            alert_message = "\n\n<i>⚠️ Alert: OpenRouter limit reached or error occurred. Using default system.</i>"

        # 1. Telegram Post (Using HTML to avoid markdown asterisk conflicts)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            t_url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_BOT_TOKEN}/sendPhoto"
            caption = f"🔥 <b>{final_title}</b>\n\n{final_desc}\n\n🛒 <b>Buy Here:</b> {affiliate_link}{alert_message}"
            
            t_res = requests.post(t_url, data={"chat_id": TELEGRAM_CHAT_ID, "photo": img_url, "caption": caption, "parse_mode": "HTML"})
            if t_res.status_code == 200: 
                print("✅ Telegram Post Success")
            else:
                print(f"❌ Telegram Error: {t_res.text}")

        # 2. Webhook Post
        if WEBHOOK_URL:
            w_res = requests.post(WEBHOOK_URL, json={
                "title": final_title, 
                "image_url": img_url, 
                "link": affiliate_link, 
                "desc": final_desc
            })
            if w_res.status_code == 200: 
                print("✅ Webhook Post Success")

        # Update History
        history[affiliate_link] = now.isoformat()
        save_history(history)
        print("✅ Data successfully sent and history updated!")

    except Exception as e:
        print(f"Error occurred during scraping/posting: {e}")

if __name__ == "__main__":
    process_and_post()
