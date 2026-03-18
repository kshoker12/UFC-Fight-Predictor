#!/usr/bin/env python3
"""
Predict UFC Event Fights

This script takes an event JSON file, transforms it to the proper format,
and uses the trained stacking classifier to predict the outcome of each fight.

Usage:
    python predict_event_fights.py events/UFC_Fight_Night__Tsarukyan_vs._Hooker.json
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

from evaluate_fights import load_models, predict
from transform_event_data import transform_event_to_ufc_format


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to be filesystem-safe.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem
    """
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    return filename


def predict_event_fights(event_json_path: str, model_dir: str = 'models'):
    """
    Transform event data and predict outcomes for all fights.
    
    Args:
        event_json_path: Path to JSON event file
        model_dir: Directory containing saved models
        
    Returns:
        DataFrame with predictions added
    """
    # Load and transform event data
    print("=" * 80)
    print("TRANSFORMING EVENT DATA")
    print("=" * 80)
    print(f"Loading event from: {event_json_path}")
    
    try:
        df = transform_event_to_ufc_format(event_json_path)
        print(df)
        print(f"✓ Transformed {len(df)} fights")
        
        # TODO: Remove this after testing. Save DataFrame to Excel file in root directory for inspection
        excel_filename = 'transformed_data_before_predictions.xlsx'
        df.to_excel(excel_filename, index=False, engine='openpyxl')
        print(f"✓ Saved transformed DataFrame to {excel_filename}")
    except Exception as e:
        print(f"Error transforming event data: {e}", file=sys.stderr)
        raise
    
    # Load models
    print("\n" + "=" * 80)
    print("LOADING MODELS")
    print("=" * 80)
    try:
        preprocessor, model = load_models(model_dir)
    except Exception as e:
        print(f"Error loading models: {e}", file=sys.stderr)
        raise
    
    # Prepare data for prediction
    # The stacking model has preprocessors in its base estimators, so we should pass
    # the raw DataFrame directly to the model (not preprocessed)
    # The transform function should have already filtered to only the 30 required columns
    # Exclude metadata columns (r_name, b_name) from features
    metadata_cols = ['r_name', 'b_name']
    feature_cols = [col for col in df.columns if col not in metadata_cols]
    X = df[feature_cols].copy()
    
    # Make predictions
    # Note: The stacking model handles preprocessing internally through its base estimators
    print("\n" + "=" * 80)
    print("MAKING PREDICTIONS")
    print("=" * 80)
    try:
        # Pass raw data directly to stacking model (it has built-in preprocessors)
        print("Making predictions (stacking model handles preprocessing internally)...")
        predictions = model.predict(X)
        probabilities = model.predict_proba(X)
        print(f"✓ Predictions completed: {len(predictions)} predictions made")
    except Exception as e:
        print(f"Error making predictions: {e}", file=sys.stderr)
        raise
    
    # Add predictions to dataframe
    df['predicted_winner'] = predictions
    df['prediction_probability'] = probabilities[:, 1] if probabilities.shape[1] == 2 else None
    
    # Map predictions to fighter names (True = r_name wins, False = b_name wins)
    df['predicted_winner_name'] = df.apply(
        lambda row: row['r_name'] if row['predicted_winner'] else row['b_name'],
        axis=1
    )
    
    return df, predictions, probabilities


