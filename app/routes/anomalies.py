"""
Anomaly detection API routes.

Provides endpoints for querying GNN-based anomaly scores for towers.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.models import (
    TowerAnomalyScore,
    TowerWithAnomalyScore,
    AnomalyScoreStats,
    AnomalyScoreDistribution,
    AnomalyMetrics,
    ModelVersionInfo,
)
from app.services import HasuraClient, get_hasura_client

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("/versions", response_model=list[ModelVersionInfo])
async def get_model_versions(
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get list of available model versions with their metadata.

    Returns all unique model versions that have been imported,
    along with run IDs and tower counts.
    """
    query = """
    query GetModelVersions {
        tower_anomaly_scores(
            distinct_on: [model_version, run_id],
            order_by: [{model_version: desc}, {run_id: desc}, {created_at: desc}]
        ) {
            model_version
            run_id
            created_at
        }
    }
    """

    data = await hasura.execute(query, {})
    versions_raw = data.get("tower_anomaly_scores", [])

    # Get counts for each version
    results = []
    seen = set()
    for v in versions_raw:
        key = (v["model_version"], v.get("run_id"))
        if key in seen:
            continue
        seen.add(key)

        # Get count for this version
        count_query = """
        query GetVersionCount($model_version: String!, $run_id: String) {
            tower_anomaly_scores_aggregate(where: {
                model_version: {_eq: $model_version},
                run_id: {_eq: $run_id}
            }) {
                aggregate { count }
            }
        }
        """
        count_data = await hasura.execute(count_query, {
            "model_version": v["model_version"],
            "run_id": v.get("run_id"),
        })
        count = count_data.get("tower_anomaly_scores_aggregate", {}).get("aggregate", {}).get("count", 0)

        results.append(ModelVersionInfo(
            model_version=v["model_version"],
            run_id=v.get("run_id"),
            tower_count=count,
            created_at=v.get("created_at"),
        ))

    return results


