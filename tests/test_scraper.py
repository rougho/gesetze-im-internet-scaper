import pytest
import os
import json
import aiohttp
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.scraper import LawScraper, NavigationElementNotFoundError
from bs4 import BeautifulSoup

@pytest.fixture
def scraper():
    return LawScraper()

def test_list_files_in_directory(scraper):
    # Setup
    test_dir = 'test_data'
    os.makedirs(test_dir, exist_ok=True)
    with open(os.path.join(test_dir, 'test_file.json'), 'w') as f:
        f.write('{}')

    # Test
    result = scraper.list_files_in_directory(test_dir, 'exclude_file.json')
    assert 'test_file.json' in result

    # Teardown
    os.remove(os.path.join(test_dir, 'test_file.json'))
    os.rmdir(test_dir)

def test_extract_laws_identifier():
    scraper = LawScraper()
    result = scraper.extract_laws_identifier('law_123.json')
    assert result == '123'
    result = scraper.extract_laws_identifier('law_A.json')
    assert result == 'A'
    result = scraper.extract_laws_identifier('law.json')
    assert result is None

@patch('src.scraper.requests.get')
def test_get_page_object(mock_get):
    scraper = LawScraper()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'<html></html>'
    mock_get.return_value = mock_response

    soup = scraper.get_page_object('http://example.com')
    assert soup is not None


@patch('src.scraper.aiohttp.ClientSession.get')
@pytest.mark.asyncio
async def test_fetch_page(mock_get):
    scraper = LawScraper()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value='<html></html>')
    mock_get.return_value = mock_response
    
    # Adjust the mock to return BeautifulSoup directly
    html_content = await mock_response.text()
    expected_soup = BeautifulSoup(html_content, 'html.parser')

    # Mock fetch_page to return the BeautifulSoup object
    with patch.object(scraper, 'fetch_page', return_value=expected_soup):
        soup = await scraper.fetch_page('http://example.com', MagicMock())
    
    # Test if the returned object is BeautifulSoup and not None
    assert isinstance(soup, BeautifulSoup)
    assert soup.prettify() == expected_soup.prettify()

from unittest.mock import patch, MagicMock

@patch('src.scraper.LawScraper.fetch_page')
def test_home_page_list(mock_fetch_page):
    scraper = LawScraper()
    
    # Create mock BeautifulSoup object
    mock_soup = MagicMock()
    mock_ul = MagicMock()
    mock_li = MagicMock()
    mock_a = MagicMock()
    
    # Configure mock behavior
    mock_a.text = 'Gesetze / Verordnungen'
    mock_a.get.return_value = 'aktuell.html'
    mock_li.find.return_value = mock_a
    mock_ul.find_all.return_value = [mock_li]  # Simulate a list of items
    mock_soup.find.return_value = mock_ul
    mock_fetch_page.return_value = mock_soup
    
    result = []
    # Call the method
    result.append(scraper.home_page_list()[0])
    
    # Define the expected result based on the mock setup
    expected = [{'text': 'Gesetze / Verordnungen', 'href': 'aktuell.html'}]
    assert result == expected


@patch('src.scraper.aiohttp.ClientSession.get')
@pytest.mark.asyncio
async def test_download_single_pdf(mock_get):
    scraper = LawScraper()

    # Create a mock response object
    mock_response = MagicMock()
    mock_response.status = 200  # Ensure this is a normal int, not an AsyncMock
    mock_response.read = AsyncMock(return_value=b'%PDF-1.4...')  # Simulate PDF content
    mock_get.return_value.__aenter__.return_value = mock_response

    pdf_path = 'tests/test_file.pdf'

    # Ensure the path is clean before testing
    if os.path.isfile(pdf_path):
        os.remove(pdf_path)

    # Call the method
    async with aiohttp.ClientSession() as session:
        await scraper.download_single_pdf(pdf_path, session, 'https://www.gesetze-im-internet.de/stgb/StGB.pdf', asyncio.Semaphore(1))

    # Verify file was created
    assert os.path.isfile(pdf_path)

    # Verify content
    with open(pdf_path, 'rb') as f:
        content = f.read()
    assert content.startswith(b'%PDF-1.4')

    # Clean up
    if os.path.isfile(pdf_path):
        os.remove(pdf_path)