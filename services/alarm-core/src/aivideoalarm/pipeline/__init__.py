"""The three-tier escalation pipeline. See docs/architecture.md and
docs/adr/0001-extend-not-replace-frigate.md for the design this
implements.

Tier 0 (tier0_zone_filter): Frigate's own zone/mask filter, plus this
        project's zone+label+time-window rule matrix.
Tier 1 (tier1_local): local re-classification + temporal-consistency
        check, running on CPU/CUDA (the Coral stays with Frigate).
Tier 2 (tier2_cloud): Claude vision escalation, gated by confidence and
        stakes, rate-limited to a small daily cap.
Fusion (fusion): combines tier outputs into the final decision.
"""
