import requests
import subprocess
import paramiko
import time
import os
import json
import sys
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime
from dotenv import load_dotenv
from colorama import Fore, Style
import pytz
from playwright.sync_api import sync_playwright

if getattr(sys, 'frozen', False):  # 檢查是否是打包的 .exe
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(base_path, "config.env")
json_path = os.path.join(base_path, "posts.json")
mail_content_path = os.path.join(base_path, "content.txt")
load_dotenv(env_path)
tz = pytz.timezone('Asia/Taipei')

class PTTScraper:
    def __init__(self):
        self.base_url = "https://www.ptt.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.session = requests.Session()
        self.results = []

    def get_page_content(self, url):
        response = self.session.get(url, headers=self.headers)
        response.encoding = 'utf-8'
        return BeautifulSoup(response.text, 'html.parser')

    def search_posts(self, keywords, max_pages=1):
        if isinstance(keywords, str):
            keywords = [keywords]
        current_url = "/bbs/drama-ticket/index.html"
        
        for _ in range(max_pages):
            soup = self.get_page_content(f"{self.base_url}{current_url}")
            
            # Find all posts
            posts = soup.find_all('div', class_='r-ent')
            
            for post in posts:
                title_element = post.find('div', class_='title').find('a')
                if not title_element:
                    continue
                title = title_element.text.strip()
                if not title.startswith('[售票]'):
                    continue
                if any(keyword in title for keyword in ["綁", "合售"]):
                    continue
                if any(keyword in title for keyword in keywords):
                    author = post.find('div', class_='author').text.strip()
                    link = title_element['href']
                    self.results.append({
                        'author': author,
                        'title': title,
                        'link': link,
                        'send': ""
                    })
            
            # Find link to previous page
            prev_link = soup.find('a', string='‹ 上頁')
            if not prev_link:
                break
            current_url = prev_link['href']

    def save_to_json(self, posts=[]):
        taiwan_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        if self.results:
            existing_links = [post['link'] for post in posts]
            new_results = []
            for result in self.results:
                if not result['link'] in existing_links:
                    new_results.append(result)
            if new_results:
                print(f"{Fore.GREEN}[{taiwan_time}] 找到符合的貼文: {len(new_results)}則{Style.RESET_ALL}")
                posts.extend(new_results)
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(posts, f, ensure_ascii=False, indent=4)
            else:
                print(f"{Fore.MAGENTA}[{taiwan_time}] 沒有找到符合的貼文{Style.RESET_ALL}")
        else:
            print(f"{Fore.MAGENTA}[{taiwan_time}] 沒有找到符合的貼文{Style.RESET_ALL}")
    
    def send_message(self, posts=[], chrome_path="", username="", password="", mail_content=""):
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=chrome_path, headless=True)  # headless=False 可見界面，True 則隱藏
            page = browser.new_page()
            page.goto("https://term.ptt.cc/")  # 輸入目標網站 URL
            
            page.wait_for_timeout(200)

            try:
                page.wait_for_selector('text=請輸入代號', timeout=2000)
                # # 輸入文字
                page.keyboard.type(username, delay=20)
                page.keyboard.press('Enter')  # 按下 Enter 鍵進行提交
                page.keyboard.type(password, delay=20)
                page.keyboard.press('Enter')  # 按下 Enter 鍵進行提交
                print("Login")
            except Exception as e:
                print("Login")

            try:
                page.wait_for_selector('text=重複登入', timeout=2000)
                page.keyboard.press('Y')
                page.keyboard.press('Enter')
                print("Login success")
            except Exception as e:
                print("Login success")
            
            try:
                page.wait_for_selector('text=任意鍵', timeout=2000)
                page.keyboard.press('Enter')
                page.wait_for_selector('text=任意鍵', timeout=2000)
                page.keyboard.press('Enter')  # 按下 Enter 鍵進行提交
                print("-")
            except Exception as e:
                print("-")

            try:
                page.wait_for_selector('text=私人信件區', timeout=2000)
                page.keyboard.press('M')
                page.keyboard.press('Enter')
                print("-")
            except Exception as e:
                print("-")
            
            for post in posts:
                if post['send'] == "v":
                    continue
                page.wait_for_selector('text=站內寄信')
                page.keyboard.press('S')
                page.keyboard.press('Enter')
                page.wait_for_selector('text=使用者代號')
                page.keyboard.type(post['author'])
                page.keyboard.press('Enter')
                page.keyboard.type("Re: " + post['title'])
                page.keyboard.press('Enter')
                page.keyboard.type(mail_content)
                page.keyboard.press('Enter')
                page.keyboard.press('Control+X')
                page.wait_for_selector('text=要儲存檔案')
                page.keyboard.press('S')
                page.keyboard.press('Enter')
                page.keyboard.press('N')
                page.keyboard.press('Enter')

                page.wait_for_selector('text=任意鍵')
                page.keyboard.press('Enter')
                post['send'] = "v"
                print(f"{Fore.GREEN}Sent message to {post['author']}: {post['title']} {Style.RESET_ALL}")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(posts, f, ensure_ascii=False, indent=4)
            page.wait_for_timeout(1000)
            browser.close()
        
def main():
    posts = []
    mail_content = ""
    with open(json_path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    with open(mail_content_path, 'r', encoding='utf-8') as f:
        mail_content = f.read()

    chrome_path = os.getenv("CHROME_PATH", "__");
    keywords_str = os.getenv("KEYWORDS", "__");
    username = os.getenv("PTT_USERNAME", "__");
    password = os.getenv("PTT_PASSWORD", "__");
    interval = os.getenv("INTERVAL", "15");
    keywords = keywords_str.split(",")

    print(f"{Fore.YELLOW} Chrome Page: {Fore.CYAN}{chrome_path}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW} Username: {Fore.CYAN}{username}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW} Starting search for posts by keywords: {Fore.CYAN}{keywords}{Style.RESET_ALL}")
    while True:
        scraper = PTTScraper()
        scraper.search_posts(keywords)
        scraper.save_to_json(posts)

        unsend_posts = [post for post in posts if post['send'] == ""]
        if (len(unsend_posts) > 0):
            scraper.send_message(posts, chrome_path, username, password, mail_content)
        time.sleep(int(interval))
    # Uncomment and add your PTT credentials to send messages

if __name__ == "__main__":
    main()
