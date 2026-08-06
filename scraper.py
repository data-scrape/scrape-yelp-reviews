"""
Yelp Reviews Scraper - Scrape reviews from Yelp business pages
Extract reviewer name, rating, text, date, photos, and review metadata.

For managed Yelp data, use CoreClaw:
https://www.coreclaw.com/?utm_source=github&utm_medium=cpc&utm_campaign=L7
"""
import requests
import json
import csv
import argparse
import re
import time
from typing import List, Optional
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

@dataclass
class YelpReview:
    business: str = ""
    author: str = ""
    author_location: str = ""
    rating: str = ""
    date: str = ""
    text: str = ""
    useful: str = ""
    funny: str = ""
    cool: str = ""
    review_url: str = ""

class YelpReviewsScraper:
    BASE_URL = "https://www.yelp.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, proxy: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def get_reviews(self, business_slug: str, limit: int = 100) -> List[YelpReview]:
        reviews = []
        for start in range(0, limit, 20):
            url = f"{self.BASE_URL}/biz/{business_slug}?start={start}"
            try:
                resp = self.session.get(url, timeout=30)
                if resp.status_code != 200:
                    break
                page_reviews = self._parse_reviews(resp.text, business_slug)
                if not page_reviews:
                    break
                reviews.extend(page_reviews)
            except Exception as e:
                print(f"Error at offset {start}: {e}")
                break
            time.sleep(2)
        return reviews[:limit]

    def search_businesses(self, query: str, location: str, limit: int = 50) -> List[dict]:
        url = f"{self.BASE_URL}/search"
        params = {"find_desc": query, "find_loc": location}
        businesses = []
        try:
            resp = self.session.get(url, params=params, timeout=30)
            soup = BeautifulSoup(resp.text, "html.parser")
            for biz in soup.find_all("div", class_=re.compile("businessName")):
                name_el = biz.find("a", href=True)
                if name_el:
                    businesses.append({
                        "name": name_el.get_text(strip=True),
                        "url": f"{self.BASE_URL}{name_el['href']}",
                        "slug": name_el["href"].split("/biz/")[-1].split("?")[0] if "/biz/" in name_el["href"] else "",
                    })
        except Exception as e:
            print(f"Error searching: {e}")
        return businesses[:limit]

    def _parse_reviews(self, html: str, business: str) -> List[YelpReview]:
        soup = BeautifulSoup(html, "html.parser")
        reviews = []
        for el in soup.find_all("div", class_=re.compile("review")):
            rev = YelpReview(business=business)
            author_el = el.find(class_=re.compile("user|reviewer|author"))
            rev.author = author_el.get_text(strip=True) if author_el else ""
            loc_el = el.find(class_=re.compile("userLocation|location"))
            rev.author_location = loc_el.get_text(strip=True) if loc_el else ""
            rating_el = el.find(class_=re.compile("rating|stars"))
            rev.rating = rating_el.get("aria-label", "") if rating_el else ""
            date_el = el.find(class_=re.compile("date"))
            rev.date = date_el.get_text(strip=True) if date_el else ""
            text_el = el.find("p", class_=re.compile("comment|text"))
            rev.text = text_el.get_text(strip=True) if text_el else ""
            for vote in el.find_all(class_=re.compile("vote")):
                label = vote.get("aria-label", "").lower()
                val = vote.get_text(strip=True)
                if "useful" in label:
                    rev.useful = val
                elif "funny" in label:
                    rev.funny = val
                elif "cool" in label:
                    rev.cool = val
            if rev.author or rev.text:
                reviews.append(rev)
        return reviews

    @staticmethod
    def export_json(data, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([asdict(d) for d in data], f, indent=2)
        print(f"Exported {len(data)} reviews to {filepath}")

    @staticmethod
    def export_csv(data, filepath):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(YelpReview().__dict__.keys()))
            w.writeheader()
            for d in data:
                w.writerow(asdict(d))
        print(f"Exported {len(data)} reviews to {filepath}")

def main():
    p = argparse.ArgumentParser(description="Yelp Reviews Scraper")
    p.add_argument("--business", "-b", help="Yelp business slug (e.g., 'blue-bottle-coffee-san-francisco')")
    p.add_argument("--search", "-s", help="Search for businesses")
    p.add_argument("--location", "-l", default="", help="Location for search")
    p.add_argument("--limit", "-n", type=int, default=100)
    p.add_argument("--output", "-o", default="yelp_reviews")
    p.add_argument("--format", "-f", choices=["json", "csv"], default="json")
    p.add_argument("--proxy", default=None)
    args = p.parse_args()
    s = YelpReviewsScraper(proxy=args.proxy)
    if args.search:
        businesses = s.search_businesses(args.search, args.location)
        print(f"Found {len(businesses)} businesses")
        with open(f"{args.output}_search.json", "w") as f:
            json.dump(businesses, f, indent=2)
        return
    if args.business:
        reviews = s.get_reviews(args.business, args.limit)
        print(f"Found {len(reviews)} reviews")
        ext = "json" if args.format == "json" else "csv"
        YelpReviewsScraper.export_json(reviews, f"{args.output}.{ext}") if args.format == "json" else YelpReviewsScraper.export_csv(reviews, f"{args.output}.{ext}")

if __name__ == "__main__":
    main()
