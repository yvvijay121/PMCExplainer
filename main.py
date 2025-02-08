from flask import Flask
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route('/<pmc_id>')
def get_pmc_page(pmc_id):
    url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        article_content = soup.find('section', {'aria-label': 'Article content'})
        if article_content:
            return article_content.prettify()
        else:
            return "Article content not found"
    else:
        return f"Error {response.status_code}: Unable to retrieve page for PMC ID {pmc_id}. Response: {response.text}"

if __name__ == '__main__':
    app.run(debug=True)