# MMA-Fight-Predictor

Predict UFC fight outcomes by scraping fighter and event data, transforming it to the model’s expected feature set, and running a trained stacking classifier.

## What this project does
- Scrapes UFC event pages and fighter profiles (via `ufcstats.com`) to build structured event JSON files (see `events/`).
- Transforms event JSON into model-ready features using `transform_event_data.py` (age, stance normalization, win/loss ratios, career stats, finish rates, momentum, etc.).
- Runs a trained stacking model to generate winner predictions and per-fighter win probabilities with `predict_event_fights.py`.
- Saves lightweight CSV outputs in `predictions/` and an optional debug Excel of transformed features (`transformed_data_before_predictions.xlsx`).

## Key pieces
- **Scraper:** `ufc-analytics-scraper-simple.py` pulls event fights, fighter profiles, finish rates, and momentum. Produces event JSON in the expected schema.
- **Transformation:** `transform_event_data.py` maps event JSON into the UFC.csv-like feature set, engineers features, orders columns to match the trained preprocessor, and drops unused metadata.
- **Model loading & inference:** `evaluate_fights.py` / `predict_event_fights.py` load the saved preprocessor and stacking classifier from `models/` (joblib artifacts), run predictions, and print nicely formatted results.
- **Notebooks:** `eda.ipynb` documents feature selection, preprocessing choices, and model training rationale.

## Typical workflow
1) Scrape event data  
   - Use `ufc-analytics-scraper-simple.py` to fetch an event and write JSON to `events/`.
2) Transform to model features  
   - Run `transform_event_to_ufc_format(event_json_path)` (used inside `predict_event_fights.py`) to get the ordered feature frame the model expects.
3) Predict outcomes  
   - `python predict_event_fights.py events/<event_file>.json`  
   - Outputs CSV to `predictions/` with per-fighter probabilities and predicted winner; prints a summary to stdout.

## Inputs and outputs
- **Input:** Event JSON with fights, each including `fighter_a` / `fighter_b` datasets (profile, career stats, finish rates, momentum, wins/losses, etc.).
- **Output:** CSV per event with `fighter_1`, `fighter_2`, predicted winner, and win probabilities; optional Excel debug of transformed features.

## Notes and limits
- Model artifacts must exist in `models/` (`preprocessor.joblib`, `stacking_model.joblib`).
- Scraper currently focuses on UFC Stats; missing or new fighters may yield sparse data that the transformer will impute/leave as null.
- Some temporary behaviors (e.g., which events are scraped) may be toggled in the scraper’s main block. Adjust to target upcoming or past events as needed.
# UFC-Fight-Predictor
