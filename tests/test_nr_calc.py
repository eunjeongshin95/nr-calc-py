"""nr_calc.py 골든 벡터 테스트 (테스트벤치).

기준 문서: docs/spec.md v1.1
- 기대값은 (1) 널리 알려진 값, (2) 스펙 표 그대로, (3) TS 38.214 5.1.3.2 공식 분기별 손계산 값을 쓴다.
- 손계산 값은 계산 과정을 주석으로 남긴다.
- 사용자가 아는 값은 KNOWN_TBS 표에 한 줄씩 추가하면 된다.
"""

import json
from fractions import Fraction as F

import pytest

import nr_calc as n

R948 = F(948, 1024)  # 256QAM 표 MCS 27 (TS 38.214 표 5.1.3.1-2)


# ---------------------------------------------------------------------------
# 1. TBS 골든 벡터
# ---------------------------------------------------------------------------

# (qm, R, v, n_prb, n_symb, dmrs_pos, x_overhead, dmrs_type, n_cdm, 기대 TBS)
# ★ 사용자가 아는 값은 여기에 추가 ★
KNOWN_TBS = [
    # 널리 알려진 값 (CLAUDE.md): 273 RB, 256QAM MCS 27, 14심볼, DMRS 1심볼(pos0), N'_RE=156
    pytest.param(8, R948, 1, 273, 14, 0, 0, 1, 2, 319_784, id="273RB-256QAM-1L-pos0"),
    pytest.param(8, R948, 4, 273, 14, 0, 0, 1, 2, 1_277_992, id="273RB-256QAM-4L-pos0"),
]

# 공식 분기별 손계산 (TS 38.214 5.1.3.2)
HAND_CALC_TBS = [
    # [A] N_info ≤ 3824, 표 최소값 24
    #   QPSK R=120/1024, 1 RB, 14심볼 pos2 type1 CDM2 → N'_RE = 168−36 = 132
    #   N_info = 132 × 120/1024 × 2 = 30.9375, n = max(3, 4−6) = 3
    #   N'_info = max(24, 8×⌊30.9375/8⌋ = 24) = 24 → 표 5.1.3.2-1 → 24
    pytest.param(2, F(120, 1024), 1, 1, 14, 2, 0, 1, 2, 24, id="A-Ninfo<=3824-min"),

    # [B] N_info ≤ 3824, 표 조회
    #   16QAM R=658/1024, 10 RB, N'_RE=132 → N_RE=1320
    #   N_info = 1320 × 658/1024 × 4 = 3392.8125, ⌊log2⌋ = 11 → n = 5
    #   N'_info = 32 × ⌊3392.8125/32⌋ = 32 × 106 = 3392 → 표에서 3392 이상 최소값 3496
    pytest.param(4, F(658, 1024), 1, 10, 14, 2, 0, 1, 2, 3496, id="B-Ninfo<=3824-table"),

    # [C] N_info > 3824, R ≤ 1/4 (C = ⌈(N'_info+24)/3816⌉)
    #   QPSK R=120/1024, 273 RB, N'_RE=132 → N_RE=36036
    #   N_info = 36036 × 120/1024 × 2 = 8445.9375, N_info−24 = 8421.9375, ⌊log2⌋ = 13 → n = 8
    #   N'_info = 256 × round(32.898) = 256 × 33 = 8448
    #   C = ⌈8472/3816⌉ = 3, TBS = 24 × ⌈8472/24⌉ − 24 = 24 × 353 − 24 = 8448
    pytest.param(2, F(120, 1024), 1, 273, 14, 2, 0, 1, 2, 8448, id="C-R<=1/4"),

    # [D] N_info > 3824, R > 1/4, N'_info ≤ 8424 (C = 1)
    #   16QAM R=658/1024, 20 RB, N_RE=2640
    #   N_info = 2640 × 658/1024 × 4 = 6785.625, N_info−24 = 6761.625, ⌊log2⌋ = 12 → n = 7
    #   N'_info = 128 × round(52.825) = 128 × 53 = 6784
    #   TBS = 8 × ⌈6808/8⌉ − 24 = 6808 − 24 = 6784
    pytest.param(4, F(658, 1024), 1, 20, 14, 2, 0, 1, 2, 6784, id="D-R>1/4-C=1"),

    # [E] N_info > 3824, R > 1/4, N'_info > 8424 (C > 1), spec 기본 DMRS pos2
    #   256QAM R=948/1024, 273 RB, N'_RE=132 → N_RE=36036
    #   N_info = 36036 × 948/1024 × 8 = 266891.625, N_info−24 = 266867.625, ⌊log2⌋ = 18 → n = 13
    #   N'_info = 8192 × round(32.576) = 8192 × 33 = 270336
    #   C = ⌈270360/8424⌉ = 33, TBS = 264 × ⌈270360/264⌉ − 24 = 264 × 1025 − 24 = 270576
    pytest.param(8, R948, 1, 273, 14, 2, 0, 1, 2, 270_576, id="E-C>1-pos2"),

    # [F] round .5 경계: .5를 올려야 맞음 (Python 내장 round()면 94248로 틀림)
    #   64QAM 표 MCS 11: Qm=4, R=378/1024, 2 layer, 224 RB, 14심볼 pos1 → DMRS 2심볼, N'_RE = 168−24 = 144
    #   N_RE = 144 × 224 = 32256, N_info = 32256 × 378/1024 × 4 × 2 = 95256
    #   N_info−24 = 95232, ⌊log2⌋ = 16 → n = 11, 95232/2048 = 46.5 → 올림 47 → N'_info = 96256
    #   C = ⌈96280/8424⌉ = 12, TBS = 96 × ⌈96280/96⌉ − 24 = 96 × 1003 − 24 = 96264
    pytest.param(4, F(378, 1024), 2, 224, 14, 1, 0, 1, 2, 96_264, id="F-round-half-up"),

    # [G] DMRS type 2, CDM group 1개, pos3 (spec §3.3)
    #   DMRS 4심볼 × 4 RE × 1 = 16 → N'_RE = 152, N_RE = 152 × 273 = 41496
    #   N_info = 41496 × 948/1024 × 8 = 307329.75, N_info−24 = 307305.75, ⌊log2⌋ = 18 → n = 13
    #   N'_info = 8192 × round(37.513) = 8192 × 38 = 311296
    #   C = ⌈311320/8424⌉ = 37, TBS = 296 × ⌈311320/296⌉ − 24 = 296 × 1052 − 24 = 311368
    pytest.param(8, R948, 1, 273, 14, 3, 0, 2, 1, 311_368, id="G-type2-CDM1-pos3"),
]


