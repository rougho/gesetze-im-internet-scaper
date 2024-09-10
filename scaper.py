import os
import json
from bs4 import BeautifulSoup as bs
import requests
from urllib.parse import urljoin
import re

BASE_URL = "https://www.gesetze-im-internet.de/"

DIR =  "data/"
HOME_PAGE_LIST_FNAME = "home_page_list.json"
LAWS_LIST = "laws_list.json"
ALPHAB_LAWS_LIST_DIR = "laws_list_by_alphabet"
def write_to_json(data, file_name) -> None:
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(DIR, file_name), "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False) 

def load_json_data(file_path = HOME_PAGE_LIST_FNAME)->list:
    with open(os.path.join(DIR, file_path), "r", encoding="utf-8") as file:
        data = json.load(file)
    return data

def get_page_object(url = BASE_URL) -> object:
    response = requests.get(url)
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
        write_to_json(data, HOME_PAGE_LIST_FNAME)
        return data
    else:
        print("Navigation element not found.")
        exit(1)


def get_laws_alphabetically_list(relative_url = home_page_list()[0]['href']):
    llist = []
    full_path = urljoin(BASE_URL, relative_url)
    page_object = get_page_object(full_path)
    laws_list = page_object.find(id="content_2022")
    laws_list = laws_list.find(id="paddingLR12")
    laws_list = laws_list.find_all('a')
    for a in laws_list:
        a_tag = a
        if a_tag:
            text = a_tag.text
            href = a_tag.get("href")
            llist.append({"text": text, "href": re.sub("./", "", href)}) 
    write_to_json(llist, LAWS_LIST)   
    return llist

def get_laws_by_alphabet(base_url = BASE_URL, laws_list = get_laws_alphabetically_list()):
    for law in laws_list:
        os.makedirs(os.path.join(DIR,ALPHAB_LAWS_LIST_DIR), exist_ok=True)
        print(law)


# home_page_list()
# data = load_json_data(LAWS_LIST)
# print(data)

print(get_laws_by_alphabet())