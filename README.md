# UFC Fight Predictor

An end-to-end UFC fight outcome predictor, presented as a Streamlit app.

The app can show:
- Predicted results for upcoming and past events (precomputed predictions)
- A “custom matchup” screen where you can enter two fighters and get live probabilities (when model artifacts are available)

[Live demo](https://ufc-fight-predictor-ks.streamlit.app/)

## What this project does
Behind the scenes, the prediction pipeline is:
1. Scrape UFC data (fighters + events) and store it as event JSON in `events/`
2. Transform that JSON into the feature format the model expects (`transform_event_data.py`)
3. Run a trained stacking classifier to get a predicted winner + win probabilities (`predict_event_fights.py`)
4. Save results as lightweight CSV files in `predictions/` for fast display in the UI (`app.py`)

## How to use the app
1. Open the Streamlit UI.
2. Switch between `Upcoming` and `Past` to browse events.
3. For each event, the app displays the predicted winner and win probabilities per bout.
4. Use `Custom matchup` to pick two fighters and run live inference (only works if `models/stacking_model.joblib` exists).

## Where predictions come from
Predictions are stored per event as CSV files under `predictions/`.

The Streamlit UI reads CSVs using these columns:
- `fighter_1`
- `fighter_2`
- `fighter_1_probability`
- `fighter_2_probability`
- `predicted_winner`

## Model inputs (high level)
`transform_event_data.py` builds model features from the scraped fighter/event data, including things like:
- Age at fight time (from DOB)
- Win/loss ratios
- Stance normalization (Orthodox/Southpaw)
- Division normalization
- Additional engineered performance rates (e.g., finish/KO/submission-related signals and momentum)

It also ensures the final feature columns are in the exact order expected by the trained preprocessor.

## Models in the stacking classifier
The classifier is a stacking ensemble made from several models:
- Base models: MLP, LightGBM, Logistic Regression, SVM, Random Forest
- Final (meta) model: Logistic Regression (it combines the base models' predictions)

## Automation (keeping it up to date)
This repo includes a scheduled GitHub Action:
- `.github/workflows/update-upcoming-and-predictions.yml`

Every ~24 hours, it fetches the newest upcoming event, runs `predict_event_fights.py`, and commits updated `events/` and `predictions/` so the UI stays fresh.

## Limitations
- This is a statistical model, not a guarantee—fight outcomes can hinge on injuries, styles, and matchup-specific variables that won’t always be captured perfectly.
- Scraping is sourced from UFC Stats; if data is missing or incomplete for a fighter, the feature transformer may produce sparse features.
