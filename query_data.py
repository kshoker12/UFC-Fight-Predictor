import json  # For output
import importlib.util
import re
from pathlib import Path

def load_scraper_simple():
    """
    Dynamically import functions from ufc-analytics-scraper-simple.py.
    (The file name contains hyphens, so we can't import it normally.)
    """
    script_path = Path(__file__).with_name("ufc-analytics-scraper-simple.py")
    spec = importlib.util.spec_from_file_location(
        "ufc_analytics_scraper_simple", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scraper = load_scraper_simple()


def get_upcoming_events():
    """Get list of upcoming UFC events using the simple scraper."""
    return scraper.get_upcoming_events()


def get_event_fights(event_url):
    """
    Get event data including all fights with fighter profiles using the simple scraper.
    
    Returns the complete event data structure with fights.
    """
    return scraper.get_event_data(event_url)


def sanitize_filename(name: str) -> str:
    """
    Convert event name to a safe filename by removing/replacing invalid characters.
    
    Args:
        name: Event name string
        
    Returns:
        Sanitized filename string
    """
    # Replace invalid filename characters with underscores
    # Windows: < > : " / \ | ? *
    # Unix/Linux: /
    # Also remove leading/trailing spaces and dots
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    sanitized = re.sub(r'\s+', '_', sanitized)  # Replace spaces with underscores
    sanitized = sanitized.strip('._')  # Remove leading/trailing dots and underscores
    return sanitized


if __name__ == "__main__":
    try:
        events = get_upcoming_events()[0:1]
        print(events)

        if not events:
            print(json.dumps({"error": "No upcoming events found"}, indent=4))
        else:
            for next_event in events:
                # Get complete event data with all fights and fighter profiles
                event_data = get_event_fights(next_event['link'])
                
                # Create events directory if it doesn't exist
                events_dir = Path(__file__).parent / 'events'
                events_dir.mkdir(exist_ok=True)
                
                # Sanitize event name for filename
                event_filename = sanitize_filename(event_data['name'])
                output_path = events_dir / f"{event_filename}.json"
                
                # Save to file
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(event_data, f, indent=4, ensure_ascii=False)
                
                print(f"Event data saved to: {output_path}")
                print(f"Event: {event_data['name']}")
                print(f"Date: {event_data['date']}")
                print(f"Location: {event_data['location']}")
                print(f"Number of fights: {len(event_data['fights'])}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
