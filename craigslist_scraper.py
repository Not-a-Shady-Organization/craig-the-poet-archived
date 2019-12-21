from Scraper import Scraper
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--city', help='City from which to scrape craigslist missed connections ads')
    parser.add_argument('--count', help='With city, how many ads to scrape')

    parser.add_argument('--url', help='URL of single craigslist missed connections ad to scrape')

    parser.add_argument('--bucket-dir', help='Destination bucket, if not the ad\'s city')
    args = parser.parse_args()

    if not args.url and not (args.city and args.count):
        print('Must specify --city and --count, or a specific ad --url. Exiting...')
        exit()

    # TODO : This is brittle
    ad_list_url = f'https://{args.city}.craigslist.org/d/missed-connections/search/mis'

    s = Scraper()

    if args.url:
        s.scrape_ad_to_bucket(args.url, bucket_dir=args.bucket_dir)
    else:
        s.scrape_ads_to_bucket(ad_list_url, int(args.count), bucket_dir=args.bucket_dir)
