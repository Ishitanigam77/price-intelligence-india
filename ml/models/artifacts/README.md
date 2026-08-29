# ml/models/artifacts/

Directory for versioned XGBoost artifacts written by `ml.training.train`.

Each successful training run creates `sale-price-xgb-features-v1-<timestamp>/` containing
`model.json`, `preprocessor.json`, and `metadata.json`, plus a `latest.json` pointer.

These files are gitignored. They are produced from stored price observations and sale events;
they are never fabricated to force a fit. When history is inadequate the trainer returns
`INSUFFICIENT_DATA` and writes nothing here.
