"""5G NR TB size 계산 모듈.

기준 문서: docs/spec.md (v1.0)
- TBS 결정 절차: 3GPP TS 38.214 5.1.3.2
- MCS 표: TS 38.214 5.1.3.1 (표 5.1.3.1-1, -2, -4)
- DMRS 위치: TS 38.211 표 7.4.1.1.2-3 (PDSCH), 표 6.4.1.1.3-3 (PUSCH)

화면과 무관하게 동작하며 표준 라이브러리만 사용한다 (Colab·Pyodide에서 그대로 import 가능).
코딩레이트 R은 fractions.Fraction으로 다뤄 부동소수 오차 없이 계산한다 (예: 682.5/1024).

공개 함수 (spec §3, §4):
    tbs(qm, r, v, n_prb, n_symb, dmrs_pos, x_overhead, dmrs_type, n_cdm) -> int
    dmrs_symbols(n_symb, dmrs_pos)                     -> list[int]
    dmrs_info(dmrs_type)                               -> dict   (CDM group 최대 개수 등, 입력 창 표시용)
    validate(cfg, qm, v, n_prb, n_symb)                -> list[str]
    best_tbs(cfg, qm, v, n_prb, n_symb, n_bytes=None)  -> dict   (자원 size mode)
    find_resources(cfg, n_bytes)                       -> dict   (TB size mode)
    data_rate_mbps(tbs_bits, scs_khz)                  -> float
"""

from __future__ import annotations

from fractions import Fraction
from math import floor

# ---------------------------------------------------------------------------
# 참조 표 (spec §5)
# ---------------------------------------------------------------------------

def _mcs_table(text: str) -> list[tuple[int, Fraction]]:
    """'Qm,R×1024' 목록 문자열을 [(Qm, R×1024), ...] 로 바꾼다. 리스트 index = MCS index."""
    return [(int(qm), Fraction(r)) for qm, r in (item.split(",") for item in text.split())]


# TS 38.214 표 5.1.3.1-1 (64QAM 표), MCS 0~28
_MCS_64QAM = _mcs_table("""
    2,120 2,157 2,193 2,251 2,308 2,379 2,449 2,526 2,602 2,679
    4,340 4,378 4,434 4,490 4,553 4,616 4,658
    6,438 6,466 6,517 6,567 6,616 6,666 6,719 6,772 6,822 6,873 6,910 6,948
""")

# TS 38.214 표 5.1.3.1-2 (256QAM 표), MCS 0~27
_MCS_256QAM = _mcs_table("""
    2,120 2,193 2,308 2,449 2,602
    4,378 4,434 4,490 4,553 4,616 4,658
    6,466 6,517 6,567 6,616 6,666 6,719 6,772 6,822 6,873
    8,682.5 8,711 8,754 8,797 8,841 8,885 8,916.5 8,948
""")

# TS 38.214 표 5.1.3.1-4 (1024QAM 표, DL 전용), MCS 0~26
_MCS_1024QAM = _mcs_table("""
    2,120 2,193 2,449
    4,378 4,490 4,616
    6,466 6,517 6,567 6,616 6,666 6,719 6,772 6,822 6,873
    8,682.5 8,711 8,754 8,797 8,841 8,885 8,916.5 8,948
    10,805.5 10,853 10,900 10,948
""")

MCS_TABLES: dict[str, list[tuple[int, Fraction]]] = {
    "64qam": _MCS_64QAM,
    "256qam": _MCS_256QAM,
    "1024qam": _MCS_1024QAM,
}

MOD_NAMES = {2: "QPSK", 4: "16QAM", 6: "64QAM", 8: "256QAM", 10: "1024QAM"}

# TS 38.214 표 5.1.3.2-1 (N_info ≤ 3824일 때의 TBS), 93개
TBS_TABLE = (
    24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128, 136, 144, 152, 160,
    168, 176, 184, 192, 208, 224, 240, 256, 272, 288, 304, 320, 336, 352, 368, 384,
    408, 432, 456, 480, 504, 528, 552, 576, 608, 640, 672, 704, 736, 768, 808, 848,
    888, 928, 984, 1032, 1064, 1128, 1160, 1192, 1224, 1256, 1288, 1320, 1352, 1416,
    1480, 1544, 1608, 1672, 1736, 1800, 1864, 1928, 2024, 2088, 2152, 2216, 2280,
    2408, 2472, 2536, 2600, 2664, 2728, 2792, 2856, 2976, 3104, 3240, 3368, 3496,
    3624, 3752, 3824,
)

