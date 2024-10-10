import logging
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from playwright.async_api import async_playwright
import re
from config import API_KEY

# uvicorn scraper_service:app --host 0.0.0.0 --port 8000

# Configurazione del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Scraper Microservice")

# Definizione dei modelli di richiesta
class SearchArtistRequest(BaseModel):
    artist_name: str

class WriteToSearchbarRequest(BaseModel):
    search_text: str

class SearchTicketsRequest(BaseModel):
    url: str

class MatchTicketsRequest(BaseModel):
    tickets: List[dict]
    user_ticket: str


async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        logger.warning(f"Tentativo di accesso non autorizzato con API Key: {x_api_key}")
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/search_artist", dependencies=[Depends(verify_api_key)])
async def search_artist(request: SearchArtistRequest):
    artist_name = request.artist_name
    results_list = []
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto("https://www.fansale.it/event")
            await page.wait_for_selector("#headerSearchbarMainField", timeout=7000)
            search_box = await page.query_selector("#headerSearchbarMainField")
            await search_box.fill("")
            await search_box.type(artist_name)

            await asyncio.sleep(0.8)
            

            await page.wait_for_selector(".Header-SuggestionList", timeout=7000)
            suggestion_list = await page.query_selector(".Header-SuggestionList")

            results = await suggestion_list.query_selector_all("li.SuggestionList-Suggestion a.Suggestion-Link")

            for result in results:
                result_name_element = await result.query_selector(".Suggestion-Name")
                result_name = await result_name_element.inner_text()

                result_type_element = await result.query_selector(".Suggestion-Type")
                result_type = await result_type_element.inner_text()

                result_link = await result.get_attribute("href")
                
                if result_type == "Evento":
                    results_list.append((result_name, result_type, result_link))

            return {"results_list": results_list}
        except Exception as e:
            logger.error(f"Errore durante la ricerca: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
        finally:
            await browser.close()

@app.post("/write_to_searchbar_and_click_first_result", dependencies=[Depends(verify_api_key)])
async def write_to_searchbar_and_click_first_result(request: WriteToSearchbarRequest):
    search_text = request.search_text
    concert_list = []
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto("https://www.ticketone.it/")

            await page.wait_for_selector("#searchterm", timeout=15000)
            search_input = await page.query_selector("#searchterm")
            await search_input.fill("")
            await search_input.type(search_text)

            await asyncio.sleep(1)

            await page.wait_for_selector("#suggest-list", timeout=15000)
            suggestions = await page.query_selector("#suggest-list")

            first_result = await suggestions.query_selector('result-item a.as-result-link')
            if not first_result:
                logger.warning("Nessun risultato trovato nella ricerca")
                return {"concert_list": concert_list}

            await first_result.click()

            await page.wait_for_selector('article.listing-item', timeout=10000)
            concert_entries = await page.query_selector_all('article.listing-item')

            for entry in concert_entries:
                try:
                    date_element = await entry.query_selector('.event-listing-date')
                    month_year_element = await entry.query_selector('.event-listing-month')
                    date = f"{await date_element.inner_text()} {await month_year_element.inner_text()}"

                    city_element = await entry.query_selector('.event-listing-city')
                    city = await city_element.inner_text()

                    venue_element = await entry.query_selector('.event-listing-venue')
                    venue = await venue_element.inner_text()

                    location = f"{city}, {venue}"
                    if "PACKAGE" in location:
                        continue
                    
                    concert_list.append({
                        "date": date,
                        "location": location
                    })
                except Exception as e:
                    logger.error(f"Errore durante l'estrazione dei dati: {e}")
            print(concert_list)
            return {"concert_list": concert_list}
        except Exception as e:
            logger.error(f"Errore durante la ricerca del concerto: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
        finally:
            await browser.close()

@app.post("/search_tickets", dependencies=[Depends(verify_api_key)])
async def search_tickets(request: SearchTicketsRequest):
    url = request.url
    ticket_data = []
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url)

            await page.wait_for_selector('.js-EventEntry', timeout=10000)
            event_entries = await page.query_selector_all('.js-EventEntry')

            logger.info(f"Found {len(event_entries)} event entries")

            for entry in event_entries:
                entry_class = await entry.get_attribute('class')
                if 'hidden' not in entry_class.split():
                    try:
                        href = await entry.get_attribute('href')
                        logger.debug(f"Found href: {href}")

                        day_element = await entry.query_selector('.EvEntryRow-Day') or await entry.query_selector('.EvEntryRow-SubscriptionDateElement')
                        raw_day = await day_element.inner_text()
                        raw_day = raw_day.replace('\xa0', ' ').strip()

                        match = re.match(r'(\d{1,2})\.? (\w+) ?(\d{2})?', raw_day)
                        if match:
                            day = match.group(1)
                            month = match.group(2)
                            year = match.group(3)
                            if year:
                                full_year = f"20{year}"
                                formatted_date = f"{day} {month} {full_year}"
                            else:
                                formatted_date = f"{day} {month}"
                            logger.debug(f"Formatted day: {formatted_date}")
                        else:
                            formatted_date = raw_day

                        name_element = await entry.query_selector('.EvEntryRow-smallSubtitle')
                        name = await name_element.inner_text()

                        location_element = await entry.query_selector('.EvEntryRow-highlightedTitle')
                        location = await location_element.inner_text()
                        logger.debug(f"Extracted name: {name}, location: {location}")

                        price_element = await entry.query_selector('.EvEntryRow-moneyValueFormatSmall') or await entry.query_selector('.EvEntryRow-moneyValueFormat')
                        price = await price_element.inner_text()
                        logger.debug(f"Extracted price: {price}")

                        ticket_info = {
                            'day': formatted_date,
                            'location': location,
                            'price': price,
                        }
                        ticket_data.append(ticket_info)
                        logger.info(f"Extracted ticket info: {ticket_info}")

                    except Exception as e:
                        logger.error(f"Error durante data extraction: {e}")
            return {"ticket_data": ticket_data}
        except Exception as e:
            logger.error(f"Errore durante lo scraping dei biglietti: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
        finally:
            await browser.close()

@app.post("/match_tickets", dependencies=[Depends(verify_api_key)])
async def match_tickets(request: MatchTicketsRequest):
    tickets = request.tickets
    user_ticket = request.user_ticket
    matched_tickets = [ticket for ticket in tickets if ticket['day'] == user_ticket]
    return {"matched_tickets": matched_tickets}
