"""
Simplified UFC Analytics Scraper

This scraper only extracts the essential data needed for fight predictions:
- Fighter profile data (height, weight, reach, stance, DOB, career stats)
- Win/loss/draw record
- Match-specific data (title_fight, division, event info)
"""

import requests
from bs4 import BeautifulSoup
from difflib import get_close_matches
import time as sleeptime
import re


def search_fighter_by_name_part(query):
    """Search for fighters by name part."""
    url = "http://ufcstats.com/statistics/fighters/search"
    params = {"query": query}
    response = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', class_='b-statistics__table')
    if not table:
        return []
    rows = table.find('tbody').find_all('tr', class_='b-statistics__table-row')
    candidates = []
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 2:
            continue
        first_name_col = cols[0].find('a', class_='b-link_style_black')
        last_name_col = cols[1].find('a', class_='b-link_style_black')
        if not first_name_col or not last_name_col:
            continue
        first_name = first_name_col.get_text(strip=True)
        last_name = last_name_col.get_text(strip=True)
        fighter_link = last_name_col['href']
        full_name = f"{first_name} {last_name}".strip()
        candidates.append((full_name, fighter_link))
    return candidates


def get_fighter_url_by_name(fighter_name):
    """Get fighter URL by name."""
    name_parts = fighter_name.strip().split()
    fighter_name_clean = fighter_name.strip().lower()
    print(f"    Searching for fighter: {fighter_name}")

    if len(name_parts) > 1:
        last_name = name_parts[-1]
        first_name = name_parts[0]
        full_name = fighter_name.strip()
        
        # Strategy 1: Try searching with full name first (most specific)
        candidates = search_fighter_by_name_part(full_name)
        if candidates:
            # Check for exact match
            for c in candidates:
                if c[0].strip().lower() == fighter_name_clean:
                    print(f"    ✓ Exact match found (full name search): {c[0]}")
                    return c[1]
            # If full name search returned results but no exact match, use first one
            print(f"    ✓ Using result from full name search: {candidates[0][0]}")
            return candidates[0][1]
        
        # Strategy 2: Try first name (usually more unique than last name)
        candidates = search_fighter_by_name_part(first_name)
        if candidates:
            # Try exact match first
            for c in candidates:
                if c[0].strip().lower() == fighter_name_clean:
                    print(f"    ✓ Exact match found (first name search): {c[0]}")
                    return c[1]
            # Use get_close_matches with higher cutoff for first name results
            all_names = [c[0].lower() for c in candidates]
            close = get_close_matches(fighter_name_clean, all_names, n=1, cutoff=0.7)
            if close:
                best = close[0]
                for c in candidates:
                    if c[0].lower() == best:
                        print(f"    ✓ Close match found (first name search): {c[0]}")
                        return c[1]
        
        # Strategy 3: Try last name (less specific, so use higher cutoff)
        candidates = search_fighter_by_name_part(last_name)
        if candidates:
            # Try exact match first
            for c in candidates:
                if c[0].strip().lower() == fighter_name_clean:
                    print(f"    ✓ Exact match found (last name search): {c[0]}")
                    return c[1]
            # Use get_close_matches with higher cutoff (0.8) for last name since it's less specific
            all_names = [c[0].lower() for c in candidates]
            close = get_close_matches(fighter_name_clean, all_names, n=1, cutoff=0.8)
            if close:
                best = close[0]
                for c in candidates:
                    if c[0].lower() == best:
                        print(f"    ✓ Close match found (last name search): {c[0]}")
                        return c[1]
        
        # If we still have candidates from last name search, warn and use best match
        if candidates:
            print(f"    ⚠ No close match found, using first candidate from last name search: {candidates[0][0]}")
            return candidates[0][1]
        
        raise ValueError(f"No suitable match found for fighter: {fighter_name_clean}")
    else:
        query = name_parts[0]
        candidates = search_fighter_by_name_part(query)
        if not candidates:
            raise ValueError(f"No suitable match found for fighter: {fighter_name_clean}")
        
        # Try exact match first
        for c in candidates:
            if c[0].lower() == fighter_name_clean:
                print(f"    ✓ Exact match found: {c[0]}")
                return c[1]
        
        all_names = [c[0].lower() for c in candidates]
        close = get_close_matches(fighter_name_clean, all_names, n=1, cutoff=0.7)
        if close:
            best = close[0]
            for c in candidates:
                if c[0].lower() == best:
                    print(f"    ✓ Close match found: {c[0]}")
                    return c[1]
        
        print(f"    ⚠ No close match found, using first candidate: {candidates[0][0]}")
        return candidates[0][1]


