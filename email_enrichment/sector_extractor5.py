from domain_scraper6 import DomainScraper

class SectorExtractor:
    def __init__(self):
        self.scraper = DomainScraper()
        self._cache = {}

    def extract_sector(self, company_domain: str) -> str:
        if not company_domain:
            return "Unknown"
        if company_domain in self._cache:
            return self._cache[company_domain]
        company_info = self.scraper.get_domain_info(company_domain)
        sector = company_info.get("sector", "Unknown")
        self._cache[company_domain] = sector
        return sector
