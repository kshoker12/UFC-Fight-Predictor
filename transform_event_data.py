"""
Transform Event JSON Data to UFC.csv Format

This module transforms JSON event data from the events folder into a DataFrame
matching the UFC.csv format with all required feature engineering steps.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd


def transform_event_to_ufc_format(event_json_path: Union[str, Path]) -> pd.DataFrame:
    """
    Transform JSON event data to UFC.csv format DataFrame.
    
    Args:
        event_json_path: Path to JSON file in events folder
        
    Returns:
        DataFrame with UFC.csv format columns
    """
    # Load JSON data
    with open(event_json_path, 'r', encoding='utf-8') as f:
        event_data = json.load(f)
    
    # Parse event data
    event_name = event_data.get('name', '')
    event_date = event_data.get('date', '')
    event_location = event_data.get('location', '')
    event_link = event_data.get('link', '')
    fights = event_data.get('fights', [])
    
    # Generate event_id and fight_id from link
    event_id = extract_id_from_url(event_link) if event_link else ''
    
    # Process each fight
    fight_rows = []
    for fight_idx, fight in enumerate(fights):
        fighter_a = fight.get('fighter_a', {})
        fighter_b = fight.get('fighter_b', {})
        
        # Get division and title_fight from fight data if available
        division = fight.get('division', 'unknown') if isinstance(fight, dict) else 'unknown'
        title_fight = fight.get('title_fight', 0) if isinstance(fight, dict) else 0
        
        # Extract fighter data
        fighter_a_data = extract_fighter_data(
            fighter_a, 
            fighter_b, 
            'a',
            event_date
        )
        fighter_b_data = extract_fighter_data(
            fighter_b,
            fighter_a,
            'b',
            event_date
        )
        
        # Combine into fight row
        # Include columns needed for feature engineering, plus metadata
        
        fight_row = {
            'date': event_date,  # Needed for age calculation, then dropped
            'division': division,  # Needed for normalization, then dropped
            'title_fight': title_fight,  # Kept after feature engineering
            'event_name': event_name,  # Metadata, not a feature
            'r_name': fighter_a.get('name', '') if isinstance(fighter_a, dict) else '',  # Metadata, not a feature
            'b_name': fighter_b.get('name', '') if isinstance(fighter_b, dict) else '',  # Metadata, not a feature
            **fighter_a_data,
            **fighter_b_data,
        }
        
        fight_rows.append(fight_row)
    
    # Create DataFrame
    df = pd.DataFrame(fight_rows)
    
    # Apply feature engineering
    df = apply_feature_engineering(df)
    
    return df


def transform_matchup_to_features(
    fighter_a: Dict,
    fighter_b: Dict,
    *,
    date_str: str = "",
    division: str = "unknown",
    title_fight: int = 0,
    event_name: str = "Matchup",
) -> pd.DataFrame:
    fighter_a_data = extract_fighter_data(fighter_a, fighter_b, "a", date_str)
    fighter_b_data = extract_fighter_data(fighter_b, fighter_a, "b", date_str)
    fight_row = {
        "date": date_str,
        "division": division,
        "title_fight": title_fight,
        "event_name": event_name,
        "r_name": fighter_a.get("name", "") if isinstance(fighter_a, dict) else "",
        "b_name": fighter_b.get("name", "") if isinstance(fighter_b, dict) else "",
        **fighter_a_data,
        **fighter_b_data,
    }
    df = pd.DataFrame([fight_row])
    return apply_feature_engineering(df)


def extract_id_from_url(url: str) -> str:
    """Extract ID from UFC stats URL."""
    match = re.search(r'/([a-z0-9]+)$', url)
    return match.group(1) if match else ''


def extract_fighter_data(
    fighter: Dict,
    opponent: Dict,
    corner: str,
    fight_date: str
) -> Dict:
    """
    Extract fighter data for a specific corner (r or b).
    
    Args:
        fighter: Fighter dictionary with name and dataset
        opponent: Opponent fighter dictionary
        corner: 'a' or 'b' (maps to 'r' or 'b' in UFC.csv)
        fight_date: Date of the fight
        
    Returns:
        Dictionary with fighter stats prefixed with r_ or b_
    """
    prefix = 'r' if corner == 'a' else 'b'
    
    fighter_name = fighter.get('name', '') if isinstance(fighter, dict) else ''
    fighter_dataset = fighter.get('dataset', []) if isinstance(fighter, dict) else []
    
    # Ensure dataset is a list
    if not isinstance(fighter_dataset, list):
        fighter_dataset = []
    
    # Calculate career averages from all available fights
    career_stats = calculate_career_averages(fighter_dataset)
    
    # Extract win/loss record from dataset
    # First check if wins/losses are already in the dataset (from simple scraper)
    wins = None
    losses = None
    draws = None
    
    if fighter_dataset and isinstance(fighter_dataset, list) and len(fighter_dataset) > 0:
        first_fight = fighter_dataset[0]
        if isinstance(first_fight, dict):
            # Check if wins/losses are directly in the dataset (simple scraper format)
            if 'wins' in first_fight and 'losses' in first_fight:
                wins = first_fight.get('wins', 0)
                losses = first_fight.get('losses', 0)
                draws = first_fight.get('draws', 0)
    
    # If not found, calculate from fight results (old scraper format)
    if wins is None or losses is None:
        wins, losses, draws = calculate_fight_record(fighter_dataset)
    
    # Extract fighter profile data from dataset (should be in all fight records)
    # Get from first fight record if available
    height = None
    weight = None
    reach = None
    stance = None
    dob = None
    
    # Also check for career stats from profile (may be more accurate than calculated)
    career_splm = None
    career_str_acc = None
    career_sapm = None
    career_str_def = None
    career_td_avg = None
    career_td_acc = None
    career_td_def = None
    career_sub_avg = None
    
    if fighter_dataset and isinstance(fighter_dataset, list) and len(fighter_dataset) > 0:
        first_fight = fighter_dataset[0]
        if isinstance(first_fight, dict):
            height = first_fight.get('height')
            weight = first_fight.get('weight')
            reach = first_fight.get('reach')
            stance = first_fight.get('stance')
            dob = first_fight.get('dob')
            # Get career stats from profile if available
            career_splm = first_fight.get('career_splm')
            career_str_acc = first_fight.get('career_str_acc')
            career_sapm = first_fight.get('career_sapm')
            career_str_def = first_fight.get('career_str_def')
            career_td_avg = first_fight.get('career_td_avg')
            career_td_acc = first_fight.get('career_td_acc')
            career_td_def = first_fight.get('career_td_def')
            career_sub_avg = first_fight.get('career_sub_avg')
    
    # Use career stats from profile if available, otherwise use calculated averages
    splm = career_splm if career_splm is not None else career_stats.get('splm', None)
    str_acc = career_str_acc if career_str_acc is not None else career_stats.get('str_acc', None)
    sapm = career_sapm if career_sapm is not None else career_stats.get('sapm', None)
    str_def = career_str_def if career_str_def is not None else career_stats.get('str_def', None)
    td_avg = career_td_avg if career_td_avg is not None else career_stats.get('td_avg', None)
    td_avg_acc = career_td_acc if career_td_acc is not None else career_stats.get('td_avg_acc', None)
    td_def = career_td_def if career_td_def is not None else career_stats.get('td_def', None)
    sub_avg = career_sub_avg if career_sub_avg is not None else career_stats.get('sub_avg', None)
    td_acc = career_td_acc if career_td_acc is not None else career_stats.get('td_acc', None)
    
    # Build fighter data dictionary - only include columns needed for feature engineering
    # These are the columns from columns_to_keep in eda.ipynb that are needed before feature engineering
    fighter_data = {
        # Profile data (needed for feature engineering, then some dropped)
        f'{prefix}_wins': wins,
        f'{prefix}_losses': losses,
        f'{prefix}_draws': draws,
        f'{prefix}_height': height,
        f'{prefix}_weight': weight,
        f'{prefix}_reach': reach,
        f'{prefix}_stance': stance,
        f'{prefix}_dob': dob,
        # Career averages (use profile stats if available, otherwise calculated)
        f'{prefix}_splm': splm,
        f'{prefix}_str_acc': str_acc,
        f'{prefix}_sapm': sapm,
        f'{prefix}_str_def': str_def,
        f'{prefix}_td_avg': td_avg,
        f'{prefix}_td_avg_acc': td_avg_acc,
        f'{prefix}_td_def': td_def,
        f'{prefix}_sub_avg': sub_avg,
        # Takedown accuracy (kept after feature engineering)
        f'{prefix}_td_acc': td_acc,
    }
    
    return fighter_data


def calculate_career_averages(fighter_dataset: List[Dict]) -> Dict:
    """
    Calculate career averages from all available fights.
    
    Calculates averages for:
    - r_splm (significant strikes landed per minute)
    - r_sapm (significant strikes absorbed per minute)
    - r_td_def (takedown defense percentage)
    - r_str_acc (striking accuracy)
    
    Args:
        fighter_dataset: List of fight dictionaries
        
    Returns:
        Dictionary with average statistics
    """
    if not fighter_dataset:
        return {}
    
    # Validate dataset is list of dicts
    if not isinstance(fighter_dataset, list):
        return {}
    
    # Extract relevant stats from each fight
    stats_list = []
    
    for fight in fighter_dataset:
        # Skip if not a dictionary
        if not isinstance(fight, dict):
            continue
        # Calculate significant strikes per minute
        sig_str_landed = fight.get('TOT_fighter_SigStr_landed')
        sig_str_attempted = fight.get('TOT_fighter_SigStr_attempted')
        time_seconds = fight.get('Time', 0)
        
        if sig_str_landed is not None and time_seconds and time_seconds > 0:
            minutes = time_seconds / 60.0
            splm = sig_str_landed / minutes if minutes > 0 else None
        else:
            splm = None
        
        # Calculate significant strikes absorbed per minute
        sig_str_opp_landed = fight.get('TOT_opponent_SigStr_landed')
        if sig_str_opp_landed is not None and time_seconds and time_seconds > 0:
            minutes = time_seconds / 60.0
            sapm = sig_str_opp_landed / minutes if minutes > 0 else None
        else:
            sapm = None
        
        # Takedown accuracy
        td_landed = fight.get('TOT_fighter_Td_landed')
        td_attempted = fight.get('TOT_fighter_Td_attempted')
        td_acc = None
        if td_attempted and td_attempted > 0:
            td_acc = (td_landed / td_attempted * 100) if td_landed is not None else None
        
        # Striking accuracy
        str_acc = fight.get('TOT_fighter_SigStr_percentage')
        
        # Takedown defense - need opponent stats
        td_opp_landed = fight.get('TOT_opponent_Td_landed')
        td_opp_attempted = fight.get('TOT_opponent_Td_attempted')
        td_def = None
        if td_opp_attempted and td_opp_attempted > 0:
            td_def = 100 - (td_opp_landed / td_opp_attempted * 100) if td_opp_landed is not None else None
        
        # Average takedowns per 15 minutes
        if td_landed is not None and time_seconds and time_seconds > 0:
            minutes = time_seconds / 60.0
            td_avg = (td_landed / minutes * 15) if minutes > 0 else None
        else:
            td_avg = None
        
        # Takedown average accuracy
        td_avg_acc = td_acc  # Same as td_acc
        
        # Submission attempts per 15 minutes
        sub_att = fight.get('TOT_fighter_SubAtt', 0)
        if sub_att is not None and time_seconds and time_seconds > 0:
            minutes = time_seconds / 60.0
            sub_avg = (sub_att / minutes * 15) if minutes > 0 else None
        else:
            sub_avg = None
        
        stats_list.append({
            'splm': splm,
            'sapm': sapm,
            'td_acc': td_acc,
            'str_acc': str_acc,
            'td_def': td_def,
            'td_avg': td_avg,
            'td_avg_acc': td_avg_acc,
            'sub_avg': sub_avg,
        })
    
    # Calculate averages (ignore NaN values)
    if not stats_list:
        return {}
    
    avg_stats = {}
    for key in ['splm', 'sapm', 'td_acc', 'str_acc', 'td_def', 'td_avg', 'td_avg_acc', 'sub_avg']:
        values = [s[key] for s in stats_list if s[key] is not None and not np.isnan(s[key])]
        if values:
            avg_stats[key] = np.mean(values)
        else:
            avg_stats[key] = None
    
    return avg_stats


def calculate_fight_record(fighter_dataset: List[Dict]) -> tuple:
    """
    Calculate win/loss/draw record from fighter dataset.
    
    Args:
        fighter_dataset: List of fight dictionaries
        
    Returns:
        Tuple of (wins, losses, draws)
    """
    wins = 0
    losses = 0
    draws = 0
    
    if not fighter_dataset or not isinstance(fighter_dataset, list):
        return wins, losses, draws
    
    for fight in fighter_dataset:
        # Skip if not a dictionary
        if not isinstance(fight, dict):
            continue
            
        result = fight.get('result', '').lower()
        if result == 'win':
            wins += 1
        elif result == 'loss':
            losses += 1
        elif result in ['draw', 'nc', 'no contest']:
            draws += 1
    
    return wins, losses, draws


def apply_feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all feature engineering steps from eda.ipynb.
    
    Steps:
    1. Age calculation from DOB
    2. Win-loss ratio calculation
    3. Stance normalization (Orthodox/Southpaw) and open_stance feature
    4. Division normalization
    5. Drop columns: r_id, b_id, r_dob, b_dob, r_wins, r_losses, b_wins, b_losses, 
       r_draws, b_draws, r_stance, b_stance, date
    
    Args:
        df: DataFrame with UFC.csv format columns
        
    Returns:
        DataFrame with feature engineering applied
    """
    df = df.copy()
    
    # 1. Age calculation from DOB
    if 'r_dob' in df.columns and 'b_dob' in df.columns:
        # Parse DOB if available (handle multiple formats like "Nov 17, 1997" or "1997/11/17")
        # Let pandas auto-detect the format
        df['r_dob'] = pd.to_datetime(df['r_dob'], errors='coerce')
        df['b_dob'] = pd.to_datetime(df['b_dob'], errors='coerce')
        
        # Parse fight date (handle various formats)
        fight_date = pd.to_datetime(df['date'], errors='coerce')
        
        # Calculate age at fight date (or today if fight date is invalid)
        # Use today's date if fight_date is invalid (for upcoming fights)
        today = pd.Timestamp.today()
        calc_date = fight_date.fillna(today)
        
        # Calculate age
        df['r_age'] = ((calc_date - df['r_dob']).dt.days / 365.25).round(2)
        df['b_age'] = ((calc_date - df['b_dob']).dt.days / 365.25).round(2)
    
    # 2. Win-loss ratio calculation
    # Handle division by zero: if wins + losses = 0, ratio is NaN
    total_r = df['r_wins'] + df['r_losses']
    total_b = df['b_wins'] + df['b_losses']
    df['r_win_loss_ratio'] = df['r_wins'] / total_r.replace(0, np.nan)
    df['b_win_loss_ratio'] = df['b_wins'] / total_b.replace(0, np.nan)
    
    # 3. Stance normalization keeping r_stance and b_stance
    if 'r_stance' in df.columns and 'b_stance' in df.columns:
        valid_stances = {'Orthodox', 'Southpaw'}
        
        # Normalize stances (fill None/NaN with 'Orthodox')
        df['r_stance'] = df['r_stance'].fillna('Orthodox')
        df['b_stance'] = df['b_stance'].fillna('Orthodox')
        
        # Map invalid stances to 'Orthodox'
        df['r_stance'] = df['r_stance'].where(
            df['r_stance'].isin(valid_stances), 
            'Orthodox'
        )
        df['b_stance'] = df['b_stance'].where(
            df['b_stance'].isin(valid_stances),
            'Orthodox'
        )
        
    
    # 4. Division normalization
    if 'division' in df.columns:
        df['division'] = normalize_division(df['division'])
    
    # 5. Drop columns (after feature engineering)
    # Drop columns that are no longer needed after feature engineering
    columns_to_drop = [
        'r_wins', 'r_losses', 'b_wins', 'b_losses', 
        'r_draws', 'b_draws', 
        # 'r_stance', 'b_stance',  # TEMPORARY: Keep these columns
        'r_dob', 'b_dob', 'date', 'division'
    ]
    
    # Only drop columns that exist
    columns_to_drop = [col for col in columns_to_drop if col in df.columns]
    df = df.drop(columns=columns_to_drop)
    
    # Final columns after feature engineering (matching what preprocessor expects)
    # These must be in the EXACT order the preprocessor was trained on
    # Order matches preprocessor.feature_names_in_ from the saved model
    final_columns = [
        'b_height', 'r_height', 'b_reach', 'r_reach', 'r_weight', 'b_weight',
        'r_splm', 'b_splm', 'r_td_acc', 'b_td_acc', 'r_str_acc', 'b_str_acc',
        'r_sapm', 'b_sapm', 'r_str_def', 'b_str_def', 'r_td_avg', 'b_td_avg',
        'r_td_avg_acc', 'b_td_avg_acc', 'r_td_def', 'b_td_def', 'r_sub_avg', 'b_sub_avg',
        'title_fight', 'r_age', 'b_age', 'r_win_loss_ratio', 'b_win_loss_ratio', 
        'r_stance', 'b_stance', 'r_ko_rate', 'b_ko_rate', 'r_momentum', 'b_momentum',
        'r_sub_rate', 'b_sub_rate'
    ]
    
    # Check for missing required columns and add them with NaN
    missing_cols = [col for col in final_columns if col not in df.columns]
    if missing_cols:
        for col in missing_cols:
            df[col] = None
    
    # Select only the final columns in the exact order expected by preprocessor
    # This ensures column order matches what the model was trained on
    # But keep metadata columns (event_name, r_name, b_name) for display purposes
    metadata_cols = ['event_name', 'r_name', 'b_name']
    metadata_to_keep = [col for col in metadata_cols if col in df.columns]
    
    # Select feature columns in correct order, then add metadata
    df_features = df[final_columns].copy()
    
    # Add metadata columns back (they won't be used by the model)
    for col in metadata_to_keep:
        df_features[col] = df[col].values
    
    return df_features


def normalize_division(division_series: pd.Series) -> pd.Series:
    """
    Normalize division names to standard format.
    
    Args:
        division_series: Series of division names
        
    Returns:
        Series of normalized division names
    """
    normalized = division_series.str.lower().str.strip()
    
    # Map variations to standard names
    division_map = {
        'strawweight': 'strawweight',
        'flyweight': 'flyweight',
        'bantamweight': 'bantamweight',
        'featherweight': 'featherweight',
        'lightweight': 'lightweight',
        'welterweight': 'welterweight',
        'middleweight': 'middleweight',
        'light heavyweight': 'light heavyweight',
        'lightheavyweight': 'light heavyweight',
        'lhw': 'light heavyweight',
        'heavyweight': 'heavyweight',
        'women\'s strawweight': 'strawweight',
        'women\'s flyweight': 'flyweight',
        'women\'s bantamweight': 'bantamweight',
        'women\'s featherweight': 'featherweight',
    }
    
    # Replace with mapped values, keep unknown as 'other'
    normalized = normalized.replace(division_map)
    normalized = normalized.where(
        normalized.isin(division_map.values()),
        'other'
    )
    
    return normalized


