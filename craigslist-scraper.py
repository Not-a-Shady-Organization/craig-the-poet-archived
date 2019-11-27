from bs4 import BeautifulSoup
import requests

page = requests.get('https://portland.craigslist.org/d/missed-connections/search/mis')
soup = BeautifulSoup(page.text, 'html.parser')
elements = soup.find_all(class_='result-title')

for element in elements[:4]:
    result_url = element['href']
    result_page = requests.get(result_url)
    result_soup = BeautifulSoup(result_page.text, 'html.parser')

    result_title = result_soup.find(id='titletextonly')
    result_title_blob = result_title.text

    result_body = result_soup.find(id='postingbody')
    bad_text = 'QR Code Link to This Post'
    result_text = [x for x in result_body.text.split('\n') if x != bad_text and x != '']
    result_blob = '\n'.join(result_text)

    print(result_title_blob)
    print(result_blob)
    print()
