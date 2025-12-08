from collections import defaultdict

from fastapi import APIRouter, Depends

from app.models import (
    BandDistributionMetric,
    BandDistributionEntry,
    ProviderBandDistribution,
)
from app.services import HasuraClient, get_hasura_client

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/band-distribution", response_model=BandDistributionMetric)
async def get_band_distribution(
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get band distribution metric: how many towers have how many bands,
    grouped by provider/carrier and EN-DC status.

    Returns:
    - by_provider: For each provider, shows distribution of band counts
      across their towers, plus EN-DC breakdown
    - overall: Aggregate distribution across all towers
    - total_towers: Total number of unique towers
    - endc_summary: Count of towers with/without EN-DC
    """
    # Query to get tower-provider combinations with their band counts and EN-DC status
    query = """
    query GetBandDistribution {
        tower_providers {
            tower_id
            provider_id
            endc_available
            provider {
                id
                name
            }
            tower {
                id
                tower_bands_aggregate {
                    aggregate {
                        count
                    }
                }
            }
        }
        providers {
            id
            name
        }
    }
    """

    data = await hasura.execute(query, {})
    tower_providers = data.get("tower_providers", [])
    providers = {p["id"]: p["name"] for p in data.get("providers", [])}

    # Track per-provider stats
    # provider_id -> { band_count -> [tower_ids], endc_towers: set, non_endc_towers: set }
    provider_stats: dict = defaultdict(lambda: {
        "band_counts": defaultdict(set),
        "endc_towers": set(),
        "non_endc_towers": set(),
    })

    # Track overall stats
    overall_band_counts: dict[int, set] = defaultdict(set)  # band_count -> tower_ids
    all_towers: set = set()
    endc_enabled_towers: set = set()
    endc_disabled_towers: set = set()

    for tp in tower_providers:
        tower_id = tp["tower_id"]
        provider_id = tp["provider_id"]
        endc = tp.get("endc_available", False)

        # Get band count for this tower
        band_count = (
            tp.get("tower", {})
            .get("tower_bands_aggregate", {})
            .get("aggregate", {})
            .get("count", 0)
        )

        # Per-provider tracking
        stats = provider_stats[provider_id]
        stats["band_counts"][band_count].add(tower_id)
        if endc:
            stats["endc_towers"].add(tower_id)
        else:
            stats["non_endc_towers"].add(tower_id)

        # Overall tracking
        all_towers.add(tower_id)
        overall_band_counts[band_count].add(tower_id)
        if endc:
            endc_enabled_towers.add(tower_id)
        else:
            endc_disabled_towers.add(tower_id)

    # Build per-provider distribution
    by_provider = []
    for provider_id, stats in sorted(provider_stats.items()):
        distribution = [
            BandDistributionEntry(band_count=bc, tower_count=len(towers))
            for bc, towers in sorted(stats["band_counts"].items())
        ]
        all_provider_towers = set()
        for towers in stats["band_counts"].values():
            all_provider_towers.update(towers)

        by_provider.append(ProviderBandDistribution(
            provider_id=provider_id,
            provider_name=providers.get(provider_id),
            distribution=distribution,
            total_towers=len(all_provider_towers),
            endc_towers=len(stats["endc_towers"]),
            non_endc_towers=len(stats["non_endc_towers"]),
        ))

    # Build overall distribution
    overall = [
        BandDistributionEntry(band_count=bc, tower_count=len(towers))
        for bc, towers in sorted(overall_band_counts.items())
    ]

    return BandDistributionMetric(
        by_provider=by_provider,
        overall=overall,
        total_towers=len(all_towers),
        endc_summary={
            "endc_enabled": len(endc_enabled_towers),
            "endc_disabled": len(endc_disabled_towers),
        },
    )
