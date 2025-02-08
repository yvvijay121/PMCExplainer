from flask import Flask, request
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
from llm_functions import *
from tinydb import TinyDB, Query

app = Flask(__name__)

load_dotenv()

# Example usage of an environment variable
key = os.getenv("OPENAI_KEY")
# Initialize TinyDB
db = TinyDB('db.json')

def scrape_pmc_page(pmc_id, convert_sup=False):
    """
    Scrapes the content of a PMC (PubMed Central) article page.

    Args:
        pmc_id (str): The PMC ID of the article to scrape.
        convert_sup (bool): Whether to convert <sup> tags to plain text. Defaults to False.

    Returns:
        tuple: A tuple containing:
            - list: A list of BeautifulSoup Tag objects representing the sections of the article content.
            - int: The HTTP status code of the response.
            - str: The raw HTML content of the response.

    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.

    Notes:
        - The function removes certain tags (e.g., "sup", "img") from the article content.
        - Links with the text "Open in a new tab" are decomposed.
        - Links with the class "usa-link" are unwrapped.
        - Only sections with the class "abstract" or IDs starting with "S" are returned.
    """
    url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        article_content = soup.find("section", {"aria-label": "Article content"})
        # Remove img tags
        for element in article_content.find_all("img"):
            element.decompose()

        # Remove or convert sup tags based on a boolean option
        if convert_sup:
            for element in article_content.find_all("sup"):
                sup_text = element.get_text()  # Extract the text
                element.replace_with(f'<>{sup_text}<>')  # Replace <sup> with its text
        else:
            for element in article_content.find_all("sup"):
                element.decompose()

        links_to_decompose = article_content.find_all("a", string="Open in a new tab")
        for link in links_to_decompose:
            link.decompose()

        links_to_unwrap = article_content.find_all("a", class_="usa-link")
        for link in links_to_unwrap:
            link.unwrap()
        article_content = article_content.findChildren(recursive=False)[0]
        section_tags = article_content.findChildren(recursive=False)
        section_tags = [tag for tag in section_tags if tag.get("class") == ["abstract"] or tag.get("id", "").startswith("S")]
        return section_tags, response.status_code, response.text
    else:
        return None, response.status_code, response.text

@app.route("/comprehension/<pmc_id>")
def comprehension(pmc_id):
    # Check if the result is already cached
    query = Query()
    cached_result = db.search((query.pmc_id == pmc_id) & (query.function == 'comprehension'))
    if cached_result:
        return cached_result[0]['result']
    section_tags, status_code, response_text = scrape_pmc_page(pmc_id)
    if section_tags:
        result = str(comprehension_check(section_tags[0].get_text(), key))
        # Cache the result
        db.insert({'pmc_id': pmc_id, 'function': 'comprehension', 'result': result})
        return result
    else:
        return f"Error {status_code}: Unable to retrieve page for PMC ID {pmc_id}. Response: {response_text}"

@app.route("/rewrite/<pmc_id>")
def rewrite(pmc_id):
    comprehension_level = int(request.args.get('level'))
    if not comprehension_level:
        return "Error: 'level' query parameter is required.", 400
    
    # Check if the result is already cached
    query = Query()
    cached_result = db.search((query.pmc_id == pmc_id) & (query.function == 'rewrite') & (query.level == comprehension_level))
    if cached_result:
        return cached_result[0]['result']    

    section_tags, status_code, response_text = scrape_pmc_page(pmc_id, True)

    return_list = []

    if section_tags:
        for tag in section_tags[:5]:
            return_list.append(rewrite_comprehension(tag.get_text(), comprehension_level, key))
        result = '\n'.join(return_list)
        db.insert({'pmc_id': pmc_id, 'level': comprehension_level, 'function': 'comprehension', 'rewrite': result})
        return result
    else:
        return f"Error {status_code}: Unable to retrieve page for PMC ID {pmc_id}. Response: {response_text}"
        

if __name__ == "__main__":
    app.run(debug=True)
