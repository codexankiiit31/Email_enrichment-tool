import json
import os
from typing import Dict, Tuple
from urllib.parse import urlparse

import gensim.downloader as api
from gensim.models import KeyedVectors

from domain_scraper6 import DomainScraper


class DomainTypeDetectorFastText:
    CACHE_FILE = "domain_cache_fasttext.json"
    _word_vectors: KeyedVectors = None  # static cache for GloVe model

    def __init__(self, scraper: DomainScraper):
        self.scraper = scraper
        self.domain_cache = self.load_cache()

        # Load GloVe small model only once globally
        if DomainTypeDetectorFastText._word_vectors is None:
            print("Loading GloVe model (glove-twitter-100)...")
            DomainTypeDetectorFastText._word_vectors = api.load("glove-twitter-100")
            print("GloVe model loaded!")

        self.word_vectors = DomainTypeDetectorFastText._word_vectors

        # Free email domains
        self.free_email_domains: Dict[str, str] = {
            "gmail.com": "Free webmail (Google)",
            "yahoo.com": "Free webmail (Yahoo)",
            "outlook.com": "Free webmail (Microsoft)",
            "hotmail.com": "Free webmail (Microsoft)",
            "aol.com": "Free webmail (AOL)",
            "protonmail.com": "Free webmail (ProtonMail)",
            "icloud.com": "Free webmail (Apple)",
            "mail.com": "Free webmail"
        }

        # University keywords
        self.university_keywords = ["university", "college", "institute", "school", "academy"]

        # University domain suffixes
        self.university_suffixes = [".edu", ".edu.in", ".ac.in", ".ac.uk", ".ac.id", ".ac.jp", ".ac.nz"]

    # -------------------------
    # Helpers
    # -------------------------
    def normalize_domain(self, domain: str) -> str:
        domain = domain.strip().lower()
        if domain.startswith("http"):
            domain = urlparse(domain).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        if domain.endswith("/"):
            domain = domain.rstrip("/")
        return domain

    def load_cache(self) -> Dict[str, Dict]:
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {}

    def save_cache(self):
        with open(self.CACHE_FILE, "w") as f:
            json.dump(self.domain_cache, f, indent=2)

    def fasttext_similarity(self, domain_name: str, keywords: list) -> float:
        """Compute max cosine similarity between domain words and keywords using GloVe."""
        parts = domain_name.replace("-", " ").split(".")
        max_sim = 0.0
        for w in parts:
            if len(w) < 3:  # skip very short tokens
                continue
            for kw in keywords:
                try:
                    sim = self.word_vectors.similarity(w, kw)
                    max_sim = max(max_sim, sim)
                except KeyError:
                    continue
        return max_sim

    def is_university_domain(self, domain: str) -> bool:
        if any(domain.endswith(suffix) for suffix in self.university_suffixes):
            return True
        if any(kw in domain for kw in self.university_keywords):
            return True
        return False

    # -------------------------
    # Main detection
    # -------------------------
    def identify_domain_type(self, domain: str) -> Tuple[str, float]:
        domain = self.normalize_domain(domain)

        # Check cache
        if domain in self.domain_cache:
            cached = self.domain_cache[domain]
            return cached["type"], cached["confidence"]

        # 1️⃣ Free email domain
        if domain in self.free_email_domains:
            result = ("free_email", 1.0)

        else:
            try:
                info = self.scraper.get_domain_info(domain)
                sector = info.get("sector", "").lower()
                company_name = info.get("company_name", "")

                # 2️⃣ Scraper detects university
                if "education" in sector or "university" in company_name.lower():
                    result = ("university", 0.9)
                elif sector:
                    result = ("company", 0.8)
                else:
                    # 3️⃣ Fallback: rules + GloVe
                    if self.is_university_domain(domain):
                        result = ("university", 0.7)
                    else:
                        sim = self.fasttext_similarity(domain, self.university_keywords)
                        result = ("university", 0.75) if sim > 0.5 else ("company", 0.6)
            except Exception:
                # 4️⃣ Fallback if scraper fails
                if self.is_university_domain(domain):
                    result = ("university", 0.7)
                else:
                    sim = self.fasttext_similarity(domain, self.university_keywords)
                    result = ("university", 0.75) if sim > 0.5 else ("company", 0.6)

        # Cache result
        self.domain_cache[domain] = {"type": result[0], "confidence": result[1]}
        self.save_cache()
        return result

    # -------------------------
    # Human-readable label
    # -------------------------
    def get_domain_type_label(self, domain: str) -> str:
        domain_type, conf = self.identify_domain_type(domain)
        if domain_type == "free_email":
            return f"Free Webmail ({conf*100:.0f}% confidence)"
        elif domain_type == "university":
            return f"University/Educational ({conf*100:.0f}% confidence)"
        else:
            return f"Company/Business ({conf*100:.0f}% confidence)"