@pytest.mark.parametrize(
    "qm, r, v, n_prb, n_symb, pos, oh, dmrs_type, n_cdm, expected",
    KNOWN_TBS + HAND_CALC_TBS,
)
def test_tbs_golden(qm, r, v, n_prb, n_symb, pos, oh, dmrs_type, n_cdm, expected):
    assert n.tbs(qm, r, v, n_prb, n_symb, pos, oh, dmrs_type, n_cdm) == expected


def test_round_half_up_differs_from_builtin_round():
    """spec §3 5단계: round는 .5를 올린다. Python round()는 짝수 반올림이라 다르다."""
    assert n._round_half_up(F(93, 2)) == 47
    assert round(F(93, 2)) == 46  # 내장 round()를 쓰면 안 되는 이유
    assert n._round_half_up(F(95, 2)) == 48
    assert n._round_half_up(F(46)) == 46


def test_tbs_increases_with_rb():
    """spec §4.2: TBS는 RB 개수에 대해 증가 → 이분 탐색 전제 확인."""
    values = [n.tbs(8, R948, 1, prb, 14) for prb in range(1, 276)]
    assert all(a <= b for a, b in zip(values, values[1:]))


def test_n_re_capped_at_156():
    """TS 38.214 5.1.3.2: N_RE = min(156, N'_RE) × n_PRB. DMRS가 12 RE 이하면 결과가 같다."""
    base = n.tbs(8, R948, 1, 273, 14, 0, 0, 1, 2)   # N'_RE = 156
    assert n.tbs(8, R948, 1, 273, 14, 0, 0, 2, 1) == base  # N'_RE = 164 → 156
    assert n.tbs(8, R948, 1, 273, 14, 2, 0, 2, 1) == base  # N'_RE = 156


# ---------------------------------------------------------------------------
# 2. 참조 표 (spec §3.2, §3.3, §5)
# ---------------------------------------------------------------------------

