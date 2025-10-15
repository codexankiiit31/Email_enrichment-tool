from typing import List, Dict
from company_finder4 import CompanyFinder
from person_name_extractor2 import PersonNameExtractor
from email_validator3 import EmailValidator
from sector_extractor5 import SectorExtractor

class EnrichmentEngine:
    def __init__(self):
        self.company_finder = CompanyFinder()
        self.name_extractor = PersonNameExtractor()
        self.validator = EmailValidator()
        self.sector_extractor = SectorExtractor()

    # -------------------------
    # Single Email Enrichment
    # -------------------------
    def enrich_email(self, email: str) -> Dict:
        if not self.validator.validate_email(email):
            return {"email": email, "error": "Invalid email format"}

        email_lower = email.lower()
        email_user, email_domain = email_lower.split("@")

        # ✅ KEY CHANGE: Pass the full email instead of just the username
        # This allows PersonNameExtractor to:
        # 1. Parse the username (elon.musk → Elon Musk)
        # 2. Use the domain for web scraping if needed
        likely_person = self.name_extractor.extract_person_name(email_lower)
        
        domain_type_label = self.company_finder.get_domain_type_label(email_domain)

        related_university, university_domain, uni_confidence = self.company_finder.find_related_university(email_domain, likely_person)
        related_company, company_domain, company_confidence, detected_sector = self.company_finder.find_related_company(email_domain, likely_person)

        sector = "Unknown"
        if detected_sector:
            sector = detected_sector
        elif company_domain:
            sector = self.sector_extractor.extract_sector(company_domain)
        elif university_domain:
            sector = "Education"

        return {
            "email": email,
            "email_domain": email_domain,
            "domain_type": domain_type_label,
            "likely_person": likely_person or "N/A",
            "related_university": related_university or "N/A",
            "university_domain": university_domain or "N/A",
            "related_company": related_company or "N/A",
            "company_domain": company_domain or "N/A",
            "sector": sector,
            "confidence": {
                "domain": "High",
                "university": uni_confidence,
                "company": company_confidence
            }
        }

    # -------------------------
    # Batch Enrichment
    # -------------------------
    def enrich_batch(self, emails: List[str]) -> List[Dict]:
        return [self.enrich_email(email) for email in emails]


# Optional: Add a method to test name extraction in isolation
    def test_name_extraction(self, email: str) -> Dict:
        """
        Debug helper to see what name extraction returns
        """
        email_lower = email.lower()
        if "@" in email_lower:
            email_user, email_domain = email_lower.split("@")
        else:
            email_user = email_lower
            email_domain = None
        
        return {
            "original_email": email,
            "email_user": email_user,
            "email_domain": email_domain,
            "extracted_name": self.name_extractor.extract_person_name(email_lower),
            "from_username_only": self.name_extractor.parse_name_from_username(email_user) if hasattr(self.name_extractor, 'parse_name_from_username') else "Method not available"
        }
