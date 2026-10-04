import numpy as np
import pandas as pd
import pytest
from src.models import train_fair_value as t

FACTORS = {"ipl": {"M_batting": 1.0, "M_bowling": 1.0}, "bbl": {"M_batting": 0.8, "M_bowling": 1.1}}


def _cells():
    bat = pd.DataFrame([
        {"player_id": "a", "start_year": 2025, "comp": "ipl", "phase": "Middle", "runs": 100.0, "balls": 100.0, "dis": 2.0},
        {"player_id": "b", "start_year": 2025, "comp": "bbl", "phase": "Middle", "runs": 100.0, "balls": 100.0, "dis": 2.0}])
    bowl = pd.DataFrame([
        {"player_id": "c", "start_year": 2025, "comp": "ipl", "phase": "Middle", "runs": 120.0, "balls": 100.0, "wickets": 4.0},
        {"player_id": "d", "start_year": 2025, "comp": "bbl", "phase": "Middle", "runs": 120.0, "balls": 100.0, "wickets": 4.0}])
    return bat, bowl


def test_multiplier_clip_and_direction():
    m = t.multiplier([0.5, 1.0, 2.0], lam=0.5)
    assert m[0] == pytest.approx(0.8) and m[1] == pytest.approx(1.0) and m[2] == pytest.approx(1.5)
    assert t.multiplier([1.2])[0] > 1.0 > t.multiplier([0.8])[0]


def test_impact_centred_and_league_adjusted():
    bat, bowl = _cells()
    long, w, v = t.build_impact(bat, bowl, FACTORS)
    imp = long.set_index(["player_id"]).impact
    assert imp["a"] == pytest.approx(0.0)      # league-average IPL batter
    assert imp["b"] == pytest.approx(-20.0)    # 100 runs * 0.8 - 100 balls * 1.0 rpb
    assert imp["c"] == pytest.approx(0.0)
    assert imp["d"] == pytest.approx(-12.0)    # 100*1.2 - 120*1.1
    assert v["Middle"] == pytest.approx(30.0) and w["Middle"] == pytest.approx(1.0)


def test_unknown_competition_raises():
    bat, bowl = _cells()
    bat.loc[1, "comp"] = "xyz"
    with pytest.raises(ValueError):
        t.build_impact(bat, bowl, FACTORS)


def _long():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(40):
        rows.append(dict(player_id="bt%d" % i, start_year=2025, comp="ipl", phase="Middle", disc="bat",
                         balls=200.0, impact=float(rng.normal(0, 50))))
    for i in range(10):
        rows.append(dict(player_id="bw%d" % i, start_year=2025, comp="ipl", phase="Middle", disc="bowl",
                         balls=300.0, impact=float(rng.normal(0, 50))))
    return pd.DataFrame(rows)


def test_scarcity_fewer_qualified_means_higher_S():
    scar = t.scarcity_table(_long(), mode="all")
    s = scar.set_index("disc").S_norm
    assert s["bowl"] > s["bat"]
    assert (t.multiplier(scar.S_norm[scar.S_norm > 1]) > 1).all()


def test_fair_value_positive_bounded_and_centred():
    long = _long()
    scar = t.scarcity_table(long, mode="all")
    out, scales = t.fair_value(long, scar, {"Middle": 1.0})
    assert (out.fair_value > 0).all() and (out.fair_value <= 150).all()
    assert out.qualified_any.all()
    assert out.loc[out.bat_balls > 0, "z_bat"].median() == pytest.approx(0.0, abs=1e-9)
    assert out.loc[out.bowl_balls > 0, "z_bowl"].median() == pytest.approx(0.0, abs=1e-9)
    assert "bat_median_z" in scales and "bowl_median_z" in scales