def print_fight_predictions(df: pd.DataFrame, predictions, probabilities):
    """
    Print formatted predictions for each fight.
    
    Args:
        df: DataFrame with fight data and predictions
        predictions: Array of predictions
        probabilities: Array of prediction probabilities
    """
    print("\n" + "=" * 80)
    print("FIGHT PREDICTIONS")
    print("=" * 80)
    
    event_name = df.iloc[0]['event_name'] if 'event_name' in df.columns else 'Unknown Event'
    print(f"\nEvent: {event_name}")
    print(f"Total Fights: {len(df)}")
    print("\n" + "-" * 80)
    
    for idx, row in df.iterrows():
        fighter_r = row.get('r_name', 'Unknown')
        fighter_b = row.get('b_name', 'Unknown')
        
        # Determine prediction and probabilities
        if probabilities.shape[1] == 2:
            prob_red_wins = float(probabilities[idx, 1])
            prob_blue_wins = float(probabilities[idx, 0])
            
            if predictions[idx]:
                predicted_winner = fighter_r
                confidence = prob_red_wins
            else:
                predicted_winner = fighter_b
                confidence = prob_blue_wins
        else:
            # Fallback for non-binary classification
            predicted_winner = row.get('predicted_winner_name', 'Unknown')
            confidence = row.get('prediction_probability', 0.5)
            prob_red_wins = confidence if predictions[idx] else (1 - confidence)
            prob_blue_wins = (1 - confidence) if predictions[idx] else confidence
        
        # Get division if available
        division = row.get('division', 'Unknown')
        title_fight = row.get('title_fight', 0)
        title_str = " (TITLE FIGHT)" if title_fight else ""
        
        print(f"\nFight {idx + 1}: {fighter_r} vs {fighter_b}")
        print(f"  Division: {division}{title_str}")
        print(f"  Predicted Winner: {predicted_winner}")
        print(f"  Confidence: {confidence:.1%}")
        
        if probabilities.shape[1] == 2:
            print(f"  Win Probabilities:")
            print(f"    {fighter_r}: {prob_red_wins:.1%}")
            print(f"    {fighter_b}: {prob_blue_wins:.1%}")
    
    print("\n" + "=" * 80)


def main():
    """Main function to run fight predictions on an event."""
    parser = argparse.ArgumentParser(
        description='Predict UFC fight outcomes from event JSON file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'event_file',
        type=str,
        help='Path to JSON event file (e.g., events/UFC_Fight_Night__Tsarukyan_vs._Hooker.json)'
    )
    
    parser.add_argument(
        '--model-dir',
        type=str,
        default='models',
        help='Directory containing saved models (default: models)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Optional CSV file to save predictions'
    )
    
    args = parser.parse_args()
    
    # Validate event file exists
    event_path = Path(args.event_file)
    if not event_path.exists():
        print(f"Error: Event file not found: {event_path}", file=sys.stderr)
        sys.exit(1)
    
    # Predict fights
    try:
        df, predictions, probabilities = predict_event_fights(
            str(event_path),
            args.model_dir
        )
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print predictions
    print_fight_predictions(df, predictions, probabilities)
    
    # Create simplified DataFrame with only essential columns
    simplified_df = pd.DataFrame({
        'fighter_1': df['r_name'].values,
        'fighter_2': df['b_name'].values,
        'fighter_1_probability': probabilities[:, 1] if probabilities.shape[1] == 2 else [0.5] * len(df),
        'fighter_2_probability': probabilities[:, 0] if probabilities.shape[1] == 2 else [0.5] * len(df),
        'predicted_winner': df['predicted_winner_name'].values
    })
    
    # Save predictions to CSV in predictions/ folder
    predictions_dir = Path('predictions')
    predictions_dir.mkdir(exist_ok=True)
    
    # Generate filename from event file name or event name
    event_path = Path(args.event_file)
    if 'event_name' in df.columns and len(df) > 0:
        event_name = df.iloc[0].get('event_name', '')
        if event_name:
            # Use event name for filename
            filename = sanitize_filename(event_name) + '.csv'
        else:
            # Fallback to event file name
            filename = event_path.stem + '_predictions.csv'
    else:
        # Fallback to event file name
        filename = event_path.stem + '_predictions.csv'
    
    output_path = predictions_dir / filename
    simplified_df.to_csv(output_path, index=False)
    print(f"\n✓ Predictions saved to {output_path}")
    
    # Also save to custom location if requested
    if args.output:
        custom_output_path = Path(args.output)
        simplified_df.to_csv(custom_output_path, index=False)
        print(f"✓ Predictions also saved to {custom_output_path}")


if __name__ == '__main__':
    main()