# TS 38.101-1 표 5.3.2-1 (FR1), TS 38.101-2 표 5.3.2-1 (FR2): {SCS kHz: {대역폭 MHz: 최대 RB}} (spec §5.3)
BANDWIDTH_MAX_RB = {
    "FR1": {
        15: {5: 25, 10: 52, 15: 79, 20: 106, 25: 133, 30: 160, 35: 188, 40: 216, 45: 242, 50: 270},
        30: {5: 11, 10: 24, 15: 38, 20: 51, 25: 65, 30: 78, 35: 92, 40: 106, 45: 119, 50: 133,
             60: 162, 70: 189, 80: 217, 90: 245, 100: 273},
        60: {10: 11, 15: 18, 20: 24, 25: 31, 30: 38, 35: 44, 40: 51, 45: 58, 50: 65, 60: 79,
             70: 93, 80: 107, 90: 121, 100: 135},
    },
    "FR2": {
        60: {50: 66, 100: 132, 200: 264},
        120: {50: 32, 100: 66, 200: 132, 400: 264},
    },
}

# TS 38.211 표 7.4.1.1.2-3 (PDSCH mapping type A, single-symbol DMRS, l0 = 2).
# (할당 심볼 길이들, (pos0, pos1, pos2, pos3)별 DMRS 심볼 위치)  — spec §3.2
_DMRS_TABLE = (
    ((3, 4),     ([2], [2],     [2],       [2])),
    ((5, 6, 7),  ([2], [2, 4],  [2, 4],    [2, 4])),
    ((8, 9),     ([2], [2, 7],  [2, 7],    [2, 7])),
    ((10, 11),   ([2], [2, 9],  [2, 6, 9], [2, 6, 9])),
    ((12,),      ([2], [2, 9],  [2, 6, 9], [2, 5, 8, 11])),
    ((13, 14),   ([2], [2, 11], [2, 7, 11], [2, 5, 8, 11])),
)

# DMRS configuration type별 CDM group 정보 (spec §3.3)
# TS 38.211 표 7.4.1.1.2-1 (type 1), 표 7.4.1.1.2-2 (type 2), single-symbol DMRS 기준
DMRS_TYPE_INFO = {
    1: {"max_cdm_groups": 2, "re_per_cdm_group": 6, "max_ports": 4},
    2: {"max_cdm_groups": 3, "re_per_cdm_group": 4, "max_ports": 6},
}

PORTS_PER_CDM_GROUP = 2  # single-symbol DMRS에서 CDM group 하나가 쓰는 포트 수 (TS 38.212 표 7.3.1.2.2-1/-3)

# 시스템 설정 기본값 (spec §2.1)
DEFAULT_CFG = {
    "scs_khz": 30,        # subcarrier spacing
    "n_rb_max": 273,      # 최대 RB
    "n_tx": 4,            # Tx antenna 개수
    "n_rx": 4,            # Rx antenna 개수
    "link": "DL",         # "DL"(PDSCH) / "UL"(PUSCH)
    "n_dl": 14,           # 슬롯 내 DL 심볼 수
    "n_f": 0,             # Flexible(guard) 심볼 수
    "n_ul": 0,            # UL 심볼 수
    "mcs_table": "256qam",  # "64qam" / "256qam" / "1024qam"
    "dmrs_pos": 2,        # dmrs-AdditionalPosition 0~3
    "dmrs_type": 1,       # DMRS configuration type 1 / 2
    "n_cdm": 2,           # data 없는 CDM group 수 (type 1: 1~2, type 2: 1~3)
    "x_overhead": 0,      # xOverhead 0 / 6 / 12 / 18
}

MAX_LAYERS = 4  # 코드워드 1개의 최대 layer (TS 38.211 표 7.3.1.3-1, spec D5)

# ---------------------------------------------------------------------------
# 기본 계산
# ---------------------------------------------------------------------------

def _ceil_div(a: int | Fraction, b: int | Fraction) -> int:
    """⌈a / b⌉ (정수·분수 정확 계산)."""
    return -floor(-Fraction(a) / Fraction(b))


