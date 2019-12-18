from Scraper import Scraper
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('city')
    parser.add_argument('count')
    args = parser.parse_args()

    # TODO : This is brittle
    ad_list_url = f'https://{args.city}.craigslist.org/d/missed-connections/search/mis'

    s = Scraper(ad_list_url)
    s.scrape_to_bucket(int(args.count))
