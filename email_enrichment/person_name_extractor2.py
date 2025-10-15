import re
import json
import requests
from bs4 import BeautifulSoup
import spacy
from functools import lru_cache
from typing import Optional, List

class PersonNameExtractor:
    def __init__(self, language: str = "en"):
        """
        Initialize NLP model and regex patterns for name extraction.
        """
        self.language = language
        try:
            if language == "en":
                self.nlp = spacy.load("en_core_web_sm")
            elif language == "xx":  # multilingual
                self.nlp = spacy.load("xx_ent_wiki_sm")
            else:
                self.nlp = spacy.blank(language)
        except OSError:
            print(f"⚠️ SpaCy model for '{language}' not found. Using blank pipeline.")
            self.nlp = spacy.blank(language)

        # Titles often used in names
        self.name_titles = [
            "Mr", "Mrs", "Ms", "Dr", "Prof", "Er", "Miss", "Mx",
            "Shri", "Smt", "Madam", "Sir"
        ]

        # Common role keywords to detect names around them
        self.role_keywords = [
            "CEO", "Founder", "Director", "Professor", "Manager",
            "Head", "President", "Chairman", "Lead", "Engineer",
            "Developer", "Researcher", "Scientist"
        ]

        # Regex to capture names with titles
        self.name_pattern = re.compile(
            r'\b(?:' + '|'.join(self.name_titles) + r')\.?\s+[A-Z][a-z]+\s*[A-Z]?[a-z]*\b'
        )

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        # Pages to check for staff/team/leadership
        self.pages_to_scrape = ["", "/about", "/team", "/leadership", "/founders", "/management"]

    # -------------------------
    # Email Username Parser
    # -------------------------
    def parse_name_from_username(self, username: str) -> Optional[str]:
        """
        Extract name from email username like 'john.doe' or 'j_smith'.
        Returns properly formatted name.
        """
        if not username:
            return None
        
        # Remove numbers and special chars, split on dots/underscores/dashes
        parts = re.split(r'[._\-\d]+', username.lower())
        parts = [p.strip() for p in parts if p and len(p) > 1]
        
        if len(parts) >= 2:
            # Capitalize first letter of each part
            return ' '.join(p.capitalize() for p in parts[:2])
        elif len(parts) == 1 and len(parts[0]) > 2:
            return parts[0].capitalize()
        
        return None

    # -------------------------
    # Core Name Extraction
    # -------------------------
    @lru_cache(maxsize=100)
    def extract_names(self, text: str) -> List[str]:
        """
        Extract possible person names from a given text.
        Combines NER + regex + role-based detection.
        """
        if not text:
            return []

        names = set()

        # --- 1. Named Entity Recognition (NER) ---
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ == "PERSON" and len(ent.text.split()) <= 4:
                names.add(ent.text.strip())

        # --- 2. Regex-based Title Matching ---
        for match in self.name_pattern.findall(text):
            names.add(match.strip())

        # --- 3. Role-based detection (improved pattern) ---
        for role in self.role_keywords:
            # More flexible pattern to catch various name formats
            pattern = re.compile(
                rf"(?:{role}\s+[:\-–]?\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{0,2}})",
                re.IGNORECASE
            )
            for match in pattern.findall(text):
                names.add(match.strip())

        # --- 4. Standalone capitalized names (First Last) ---
        standalone_pattern = re.compile(r'\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b')
        for match in standalone_pattern.findall(text):
            names.add(match.strip())

        # --- 5. Clean and Normalize ---
        clean_names = set()
        for name in names:
            cleaned = re.sub(r"[^A-Za-z\s]", "", name).strip()
            # Filter out common false positives
            if (2 <= len(cleaned) <= 40 and 
                not cleaned.lower() in ['about us', 'contact us', 'privacy policy', 'terms conditions']):
                clean_names.add(cleaned)

        return sorted(clean_names)

    # -------------------------
    # Scrape multiple pages for names
    # -------------------------
    def scrape_website_for_names(self, domain: str) -> List[str]:
        all_names = set()
        domain = domain if domain.startswith("http") else f"https://{domain}"

        for page in self.pages_to_scrape:
            try:
                url = domain.rstrip("/") + page
                response = requests.get(url, headers=self.headers, timeout=5)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer"]):
                    script.decompose()
                
                text = soup.get_text(separator=" ", strip=True)
                all_names.update(self.extract_names(text))

                # --- Check JSON-LD for structured person data ---
                scripts = soup.find_all("script", type="application/ld+json")
                for script in scripts:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get("@type") == "Person":
                            if data.get("name"):
                                all_names.add(data.get("name"))
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and item.get("@type") == "Person":
                                    if item.get("name"):
                                        all_names.add(item.get("name"))
                    except Exception:
                        continue
            except Exception:
                continue

        # Filter None values
        all_names = {name for name in all_names if name}
        return sorted(all_names)

    # -------------------------
    # Fallback DuckDuckGo search
    # -------------------------
    def duckduckgo_search_names(self, domain: str) -> List[str]:
        """Search DuckDuckGo and extract names from snippets"""
        try:
            url = "https://duckduckgo.com/html"
            params = {"q": f"{domain} team OR leadership OR founders"}
            response = requests.get(url, params=params, headers=self.headers, timeout=5)
            soup = BeautifulSoup(response.content, "html.parser")
            snippets = " ".join([a.get_text(strip=True) for a in soup.find_all("a", href=True)])
            return self.extract_names(snippets)
        except Exception:
            return []

    # -------------------------
    # Best Guess Extraction (for domains)
    # -------------------------
    def extract_best_guess_from_domain(self, domain: str) -> Optional[str]:
        """
        Return the most likely person name using:
        1. Website scraping (homepage + team pages)
        2. JSON-LD structured data
        3. DuckDuckGo fallback
        """
        # 1. Scrape website
        names = self.scrape_website_for_names(domain)
        if names:
            return names[0]  # return first/highest-ranked

        # 2. DuckDuckGo fallback
        names = self.duckduckgo_search_names(domain)
        if names:
            return names[0]

        return None
    
    # -------------------------
    # Main Entry Point
    # -------------------------
    def extract_person_name(self, text: str) -> Optional[str]:
        """
        Extract person name from email address or text.
        
        Strategy:
        1. If it's an email, parse the username part
        2. Try NER on the parsed text
        3. Try scraping the domain (if available)
        """
        if not text:
            return None
        
        # Check if it's an email address
        email_match = re.match(r'([^@]+)@([^@]+)', text)
        
        if email_match:
            username = email_match.group(1)
            domain = email_match.group(2)
            
            # Strategy 1: Parse name from username
            parsed_name = self.parse_name_from_username(username)
            if parsed_name:
                return parsed_name
            
            # Strategy 2: Try NER on username (converted to readable text)
            username_text = username.replace('.', ' ').replace('_', ' ').replace('-', ' ')
            names = self.extract_names(username_text)
            if names:
                return names[0]
            
            # Strategy 3: Scrape the domain website
            try:
                scraped_names = self.scrape_website_for_names(domain)
                if scraped_names:
                    return scraped_names[0]
            except Exception:
                pass
            
            # Strategy 4: DuckDuckGo fallback
            try:
                search_names = self.duckduckgo_search_names(domain)
                if search_names:
                    return search_names[0]
            except Exception:
                pass
        
        else:
            # Not an email - try direct name extraction
            names = self.extract_names(text)
            if names:
                return names[0]
            
            # If text looks like a domain, try web scraping
            if '.' in text and not ' ' in text:
                try:
                    return self.extract_best_guess_from_domain(text)
                except Exception:
                    pass
        
        return None