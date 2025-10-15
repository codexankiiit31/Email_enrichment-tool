from typing import Dict, Optional, Tuple
import tldextract
import re
import json
import os

from domain_scraper6 import DomainScraper
from domain_type_detector7 import DomainTypeDetectorFastText


class CompanyFinder:
    CACHE_FILE = "university_cache.json"

    def __init__(self):
        self.scraper = DomainScraper()
        self.detector = DomainTypeDetectorFastText(self.scraper)

        # Free email domains
        self.free_email_domains: Dict[str, str] = {
            "gmail.com": "Free webmail (Google)",
            "yahoo.com": "Free webmail (Yahoo)",
            "outlook.com": "Free webmail (Microsoft)",
            "hotmail.com": "Free webmail (Microsoft)",
            "aol.com": "Free webmail (AOL)",
            "mail.com": "Free webmail",
            "protonmail.com": "Free webmail (ProtonMail)",
            "icloud.com": "Free webmail (Apple)"
        }

        # University keywords for fallback rules
        self.university_keywords = [
            "university", "college", "institute", "school", "academy",
            "edu", "ac.in", "ac.uk", "ac.id", "ac.jp", "ac.nz", ".edu"
        ]

        # Known university domains
        self.university_domains = self.load_university_domains()

        # Load scraped university cache
        self.university_cache: Dict[str, Tuple[str, str]] = self.load_cache()

    # -------------------------
    # University domain list
    # -------------------------
    def load_university_domains(self) -> Dict[str, str]:
        return {
            "iitjammu.ac.in": "Indian Institute of Technology Jammu (IIT Jammu)",
            "iitd.ac.in": "Indian Institute of Technology Delhi (IIT Delhi)",
            "iitb.ac.in": "Indian Institute of Technology Bombay (IIT Bombay)",
            "iitkgp.ac.in": "Indian Institute of Technology Kharagpur (IIT Kharagpur)",
            "iitm.ac.in": "Indian Institute of Technology Madras (IIT Madras)",
            "iitk.ac.in": "Indian Institute of Technology Kanpur (IIT Kanpur)",
            "iitg.ac.in": "Indian Institute of Technology Guwahati (IIT Guwahati)",
            "iitr.ac.in": "Indian Institute of Technology Roorkee (IIT Roorkee)",
            "iitbhu.ac.in": "Indian Institute of Technology Varanasi (IIT BHU)",
            "berkeley.edu": "University of California, Berkeley",
            "mit.edu": "Massachusetts Institute of Technology",
            "stanford.edu": "Stanford University",
            "harvard.edu": "Harvard University",
            "oxford.ac.uk": "University of Oxford",
            "cam.ac.uk": "University of Cambridge"
        }

    # -------------------------
    # Domain type detection
    # -------------------------
    def identify_domain_type(self, domain: str) -> str:
        domain_type, _ = self.detector.identify_domain_type(domain)
        return domain_type

    def get_domain_type_label(self, domain: str) -> str:
        return self.detector.get_domain_type_label(domain)

    # -------------------------
    # University & Company Matching
    # -------------------------
    def find_related_university(
        self, domain: str, person_name: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], str]:
        domain_lower = domain.lower()

        # ✅ 1️⃣ Check cached results first
        if domain_lower in self.university_cache:
            uni_name, confidence = self.university_cache[domain_lower]
            return uni_name, domain_lower, confidence

        # ✅ 2️⃣ Check known university domains
        for uni_domain, uni_name in self.university_domains.items():
            if domain_lower == uni_domain.lower():
                self.university_cache[domain_lower] = (uni_name, "High")
                self.save_cache()
                return uni_name, domain_lower, "High"

        # 🧰 3️⃣ Domain suffix rules
        if ".ac." in domain_lower or ".edu" in domain_lower:
            self.university_cache[domain_lower] = (f"University ({domain})", "Medium")
            self.save_cache()
            return f"University ({domain})", domain_lower, "Medium"

        # 📝 4️⃣ Keyword fallback
        if any(keyword in domain_lower for keyword in self.university_keywords):
            self.university_cache[domain_lower] = (f"University ({domain})", "Low")
            self.save_cache()
            return f"University ({domain})", domain_lower, "Low"

        # 🌐 5️⃣ Scrape homepage for additional signals
        try:
            info = self.scraper.get_domain_info(domain)
            html = info.get("html", "")
            title = info.get("title", "") or ""
            description = info.get("meta_description", "") or ""

            combined_text = " ".join([title, description, html[:5000]]).lower()

            edu_keywords = [
                "university", "college", "institute", "campus",
                "faculty", "admissions", "research", "students"
            ]

            if any(kw in combined_text for kw in edu_keywords):
                # Regex for "University of XYZ"
                if re.search(r"university\s+of\s+[A-Z][a-z]+", html, re.IGNORECASE):
                    self.university_cache[domain_lower] = (f"University ({domain})", "High")
                    self.save_cache()
                    return f"University ({domain})", domain_lower, "High"

                # JSON-LD structured data check
                if '"@type":"CollegeOrUniversity"' in html.replace(" ", ""):
                    self.university_cache[domain_lower] = (f"University ({domain})", "High")
                    self.save_cache()
                    return f"University ({domain})", domain_lower, "High"

                # Weak signals
                self.university_cache[domain_lower] = (f"University ({domain})", "Medium")
                self.save_cache()
                return f"University ({domain})", domain_lower, "Medium"

        except Exception:
            # Scraper failed → fallback only
            pass

        # 6️⃣ Not a university
        self.university_cache[domain_lower] = (None, "Low")
        self.save_cache()
        return None, None, "Low"

    def find_related_company(
        self, email_domain: str, person_name: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], str, Optional[str]]:
        # 1️⃣ Free webmail check
        if email_domain in self.free_email_domains:
            return None, None, "Low", None

        # 2️⃣ Obvious university keywords
        if any(keyword in email_domain.lower() for keyword in ["edu", ".ac", "university"]):
            return None, None, "Low", None

        # 3️⃣ Extract clean company domain using tldextract
        ext = tldextract.extract(email_domain)
        company_domain = ext.domain or email_domain

        # 4️⃣ Try scraping info
        domain_info = self.scraper.get_domain_info(email_domain)
        if domain_info.get("scraped"):
            company_name = domain_info.get("company_name") or company_domain.title()
            sector = domain_info.get("sector")
            confidence = "High" if domain_info.get("company_name") else "Medium"

            # Lower confidence for deep subdomains
            if email_domain.count(".") > 2:
                confidence = "Low"

            return company_name, email_domain, confidence, sector

        # 5️⃣ Fallback: simple title case
        company_name = company_domain.replace("-", " ").title()
        return company_name, email_domain, "Medium", None

    # -------------------------
    # Cache handling
    # -------------------------
    def load_cache(self) -> Dict[str, Tuple[str, str]]:
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_cache(self):
        with open(self.CACHE_FILE, "w") as f:
            json.dump(self.university_cache, f, indent=2)
