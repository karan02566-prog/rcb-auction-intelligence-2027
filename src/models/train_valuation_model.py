import json
import numpy as np
import pandas as pd
from pathlib import Path

def train_pure_numpy_valuation():
    input_path = Path("data/processed/master_player_features.csv")
    reports_dir = Path("reports")
    processed_dir = Path("data/processed")
    
    reports_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Missing master feature store at {input_path}")
        
    df = pd.read_csv(input_path)
    df_model = df[df["avg_sold_price"].notna() & (df["avg_sold_price"] > 0)].copy()
    
    # Feature selection & One-Hot Encoding
    features_num = ["times_in_auction", "total_matches_played", "competitions_count"]
    features_cat = ["primary_role", "nationality"]
    
    encoded_cats = pd.get_dummies(df_model[features_cat], drop_first=True, dtype=float)
    X = pd.concat([df_model[features_num], encoded_cats], axis=1)
    
    # Add Intercept / Bias term
    X["intercept"] = 1.0
    
    X_matrix = X.values
    y = df_model["avg_sold_price"].values
    
    # Solve OLS Regression via Least Squares: (X^T * X)^(-1) * X^T * y
    weights, residuals, rank, s = np.linalg.lstsq(X_matrix, y, rcond=None)
    
    # Predict Valuations
    y_pred = np.maximum(0, X_matrix @ weights)
    
    # Calculate Evaluation Metrics
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - (ss_res / ss_tot)
    mae = np.mean(np.abs(y - y_pred))
    rmse = np.sqrt(np.mean((y - y_pred) ** 2))
    
    # Generate Output Dataframe with Market Indicators
    df_model["predicted_valuation"] = np.round(y_pred, 2)
    df_model["valuation_diff"] = np.round(df_model["predicted_valuation"] - df_model["latest_sold_price"], 2)
    df_model["market_status"] = df_model["valuation_diff"].apply(
        lambda x: "Underpriced (Target)" if x > 0 else "Overpriced / Premium"
    )
    
    out_preds_path = processed_dir / "player_valuations_predicted.csv"
    df_model.to_csv(out_preds_path, index=False)
    
    metrics = {
        "r2_score": round(float(r2), 4),
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "total_players_modeled": len(df_model)
    }
    
    metrics_path = reports_dir / "valuation_model_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    
    print("\nPure NumPy/Pandas Valuation Model Completed Successfully:")
    print(f" - R² Score: {r2:.4f}")
    print(f" - MAE: {mae:,.2f}")
    print(f" - RMSE: {rmse:,.2f}")
    print(f" - Total Players Modeled: {len(df_model)}")
    print(f" - Output Saved: {out_preds_path}")

if __name__ == "__main__":
    train_pure_numpy_valuation()