def _floor_log2(x: Fraction) -> int:
    """⌊log2(x)⌋, x ≥ 1. x ≥ 1이면 ⌊log2(x)⌋ = ⌊log2(⌊x⌋)⌋ 이므로 정수 비트 길이로 구한다."""
    return floor(x).bit_length() - 1


def _round_half_up(x: Fraction) -> int:
    """.5를 올리는 반올림 (TS 38.214 5.1.3.2의 round). Python round()는 짝수 반올림이라 쓰지 않는다."""
    return floor(x + Fraction(1, 2))


def dmrs_symbols(n_symb: int, dmrs_pos: int) -> list[int]:
    """할당 심볼 길이와 dmrs-AdditionalPosition에 따른 DMRS 심볼 위치 (spec §3.2).

    TS 38.211 표 7.4.1.1.2-3 (PDSCH type A). PUSCH(표 6.4.1.1.3-3)도 4~14 심볼에서 같은 값.
    """
    if dmrs_pos not in (0, 1, 2, 3):
        raise ValueError(f"dmrs_pos는 0~3이어야 합니다: {dmrs_pos}")
    for lengths, positions in _DMRS_TABLE:
        if n_symb in lengths:
            return list(positions[dmrs_pos])
    raise ValueError(f"지원하지 않는 심볼 길이입니다 (3~14): {n_symb}")


def dmrs_info(dmrs_type: int) -> dict:
    """DMRS configuration type의 CDM group 최대 개수·CDM group당 RE·최대 포트 (spec §3.3).

    입력 창에 "CDM group 최대 N개"를 표시하고 선택지를 1~N으로 만드는 데 쓴다.
    """
    if dmrs_type not in DMRS_TYPE_INFO:
        raise ValueError(f"DMRS type은 1 또는 2여야 합니다: {dmrs_type}")
    info = dict(DMRS_TYPE_INFO[dmrs_type])
    info["cdm_choices"] = list(range(1, info["max_cdm_groups"] + 1))
    return info


def n_dmrs_re_per_prb(n_symb: int, dmrs_pos: int, dmrs_type: int = 1, n_cdm: int = 2) -> int:
    """RB당 DMRS RE 수 N_DMRS (data 없는 CDM group 오버헤드 포함, TS 38.214 5.1.3.2, spec §3-1).

    N_DMRS = DMRS 심볼 수 × RE_CDM(type) × N_CDM
    """
    info = dmrs_info(dmrs_type)
    if not 1 <= n_cdm <= info["max_cdm_groups"]:
        raise ValueError(f"type {dmrs_type}의 CDM group은 1~{info['max_cdm_groups']}개입니다: {n_cdm}")
    return len(dmrs_symbols(n_symb, dmrs_pos)) * info["re_per_cdm_group"] * n_cdm


def n_re_per_prb(n_symb: int, dmrs_pos: int, x_overhead: int,
                 dmrs_type: int = 1, n_cdm: int = 2) -> int:
    """RB 하나의 데이터 RE 수 N'_RE (TS 38.214 5.1.3.2 1단계, spec §3-1).

    N'_RE = 12 × N_symb − N_DMRS − N_oh
    """
    return 12 * n_symb - n_dmrs_re_per_prb(n_symb, dmrs_pos, dmrs_type, n_cdm) - x_overhead


