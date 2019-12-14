import requests
from bs4 import BeautifulSoup


class Scraper():
    def __init__(self, url):
        self.url = url
        self.type = self.classify(url)

        if self.type == 'craigslist':
            self.craigslist_scrape()
        else:
            raise DomainError(f'Unrecognized domain for site "{url}"')


    # TODO: Make more sophisticated. Handle cases where e.g. CL ad is titles YELP BOY TASTY
    def classify(self, url):
        if 'craigslist' in url:
            return 'craigslist'

        if 'yelp' in url:
            return 'yelp'

    # TODO: Add more scrapers for more sites
    def craigslist_scrape(self):
        result_page = requests.get(self.url)
        result_soup = BeautifulSoup(result_page.text, 'html.parser')

        # Get Craigslist title
        result_title_element = result_soup.find(id='titletextonly')
        result_title = result_title_element.text

        # Get Craigslist body
        result_body_element = result_soup.find(id='postingbody')
        bad_text = 'QR Code Link to This Post'
        result_text = [x for x in result_body_element.text.split('\n') if x != bad_text and x != '']
        result_body = '\n'.join(result_text)

        self.title = result_title
        self.body = result_body
