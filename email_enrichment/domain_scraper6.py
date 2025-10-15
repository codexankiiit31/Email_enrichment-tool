import re
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

class DomainScraper:
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.timeout = 5
        self.sector_keywords = {
            "Technology": ["software", "technology", "ai", "ml", "cloud", "saas", "fintech", "edtech", "devops", "digital", "app", "platform"],
            "Finance": ["bank", "finance", "investment", "trading", "crypto", "insurance"],
            "Healthcare": ["health", "medical", "hospital", "pharma", "healthcare", "clinic"],
            "Retail": ["retail", "ecommerce", "shop", "store", "commerce"],
            "Manufacturing": ["manufacturing", "factory", "production", "industrial"],
            "Consulting": ["consulting", "consultant", "advisory", "services"],
            "Education": ["education", "school", "university", "training", "learning"],
            "Media": ["media", "publishing", "news", "content", "entertainment"],
            "Energy": ["energy", "oil", "gas", "renewable", "power"],
            "Real Estate": ["real estate", "property", "realty", "construction"]
        }

    def normalize_url(self, domain: str) -> str:
        parsed = urlparse(domain if domain.startswith("http") else f"https://{domain}")
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc or parsed.path
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return f"{scheme}://{netloc}".rstrip("/")

    def is_university_domain(self, domain: str) -> bool:
        keywords = ["university", "college", "institute", "school", "academy", ".edu", ".ac."]
        return any(k in domain.lower() for k in keywords)

    def get_domain_info(self, domain: str) -> Dict:
        url = self.normalize_url(domain)
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            if self.is_university_domain(domain):
                name = self.extract_university_name(soup, domain)
                sector = "Education"
            else:
                name = self.extract_company_name(soup, domain)
                description = self.extract_description(soup)
                sector = self.extract_sector(soup, description, domain)

            return {"domain": domain, "company_name": name, "description": self.extract_description(soup), "sector": sector, "scraped": True}

        except Exception as e:
            snippets = self.search_google_like(domain)
            snippet_text = " ".join(snippets).lower()
            sector = self.detect_sector_from_text(snippet_text)
            return {"domain": domain, "company_name": None, "description": None, "sector": sector, "scraped": False, "error": f"{type(e).__name__}: {e}"}

    # Name & description extraction
    def extract_company_name(self, soup: BeautifulSoup, domain: str) -> str:
        for meta in ["og:title", "og:site_name"]:
            tag = soup.find("meta", property=meta)
            if tag and tag.get("content"):
                return tag.get("content").strip()
        title = soup.find("title")
        if title and title.string:
            return title.string.split("|")[0].strip()
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
        return domain.split(".")[0].capitalize()

    def extract_university_name(self, soup: BeautifulSoup, domain: str) -> str:
        title = soup.find("title")
        if title and title.string:
            return title.string.strip()
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
        return domain.split(".")[0].replace("-", " ").title()

    def extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        for attr in [{"name": "description"}, {"property": "og:description"}]:
            tag = soup.find("meta", attrs=attr)
            if tag and tag.get("content"):
                return tag.get("content")[:300]
        p = soup.find("p")
        if p and p.get_text(strip=True):
            return p.get_text(strip=True)[:300]
        return None

    # Sector detection
    def extract_sector(self, soup: BeautifulSoup, description: Optional[str], domain: str) -> str:
        text = ""
        if soup.body:
            text += soup.body.get_text(separator=" ", strip=True).lower()
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords and meta_keywords.get("content"):
            text += " " + meta_keywords.get("content").lower()
        title = soup.find("title")
        if title and title.string:
            text += " " + title.string.lower()
        if description:
            text += " " + description.lower()
        sector = self.detect_sector_from_text(text)
        if sector != "Unknown":
            return sector
        snippets = self.search_google_like(f"{domain} company sector")
        snippet_text = " ".join(snippets).lower()
        return self.detect_sector_from_text(snippet_text)

    def detect_sector_from_text(self, text: str) -> str:
        for sector, keywords in self.sector_keywords.items():
            if any(k in text for k in keywords):
                return sector
        return "Unknown"

    # Fallback search
    def search_google_like(self, query: str) -> List[str]:
        try:
            url = "https://duckduckgo.com/html"
            params = {"q": query}
            response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
            soup = BeautifulSoup(response.content, "html.parser")
            snippets = []
            for link in soup.find_all("a", href=re.compile("http")):
                text = link.get_text(strip=True)
                if text and text not in snippets:
                    snippets.append(text)
                if len(snippets) >= 5:
                    break
            return snippets
        except Exception:
            return []
