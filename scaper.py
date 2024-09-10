import os
import json
from bs4 import BeautifulSoup as bs
import requests

BASE_URL = "https://www.gesetze-im-internet.de/"
DIR =  "data/"

def write_to_json(data, file_name) -> None:
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(DIR, file_name), "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False) 

def get_page_object(url = BASE_URL) -> object:
    response = requests.get(BASE_URL)
    response.encoding = 'utf-8' 
    if response.status_code == 200:
        return bs(response.content, "html.parser")
    return response.status_code

def home_page_list(obj = get_page_object()) -> list:
    ulist = obj.find(id="nav_2022")
    if ulist:
        elements = ulist.find_all("li")
        data = []

        for li in elements:
            a_tag = li.find("a")
            if a_tag:
                text = a_tag.text
                href = a_tag.get("href")
                data.append({"text": text, "href": href})

        print(json.dumps(data, indent=4, ensure_ascii=False))
        write_to_json(data, "home_page_list.json")
    else:
        print("Navigation element not found.")


home_page_list()