@router.get("/stats", response_model=AnomalyScoreStats)
async def get_anomaly_stats(
    model_version: str = Query(default="gnn-link-pred-v1", description="Model version to query"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get summary statistics for anomaly scores.

    Returns aggregate stats like mean, std, min, max, and counts above percentile thresholds.
    """
    query = """
    query GetAnomalyStats($model_version: String!) {
        tower_anomaly_scores_aggregate(where: {model_version: {_eq: $model_version}}) {
            aggregate {
                count
                avg { anomaly_score }
                stddev { anomaly_score }
                min { anomaly_score }
                max { anomaly_score }
            }
        }
        above_95: tower_anomaly_scores_aggregate(where: {
            model_version: {_eq: $model_version},
            percentile: {_gt: 95}
        }) {
            aggregate { count }
        }
        above_99: tower_anomaly_scores_aggregate(where: {
            model_version: {_eq: $model_version},
            percentile: {_gt: 99}
        }) {
            aggregate { count }
        }
        tower_anomaly_scores(where: {model_version: {_eq: $model_version}}, limit: 1) {
            run_id
        }
    }
    """

    data = await hasura.execute(query, {"model_version": model_version})

    agg = data.get("tower_anomaly_scores_aggregate", {}).get("aggregate", {})
    above_95 = data.get("above_95", {}).get("aggregate", {}).get("count", 0)
    above_99 = data.get("above_99", {}).get("aggregate", {}).get("count", 0)
    scores = data.get("tower_anomaly_scores", [])
    run_id = scores[0].get("run_id") if scores else None

    return AnomalyScoreStats(
        total_scored=agg.get("count", 0),
        mean_score=agg.get("avg", {}).get("anomaly_score", 0) or 0,
        std_score=agg.get("stddev", {}).get("anomaly_score", 0) or 0,
        min_score=agg.get("min", {}).get("anomaly_score", 0) or 0,
        max_score=agg.get("max", {}).get("anomaly_score", 1) or 1,
        above_95th_percentile=above_95,
        above_99th_percentile=above_99,
        model_version=model_version,
        run_id=run_id,
    )


@router.get("/top", response_model=list[TowerWithAnomalyScore])
async def get_top_anomalies(
    limit: int = Query(default=100, ge=1, le=1000, description="Number of top anomalies to return"),
    min_percentile: float = Query(default=95.0, ge=0, le=100, description="Minimum percentile threshold"),
    model_version: str = Query(default="gnn-link-pred-v1", description="Model version to query"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get top anomalous towers sorted by anomaly score.

    Returns towers with the highest anomaly scores, useful for identifying
    potential coverage gaps or unusual network configurations.
    """
    query = """
    query GetTopAnomalies($limit: Int!, $min_percentile: Float!, $model_version: String!) {
        tower_anomaly_scores(
            where: {
                model_version: {_eq: $model_version},
                percentile: {_gte: $min_percentile}
            },
            order_by: {anomaly_score: desc},
            limit: $limit
        ) {
            tower_id
            anomaly_score
            percentile
            link_pred_error
            neighbor_inconsistency
            tower {
                latitude
                longitude
                tower_type
                provider_count
            }
        }
    }
    """

    data = await hasura.execute(query, {
        "limit": limit,
        "min_percentile": min_percentile,
        "model_version": model_version,
    })

    results = []
    for score in data.get("tower_anomaly_scores", []):
        tower = score.get("tower", {})
        results.append(TowerWithAnomalyScore(
            tower_id=score["tower_id"],
            latitude=tower.get("latitude", 0),
            longitude=tower.get("longitude", 0),
            tower_type=tower.get("tower_type"),
            provider_count=tower.get("provider_count", 1),
            anomaly_score=score["anomaly_score"],
            percentile=score.get("percentile"),
            link_pred_error=score.get("link_pred_error"),
            neighbor_inconsistency=score.get("neighbor_inconsistency"),
        ))

    return results


@router.get("/in-bounds", response_model=list[TowerWithAnomalyScore])
async def get_anomalies_in_bounds(
    min_lat: float = Query(..., ge=-90, le=90, description="Minimum latitude"),
    max_lat: float = Query(..., ge=-90, le=90, description="Maximum latitude"),
    min_lng: float = Query(..., ge=-180, le=180, description="Minimum longitude"),
    max_lng: float = Query(..., ge=-180, le=180, description="Maximum longitude"),
    min_percentile: float = Query(default=0.0, ge=0, le=100, description="Minimum percentile threshold"),
    limit: int = Query(default=1000, ge=1, le=5000, description="Maximum results"),
    model_version: str = Query(default="gnn-link-pred-v1", description="Model version to query"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get anomaly scores for towers within a geographic bounding box.

    Used by the map to display anomaly indicators when zoomed into an area.
    """
    query = """
    query GetAnomaliesInBounds(
        $min_lat: Float!, $max_lat: Float!, $min_lng: Float!, $max_lng: Float!,
        $min_percentile: Float!, $limit: Int!, $model_version: String!
    ) {
        tower_anomaly_scores(
            where: {
                model_version: {_eq: $model_version},
                percentile: {_gte: $min_percentile},
                tower: {
                    latitude: {_gte: $min_lat, _lte: $max_lat},
                    longitude: {_gte: $min_lng, _lte: $max_lng}
                }
            },
            order_by: {anomaly_score: desc},
            limit: $limit
        ) {
            tower_id
            anomaly_score
            percentile
            link_pred_error
            neighbor_inconsistency
            tower {
                latitude
                longitude
                tower_type
                provider_count
            }
        }
    }
    """

    data = await hasura.execute(query, {
        "min_lat": min_lat,
        "max_lat": max_lat,
        "min_lng": min_lng,
        "max_lng": max_lng,
        "min_percentile": min_percentile,
        "limit": limit,
        "model_version": model_version,
    })

    results = []
    for score in data.get("tower_anomaly_scores", []):
        tower = score.get("tower", {})
        results.append(TowerWithAnomalyScore(
            tower_id=score["tower_id"],
            latitude=tower.get("latitude", 0),
            longitude=tower.get("longitude", 0),
            tower_type=tower.get("tower_type"),
            provider_count=tower.get("provider_count", 1),
            anomaly_score=score["anomaly_score"],
            percentile=score.get("percentile"),
            link_pred_error=score.get("link_pred_error"),
            neighbor_inconsistency=score.get("neighbor_inconsistency"),
        ))

    return results


@router.get("/distribution", response_model=list[AnomalyScoreDistribution])
async def get_anomaly_distribution(
    buckets: int = Query(default=20, ge=5, le=100, description="Number of histogram buckets"),
    model_version: str = Query(default="gnn-link-pred-v1", description="Model version to query"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get distribution of anomaly scores as a histogram.

    Returns bucket counts for visualization in charts/analytics.
    """
    # Get all scores and bucket them (Hasura doesn't have histogram aggregation)
    query = """
    query GetAllScores($model_version: String!) {
        tower_anomaly_scores(where: {model_version: {_eq: $model_version}}) {
            anomaly_score
        }
    }
    """

    data = await hasura.execute(query, {"model_version": model_version})
    scores = [s["anomaly_score"] for s in data.get("tower_anomaly_scores", [])]

    if not scores:
        return []

    # Create histogram buckets
    bucket_size = 1.0 / buckets
    distribution = []

    for i in range(buckets):
        bucket_start = i * bucket_size
        bucket_end = (i + 1) * bucket_size
        count = sum(1 for s in scores if bucket_start <= s < bucket_end)
        # Include max value in last bucket
        if i == buckets - 1:
            count += sum(1 for s in scores if s == 1.0)
        distribution.append(AnomalyScoreDistribution(
            bucket_start=round(bucket_start, 4),
            bucket_end=round(bucket_end, 4),
            count=count,
        ))

    return distribution


@router.get("/tower/{tower_id}", response_model=Optional[TowerAnomalyScore])
async def get_tower_anomaly_score(
    tower_id: int,
    model_version: str = Query(default="gnn-link-pred-v1", description="Model version to query"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get anomaly score for a specific tower.
    """
    query = """
    query GetTowerAnomalyScore($tower_id: Int!, $model_version: String!) {
        tower_anomaly_scores(where: {
            tower_id: {_eq: $tower_id},
            model_version: {_eq: $model_version}
        }) {
            id
            tower_id
            model_version
            run_id
            anomaly_score
            link_pred_error
            neighbor_inconsistency
            percentile
            created_at
        }
    }
    """

    data = await hasura.execute(query, {
        "tower_id": tower_id,
        "model_version": model_version,
    })

    scores = data.get("tower_anomaly_scores", [])
    if not scores:
        return None

    score = scores[0]
    return TowerAnomalyScore(
        id=score["id"],
        tower_id=score["tower_id"],
        model_version=score["model_version"],
        run_id=score.get("run_id"),
        anomaly_score=score["anomaly_score"],
        link_pred_error=score.get("link_pred_error"),
        neighbor_inconsistency=score.get("neighbor_inconsistency"),
        percentile=score.get("percentile"),
        created_at=score.get("created_at"),
    )


@router.get("/metrics", response_model=AnomalyMetrics)
async def get_anomaly_metrics(
    model_version: str = Query(default="gnn-link-pred-v1", description="Model version to query"),
    top_n: int = Query(default=20, ge=1, le=100, description="Number of top anomalies to include"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get comprehensive anomaly metrics for the dashboard.

    Combines stats, distribution, and top anomalies in a single response.
    """
    # Get stats
    stats = await get_anomaly_stats(model_version=model_version, hasura=hasura)

    # Get distribution
    distribution = await get_anomaly_distribution(buckets=20, model_version=model_version, hasura=hasura)

    # Get top anomalies
    top_anomalies = await get_top_anomalies(
        limit=top_n,
        min_percentile=95.0,
        model_version=model_version,
        hasura=hasura,
    )

    return AnomalyMetrics(
        stats=stats,
        distribution=distribution,
        top_anomalies=top_anomalies,
    )
