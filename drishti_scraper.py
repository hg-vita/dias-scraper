import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import gspread
from oauth2client.service_account import ServiceAccountCredentials

BASE_URL = "https://www.drishtiias.com"

def get_full_article_text(article_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(article_url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        content_div = soup.find("div", class_="ckeditor-content")
        if not content_div:
            return "", []

        result = []
        for element in content_div.children:
            if element.name == "h3":
                result.append(f"\n### {element.get_text(strip=True)}\n")
            elif element.name == "p":
                result.append(element.get_text(strip=True))
            elif element.name == "ul":
                for li in element.find_all("li"):
                    result.append(f"- {li.get_text(strip=True)}")
            elif element.name == "ol":
                for i, li in enumerate(element.find_all("li"), 1):
                    result.append(f"{i}. {li.get_text(strip=True)}")

        tags = []
        for ul in soup.find_all("ul"):
            if "Tags:" in ul.get_text():
                tags = [a.get_text(strip=True) for a in ul.find_all("a")]
                break

        return "\n".join(result), tags

    except Exception as e:
        print(f"[Error scraping article] {article_url} => {e}")
        return "", []

def scrape_drishti_news(date):
    url = f"{BASE_URL}/current-affairs-news-analysis-editorials/news-analysis/{date}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"[Error fetching page for {date}] => {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    articles = []

    for index, h1 in enumerate(soup.find_all("h1"), start=1):
        a_tag = h1.find("a")
        if a_tag and a_tag.get("href"):
            title = a_tag.get_text(strip=True)
            href = a_tag["href"]
            article_url = href if href.startswith("http") else BASE_URL + href

            article_id = f"article_{date}_{index}"
            full_text, tags = get_full_article_text(article_url)

            articles.append({
                "id": article_id,
                "title": title,
                "url": article_url,
                "date": date,
                "full_text": full_text,
                "tags": tags
            })

    return articles

def append_to_google_sheet(articles, spreadsheet_name, worksheet_name, keyfile_dict):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(spreadsheet_name).worksheet(worksheet_name)

    rows = [
        [
            a["id"],
            a["title"],
            a["date"],
            a["url"],
            a["full_text"][:3000],  # Google Sheets cell limit
            ", ".join(a["tags"])
        ]
        for a in articles
    ]

    if rows:
        sheet.append_rows(rows, value_input_option="RAW")
        print(f"[✔] Appended {len(rows)} rows to Google Sheet.")
    else:
        print("[⚠] No new rows to append.")

def main():
    # T-1 date in IST
    yesterday_ist = (datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(days=1)).strftime("%d-%m-%Y")
    print(f"Scraping Drishti IAS for {yesterday_ist}...")

    articles = scrape_drishti_news(yesterday_ist)
    if not articles:
        print("[ℹ] No articles found.")
        return

    keyfile_dict = json.loads(os.environ["GCP_SERVICE_ACCOUNT"])
    append_to_google_sheet(
        articles,
        spreadsheet_name="drishti_articles_combined",
        worksheet_name="drishti_articles_combined",
        keyfile_dict=keyfile_dict
    )

if __name__ == "__main__":
    main()
