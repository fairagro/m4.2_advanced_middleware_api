
from middleware.sql_to_arc.main import ProcessingStats

def test_processing_stats_jsonld() -> None:
    stats = ProcessingStats(
        found_datasets=10,
        total_studies=5,
        total_assays=5,
        failed_datasets=1,
        failed_ids=["inv1"],
        duration_seconds=1.5
    )
    json_ld = stats.to_jsonld()
    assert "schema:CreateAction" in json_ld
    assert "PT1.50S" in json_ld
    assert "inv1" in json_ld
    
    # Test merge
    stats2 = ProcessingStats(found_datasets=5, failed_datasets=1, failed_ids=["inv2"])
    stats.merge(stats2)
    assert stats.found_datasets == 15
    assert stats.failed_datasets == 2
    assert "inv2" in stats.failed_ids
