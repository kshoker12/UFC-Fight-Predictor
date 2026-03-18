#!/usr/bin/env python3
"""
UFC Fight Prediction Script

This script loads a trained stacking classifier model and makes predictions
on new fight examples. It supports multiple input formats:
- CSV file
- JSON file
- Command-line arguments (for single predictions)

Usage:
    # From CSV file
    python evaluate_fights.py --csv input.csv
    
    # From JSON file
    python evaluate_fights.py --json input.json
    
    # Single prediction from command line (simplified example)
    python evaluate_fights.py --interactive
"""

import argparse
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


def load_models(model_dir='models'):
    """Load the preprocessor and stacking model."""
    model_dir = Path(model_dir)
    
    if not model_dir.exists():
        raise FileNotFoundError(f"Models directory '{model_dir}' not found. Please ensure models are saved.")
    
    # Load preprocessor
    preprocessor_path = model_dir / 'preprocessor.joblib'
    if not preprocessor_path.exists():
        raise FileNotFoundError(f"Preprocessor not found at {preprocessor_path}")
    
    print(f"Loading preprocessor from {preprocessor_path}...")
    preprocessor = joblib.load(preprocessor_path)
    
    # Load stacking model
    stacking_model_path = model_dir / 'stacking_model.joblib'
    if not stacking_model_path.exists():
        raise FileNotFoundError(f"Stacking model not found at {stacking_model_path}")
    
    print(f"Loading stacking model from {stacking_model_path}...")
    stacking_model = joblib.load(stacking_model_path)
    
    print("Models loaded successfully!")
    return preprocessor, stacking_model


def predict(preprocessor, model, data):
    """
    Make predictions on preprocessed data.
    
    Args:
        preprocessor: Fitted preprocessor pipeline
        model: Trained stacking classifier
        data: DataFrame with feature columns
    
    Returns:
        predictions: Array of predicted classes
        probabilities: Array of prediction probabilities
    """
    # Preprocess the data
    print("\nPreprocessing data...")
    try:
        data_processed = preprocessor.transform(data)
    except Exception as e:
        raise ValueError(f"Error during preprocessing: {e}. Ensure input data has correct columns.")
    
    # Make predictions
    print("Making predictions...")
    predictions = model.predict(data_processed)
    probabilities = model.predict_proba(data_processed)
    
    return predictions, probabilities


def load_from_csv(filepath):
    """Load data from CSV file."""
    print(f"Loading data from CSV: {filepath}")
    df = pd.read_csv(filepath)
    return df


def load_from_json(filepath):
    """Load data from JSON file."""
    print(f"Loading data from JSON: {filepath}")
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Handle both single dict and list of dicts
    if isinstance(data, dict):
        data = [data]
    
    df = pd.DataFrame(data)
    return df


def interactive_input():
    """Collect input interactively from user."""
    print("\nInteractive Mode")
    print("=" * 80)
    print("Please enter fighter statistics. For numerical values, enter numbers.")
    print("For categorical values, enter the exact string (e.g., 'True', 'False', 'Orthodox', 'Southpaw')")
    print()
    
    # Example feature names - adjust based on actual model features
    # This is a simplified version - you may need to adjust based on your actual feature names
    print("Note: This is a simplified interface. For full predictions, use CSV or JSON input.")
    print("The required features depend on your model's preprocessing pipeline.")
    print()
    
    # For now, just return None - user should use CSV/JSON
    print("Please use --csv or --json options for full functionality.")
    return None


def print_predictions(predictions, probabilities, data=None):
    """Pretty print predictions and probabilities."""
    print("\n" + "=" * 80)
    print("PREDICTION RESULTS")
    print("=" * 80)
    
    # Map boolean predictions to readable labels
    label_map = {True: 'Red Fighter Wins', False: 'Blue Fighter Wins'}
    if len(predictions) > 0:
        if isinstance(predictions[0], (bool, np.bool_)):
            pred_labels = [label_map[pred] for pred in predictions]
        else:
            # Handle other types (string, int, etc.)
            pred_labels = [str(pred) for pred in predictions]
    
    for i in range(len(predictions)):
        print(f"\nFight {i + 1}:")
        if data is not None and 'r_name' in data.columns and 'b_name' in data.columns:
            print(f"  Matchup: {data.iloc[i]['r_name']} vs {data.iloc[i]['b_name']}")
        
        pred_prob = probabilities[i]
        # Assuming binary classification with False (0) and True (1) classes
        if len(pred_prob) == 2:
            print(f"  Prediction: {pred_labels[i]}")
            print(f"  Probability: {pred_prob[1]:.2%} (Red wins) | {pred_prob[0]:.2%} (Blue wins)")
        else:
            print(f"  Prediction: {pred_labels[i]}")
            print(f"  Probabilities: {dict(zip(range(len(pred_prob)), pred_prob))}")
    
    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Predict UFC fight outcomes using trained stacking classifier',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--csv',
        type=str,
        help='Path to CSV file containing fight data'
    )
    input_group.add_argument(
        '--json',
        type=str,
        help='Path to JSON file containing fight data'
    )
    input_group.add_argument(
        '--interactive',
        action='store_true',
        help='Interactive mode (simplified, use CSV/JSON for full features)'
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
        help='Output file to save predictions (CSV or JSON)'
    )
    
    args = parser.parse_args()
    
    # Load models
    try:
        preprocessor, model = load_models(args.model_dir)
    except Exception as e:
        print(f"Error loading models: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Load input data
    if args.interactive:
        data = interactive_input()
        if data is None:
            sys.exit(0)
    elif args.csv:
        if not os.path.exists(args.csv):
            print(f"Error: CSV file not found: {args.csv}", file=sys.stderr)
            sys.exit(1)
        data = load_from_csv(args.csv)
    elif args.json:
        if not os.path.exists(args.json):
            print(f"Error: JSON file not found: {args.json}", file=sys.stderr)
            sys.exit(1)
        data = load_from_json(args.json)
    
    # Make predictions
    try:
        predictions, probabilities = predict(preprocessor, model, data)
    except Exception as e:
        print(f"Error making predictions: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print results
    print_predictions(predictions, probabilities, data)
    
    # Save to output file if specified
    if args.output:
        output_df = data.copy()
        output_df['prediction'] = predictions
        output_df['probability_red_wins'] = probabilities[:, 1] if probabilities.shape[1] == 2 else None
        output_df['probability_blue_wins'] = probabilities[:, 0] if probabilities.shape[1] == 2 else None
        
        output_path = Path(args.output)
        if output_path.suffix.lower() == '.json':
            output_df.to_json(args.output, orient='records', indent=2)
        else:
            output_df.to_csv(args.output, index=False)
        
        print(f"\nPredictions saved to {args.output}")


if __name__ == '__main__':
    main()