def tbs(qm: int, r, v: int, n_prb: int, n_symb: int,
        dmrs_pos: int = 2, x_overhead: int = 0,
        dmrs_type: int = 1, n_cdm: int = 2) -> int:
    """코드워드 1개의 TBS [bit] (TS 38.214 5.1.3.2, spec §3).

    qm: 변조 차수, r: 코딩레이트 R (0~1, Fraction 권장. 예: Fraction(948, 1024)),
    v: layer 수, n_prb: RB 개수, n_symb: 할당 심볼 수,
    dmrs_pos: dmrs-AdditionalPosition 0~3, x_overhead: xOverhead,
    dmrs_type: DMRS configuration type 1/2, n_cdm: data 없는 CDM group 수.
    """
    r = Fraction(str(r)) if isinstance(r, float) else Fraction(r)

    # 1) RB당 데이터 RE 수 N'_RE
    n_re_prime = n_re_per_prb(n_symb, dmrs_pos, x_overhead, dmrs_type, n_cdm)
    if n_re_prime <= 0:
        raise ValueError("N'_RE ≤ 0: 심볼 대비 DMRS·오버헤드가 너무 많습니다")

    # 2) 전체 RE 수 N_RE = min(156, N'_RE) × n_PRB
    n_re = min(156, n_re_prime) * n_prb

    # 3) 정보 비트 수 N_info = N_RE × R × Qm × v
    n_info = n_re * r * qm * v

    if n_info <= 3824:
        # 4) N_info ≤ 3824: 양자화 후 표 5.1.3.2-1에서 N'_info 이상인 가장 작은 값
        n = max(3, _floor_log2(n_info) - 6) if n_info >= 1 else 3
        n_info_prime = max(24, 2 ** n * floor(n_info / 2 ** n))
        return next(t for t in TBS_TABLE if t >= n_info_prime)

    # 5) N_info > 3824
    n = _floor_log2(n_info - 24) - 5
    n_info_prime = max(3840, 2 ** n * _round_half_up((n_info - 24) / 2 ** n))
    if r <= Fraction(1, 4):
        c = _ceil_div(n_info_prime + 24, 3816)
        return 8 * c * _ceil_div(n_info_prime + 24, 8 * c) - 24
    if n_info_prime > 8424:
        c = _ceil_div(n_info_prime + 24, 8424)
        return 8 * c * _ceil_div(n_info_prime + 24, 8 * c) - 24
    return 8 * _ceil_div(n_info_prime + 24, 8) - 24


def data_rate_mbps(tbs_bits: int, scs_khz: int) -> float:
    """Data rate [Mbps] = TBS / T_slot / 10^6, T_slot = 1 ms / 2^μ (spec §4.4)."""
    mu = {15: 0, 30: 1, 60: 2, 120: 3}[scs_khz]
    return tbs_bits * (2 ** mu) * 1000 / 1e6

# ---------------------------------------------------------------------------
# 설정·검증 (spec §2.1, §4.5)
# ---------------------------------------------------------------------------

def make_cfg(cfg: dict | None = None) -> dict:
    """기본값 위에 사용자 설정을 덮어쓴 시스템 설정 dict."""
    merged = dict(DEFAULT_CFG)
    if cfg:
        merged.update(cfg)
    return merged


def n_symb_avail(cfg: dict) -> int:
    """사용 가능한 심볼 수: DL이면 N_DL, UL이면 N_UL (spec §2.1)."""
    return cfg["n_dl"] if cfg["link"] == "DL" else cfg["n_ul"]


def v_max(cfg: dict) -> int:
    """최대 layer = min(N_Tx, N_Rx, 4, 2 × N_CDM) (spec D5, §3.1)."""
    return min(cfg["n_tx"], cfg["n_rx"], MAX_LAYERS, PORTS_PER_CDM_GROUP * cfg["n_cdm"])


def _tbs_cfg(cfg: dict, qm: int, r, v: int, n_prb: int, n_symb: int) -> int:
    """시스템 설정(cfg)의 DMRS·오버헤드 값으로 tbs()를 호출한다."""
    return tbs(qm, r, v, n_prb, n_symb, cfg["dmrs_pos"], cfg["x_overhead"],
               cfg["dmrs_type"], cfg["n_cdm"])


def modulation_orders(cfg: dict) -> list[int]:
    """선택한 MCS 표의 변조 차수 (오름차순)."""
    return sorted({qm for qm, _ in MCS_TABLES[cfg["mcs_table"]]})


def _mcs_for_qm(cfg: dict, qm: int) -> list[tuple[int, Fraction]]:
    """변조 차수가 qm인 (MCS index, R×1024) 목록 (index 오름차순)."""
    return [(i, rx) for i, (q, rx) in enumerate(MCS_TABLES[cfg["mcs_table"]]) if q == qm]