# spec §3.2 (TS 38.211 표 7.4.1.1.2-3, l0=2): 심볼 길이 → (pos0, pos1, pos2, pos3)
DMRS_EXPECTED = {
    3: ([2], [2], [2], [2]),
    4: ([2], [2], [2], [2]),
    5: ([2], [2, 4], [2, 4], [2, 4]),
    6: ([2], [2, 4], [2, 4], [2, 4]),
    7: ([2], [2, 4], [2, 4], [2, 4]),
    8: ([2], [2, 7], [2, 7], [2, 7]),
    9: ([2], [2, 7], [2, 7], [2, 7]),
    10: ([2], [2, 9], [2, 6, 9], [2, 6, 9]),
    11: ([2], [2, 9], [2, 6, 9], [2, 6, 9]),
    12: ([2], [2, 9], [2, 6, 9], [2, 5, 8, 11]),
    13: ([2], [2, 11], [2, 7, 11], [2, 5, 8, 11]),
    14: ([2], [2, 11], [2, 7, 11], [2, 5, 8, 11]),
}


@pytest.mark.parametrize("n_symb", sorted(DMRS_EXPECTED))
@pytest.mark.parametrize("pos", [0, 1, 2, 3])
def test_dmrs_symbols_table(n_symb, pos):
    assert n.dmrs_symbols(n_symb, pos) == DMRS_EXPECTED[n_symb][pos]


@pytest.mark.parametrize("n_symb", [1, 2, 15])
def test_dmrs_symbols_unsupported_length(n_symb):
    with pytest.raises(ValueError):
        n.dmrs_symbols(n_symb, 2)


# spec §3.3: DMRS 심볼 1개당 비우는 RE = RE_CDM × N_CDM
@pytest.mark.parametrize("dmrs_type, n_cdm, re_per_symbol", [
    (1, 1, 6), (1, 2, 12),
    (2, 1, 4), (2, 2, 8), (2, 3, 12),
])
def test_dmrs_re_per_symbol(dmrs_type, n_cdm, re_per_symbol):
    # pos2, 14심볼 → DMRS 3심볼
    assert n.n_dmrs_re_per_prb(14, 2, dmrs_type, n_cdm) == 3 * re_per_symbol


def test_dmrs_info():
    assert n.dmrs_info(1) == {"max_cdm_groups": 2, "re_per_cdm_group": 6, "max_ports": 4,
                              "cdm_choices": [1, 2]}
    assert n.dmrs_info(2) == {"max_cdm_groups": 3, "re_per_cdm_group": 4, "max_ports": 6,
                              "cdm_choices": [1, 2, 3]}
    with pytest.raises(ValueError):
        n.dmrs_info(3)


def test_n_re_example_from_spec():
    """spec §3.2 예: DL 14심볼, pos2, type 1, CDM 2개 → N'_RE = 132."""
    assert n.n_re_per_prb(14, 2, 0, 1, 2) == 132


def test_mcs_tables():
    """TS 38.214 표 5.1.3.1-1/-2/-4: 개수와 양 끝 값."""
    t64, t256, t1024 = n.MCS_TABLES["64qam"], n.MCS_TABLES["256qam"], n.MCS_TABLES["1024qam"]
    assert len(t64) == 29 and t64[0] == (2, 120) and t64[28] == (6, 948)
    assert len(t256) == 28 and t256[20] == (8, F("682.5")) and t256[27] == (8, 948)
    assert len(t1024) == 27 and t1024[23] == (10, F("805.5")) and t1024[26] == (10, 948)
    for table in (t64, t256, t1024):
        qms = [qm for qm, _ in table]
        assert qms == sorted(qms)  # 변조 차수는 MCS index를 따라 증가


def test_tbs_table():
    """TS 38.214 표 5.1.3.2-1: 93개, 오름차순, 24~3824."""
    assert len(n.TBS_TABLE) == 93
    assert list(n.TBS_TABLE) == sorted(set(n.TBS_TABLE))
    assert n.TBS_TABLE[0] == 24 and n.TBS_TABLE[-1] == 3824


def test_bandwidth_table_examples():
    assert n.BANDWIDTH_MAX_RB["FR1"][30][100] == 273
    assert n.BANDWIDTH_MAX_RB["FR1"][15][20] == 106
    assert n.BANDWIDTH_MAX_RB["FR2"][120][400] == 264


# ---------------------------------------------------------------------------
# 3. 자원 size mode: best_tbs (spec §4.1, §4.3)
# ---------------------------------------------------------------------------

def test_best_tbs_known_value():
    res = n.best_tbs({"dmrs_pos": 0}, 8, 1, 273, 14)
    assert res["errors"] == []
    assert res["tbs_bits"] == 319_784 and res["tbs_bytes"] == 39_973
    assert res["mcs"] == 27 and res["r_x1024"] == 948 and res["mod_name"] == "256QAM"
    assert res["dmrs_pos_list"] == [2] and res["n_dmrs_re_per_prb"] == 12


