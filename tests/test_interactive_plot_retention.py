import pandas as pd

from interactive_plots import _build_retention_hover_data, _resolve_reference_cycle_info


def test_reference_cycle_uses_first_post_formation_cycle():
    df = pd.DataFrame({
        'Cycle': [1, 2, 3, 4, 5, 6],
        'Q Dis (mAh/g)': [120, 150, 180, 200, 198, 196],
        'Efficiency (-)': [0.70, 0.85, 0.92, 0.99, 0.99, 0.99]
    })

    reference_info = _resolve_reference_cycle_info(df, 'Q Dis (mAh/g)', formation_cycles=3)

    assert reference_info['reference_cycle'] == 4
    assert reference_info['reference_capacity'] == 200.0


def test_reference_cycle_skips_anomalous_post_formation_cycle():
    df = pd.DataFrame({
        'Cycle': [1, 2, 3, 4, 5, 6],
        'Q Dis (mAh/g)': [120, 150, 180, 320, 201, 199],
        'Efficiency (-)': [0.70, 0.85, 0.92, 1.08, 0.995, 0.994]
    })

    reference_info = _resolve_reference_cycle_info(df, 'Q Dis (mAh/g)', formation_cycles=3)
    retention_values, hover_text, _ = _build_retention_hover_data(
        df,
        'Q Dis (mAh/g)',
        formation_cycles=3
    )

    assert reference_info['reference_cycle'] == 5
    assert reference_info['reference_capacity'] == 201.0
    assert hover_text.iloc[4] == "100.00% (ref cycle 5)"
    assert round(retention_values.iloc[5], 2) == 99.0


def test_retention_hover_returns_na_when_no_valid_baseline_exists():
    df = pd.DataFrame({
        'Cycle': [1, 2, 3, 4],
        'Q Dis (mAh/g)': [0, 0, 0, 0],
        'Efficiency (-)': [0.70, 0.80, 0.90, 0.95]
    })

    reference_info = _resolve_reference_cycle_info(df, 'Q Dis (mAh/g)', formation_cycles=3)
    _, hover_text, _ = _build_retention_hover_data(df, 'Q Dis (mAh/g)', formation_cycles=3)

    assert reference_info['reference_cycle'] is None
    assert hover_text.iloc[-1] == "N/A (no valid post-formation baseline)"


if __name__ == "__main__":
    test_reference_cycle_uses_first_post_formation_cycle()
    test_reference_cycle_skips_anomalous_post_formation_cycle()
    test_retention_hover_returns_na_when_no_valid_baseline_exists()
    print("interactive retention hover tests passed")
