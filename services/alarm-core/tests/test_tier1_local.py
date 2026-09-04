from aivideoalarm.pipeline.tier1_local import BoundingBox, temporal_consistency_score


def test_brief_erratic_motion_scores_low():
    """A bird flitting through frame: tiny, brief."""
    boxes = [
        BoundingBox(x=0.1, y=0.1, w=0.02, h=0.02, t=0.0),
        BoundingBox(x=0.5, y=0.3, w=0.02, h=0.02, t=0.3),
    ]
    assert temporal_consistency_score(boxes) < 0.3


def test_sustained_large_motion_scores_high():
    """A person walking across the yard: larger, sustained."""
    boxes = [
        BoundingBox(x=0.1, y=0.1, w=0.15, h=0.35, t=0.0),
        BoundingBox(x=0.3, y=0.1, w=0.15, h=0.35, t=1.0),
        BoundingBox(x=0.5, y=0.1, w=0.15, h=0.35, t=2.5),
    ]
    assert temporal_consistency_score(boxes) > 0.7


def test_single_box_is_neutral():
    assert temporal_consistency_score([BoundingBox(0, 0, 0.1, 0.1, 0.0)]) == 0.5