@pytest.mark.parametrize("table, qm, mcs", [
    ("256qam", 2, 4), ("256qam", 4, 10), ("256qam", 6, 19), ("256qam", 8, 27),
    ("64qam", 6, 28), ("1024qam", 10, 26),
])
def test_best_tbs_picks_highest_mcs_of_qm(table, qm, mcs):
    """spec D3: 변조 차수 안에서 index가 가장 큰 MCS(코딩레이트 최대)."""
    res = n.best_tbs({"mcs_table": table}, qm, 1, 100, 14)
    assert res["errors"] == [] and res["mcs"] == mcs


def test_best_tbs_margin_and_warning():
    """spec §4.3: 입력 대비 여유, TBS < 입력이면 경고."""
    ok = n.best_tbs({"dmrs_pos": 0}, 8, 1, 273, 14, n_bytes=39_000)
    assert ok["margin_bytes"] == 39_973 - 39_000 and ok["warnings"] == []
    short = n.best_tbs({"dmrs_pos": 0}, 8, 1, 273, 14, n_bytes=40_000)
    assert short["margin_bytes"] < 0 and "입력 데이터를 다 담지 못함" in short["warnings"]


def test_data_rate():
    """spec §4.4: 30 kHz → T_slot 0.5 ms. 319784 bit / 0.5 ms = 639.568 Mbps."""
    assert n.data_rate_mbps(319_784, 30) == pytest.approx(639.568)
    assert n.data_rate_mbps(319_784, 15) == pytest.approx(319.784)
    assert n.data_rate_mbps(1000, 120) == pytest.approx(8.0)


def test_result_is_json_serializable():
    """화면(JavaScript)으로 넘길 결과는 JSON 기본 타입만."""
    json.dumps(n.best_tbs(None, 8, 2, 100, 14))
    json.dumps(n.find_resources(None, 5000))


# ---------------------------------------------------------------------------
# 4. TB size mode: find_resources (spec §4.2)
# ---------------------------------------------------------------------------

def _check_find_resources(cfg, n_bytes):
    """find_resources 결과가 spec §4.2 규칙을 만족하는지 직접 확인한다."""
    cfg = n.make_cfg(cfg)
    res = n.find_resources(cfg, n_bytes)
    assert res["errors"] == []
    target = n_bytes * 8
    qm, v, prb, sy = res["qm"], res["v"], res["n_prb"], res["n_symb"]
    entries = n._mcs_for_qm(cfg, qm)
    r_max = entries[-1][1] / 1024

    assert sy == n.n_symb_avail(cfg)                                   # D2: 심볼 전체 사용
    assert res["tbs_bits"] >= target                                   # D1: 입력을 모두 담음
    assert res["tbs_bits"] == n._tbs_cfg(cfg, qm, F(res["r_x1024"]) / 1024, v, prb, sy)  # 결과 MCS로 재계산
    if prb > 1:                                                        # D2: RB 최소
        assert n._tbs_cfg(cfg, qm, r_max, v, prb - 1, sy) < target
    lower = [rx for mcs, rx in entries if mcs < res["mcs"]]            # D1: 그 RB에서 가장 낮은 MCS
    for rx in lower:
        assert n._tbs_cfg(cfg, qm, rx / 1024, v, prb, sy) < target
    for v2 in range(1, v + 1):                                         # 탐색 순서: layer → 변조 차수
        for qm2 in n.modulation_orders(cfg):
            if (v2, qm2) == (v, qm):
                break
            r2 = n._mcs_for_qm(cfg, qm2)[-1][1] / 1024
            assert n._tbs_cfg(cfg, qm2, r2, v2, cfg["n_rb_max"], sy) < target
    return res


@pytest.mark.parametrize("n_bytes", [1, 3, 100, 1000, 5000, 20_000, 33_000, 40_000, 100_000, 135_000])
def test_find_resources_rules_default_cfg(n_bytes):
    _check_find_resources(None, n_bytes)


@pytest.mark.parametrize("cfg", [
    {"dmrs_pos": 0},
    {"mcs_table": "64qam"},
    {"mcs_table": "1024qam", "dmrs_type": 2, "n_cdm": 1},
    {"link": "UL", "n_dl": 0, "n_ul": 14, "n_tx": 2, "n_rx": 2},
    {"n_rb_max": 52, "scs_khz": 15},
    {"n_dl": 10, "n_f": 2, "n_ul": 2, "x_overhead": 6},
])
@pytest.mark.parametrize("n_bytes", [500, 12_000, 60_000])
def test_find_resources_rules_various_cfg(cfg, n_bytes):
    max_res = n.find_resources(cfg, 10**9)
    if n_bytes * 8 > max_res["max_tbs_bits"]:
        pytest.skip("이 설정의 최대 전송량을 넘는 입력")
    _check_find_resources(cfg, n_bytes)


