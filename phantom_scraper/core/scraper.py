import time
import random
import logging
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent
import undetected_chromedriver as uc

class PhantomScraper:
    def __init__(self, headless: bool = True, use_undetected: bool = True):
        self.headless = headless
        self.use_undetected = use_undetected
        self.driver = None
        self.ua = UserAgent()
        self.logger = logging.getLogger(__name__)
        
    def _setup_driver(self):
        """Setup Chrome driver with anti-detection measures"""
        if self.use_undetected:
            options = uc.ChromeOptions()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = uc.Chrome(options=options)
        else:
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f'--user-agent={self.ua.random}')
            
            self.driver = webdriver.Chrome(options=options)
            
        # Execute script to remove webdriver property
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def start(self):
        """Start the browser"""
        if not self.driver:
            self._setup_driver()
            
    def stop(self):
        """Stop the browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            
    def random_delay(self, min_delay: float = 1.0, max_delay: float = 3.0):
        """Add random delay to mimic human behavior"""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
        
    def scroll_page(self, scroll_pause_time: float = 1.0):
        """Scroll page to load dynamic content"""
        if not self.driver:
            return
            
        # Get scroll height
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait to load page
            time.sleep(scroll_pause_time)
            
            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            
    def scrape_linkedin_profiles(self, search_url: str, max_profiles: int = 50) -> List[Dict[str, Any]]:
        """Scrape LinkedIn profiles from search results"""
        if not self.driver:
            self.start()
            
        profiles = []
        try:
            self.driver.get(search_url)
            self.random_delay(3, 5)
            
            # Scroll to load more profiles
            self.scroll_page()
            
            # Find profile elements
            profile_elements = self.driver.find_elements(By.CSS_SELECTOR, '.entity-result__item')
            
            for i, element in enumerate(profile_elements[:max_profiles]):
                try:
                    profile_data = self._extract_profile_data(element)
                    if profile_data:
                        profiles.append(profile_data)
                        self.random_delay(1, 2)
                except Exception as e:
                    self.logger.error(f"Error extracting profile {i}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error scraping LinkedIn profiles: {e}")
            
        return profiles
        
    def _extract_profile_data(self, element) -> Optional[Dict[str, Any]]:
        """Extract data from a single profile element"""
        try:
            # Extract name
            name_element = element.find_element(By.CSS_SELECTOR, '.entity-result__title-text a')
            name = name_element.text.strip()
            profile_url = name_element.get_attribute('href')
            
            # Extract title
            title_element = element.find_element(By.CSS_SELECTOR, '.entity-result__primary-subtitle')
            title = title_element.text.strip()
            
            # Extract company
            company_element = element.find_element(By.CSS_SELECTOR, '.entity-result__secondary-subtitle')
            company = company_element.text.strip()
            
            return {
                'name': name,
                'title': title,
                'company': company,
                'profile_url': profile_url,
                'scraped_at': time.time()
            }
        except NoSuchElementException:
            return None
            
    def scrape_google_maps(self, search_query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Scrape Google Maps business listings"""
        if not self.driver:
            self.start()
            
        businesses = []
        try:
            search_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
            self.driver.get(search_url)
            self.random_delay(3, 5)
            
            # Scroll to load more results
            self.scroll_page()
            
            # Find business elements
            business_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-result-index]')
            
            for i, element in enumerate(business_elements[:max_results]):
                try:
                    business_data = self._extract_business_data(element)
                    if business_data:
                        businesses.append(business_data)
                        self.random_delay(1, 2)
                except Exception as e:
                    self.logger.error(f"Error extracting business {i}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error scraping Google Maps: {e}")
            
        return businesses
        
    def _extract_business_data(self, element) -> Optional[Dict[str, Any]]:
        """Extract data from a single business element"""
        try:
            # Extract business name
            name_element = element.find_element(By.CSS_SELECTOR, '[data-value="Directions"]')
            name = name_element.text.strip()
            
            # Extract rating
            try:
                rating_element = element.find_element(By.CSS_SELECTOR, '.section-star-display')
                rating = rating_element.get_attribute('aria-label')
            except NoSuchElementException:
                rating = None
                
            # Extract address
            try:
                address_element = element.find_element(By.CSS_SELECTOR, '.section-info-text')
                address = address_element.text.strip()
            except NoSuchElementException:
                address = None
                
            return {
                'name': name,
                'rating': rating,
                'address': address,
                'scraped_at': time.time()
            }
        except NoSuchElementException:
            return None
            
    def scrape_website_data(self, url: str, selectors: Dict[str, str]) -> Dict[str, Any]:
        """Scrape data from any website using CSS selectors"""
        if not self.driver:
            self.start()
            
        data = {}
        try:
            self.driver.get(url)
            self.random_delay(2, 4)
            
            for key, selector in selectors.items():
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        if len(elements) == 1:
                            data[key] = elements[0].text.strip()
                        else:
                            data[key] = [elem.text.strip() for elem in elements]
                    else:
                        data[key] = None
                except Exception as e:
                    self.logger.error(f"Error extracting {key}: {e}")
                    data[key] = None
                    
        except Exception as e:
            self.logger.error(f"Error scraping website {url}: {e}")
            
        return data
