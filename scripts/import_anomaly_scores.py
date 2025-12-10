#!/usr/bin/env python3
"""
Import GNN anomaly scores from CSV into PostgreSQL.

Usage:
    python scripts/import_anomaly_scores.py --csv path/to/node_scores.csv

This script:
1. Creates the tower_anomaly_scores table if it doesn't exist
2. Imports scores from CSV (tower_id, anomaly_score, link_pred_error, neighbor_inconsistency)
3. Computes percentiles for each tower
4. Uses UPSERT to handle re-runs
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from scipy import stats


def get_db_connection():
    """Get database connection from environment or defaults."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        database=os.getenv("POSTGRES_DB", "aerocell"),
    )


def create_table(conn):
    """Create the tower_anomaly_scores table if it doesn't exist."""
    sql_path = Path(__file__).parent / "create_anomaly_table.sql"
    with open(sql_path) as f:
        sql = f.read()

    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("Table tower_anomaly_scores created/verified")


def import_scores(conn, csv_path: str, model_version: str, run_id: str):
    """Import anomaly scores from CSV."""
    print(f"Loading CSV from {csv_path}...")
    df = pd.read_csv(csv_path)

    print(f"Loaded {len(df):,} rows")
    print(f"Columns: {list(df.columns)}")

    # Compute percentiles
    print("Computing percentiles...")
    df["percentile"] = stats.rankdata(df["anomaly_score"], method="average") / len(df) * 100

    # Prepare data for insertion
    data = [
        (
            int(row["tower_id"]),
            model_version,
            run_id,
            float(row["anomaly_score"]),
            float(row["link_pred_error"]) if pd.notna(row.get("link_pred_error")) else None,
            float(row["neighbor_inconsistency"]) if pd.notna(row.get("neighbor_inconsistency")) else None,
            float(row["percentile"]),
        )
        for _, row in df.iterrows()
    ]

    # Use UPSERT to handle re-runs
    print(f"Inserting {len(data):,} scores...")
    with conn.cursor() as cur:
        # Delete existing scores for this model version
        cur.execute(
            "DELETE FROM tower_anomaly_scores WHERE model_version = %s",
            (model_version,)
        )
        deleted = cur.rowcount
        if deleted > 0:
            print(f"Deleted {deleted:,} existing scores for model_version={model_version}")

        # Insert new scores
        insert_sql = """
            INSERT INTO tower_anomaly_scores
            (tower_id, model_version, run_id, anomaly_score, link_pred_error, neighbor_inconsistency, percentile)
            VALUES %s
            ON CONFLICT (tower_id, model_version) DO UPDATE SET
                run_id = EXCLUDED.run_id,
                anomaly_score = EXCLUDED.anomaly_score,
                link_pred_error = EXCLUDED.link_pred_error,
                neighbor_inconsistency = EXCLUDED.neighbor_inconsistency,
                percentile = EXCLUDED.percentile,
                created_at = CURRENT_TIMESTAMP
        """
        execute_values(cur, insert_sql, data, page_size=10000)

    conn.commit()
    print(f"Successfully imported {len(data):,} anomaly scores")

    # Print summary stats
    print("\nSummary statistics:")
    print(f"  Mean anomaly score: {df['anomaly_score'].mean():.4f}")
    print(f"  Std anomaly score: {df['anomaly_score'].std():.4f}")
    print(f"  Min anomaly score: {df['anomaly_score'].min():.4f}")
    print(f"  Max anomaly score: {df['anomaly_score'].max():.4f}")
    print(f"  Towers above 95th percentile: {(df['percentile'] > 95).sum():,}")
    print(f"  Towers above 99th percentile: {(df['percentile'] > 99).sum():,}")


def main():
    parser = argparse.ArgumentParser(description="Import GNN anomaly scores")
    parser.add_argument("--csv", type=str, required=True, help="Path to node_scores.csv")
    parser.add_argument("--model_version", type=str, default="gnn-link-pred-v1",
                       help="Model version identifier")
    parser.add_argument("--run_id", type=str, default="gnn-link-pred-knn15-20251209",
                       help="Run identifier")
    args = parser.parse_args()

    if not Path(args.csv).exists():
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)

    conn = get_db_connection()
    try:
        create_table(conn)
        import_scores(conn, args.csv, args.model_version, args.run_id)
    finally:
        conn.close()

    print("\nDone! You can now query anomaly scores via the API.")


if __name__ == "__main__":
    main()