def validate(cfg: dict, qm: int | None = None, v: int | None = None,
             n_prb: int | None = None, n_symb: int | None = None) -> list[str]:
    """입력 검증 (spec §4.5). 오류 메시지 목록을 돌려준다 (빈 목록 = 정상)."""
    errors = []
    link = cfg["link"]
    if link not in ("DL", "UL"):
        errors.append(f"링크 방향은 DL 또는 UL이어야 합니다: {link}")
        return errors
    if cfg["mcs_table"] not in MCS_TABLES:
        errors.append(f"알 수 없는 MCS 표입니다: {cfg['mcs_table']}")
        return errors
    if link == "UL" and cfg["mcs_table"] == "1024qam":
        errors.append("UL에서는 1024QAM 표를 선택할 수 없습니다")
    if cfg["n_dl"] + cfg["n_f"] + cfg["n_ul"] != 14:
        errors.append("DL + Flexible + UL 심볼 수의 합은 14여야 합니다")
    if cfg["scs_khz"] not in (15, 30, 60, 120):
        errors.append(f"SCS는 15/30/60/120 kHz 중 하나여야 합니다: {cfg['scs_khz']}")
    if not 1 <= cfg["n_rb_max"] <= 275:
        errors.append("최대 RB는 1~275여야 합니다")
    if cfg["dmrs_pos"] not in (0, 1, 2, 3):
        errors.append("DMRS additional position은 pos0~pos3이어야 합니다")
    if cfg["x_overhead"] not in (0, 6, 12, 18):
        errors.append("xOverhead는 0/6/12/18 중 하나여야 합니다")
    # DMRS type·CDM group (spec §3.3, §4.5)
    if cfg["dmrs_type"] not in DMRS_TYPE_INFO:
        errors.append("DMRS type은 1 또는 2여야 합니다")
        return errors
    max_cdm = DMRS_TYPE_INFO[cfg["dmrs_type"]]["max_cdm_groups"]
    if not 1 <= cfg["n_cdm"] <= max_cdm:
        errors.append(f"type {cfg['dmrs_type']}의 CDM group은 최대 {max_cdm}개입니다 (1~{max_cdm} 선택)")
        return errors

    avail = n_symb_avail(cfg)
    if avail == 0:
        errors.append("해당 방향 심볼이 없음")

    if qm is not None and qm not in modulation_orders(cfg):
        errors.append(f"선택한 MCS 표에 없는 변조 차수입니다: Qm={qm}")
    if v is not None and not 1 <= v <= v_max(cfg):
        msg = f"layer 수는 1~{v_max(cfg)}여야 합니다 (min(Tx, Rx, 4, 2×CDM group))"
        if v <= min(cfg["n_tx"], cfg["n_rx"], MAX_LAYERS):
            msg += f" — data 없는 CDM group {cfg['n_cdm']}개로는 layer {v}개를 쓸 수 없음"
        errors.append(msg)
    if n_prb is not None and not 1 <= n_prb <= cfg["n_rb_max"]:
        errors.append(f"RB 개수는 1~{cfg['n_rb_max']}여야 합니다")
    if n_symb is not None:
        min_symb = 3 if link == "DL" else 4
        if n_symb > avail:
            errors.append(f"심볼 수가 사용 가능한 심볼({avail})보다 많습니다")
        elif n_symb < min_symb:
            errors.append(f"심볼 수는 {min_symb} 이상이어야 합니다 ({link})")
        elif cfg["dmrs_pos"] in (0, 1, 2, 3) and cfg["x_overhead"] in (0, 6, 12, 18) \
                and n_re_per_prb(n_symb, cfg["dmrs_pos"], cfg["x_overhead"],
                                 cfg["dmrs_type"], cfg["n_cdm"]) <= 0:
            errors.append("심볼 대비 DMRS·오버헤드가 너무 많습니다 (N'_RE ≤ 0)")
    return errors

# ---------------------------------------------------------------------------
# 모드별 알고리즘 (spec §4)
# ---------------------------------------------------------------------------

def _result(cfg: dict, tbs_bits: int, qm: int, mcs: int, r_x1024: Fraction,
            v: int, n_prb: int, n_symb: int, n_bytes: int | None) -> dict:
    """두 모드 공통 결과 dict (spec §2.3). JSON으로 바로 넘길 수 있게 기본 타입만 사용."""
    res = {
        "tbs_bits": tbs_bits,
        "tbs_bytes": tbs_bits // 8,
        "qm": qm,
        "mod_name": MOD_NAMES[qm],
        "v": v,
        "n_prb": n_prb,
        "n_symb": n_symb,
        "mcs": mcs,
        "r_x1024": float(r_x1024),
        "r": float(r_x1024 / 1024),
        "dmrs_pos_list": dmrs_symbols(n_symb, cfg["dmrs_pos"]),
        "dmrs_type": cfg["dmrs_type"],
        "n_cdm": cfg["n_cdm"],
        "n_dmrs_re_per_prb": n_dmrs_re_per_prb(n_symb, cfg["dmrs_pos"], cfg["dmrs_type"], cfg["n_cdm"]),
        "data_rate_mbps": data_rate_mbps(tbs_bits, cfg["scs_khz"]),
        "margin_bytes": None,
        "warnings": [],
        "errors": [],
    }
    if n_bytes is not None:
        res["margin_bytes"] = tbs_bits / 8 - n_bytes
        if tbs_bits < n_bytes * 8:
            res["warnings"].append("입력 데이터를 다 담지 못함")  # spec §4.3
    return res