def extract_fighter_profile(fighter_url):
    """
    Extract fighter profile data from the fighter details page.
    
    Returns a dictionary with:
    - height: Height in inches (converted from feet'inches format)
    - weight: Weight in lbs
    - reach: Reach in inches
    - stance: Stance (Orthodox/Southpaw/Switch)
    - dob: Date of birth as string
    - career_splm: Significant Strikes Landed per Minute
    - career_str_acc: Striking Accuracy %
    - career_sapm: Significant Strikes Absorbed per Minute
    - career_str_def: Strike Defense %
    - career_td_avg: Takedown Average per 15 min
    - career_td_acc: Takedown Accuracy %
    - career_td_def: Takedown Defense %
    - career_sub_avg: Submission Average per 15 min
    """
    print(f"  Fetching fighter profile from: {fighter_url}")
    response = requests.get(fighter_url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    profile = {}
    
    # Extract profile info (Height, Weight, Reach, Stance, DOB)
    info_items = soup.find_all('li', class_='b-list__box-list-item')
    for item in info_items:
        text = item.get_text(strip=True)
        if not text:
            continue
        
        # Parse Height (e.g., "Height:6' 3"")
        if text.startswith('Height:'):
            height_str = text.replace('Height:', '').strip()
            # Convert feet'inches to inches
            if "'" in height_str:
                parts = height_str.replace('"', '').split("'")
                if len(parts) == 2:
                    try:
                        feet = int(parts[0].strip())
                        inches = int(parts[1].strip())
                        profile['height'] = feet * 12 + inches
                    except:
                        profile['height'] = None
            else:
                profile['height'] = None
        
        # Parse Weight (e.g., "Weight:170 lbs.")
        elif text.startswith('Weight:'):
            weight_str = text.replace('Weight:', '').replace('lbs.', '').strip()
            try:
                profile['weight'] = float(weight_str)
            except:
                profile['weight'] = None
        
        # Parse Reach (e.g., "Reach:74"")
        elif text.startswith('Reach:'):
            reach_str = text.replace('Reach:', '').replace('"', '').strip()
            try:
                profile['reach'] = float(reach_str)
            except:
                profile['reach'] = None
        
        # Parse Stance (e.g., "STANCE:Orthodox")
        elif text.startswith('STANCE:'):
            profile['stance'] = text.replace('STANCE:', '').strip()
        
        # Parse DOB (e.g., "DOB:Nov 17, 1997")
        elif text.startswith('DOB:'):
            profile['dob'] = text.replace('DOB:', '').strip()
        
        # Parse Career Stats
        elif text.startswith('SLpM:'):
            try:
                profile['career_splm'] = float(text.replace('SLpM:', '').strip())
            except:
                profile['career_splm'] = None
        elif text.startswith('Str. Acc.:'):
            try:
                acc_str = text.replace('Str. Acc.:', '').replace('%', '').strip()
                profile['career_str_acc'] = float(acc_str)
            except:
                profile['career_str_acc'] = None
        elif text.startswith('SApM:'):
            try:
                profile['career_sapm'] = float(text.replace('SApM:', '').strip())
            except:
                profile['career_sapm'] = None
        elif text.startswith('Str. Def:'):
            try:
                def_str = text.replace('Str. Def:', '').replace('%', '').strip()
                profile['career_str_def'] = float(def_str)
            except:
                profile['career_str_def'] = None
        elif text.startswith('TD Avg.:'):
            try:
                profile['career_td_avg'] = float(text.replace('TD Avg.:', '').strip())
            except:
                profile['career_td_avg'] = None
        elif text.startswith('TD Acc.:'):
            try:
                acc_str = text.replace('TD Acc.:', '').replace('%', '').strip()
                profile['career_td_acc'] = float(acc_str)
            except:
                profile['career_td_acc'] = None
        elif text.startswith('TD Def.:'):
            try:
                def_str = text.replace('TD Def.:', '').replace('%', '').strip()
                profile['career_td_def'] = float(def_str)
            except:
                profile['career_td_def'] = None
        elif text.startswith('Sub. Avg.:'):
            try:
                profile['career_sub_avg'] = float(text.replace('Sub. Avg.:', '').strip())
            except:
                profile['career_sub_avg'] = None
    
    # Print summary of extracted profile
    if profile:
        print(f"    ✓ Extracted profile: height={profile.get('height')}, weight={profile.get('weight')}, reach={profile.get('reach')}, stance={profile.get('stance')}")
        print(f"    ✓ Career stats: SLpM={profile.get('career_splm')}, Str.Acc={profile.get('career_str_acc')}, SApM={profile.get('career_sapm')}, Str.Def={profile.get('career_str_def')}")
    else:
        print(f"    ⚠ No profile data extracted")
    
    return profile


def extract_fighter_record(fighter_url):
    """
    Extract win/loss/draw record from fighter page.
    
    First tries to extract from page header (e.g., "Record: 19-5-0"),
    then falls back to counting from fight history table.
    
    Returns tuple (wins, losses, draws)
    """
    response = requests.get(fighter_url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    wins = 0
    losses = 0
    draws = 0
    
    # Try to extract record from page header first (more accurate)
    header = soup.find('h2', class_='b-content__title')
    if header:
        header_text = header.get_text(strip=True)
        # Look for "Record: X-Y-Z" pattern
        record_match = re.search(r'Record:\s*(\d+)-(\d+)-(\d+)', header_text, re.IGNORECASE)
        if record_match:
            wins = int(record_match.group(1))
            losses = int(record_match.group(2))
            draws = int(record_match.group(3))
            print(f"    ✓ Record from page header: {wins}W-{losses}L-{draws}D")
            return wins, losses, draws
    
    # Fall back to counting from fight history table
    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        print(f"    ⚠ No fight history table found")
        return wins, losses, draws
    
    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    print(f"    Analyzing {len(rows)} fights for record (counting from table)...")
    for row in rows:
        cols = row.find_all('td', class_='b-fight-details__table-col')
        if len(cols) < 1:
            continue
        
        result_tag = cols[0].find('p', class_='b-fight-details__table-text')
        if result_tag:
            result = result_tag.get_text(strip=True).lower()
            # Skip upcoming fights (marked as 'next')
            if result == 'next':
                continue
            if result == 'win':
                wins += 1
            elif result == 'loss':
                losses += 1
            elif result in ['draw', 'nc', 'no contest']:
                draws += 1
    
    print(f"    ✓ Record (from table count): {wins}W-{losses}L-{draws}D")
    return wins, losses, draws


def count_ufc_fights(fighter_url):
    """
    Count the number of completed UFC fights for a fighter.
    
    Returns the number of completed UFC fights (excluding upcoming fights).
    """
    response = requests.get(fighter_url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        return 0
    
    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    fight_count = 0
    for row in rows:
        cols = row.find_all('td', class_='b-fight-details__table-col')
        if len(cols) < 1:
            continue
        
        result_tag = cols[0].find('p', class_='b-fight-details__table-text')
        if result_tag:
            result = result_tag.get_text(strip=True).lower()
            # Skip upcoming fights (marked as 'next')
            if result != 'next':
                fight_count += 1
    
    return fight_count


def extract_fighter_finish_rates(fighter_url):
    """
    Extract KO and submission rates from fighter's fight history.
    
    Returns dictionary with:
    - ko_rate: Percentage of wins by KO/TKO
    - sub_rate: Percentage of wins by submission
    - total_fights: Total number of completed fights
    - total_wins: Total number of wins
    """
    response = requests.get(fighter_url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        print(f"    ⚠ No fight history table found for finish rates")
        return {'ko_rate': 0.0, 'sub_rate': 0.0, 'total_fights': 0, 'total_wins': 0}
    
    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    
    total_fights = 0
    total_wins = 0
    ko_wins = 0
    sub_wins = 0
    
    for row in rows:
        cols = row.find_all('td', class_='b-fight-details__table-col')
        if len(cols) < 8:  # Need at least result and method columns
            continue
        
        # Column 0: Result (win/loss/draw/next)
        result_tag = cols[0].find('p', class_='b-fight-details__table-text')
        if not result_tag:
            continue
            
        result = result_tag.get_text(strip=True).lower()
        
        # Skip upcoming fights
        if result == 'next':
            continue
            
        total_fights += 1
        
        # Only count wins for finish rate calculation
        if result != 'win':
            continue
            
        total_wins += 1
        
        # Column 7: Method (how the fight ended)
        method_tag = cols[7].find('p', class_='b-fight-details__table-text')
        if not method_tag:
            continue
            
        method = method_tag.get_text(strip=True).lower()
        
        # Check for KO/TKO
        if any(ko_term in method for ko_term in ['ko', 'tko', 'knockout', 'technical knockout']):
            ko_wins += 1
        # Check for submission
        elif 'submission' in method or 'sub' in method:
            sub_wins += 1
    
    # Calculate rates
    ko_rate = (ko_wins / total_wins) if total_wins > 0 else 0.0
    sub_rate = (sub_wins / total_wins) if total_wins > 0 else 0.0
    
    print(f"    ✓ Finish rates: {ko_wins} KOs, {sub_wins} subs out of {total_wins} wins ({total_fights} total fights)")
    print(f"    ✓ KO rate: {ko_rate:.2%}, Sub rate: {sub_rate:.2%}")
    
    return {
        'ko_rate': round(ko_rate, 4),
        'sub_rate': round(sub_rate, 4),
        'total_fights': total_fights,
        'total_wins': total_wins
    }


def get_specific_fighter_momentum(fighter_url):
    """
    Compute the number of wins in a fighter's last 3 fights.
    
    Returns:
    - Number of wins in last 3 fights (0-3), or None if fighter has less than 3 fights
    """
    response = requests.get(fighter_url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    table = soup.find('table', class_='b-fight-details__table_type_event-details')
    if not table:
        print(f"    ⚠ No fight history table found for momentum")
        return None
    
    rows = table.find('tbody').find_all('tr', class_='b-fight-details__table-row__hover')
    
    # Get completed fights (excluding upcoming fights marked as 'next')
    completed_fights = []
    for row in rows:
        cols = row.find_all('td', class_='b-fight-details__table-col')
        if len(cols) < 1:
            continue
        
        result_tag = cols[0].find('p', class_='b-fight-details__table-text')
        if not result_tag:
            continue
            
        result = result_tag.get_text(strip=True).lower()
        
        # Skip upcoming fights
        if result == 'next':
            continue
            
        completed_fights.append(result)
    
    # Check if fighter has at least 3 completed fights
    if len(completed_fights) < 3:
        print(f"    ⚠ Fighter has only {len(completed_fights)} completed fights (< 3), momentum = None")
        return None
    
    # Get last 3 fights (most recent first in the table)
    last_3_fights = completed_fights[:3]
    
    # Count wins in last 3 fights
    wins_in_last_3 = sum(1 for result in last_3_fights if result == 'win')
    
    print(f"    ✓ Momentum: {wins_in_last_3}/3 wins in last 3 fights ({', '.join(last_3_fights)})")
    
    return wins_in_last_3


def clean_career_stats_for_new_fighters(profile, ufc_fight_count):
    """
    For fighters with less than 3 UFC fights, replace 0 values in career stats with None.
    
    This is because 0 likely means "no data" rather than "actually 0" for new fighters,
    and the imputer should use the dataset average instead.
    
    Args:
        profile: Dictionary with career stats
        ufc_fight_count: Number of UFC fights the fighter has
    
    Returns:
        Modified profile dictionary
    """
    if ufc_fight_count >= 3:
        return profile
    
    # List of career stat keys to check
    career_stat_keys = [
        'career_splm', 'career_str_acc', 'career_sapm', 'career_str_def',
        'career_td_avg', 'career_td_acc', 'career_td_def', 'career_sub_avg'
    ]
    
    # Replace 0 values with None for fighters with < 3 UFC fights
    cleaned_count = 0
    for key in career_stat_keys:
        if key in profile and profile[key] == 0:
            profile[key] = None
            cleaned_count += 1
    
    if cleaned_count > 0:
        print(f"    ⚠ Fighter has {ufc_fight_count} UFC fights (< 3), replaced {cleaned_count} zero career stats with None")
    
    return profile


def get_fighter_data_from_url(fighter_url, fighter_name=None):
    """
    Get complete fighter data directly from fighter URL.
    
    Args:
        fighter_url: Direct URL to fighter page
        fighter_name: Optional fighter name (extracted from page if not provided)
    
    Returns dictionary with:
    - name: Fighter name
    - profile: Profile data (height, weight, reach, stance, DOB, career stats)
    - wins: Number of wins
    - losses: Number of losses
    - draws: Number of draws
    """
    if fighter_name:
        print(f"\n  Getting data for fighter: {fighter_name}")
    else:
        print(f"\n  Getting data from URL: {fighter_url}")
    
    print(f"  ✓ Using fighter URL: {fighter_url}")
    
    # Extract name from page if not provided
    if not fighter_name:
        try:
            response = requests.get(fighter_url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            header = soup.find('h2', class_='b-content__title')
            if header:
                header_text = header.get_text(strip=True)
                # Extract name (everything before "Record:")
                name_match = re.search(r'^(.+?)\s*Record:', header_text)
                if name_match:
                    fighter_name = name_match.group(1).strip()
                    print(f"  ✓ Extracted name: {fighter_name}")
        except Exception as e:
            print(f"  ⚠ Could not extract name from page: {e}")
            fighter_name = "Unknown"
    
    profile = extract_fighter_profile(fighter_url)
    wins, losses, draws = extract_fighter_record(fighter_url)
    
    # Extract finish rates from fight history
    finish_rates = extract_fighter_finish_rates(fighter_url)
    
    # Extract momentum (wins in last 3 fights)
    momentum = get_specific_fighter_momentum(fighter_url)
    
    # Count UFC fights and clean career stats if fighter has < 3 fights
    ufc_fight_count = count_ufc_fights(fighter_url)
    profile = clean_career_stats_for_new_fighters(profile, ufc_fight_count)
    
    print(f"  ✓ Completed data extraction for {fighter_name}")
    return {
        'name': fighter_name,
        'profile': profile,
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'ko_rate': finish_rates['ko_rate'],
        'sub_rate': finish_rates['sub_rate'],
        'momentum': momentum
    }


def get_fighter_data(fighter_name):
    """
    Get complete fighter data including profile and record by searching for fighter name.
    
    NOTE: For more accurate results, use get_fighter_data_from_url() with a direct URL
    from the event page.
    
    Returns dictionary with:
    - name: Fighter name
    - profile: Profile data (height, weight, reach, stance, DOB, career stats)
    - wins: Number of wins
    - losses: Number of losses
    - draws: Number of draws
    """
    print(f"\n  Getting data for fighter: {fighter_name}")
    try:
        fighter_url = get_fighter_url_by_name(fighter_name)
        print(f"  ✓ Found fighter URL: {fighter_url}")
    except ValueError as e:
        print(f"  ✗ Error finding fighter: {e}")
        return {
            'name': fighter_name,
            'error': str(e),
            'profile': {},
            'wins': 0,
            'losses': 0,
            'draws': 0,
            'ko_rate': 0.0,
            'sub_rate': 0.0,
            'momentum': None
        }
    
    profile = extract_fighter_profile(fighter_url)
    wins, losses, draws = extract_fighter_record(fighter_url)
    
    # Extract finish rates from fight history
    finish_rates = extract_fighter_finish_rates(fighter_url)
    
    # Extract momentum (wins in last 3 fights)
    momentum = get_specific_fighter_momentum(fighter_url)
    
    # Count UFC fights and clean career stats if fighter has < 3 fights
    ufc_fight_count = count_ufc_fights(fighter_url)
    profile = clean_career_stats_for_new_fighters(profile, ufc_fight_count)
    
    print(f"  ✓ Completed data extraction for {fighter_name}")
    return {
        'name': fighter_name,
        'profile': profile,
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'ko_rate': finish_rates['ko_rate'],
        'sub_rate': finish_rates['sub_rate'],
        'momentum': momentum
    }


def get_upcoming_events():
    """Get list of upcoming UFC events."""
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


def get_past_events():
    """Get list of past/completed UFC events."""
    url = "http://ufcstats.com/statistics/events/completed"
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


def is_title_fight(fight_text):
    """
    Determine if a fight is a title fight based on fight description.
    
    Checks for keywords like "Title", "Championship", "Belt", "Interim", etc.
    """
    if not fight_text:
        return False
    
    fight_lower = fight_text.lower()
    title_keywords = [
        'title', 'championship', 'champion', 'belt', 'interim',
        'title fight', 'title bout', 'championship bout'
    ]
    
    return any(keyword in fight_lower for keyword in title_keywords)




def get_event_fights(event_url):
    """
    Extract fight data from event page, including fighter URLs.
    
    Returns list of fights with:
    - fighter_a: Fighter A name
    - fighter_b: Fighter B name
    - fighter_a_url: Fighter A URL (for direct access)
    - fighter_b_url: Fighter B URL (for direct access)
    - division: Weight class
    - title_fight: Boolean indicating if it's a title fight
    """
    print(f"\nExtracting fight data from event page...")
    print(f"Event URL: {event_url}")
    response = requests.get(event_url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    fights = []
    fight_rows = soup.find_all('tr', class_='b-fight-details__table-row')
    print(f"Found {len(fight_rows)} rows in fight table")
    
    for row in fight_rows:
        # Skip header row (first row)
        if not row.get('class') or 'b-fight-details__table-row__hover' not in row.get('class', []):
            continue
        
        # Get all table cells
        cells = row.find_all('td', class_='b-fight-details__table-col')
        if len(cells) < 2:
            continue
        
        # Fighter names and URLs are in the second cell (index 1)
        # First cell (index 0) is W/L result (or "next" for upcoming bouts)
        fighter_cell = cells[1] if len(cells) > 1 else cells[0]
        result_cell_text = ""
        if len(cells) > 0:
            try:
                result_tag = cells[0].find('p', class_='b-fight-details__table-text')
                if result_tag:
                    result_cell_text = result_tag.get_text(strip=True)
                else:
                    result_cell_text = cells[0].get_text(" ", strip=True)
            except Exception:
                result_cell_text = cells[0].get_text(" ", strip=True)
        
        # Extract fighter links (more reliable than text)
        fighter_links = fighter_cell.find_all('a', class_='b-link_style_black')
        
        if len(fighter_links) >= 2:
            fighter_a_link = fighter_links[0]
            fighter_b_link = fighter_links[1]
            
            fighter_a = fighter_a_link.text.strip()
            fighter_a_url = fighter_a_link['href']
            fighter_b = fighter_b_link.text.strip()
            fighter_b_url = fighter_b_link['href']
        else:
            # Fallback to text extraction if links not found
            fighters = fighter_cell.find_all('p', class_='b-fight-details__table-text')
            if len(fighters) >= 2:
                fighter_a = fighters[0].text.strip()
                fighter_b = fighters[1].text.strip()
                fighter_a_url = None
                fighter_b_url = None
            else:
                continue
            
        # Get division from weight class cell (typically cell 6)
        division = 'unknown'
        if len(cells) > 6:
            weight_class_cell = cells[6]
            weight_class_text = weight_class_cell.get_text(strip=True)
            division = extract_division_from_fight_text(weight_class_text)
        
        # Get fight description/name to check for title fight
        # Look for link in fighter cell
        fight_link = fighter_cell.find('a', class_='b-link_style_black')
        fight_description = ''
        if fight_link:
            fight_description = fight_link.text.strip()
        
        # Also check division text and row text for title indicators
        row_text = row.get_text(' ', strip=True)
        
        # Check for belt icon image (most reliable indicator of title fight)
        has_belt_icon = False
        images = row.find_all('img')
        for img in images:
            img_src = img.get('src', '').lower()
            img_alt = img.get('alt', '').lower()
            if 'belt' in img_src or 'belt' in img_alt:
                has_belt_icon = True
                break
        
        # Determine if title fight (check belt icon first, then text keywords)
        title_fight = (has_belt_icon or 
                      is_title_fight(fight_description) or 
                      is_title_fight(row_text) or 
                      is_title_fight(division))

        # Extract the winner for this bout.
        # - Upcoming fights have "next" in the W/L cell.
        # - Draw/no-contest cases are treated as "Draw".
        winner = None
        result_norm = (result_cell_text or "").strip().lower()
        if not result_norm or "next" in result_norm:
            winner = None
        elif result_norm in {"w", "win"} or "win" in result_norm:
            winner = fighter_a
        elif result_norm in {"l", "loss"} or "loss" in result_norm:
            winner = fighter_b
        elif (
            "draw" in result_norm
            or "nc" in result_norm
            or "no contest" in result_norm
            or "no-contest" in result_norm
        ):
            winner = "Draw"
        else:
            # If UFCStats uses an unexpected token that is not "next" and not win/loss,
            # treat it as a no-winner outcome.
            winner = "Draw"
        
        fights.append({
            'fighter_a': fighter_a,
            'fighter_b': fighter_b,
            'fighter_a_url': fighter_a_url,
            'fighter_b_url': fighter_b_url,
            'division': division,
            'title_fight': 1 if title_fight else 0,
            'fight_description': fight_description,
            'winner': winner,
        })
        print(f"  ✓ Fight {len(fights)}: {fighter_a} vs {fighter_b} ({division})" + (" [TITLE FIGHT]" if title_fight else ""))
        if fighter_a_url and fighter_b_url:
            print(f"    URLs: {fighter_a_url} | {fighter_b_url}")
    
    print(f"\n✓ Extracted {len(fights)} fights from event page")
    return fights


def extract_division_from_fight_text(text):
    """Extract division from text."""
    if not text:
        return 'unknown'
    
    weight_classes = [
        'strawweight', 'flyweight', 'bantamweight', 'featherweight',
        'lightweight', 'welterweight', 'middleweight', 'light heavyweight',
        'heavyweight', 'women\'s strawweight', 'women\'s flyweight',
        'women\'s bantamweight', 'women\'s featherweight'
    ]
    
    text_lower = text.lower()
    for wc in weight_classes:
        if wc in text_lower:
            return wc
    
    return 'unknown'


def get_event_data(event_url):
    """
    Get complete event data including all fights with fighter profiles.
    
    Returns dictionary with format matching what transform_event_data.py expects:
    - name: Event name
    - date: Event date
    - location: Event location
    - link: Event URL
    - fights: List of fights with fighter data in format:
        - fighter_a: dict with 'name' and 'dataset' (list with profile data)
        - fighter_b: dict with 'name' and 'dataset' (list with profile data)
        - division: Weight class
        - title_fight: 0 or 1
    """
    print("\n" + "=" * 80)
    print("GETTING EVENT DATA")
    print("=" * 80)
    print(f"Event URL: {event_url}")
    
    response = requests.get(event_url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract event metadata
    event_name = soup.find('h2', class_='b-content__title')
    event_name = event_name.text.strip() if event_name else 'Unknown Event'
    print(f"\nEvent: {event_name}")
    
    # Extract date and location
    event_info_items = soup.find_all('li', class_='b-list__box-list-item')
    event_date = 'N/A'
    event_location = 'N/A'
    for item in event_info_items:
        text = item.get_text(strip=True)
        if 'Date:' in text:
            event_date = text.replace('Date:', '').strip()
        elif 'Location:' in text:
            event_location = text.replace('Location:', '').strip()
    
    print(f"Date: {event_date}")
    print(f"Location: {event_location}")
    
    # Get fights
    fights_data = get_event_fights(event_url)
    
    # Add fighter profile data to each fight in the expected format
    print(f"\n" + "=" * 80)
    print(f"EXTRACTING FIGHTER PROFILES FOR {len(fights_data)} FIGHTS")
    print("=" * 80)
    formatted_fights = []
    for idx, fight in enumerate(fights_data, 1):
        print(f"\n[{idx}/{len(fights_data)}] Processing fight: {fight['fighter_a']} vs {fight['fighter_b']}")
        print(f"  Division: {fight.get('division', 'unknown')}, Title fight: {fight.get('title_fight', 0)}")
        
        # Get fighter A data - use URL if available (more accurate), otherwise search by name
        print(f"\n  Fighter A:")
        sleeptime.sleep(0.5)  # Rate limiting
        if fight.get('fighter_a_url'):
            fighter_a_data = get_fighter_data_from_url(fight['fighter_a_url'], fight['fighter_a'])
        else:
            fighter_a_data = get_fighter_data(fight['fighter_a'])
        
        # Get fighter B data - use URL if available (more accurate), otherwise search by name
        print(f"\n  Fighter B:")
        sleeptime.sleep(0.5)  # Rate limiting
        if fight.get('fighter_b_url'):
            fighter_b_data = get_fighter_data_from_url(fight['fighter_b_url'], fight['fighter_b'])
        else:
            fighter_b_data = get_fighter_data(fight['fighter_b'])
        
        # Format to match expected structure
        # The 'dataset' should be a list, and we put the profile data in the first item
        # This matches the format expected by transform_event_data.py
        # Include all profile fields and career stats
        fighter_a_profile = fighter_a_data.get('profile', {})
        fighter_a_dataset = [{
            'height': fighter_a_profile.get('height'),
            'weight': fighter_a_profile.get('weight'),
            'reach': fighter_a_profile.get('reach'),
            'stance': fighter_a_profile.get('stance'),
            'dob': fighter_a_profile.get('dob'),
            'wins': fighter_a_data.get('wins', 0),
            'losses': fighter_a_data.get('losses', 0),
            'draws': fighter_a_data.get('draws', 0),
            'career_splm': fighter_a_profile.get('career_splm'),
            'career_str_acc': fighter_a_profile.get('career_str_acc'),
            'career_sapm': fighter_a_profile.get('career_sapm'),
            'career_str_def': fighter_a_profile.get('career_str_def'),
            'career_td_avg': fighter_a_profile.get('career_td_avg'),
            'career_td_acc': fighter_a_profile.get('career_td_acc'),
            'career_td_def': fighter_a_profile.get('career_td_def'),
            'career_sub_avg': fighter_a_profile.get('career_sub_avg'),
            'ko_rate': fighter_a_data.get('ko_rate', 0.0),
            'sub_rate': fighter_a_data.get('sub_rate', 0.0),
            'momentum': fighter_a_data.get('momentum'),
            'result': 'win'  # Placeholder for upcoming fights
        }]
        
        fighter_b_profile = fighter_b_data.get('profile', {})
        fighter_b_dataset = [{
            'height': fighter_b_profile.get('height'),
            'weight': fighter_b_profile.get('weight'),
            'reach': fighter_b_profile.get('reach'),
            'stance': fighter_b_profile.get('stance'),
            'dob': fighter_b_profile.get('dob'),
            'wins': fighter_b_data.get('wins', 0),
            'losses': fighter_b_data.get('losses', 0),
            'draws': fighter_b_data.get('draws', 0),
            'career_splm': fighter_b_profile.get('career_splm'),
            'career_str_acc': fighter_b_profile.get('career_str_acc'),
            'career_sapm': fighter_b_profile.get('career_sapm'),
            'career_str_def': fighter_b_profile.get('career_str_def'),
            'career_td_avg': fighter_b_profile.get('career_td_avg'),
            'career_td_acc': fighter_b_profile.get('career_td_acc'),
            'career_td_def': fighter_b_profile.get('career_td_def'),
            'career_sub_avg': fighter_b_profile.get('career_sub_avg'),
            'ko_rate': fighter_b_data.get('ko_rate', 0.0),
            'sub_rate': fighter_b_data.get('sub_rate', 0.0),
            'momentum': fighter_b_data.get('momentum'),
            'result': 'win'  # Placeholder for upcoming fights
        }]
        
        formatted_fights.append({
            'fighter_a': {
                'name': fight['fighter_a'],
                'dataset': fighter_a_dataset
            },
            'fighter_b': {
                'name': fight['fighter_b'],
                'dataset': fighter_b_dataset
            },
            'division': fight.get('division', 'unknown'),
            'title_fight': fight.get('title_fight', 0),
            'fight_description': fight.get('fight_description', ''),
            'winner': fight.get('winner', None),
        })
        print(f"  ✓ Completed fight {idx}/{len(fights_data)}")
    
    print(f"\n" + "=" * 80)
    print(f"✓ COMPLETED: Extracted data for {len(formatted_fights)} fights")
    print("=" * 80)
    
    return {
        'name': event_name,
        'date': event_date,
        'location': event_location,
        'link': event_url,
        'fights': formatted_fights
    }


if __name__ == "__main__":
    # Example usage
    import json
    
    events = get_upcoming_events()
    if events:
        next_event = events[0]
        print(f"Fetching data for: {next_event['name']}")
        event_data = get_event_data(next_event['link'])
        print(json.dumps(event_data, indent=2, default=str))
    else:
        print("No upcoming events found")

