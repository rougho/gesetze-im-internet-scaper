import os
import json
import re
import shutil
from bs4 import BeautifulSoup as bs
import requests
from urllib.parse import urljoin
import aiohttp
import asyncio
from tqdm.asyncio import tqdm as async_tqdm

class LawScraper:
    BASE_URL = "https://www.gesetze-im-internet.de/"
    DIR = "data/"
    HOME_PAGE_LIST_FNAME = "home_page_list.json"
    LAWS_LIST = "laws_list.json"
    ALPHAB_LAWS_LIST_DIR = "laws_list_by_alphabet"
    PDF_DIR = os.path.join(DIR, "pdf")
    SEMAPHORE_LIMIT = 10
    DELAY_BETWEEN_LAWS = 5

    def __init__(self, base_url: str = None, dir_path: str = None, home_page_list_fname: str = None, 
                 laws_list_fname: str = None, alphab_laws_list_dir: str = None, pdf_dir: str = None, 
                 semaphore_limit: int = None, delay_between_laws: int = None):
        """
        Initializes the LawScraper with optional parameters for URLs and directory paths.

        Args:
            base_url (str, optional): Base URL of the website. Defaults to None.
            dir_path (str, optional): Path to the directory where data will be stored. Defaults to None.
            home_page_list_fname (str, optional): Filename for the homepage list JSON. Defaults to None.
            laws_list_fname (str, optional): Filename for the laws list JSON. Defaults to None.
            alphab_laws_list_dir (str, optional): Directory name for alphabetically categorized law files. Defaults to None.
            pdf_dir (str, optional): Directory where PDFs will be downloaded. Defaults to None.
            semaphore_limit (int, optional): Limit for simultaneous downloads. Defaults to None.
            delay_between_laws (int, optional): Delay in seconds between law downloads. Defaults to None.
        """
        self.BASE_URL = base_url or self.BASE_URL
        self.DIR = dir_path or self.DIR
        self.HOME_PAGE_LIST_FNAME = home_page_list_fname or self.HOME_PAGE_LIST_FNAME
        self.LAWS_LIST = laws_list_fname or self.LAWS_LIST
        self.ALPHAB_LAWS_LIST_DIR = alphab_laws_list_dir or self.ALPHAB_LAWS_LIST_DIR
        self.PDF_DIR = os.path.join(self.DIR, pdf_dir or self.PDF_DIR)
        self.SEMAPHORE_LIMIT = semaphore_limit or self.SEMAPHORE_LIMIT
        self.DELAY_BETWEEN_LAWS = delay_between_laws or self.DELAY_BETWEEN_LAWS

        os.makedirs(self.DIR, exist_ok=True)

    def list_files_in_directory(self, directory_path: str, exclude_file: str) -> list:
        """
        List all files in the specified directory, excluding a particular file.

        Args:
            directory_path (str): Path to the directory.
            exclude_file (str): Filename to exclude from the list.

        Returns:
            list: List of filenames in the directory, excluding the specified file.
        """
        try:
            files = [f for f in os.listdir(directory_path)
                     if os.path.isfile(os.path.join(directory_path, f))
                     and f != exclude_file]
            return files
        except FileNotFoundError:
            print(f"Directory not found: {directory_path}")
            return []
        except PermissionError:
            print(f"Permission denied: {directory_path}")
            return []

    def extract_laws_identifier(self, file_name: str) -> str:
        """
        Extracts the identifier from a law file name.

        Args:
            file_name (str): Name of the file to extract the identifier from.

        Returns:
            str: Extracted identifier or None if no match found.
        """
        pattern = r'_(\d+|[A-Za-z])\.json$'
        match = re.search(pattern, file_name)
        return match.group(1) if match else None

    def sort_files(self, files: list) -> list:
        """
        Sorts a list of files based on their extracted identifiers.

        Args:
            files (list): List of filenames to sort.

        Returns:
            list: Sorted list of filenames.
        """
        def sort_key(file_name):
            identifier = self.extract_laws_identifier(file_name)
            if identifier is None:
                return (float('inf'), '')
            if identifier.isalpha():
                return (0, identifier)
            else:
                return (1, int(identifier))
        return sorted(files, key=sort_key)

    def sanitize_filename(self, file_name: str) -> str:
        """
        Sanitizes a filename by replacing invalid characters.

        Args:
            file_name (str): Original filename.

        Returns:
            str: Sanitized filename.
        """
        return file_name.replace("/", "_").replace("\\", "_")

    def write_to_json(self, data: dict, file_name: str) -> None:
        """
        Writes data to a JSON file.

        Args:
            data (dict): Data to write.
            file_name (str): Name of the output file.
        """
        with open(os.path.join(self.DIR, file_name), "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def load_json_data(self, file_path: str) -> dict:
        """
        Loads data from a JSON file.

        Args:
            file_path (str): Path to the JSON file.

        Returns:
            dict: Parsed data from the JSON file.
        """
        with open(os.path.join(self.DIR, file_path), "r", encoding="utf-8") as file:
            return json.load(file)

    def get_page_object(self, url: str) -> bs:
        """
        Fetches and parses an HTML page from the given URL.

        Args:
            url (str): URL of the page to fetch.

        Returns:
            BeautifulSoup: Parsed HTML page object or None on error.
        """
        try:
            response = requests.get(url)
            response.encoding = 'utf-8'
            response.raise_for_status()
            return bs(response.content, "html.parser")
        except requests.RequestException as e:
            print(f"Error fetching page {url}: {e}")
            return None

    async def fetch_page(self, url: str, session: aiohttp.ClientSession) -> bs:
        """
        Asynchronously fetches and parses an HTML page from the given URL.

        Args:
            url (str): URL of the page to fetch.
            session (aiohttp.ClientSession): The aiohttp session object.

        Returns:
            BeautifulSoup: Parsed HTML page object or None on error.
        """
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                try:
                    content = await response.text()
                except UnicodeDecodeError:
                    content = await response.read()
                    content = content.decode('ISO-8859-1')
                return bs(content, "html.parser")
        except aiohttp.ClientError as e:
            print(f"Error fetching page {url}: {e}")
            return None

    def home_page_list(self) -> list:
        """
        Scrapes the home page to retrieve a list of laws and stores it in a JSON file.

        Returns:
            list: List of dictionaries containing law names and URLs.
        """
        obj = self.get_page_object(self.BASE_URL)
        if obj:
            ulist = obj.find(id="nav_2022")
            if ulist:
                elements = ulist.find_all("li")
                data = [{"text": li.find("a").text, "href": li.find("a").get("href")} for li in elements if li.find("a")]
                self.write_to_json(data, self.HOME_PAGE_LIST_FNAME)
                return data
        print("Navigation element not found.")
        exit(1)

    def get_laws_alphabetically_list(self) -> list:
        """
        Asynchronously fetches a list of laws sorted alphabetically.

        Returns:
            list: List of dictionaries containing law names and URLs.
        """
        async def async_get_laws_alphabetically_list():
            async with aiohttp.ClientSession() as session:
                llist = []
                home_page_list = self.load_json_data(self.HOME_PAGE_LIST_FNAME)
                relative_url = home_page_list[0]['href']
                full_path = urljoin(self.BASE_URL, relative_url)
                page_object = await self.fetch_page(full_path, session)
                if page_object:
                    laws_list = page_object.find(id="content_2022")
                    if laws_list:
                        laws_list = laws_list.find(id="paddingLR12")
                        laws_list = laws_list.find_all('a')
                        llist = [{"text": a.text, "href": re.sub("./", "", a.get("href"))} for a in laws_list if a]
                        self.write_to_json(llist, self.LAWS_LIST)
                return llist

        return asyncio.run(async_get_laws_alphabetically_list())

    def get_laws_by_alphabet(self, laws_list: list) -> list:
        """
        Asynchronously fetches detailed law information by alphabet and stores it.

        Args:
            laws_list (list): List of laws with URLs.

        Returns:
            list: List of detailed law information.
        """
        async def async_get_laws_by_alphabet(laws_list):
            os.makedirs(os.path.join(self.DIR, self.ALPHAB_LAWS_LIST_DIR), exist_ok=True)
            laws_info = []

            async with aiohttp.ClientSession() as session:
                tasks = [self.fetch_law_details(urljoin(self.BASE_URL, law['href']), session, laws_info) for law in laws_list]
                await asyncio.gather(*tasks)

            self.write_to_json(laws_info, os.path.join(self.ALPHAB_LAWS_LIST_DIR, 'full_laws_list.json'))
            return laws_info

        return asyncio.run(async_get_laws_by_alphabet(laws_list))

    async def fetch_law_details(self, url: str, session: aiohttp.ClientSession, laws_info: list) -> None:
        """
        Fetches details of individual laws from a URL.

        Args:
            url (str): URL of the law.
            session (aiohttp.ClientSession): The aiohttp session object.
            laws_info (list): List to store the fetched law details.
        """
        page_object = await self.fetch_page(url, session)
        if page_object:
            table = page_object.find(id="content_2022")
            if table:
                table_items_list = table.find(id="paddingLR12")
                if table_items_list:
                    table_items = table_items_list.find_all('p')
                    each_law = []
                    for item in table_items:
                        law_link_tag = item.find('a', href=True)
                        if law_link_tag:
                            law_webpage_link = urljoin(self.BASE_URL, law_link_tag['href'])
                            title = law_link_tag.text.strip()
                            description = law_link_tag.find('abbr')['title'] if law_link_tag.find('abbr') else ''

                            pdf_link_tag = item.find('a', href=True, title=lambda t: t and 'PDF' in t)
                            pdf_link = urljoin(self.BASE_URL, pdf_link_tag['href']) if pdf_link_tag else None

                            each_law.append({
                                'webpage_link': law_webpage_link,
                                'title': title,
                                'description': description,
                                'pdf_link': pdf_link
                            })
                    laws_info.extend(each_law)
                    law_file_name = os.path.join(self.ALPHAB_LAWS_LIST_DIR, re.sub(".html", "", url.split("/")[-1]) + ".json")
                    self.write_to_json(each_law, law_file_name)

    def display_available_laws(self) -> list:
        """
        Displays available laws from the sorted list of laws.

        Returns:
            list: Sorted list of law files.
        """
        laws = self.list_files_in_directory(os.path.join(self.DIR, self.ALPHAB_LAWS_LIST_DIR), "full_laws_list.json")
        sort_law = self.sort_files(laws)
        print("Title \t\t Description")
        for law in sort_law:
            print(f"== {self.extract_laws_identifier(law)} ==")
            content = self.load_json_data(os.path.join(self.ALPHAB_LAWS_LIST_DIR, law))
            for index, item in enumerate(content):
                print(f"{index+1} - {item['title']}      {item['description'][:80]} ")
        return self.sort_files(laws)

    def download_all_pdfs(self) -> None:
        """
        Synchronously downloads all PDFs related to the laws.

        Returns:
            None
        """
        async def async_download_all_pdfs():
            if os.path.exists(self.PDF_DIR):
                shutil.rmtree(self.PDF_DIR)
                print(f"Deleted existing directory: {self.PDF_DIR}")

            os.makedirs(self.PDF_DIR, exist_ok=True)
            print(f"Created new directory: {self.PDF_DIR}")

            laws = self.list_files_in_directory(os.path.join(self.DIR, self.ALPHAB_LAWS_LIST_DIR), "full_laws_list.json")
            sort_law = self.sort_files(laws)
            semaphore = asyncio.Semaphore(self.SEMAPHORE_LIMIT)

            async with aiohttp.ClientSession() as session:
                for index, law in enumerate(sort_law):
                    alphabetic_file_name = os.path.join(self.PDF_DIR, self.extract_laws_identifier(law))
                    os.makedirs(alphabetic_file_name, exist_ok=True)
                    content = self.load_json_data(os.path.join(self.ALPHAB_LAWS_LIST_DIR, law))

                    tasks = [self.download_single_pdf(
                        os.path.join(alphabetic_file_name, f"{self.sanitize_filename(item['title'])}.pdf"),
                        session,
                        item['pdf_link'],
                        semaphore
                    ) for item in content]

                    for task in async_tqdm(asyncio.as_completed(tasks), total=len(tasks)):
                        await task

                    if index < len(sort_law) - 1:
                        await asyncio.sleep(self.DELAY_BETWEEN_LAWS)

        asyncio.run(async_download_all_pdfs())

    async def download_single_pdf(self, pdf_path: str, session: aiohttp.ClientSession, pdf_link: str, 
                                  semaphore: asyncio.Semaphore, retries: int = 0, max_retries: int = 5) -> None:
        """
        Asynchronously downloads a single PDF with retry logic.

        Args:
            pdf_path (str): Path to save the PDF.
            session (aiohttp.ClientSession): The aiohttp session object.
            pdf_link (str): URL of the PDF.
            semaphore (asyncio.Semaphore): Semaphore to control concurrent downloads.
            retries (int, optional): Number of retries. Defaults to 0.
            max_retries (int, optional): Maximum number of retries. Defaults to 5.

        Returns:
            None
        """
        async with semaphore:
            try:
                async with session.get(pdf_link, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        with open(pdf_path, 'wb') as f:
                            f.write(await response.read())
                    else:
                        print(f"Failed to download {pdf_link}: Status {response.status}")
            except aiohttp.ClientOSError as e:
                if retries < max_retries:
                    print(f"Retry {retries + 1} for {pdf_link} after error: {e}")
                    await asyncio.sleep(2 ** retries)  # Exponential backoff
                    await self.download_single_pdf(pdf_path, session, pdf_link, semaphore, retries + 1)
                else:
                    print(f"Failed to download {pdf_link} after {max_retries} retries")
            except Exception as e:
                print(f"Unexpected error for {pdf_link}: {e}")

    def start_download(self) -> None:
        """
        Starts the download process: scrapes the homepage, retrieves the laws, and downloads all PDFs.

        Returns:
            None
        """
        self.home_page_list()
        laws_list = self.get_laws_alphabetically_list()
        self.get_laws_by_alphabet(laws_list=laws_list)
        self.download_all_pdfs()