def _error_result(errors: list[str]) -> dict:
    return {"errors": errors, "warnings": []}


def best_tbs(cfg: dict | None, qm: int, v: int, n_prb: int, n_symb: int,
             n_bytes: int | None = None) -> dict:
    """자원 size mode (spec §4.1) / 결과 창 재계산 (spec §4.3).

    변조 차수 qm인 MCS 중 index가 가장 큰 것(= 코딩레이트 최대, D3)으로 TBS를 계산한다.
    n_bytes를 주면 입력 대비 여유와 '다 담지 못함' 경고를 함께 돌려준다.
    """
    cfg = make_cfg(cfg)
    errors = validate(cfg, qm, v, n_prb, n_symb)
    if errors:
        return _error_result(errors)
    mcs, r_x1024 = _mcs_for_qm(cfg, qm)[-1]
    t = _tbs_cfg(cfg, qm, r_x1024 / 1024, v, n_prb, n_symb)
    return _result(cfg, t, qm, mcs, r_x1024, v, n_prb, n_symb, n_bytes)


def find_resources(cfg: dict | None, n_bytes: int) -> dict:
    """TB size mode (spec §4.2): 입력 Byte를 담는 최소 자원과 가장 작은 TBS를 찾는다.

    순서: layer 1부터 → 변조 차수 낮은 것부터 → 최대 코딩레이트로 최소 RB(이분 탐색, D2)
          → 그 RB에서 TBS ≥ 입력이 되는 가장 낮은 MCS (D1).
    심볼 수는 사용 가능한 심볼 전체로 고정한다 (D2).
    """
    cfg = make_cfg(cfg)
    if not isinstance(n_bytes, int) or n_bytes < 1:
        return _error_result(["송신 데이터는 1 이상의 정수(Byte)여야 합니다"])
    n_symb = n_symb_avail(cfg)
    errors = validate(cfg, n_symb=n_symb)
    if errors:
        return _error_result(errors)

    target = n_bytes * 8
    rb_max = cfg["n_rb_max"]

    for v in range(1, v_max(cfg) + 1):
        for qm in modulation_orders(cfg):
            entries = _mcs_for_qm(cfg, qm)
            _, rx_max = entries[-1]
            r_max = rx_max / 1024
            if _tbs_cfg(cfg, qm, r_max, v, rb_max, n_symb) < target:
                continue  # 이 Qm·layer로는 최대 RB로도 부족
            # TBS는 RB 개수에 대해 증가 → 최소 RB 이분 탐색
            lo, hi = 1, rb_max
            while lo < hi:
                mid = (lo + hi) // 2
                if _tbs_cfg(cfg, qm, r_max, v, mid, n_symb) >= target:
                    hi = mid
                else:
                    lo = mid + 1
            n_prb = lo
            # 같은 RB에서 입력을 담는 가장 낮은 MCS (= 가장 작은 TBS)
            for mcs, rx in entries:
                t = _tbs_cfg(cfg, qm, rx / 1024, v, n_prb, n_symb)
                if t >= target:
                    return _result(cfg, t, qm, mcs, rx, v, n_prb, n_symb, n_bytes)

    # 시스템 최대 전송량 초과: 최대 layer·최고 변조·최대 RB의 TBS를 함께 표시
    qm_top = modulation_orders(cfg)[-1]
    _, rx_top = _mcs_for_qm(cfg, qm_top)[-1]
    t_max = _tbs_cfg(cfg, qm_top, rx_top / 1024, v_max(cfg), rb_max, n_symb)
    res = _error_result([f"시스템 최대 전송량 초과 (최대 가능 TBS {t_max:,} bit = {t_max // 8:,} Byte)"])
    res["max_tbs_bits"] = t_max
    return res
