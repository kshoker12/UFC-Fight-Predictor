import json  # For output
import importlib.util
from functools import lru_cache
from pathlib import Path

import requests
from bs4 import BeautifulSoup

def load_scraper_run():
    """
    Dynamically import the run() helper from ufc-analytics-scraper.py.
    (The file name contains hyphens, so we can't import it normally.)
    """
    script_path = Path(__file__).with_name("ufc-analytics-scraper.py")
    spec = importlib.util.spec_from_file_location(
        "ufc_analytics_scraper", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


run_scraper = load_scraper_run()


@lru_cache(maxsize=32)
def get_fighter_dataset(fighter_name: str):
    """
    Return the full fight dataset for a fighter as a list of dicts.
    """
    try:
        df = run_scraper(fighter_name)
        return df.to_dict(orient="records")
    except Exception as exc:
        return {
            "error": f"Failed to fetch data for {fighter_name}",
            "details": str(exc),
        }


def get_upcoming_events():
    url = "http://ufcstats.com/statistics/events/upcoming"
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    events = []
    table = soup.find('table', class_='b-statistics__table-events')
    if table:
        rows = table.find_all('tr', class_='b-statistics__table-row')
        for row in rows:
            event_link = row.find('a', class_='b-link')
            if event_link:
                name = event_link.text.strip()
                date_td = row.find('span', class_='b-statistics__date')
                date = date_td.text.strip() if date_td else 'N/A'
                location_td = row.find_all('td')[-1]
                location = location_td.text.strip() if location_td else 'N/A'
                events.append({
                    'name': name,
                    'date': date,
                    'location': location,
                    'link': event_link['href']
                })
    return events

def get_event_fights(event_url):
    response = requests.get(event_url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    fights = []
    fight_rows = soup.find_all('tr', class_='b-fight-details__table-row')
    for row in fight_rows:
        fighters = row.find_all('p', class_='b-fight-details__table-text')
        if len(fighters) >= 2:
            fighter_a = fighters[0].text.strip()
            fighter_b = fighters[1].text.strip()
            fights.append({
                'fighter_a': {
                    'name': fighter_a,
                    'dataset': get_fighter_dataset(fighter_a)
                },
                'fighter_b': {
                    'name': fighter_b,
                    'dataset': get_fighter_dataset(fighter_b)
                },
            })
    return fights

if __name__ == "__main__":
    try:
        events = get_upcoming_events()
        if not events:
            print(json.dumps({"error": "No upcoming events found"}, indent=4))
        else:
            next_event = events[0]
            next_event['fights'] = get_event_fights(next_event['link'])
            # Pretty-print or save
            print(json.dumps(next_event, indent=4))
    except Exception as e:
        print(f"Error: {e}")