def test_find_resources_single_layer_when_possible():
    """기본은 single layer. 1 layer 최대(pos2, 270576 bit = 33822 Byte) 이하면 v=1."""
    assert n.find_resources(None, 33_822)["v"] == 1
    assert n.find_resources(None, 33_823)["v"] == 2


def test_find_resources_exceeds_system():
    """spec §4.2: 최대 전송량 초과 → 오류 + 최대 가능 TBS (4 layer, 256QAM MCS 27, 273 RB)."""
    res = n.find_resources(None, 10**7)
    assert res["errors"] and "시스템 최대 전송량 초과" in res["errors"][0]
    assert res["max_tbs_bits"] == n.tbs(8, R948, 4, 273, 14)


@pytest.mark.parametrize("bad", [0, -5, 1.5, "100"])
def test_find_resources_bad_input(bad):
    assert n.find_resources(None, bad)["errors"]


# ---------------------------------------------------------------------------
# 5. 입력 검증 (spec §4.5)
# ---------------------------------------------------------------------------

# (cfg 덮어쓰기, best_tbs 인자 (qm, v, n_prb, n_symb), 오류 메시지에 들어갈 문구)
VALIDATION_CASES = [
    pytest.param({"n_dl": 13}, (8, 1, 100, 13), "합은 14", id="symbols-sum"),
    pytest.param({"link": "UL"}, (8, 1, 100, 4), "해당 방향 심볼이 없음", id="no-symbol-for-link"),
    pytest.param({"n_dl": 10, "n_ul": 4}, (8, 1, 100, 12), "사용 가능한 심볼", id="symb>avail"),
    pytest.param({}, (8, 1, 100, 2), "3 이상", id="DL-min-3"),
    pytest.param({"link": "UL", "n_dl": 0, "n_ul": 14}, (8, 1, 100, 3), "4 이상", id="UL-min-4"),
    pytest.param({}, (8, 1, 274, 14), "RB 개수", id="prb>max"),
    pytest.param({}, (8, 1, 0, 14), "RB 개수", id="prb<1"),
    pytest.param({"n_tx": 2}, (8, 3, 100, 14), "layer 수는 1~2", id="v>tx"),
    pytest.param({"n_cdm": 1}, (8, 4, 100, 14), "CDM group 1개로는", id="v>2xCDM"),
    pytest.param({"dmrs_type": 3}, (8, 1, 100, 14), "DMRS type", id="bad-type"),
    pytest.param({"dmrs_type": 1, "n_cdm": 3}, (8, 1, 100, 14), "최대 2개", id="type1-cdm3"),
    pytest.param({"dmrs_type": 2, "n_cdm": 0}, (8, 1, 100, 14), "최대 3개", id="type2-cdm0"),
    pytest.param({"link": "UL", "n_dl": 0, "n_ul": 14, "mcs_table": "1024qam"}, (8, 1, 100, 14),
                 "1024QAM", id="UL-1024QAM"),
    pytest.param({"mcs_table": "64qam"}, (8, 1, 100, 14), "변조 차수", id="qm-not-in-table"),
]


@pytest.mark.parametrize("cfg, args, message", VALIDATION_CASES)
def test_validation_errors(cfg, args, message):
    res = n.best_tbs(cfg, *args)
    assert any(message in e for e in res["errors"]), res["errors"]
    assert "tbs_bits" not in res


def test_n_re_never_nonpositive_within_options():
    """spec §4.5의 'N'_RE ≤ 0' 오류는 현재 선택지로는 생기지 않는다.
    가장 불리한 경우: DL 3심볼(DMRS 1심볼 × 12 RE) + xOverhead 18 → 36 − 12 − 18 = 6 > 0."""
    worst = min(
        n.n_re_per_prb(sy, pos, oh, t, c)
        for sy in range(3, 15) for pos in range(4) for oh in (0, 6, 12, 18)
        for t, c in ((1, 1), (1, 2), (2, 1), (2, 2), (2, 3))
    )
    assert worst == 6


def test_default_cfg_is_valid():
    assert n.validate(n.make_cfg(None), 8, 4, 273, 14) == []
