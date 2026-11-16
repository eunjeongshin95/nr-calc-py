# 5G NR Calculator 사양서 (Python 버전)

> 상태: 검토 중 (v1.1, 2026-11-16)
> 목적: 한정된 시스템 자원에서 전송할 수 있는 TB size와 data rate를 계산한다.
> 계산 기준: 3GPP TS 38.214 §5.1.3 (MCS 표, TBS 결정 절차), TS 38.211 (DMRS, 코드워드-layer 매핑), TS 38.212 §7.3.1 (antenna port 표), TS 38.101-1/-2 (대역폭별 최대 RB)
> 구현: `nr_calc.py` (Python 3.11+, 표준 라이브러리만), 화면은 HTML/JS + Pyodide. 지난 TypeScript 버전(nr_calc_codetap) spec v0.3을 옮겨 옴.

---

## 1. 확정된 결정 사항

| # | 항목 | 결정 |
|---|---|---|
| D1 | "가장 가까운 TB size" | 입력 데이터를 **모두 담을 수 있는 TBS 중 가장 작은 값** (TBS ≥ 입력 비트) |
| D2 | 최소 자원 기준 | 심볼은 **사용 가능한 심볼 전체로 고정**(기본 14), **RB 개수를 최소화** |
| D3 | "최적 TB size" | 주어진 변조 차수에서 **코딩레이트가 가장 높은 MCS** → **가장 큰 TBS** |
| D4 | 링크 방향 / TDD | 슬롯의 14 심볼을 DL / Flexible(guard) / UL로 나눌 수 있게 한다. **기본은 DL 14심볼, DL 기준 계산** |
| D5 | 최대 layer | DL·UL 모두 최대 **4** (코드워드 1개의 최대 layer, §3.1). 실제 상한 = min(Tx, Rx, 4, 2 × N_CDM). Single-symbol DMRS에서 CDM group 하나는 포트 2개까지 쓰기 때문 (D8) |
| D6 | subcarrier 입력 | RB당 subcarrier는 12개 고정. 대신 **subcarrier spacing(SCS)** 을 입력한다 |
| D7 | DMRS | **Single-symbol DMRS만** 사용한다 (Double-symbol 제외). DMRS 심볼 개수는 **할당 심볼 길이와 dmrs-AdditionalPosition(pos0~pos3) 설정에 따라 표(§3.2)로 결정**한다. **DMRS configuration type 1 / type 2**를 입력으로 고른다 |
| D8 | CDM group | **data 없는 CDM group 수 N_CDM**을 입력으로 고른다 (type 1: 1~2, type 2: 1~3). 입력 창에 **선택한 type의 CDM group 최대 개수를 함께 표시**한다. DMRS 심볼에서 이 CDM group들의 RE는 data에 쓰지 않는다 (§3.3) |

---

## 2. 파라미터

### 2.1 시스템 설정 (두 모드 공통)

| 이름 | 기호 | 범위 / 선택지 | 기본값 | 설명 |
|---|---|---|---|---|
| Subcarrier spacing | μ | 15 / 30 / 60 / 120 kHz (μ=0~3) | 30 kHz | 슬롯 길이 = 1 ms / 2^μ |
| 채널 대역폭 (보조) | – | SCS별 선택지 (§5.3) | 100 MHz | 고르면 최대 RB가 자동으로 채워진다. 생략 가능 |
| RB size (최대 RB) | N_RB,max | 1 ~ 275 | 273 | 시스템이 쓸 수 있는 최대 RB 개수 |
| Tx antenna 개수 | N_Tx | 1, 2, 4, 8 | 4 | 기지국 송신 안테나 |
| Rx antenna 개수 | N_Rx | 1, 2, 4, 8 | 4 | 단말 수신 안테나 (layer 상한 결정) |
| 링크 방향 | – | DL / UL | DL | DL = PDSCH, UL = PUSCH |
| 슬롯 심볼 구성 | N_DL / N_F / N_UL | 합 = 14 | 14 / 0 / 0 | TDD 슬롯 내 DL·guard·UL 심볼 수 |
| MCS 표 | – | 64QAM / 256QAM / 1024QAM | 256QAM | 1024QAM 표는 DL에서만 선택 가능 |
| DMRS additional position | – | pos0 / pos1 / pos2 / pos3 | pos2 | 추가 DMRS 심볼 설정. 실제 DMRS 심볼 개수는 심볼 길이에 따라 §3.2 표로 정해진다. pos2는 RRC에서 값을 주지 않았을 때의 기본값 |
| DMRS configuration type | – | type 1 / type 2 | type 1 | dmrs-Type. type에 따라 CDM group 최대 개수와 CDM group당 RE 수가 달라진다 (§3.3) |
| data 없는 CDM group 수 | N_CDM | 1 ~ 최대 (type 1: 2, type 2: 3) | 2 | 입력 창 옆에 "최대 N개"를 표시한다. type을 바꿔 현재 값이 최대를 넘으면 최대값으로 맞춘다 |
| xOverhead | N_oh | 0 / 6 / 12 / 18 | 0 | RB당 추가 오버헤드 RE |

**사용 가능한 심볼 수** N_symb,avail = DL이면 N_DL, UL이면 N_UL.
**최대 layer** v_max = min(N_Tx, N_Rx, 4, 2 × N_CDM).

### 2.2 모드별 입력

| 모드 | 입력 |
|---|---|
| TB size mode | 송신 데이터 크기 (Byte, 1 이상 정수) |
| 자원 size mode | 변조 차수 Qm, layer 수 v, RB 개수 n_PRB, 심볼 수 N_symb |

모드 선택은 **라디오 버튼**으로 한다 (두 모드는 동시에 켤 수 없음).

### 2.3 출력 (두 모드가 같은 결과 창을 사용)

| 항목 | 단위 | 비고 |
|---|---|---|
| TB size | bit, Byte | layer ≤ 4이므로 코드워드(TB)는 항상 1개 |
| 변조 차수 | QPSK / 16QAM / 64QAM / 256QAM / 1024QAM | 결과 창에서 수정 가능 |
| Layer 수 | 개 | 결과 창에서 수정 가능 |
| RB 개수 | 개 | 결과 창에서 수정 가능 |
| 심볼 수 | 개 | 결과 창에서 수정 가능 |
| MCS index, 코딩레이트 | R×1024와 소수 R | |
| DMRS 심볼 개수와 위치 | 개, 심볼 번호 | 예: 3개 (2, 7, 11). 심볼 수를 바꾸면 자동으로 다시 계산 |
| DMRS type, data 없는 CDM group 수, RB당 DMRS RE | –, 개, RE | 예: type 1, CDM 2개, 36 RE |
| Data rate | Mbps | §4.4 |
| 입력 대비 여유 (TB size mode) | Byte | TBS/8 − 입력 Byte |

---

## 3. TBS 계산 절차 (TS 38.214 §5.1.3.2)

코드워드 하나의 TBS를 함수 `tbs(qm, r, v, n_prb, n_symb)`로 정의한다.

1. RB 하나에 실을 수 있는 데이터 RE 수
   `N'_RE = 12 × N_symb − N_DMRS − N_oh`
   `N_DMRS = N_DMRS_symb(N_symb, additionalPosition) × RE_CDM(type) × N_CDM`
   N_DMRS_symb는 §3.2 표, RE_CDM(type)은 §3.3 표에서 구한다. N_DMRS는 "data 없는 CDM group의 오버헤드를 포함한 RB당 DMRS RE 수"다 (TS 38.214 5.1.3.2).
   예: type 1 + CDM 2개 = 심볼당 12 RE (DMRS 심볼 전체를 비움), type 2 + CDM 1개 = 심볼당 4 RE
2. 전체 RE 수
   `N_RE = min(156, N'_RE) × n_PRB`
3. 정보 비트 수
   `N_info = N_RE × R × Qm × v`  (R = 표의 R×1024 값 / 1024)
4. N_info ≤ 3824인 경우
   - `n = max(3, ⌊log2(N_info)⌋ − 6)`
   - `N'_info = max(24, 2^n × ⌊N_info / 2^n⌋)`
   - TBS = 표 §5.2에서 N'_info 이상인 가장 작은 값
5. N_info > 3824인 경우
   - `n = ⌊log2(N_info − 24)⌋ − 5`
   - `N'_info = max(3840, 2^n × round((N_info − 24) / 2^n))` (round는 .5를 올림)
     - 구현 주의: Python 내장 `round()`는 .5를 짝수 쪽으로 반올림(banker's rounding)하므로 쓰지 않고 `floor(x + 0.5)`로 구현한다.
   - R ≤ 1/4이면: `C = ⌈(N'_info + 24) / 3816⌉`, `TBS = 8C × ⌈(N'_info + 24) / (8C)⌉ − 24`
   - 아니고 N'_info > 8424이면: `C = ⌈(N'_info + 24) / 8424⌉`, `TBS = 8C × ⌈(N'_info + 24) / (8C)⌉ − 24`
   - 그 외: `TBS = 8 × ⌈(N'_info + 24) / 8⌉ − 24`

### 3.1 Layer와 코드워드

- layer 1~4는 코드워드(TB) 1개에 매핑된다 (TS 38.211 표 7.3.1.3-1). 따라서 TBS는 위 절차를 한 번 계산한 값이다.
- Single-symbol DMRS는 type 1이 포트 4개, type 2가 포트 6개까지 지원하지만, 5 layer 이상은 코드워드 2개가 필요하므로 layer는 최대 4로 둔다 (D5, §6).
- Single-symbol DMRS에서 CDM group 하나는 포트 2개까지 쓴다. 그래서 data 없는 CDM group 1개면 layer는 최대 2다 (TS 38.212 표 7.3.1.2.2-1 type 1, 표 7.3.1.2.2-3 type 2, maxLength = 1).

### 3.2 심볼 길이별 DMRS 심볼 (TS 38.211 표 7.4.1.1.2-3, PDSCH mapping type A, single-symbol)

- 할당은 슬롯의 0번 심볼부터 시작한다고 가정한다 (mapping type A).
- 첫 DMRS 위치 l0 = 2 (dmrs-TypeA-Position = pos2) 고정.
- 표의 칸 = DMRS 심볼 위치 (괄호 안 숫자 = DMRS 심볼 개수)

| 할당 심볼 길이 | pos0 | pos1 | pos2 | pos3 |
|---|---|---|---|---|
| 3, 4 | 2 (1) | 2 (1) | 2 (1) | 2 (1) |
| 5, 6, 7 | 2 (1) | 2, 4 (2) | 2, 4 (2) | 2, 4 (2) |
| 8, 9 | 2 (1) | 2, 7 (2) | 2, 7 (2) | 2, 7 (2) |
| 10, 11 | 2 (1) | 2, 9 (2) | 2, 6, 9 (3) | 2, 6, 9 (3) |
| 12 | 2 (1) | 2, 9 (2) | 2, 6, 9 (3) | 2, 5, 8, 11 (4) |
| 13, 14 | 2 (1) | 2, 11 (2) | 2, 7, 11 (3) | 2, 5, 8, 11 (4) |

- UL(PUSCH, TS 38.211 표 6.4.1.1.3-3, mapping type A)은 4~14 심볼에서 위 표와 같은 값을 쓴다. UL의 최소 할당 길이는 4심볼이다.
- 예: DL 14심볼, pos2, type 1, CDM 2개 → DMRS 3심볼 → N'_RE = 12×14 − 3×6×2 − 0 = 132

### 3.3 DMRS configuration type별 CDM group (TS 38.211 표 7.4.1.1.2-1 type 1, 표 7.4.1.1.2-2 type 2)

| type | CDM group 최대 개수 | CDM group당 RE (RB당, DMRS 심볼당) RE_CDM | single-symbol 최대 포트 | 선택 가능한 N_CDM |
|---|---|---|---|---|
| type 1 | 2 (group 0, 1) | 6 | 4 | 1, 2 |
| type 2 | 3 (group 0, 1, 2) | 4 | 6 | 1, 2, 3 |

- 입력 창에는 선택한 type의 "CDM group 최대 개수"를 표시하고, N_CDM은 1 ~ 최대 개수 중에서 고른다.
- UL(PUSCH, transform precoding 끔)도 같은 type·CDM group 구성을 쓴다 (TS 38.211 6.4.1.1.3).
- DMRS 심볼 1개당 비우는 RE = RE_CDM × N_CDM

| | N_CDM = 1 | N_CDM = 2 | N_CDM = 3 |
|---|---|---|---|
| type 1 | 6 | 12 | – |
| type 2 | 4 | 8 | 12 |

---

## 4. 모드별 알고리즘

### 4.1 자원 size mode: `best_tbs(qm, v, n_prb, n_symb)`

1. 선택한 MCS 표에서 변조 차수가 Qm인 MCS 중 **index가 가장 큰 것**(= 코딩레이트 최대)을 고른다 (D3).
2. §3으로 TBS를 계산한다.
3. 출력: TBS, MCS index, 코딩레이트, data rate.

### 4.2 TB size mode: `find_resources(입력 Byte)`

목표 비트 B = 입력 Byte × 8. 심볼 수는 N_symb,avail로 고정한다 (D2).

```
for v = 1 .. v_max:                              # 기본 single layer, 부족할 때만 늘림
    for Qm in MCS 표의 변조 차수 (오름차순):          # 가장 낮은 변조 차수부터
        R_max = Qm의 최대 코딩레이트
        n_PRB = tbs(Qm, R_max, v, n, N_symb) ≥ B 를 만족하는 최소 n (1..N_RB,max)
        if 찾음:
            MCS = Qm의 MCS 중 tbs(Qm, R, v, n_PRB, N_symb) ≥ B 인 가장 낮은 MCS   # D1: 가장 작은 TBS
            return (TBS, Qm, MCS, R, v, n_PRB, N_symb)
return "시스템 최대 전송량 초과" + 최대 가능 TBS 표시
```

- 같은 Qm 안에서는 코딩레이트를 최대로 써서 **RB를 최소화**하고, 그 RB 개수에서 **입력을 담는 가장 작은 TBS**가 나오도록 MCS를 다시 낮춘다.
- Layer는 1 layer의 최대 변조·최대 RB로도 모자랄 때만 늘린다. 사용한 layer 수를 표시한다.
- TBS는 RB 개수에 대해 증가하는 함수이므로, 최소 RB는 이분 탐색으로 찾을 수 있다.

### 4.3 결과 창 재계산 (TB size mode)

결과 창의 Qm, v, n_PRB, N_symb를 수정한 뒤 [재계산]을 누르면 §4.1 `best_tbs`를 실행한다. 이때 입력 Byte 대비 여유를 다시 표시하고, TBS < 입력이면 "입력 데이터를 다 담지 못함" 경고를 보여 준다.

### 4.4 Data rate

- 슬롯 길이 `T_slot = 1 ms / 2^μ`
- 슬롯당 전송 비트 = 전체 TBS (해당 방향 심볼에 실린 비트)
- `Data rate [Mbps] = TBS_total / T_slot / 10^6`
- 모든 슬롯이 같은 심볼 구성(D4)이라고 가정한다. 슬롯 단위 TDD 패턴(DDDSU 등)은 이번 범위에서 제외한다.

### 4.5 입력 검증

| 조건 | 처리 |
|---|---|
| N_DL + N_F + N_UL ≠ 14 | 오류 |
| 선택한 방향의 사용 가능 심볼 = 0 | 오류 ("해당 방향 심볼이 없음") |
| N_symb > N_symb,avail | 오류 |
| N_symb < 3 (DL) 또는 < 4 (UL) | 오류 (§3.2 표에서 지원하지 않는 길이) |
| n_PRB > N_RB,max 또는 < 1 | 오류 |
| v > v_max | 오류 (CDM group 수 때문에 막히면 그 이유도 표시) |
| DMRS type이 1, 2가 아님 | 오류 |
| N_CDM < 1 또는 N_CDM > 선택한 type의 최대 개수 | 오류 ("type N의 CDM group은 최대 M개") |
| N'_RE ≤ 0 | 오류 (심볼 대비 DMRS·오버헤드가 너무 많음) |
| UL에서 1024QAM 표 선택 | 선택 불가 처리 |

---

## 5. 참조 표

> 구현 단계에서 3GPP 원문과 한 번 더 대조해 검증한다.

### 5.1 MCS 표 (TS 38.214 §5.1.3.1), 형식: `MCS: Qm, R×1024`

**64QAM 표 (Table 5.1.3.1-1)**
0:2,120 · 1:2,157 · 2:2,193 · 3:2,251 · 4:2,308 · 5:2,379 · 6:2,449 · 7:2,526 · 8:2,602 · 9:2,679 · 10:4,340 · 11:4,378 · 12:4,434 · 13:4,490 · 14:4,553 · 15:4,616 · 16:4,658 · 17:6,438 · 18:6,466 · 19:6,517 · 20:6,567 · 21:6,616 · 22:6,666 · 23:6,719 · 24:6,772 · 25:6,822 · 26:6,873 · 27:6,910 · 28:6,948

**256QAM 표 (Table 5.1.3.1-2)**
0:2,120 · 1:2,193 · 2:2,308 · 3:2,449 · 4:2,602 · 5:4,378 · 6:4,434 · 7:4,490 · 8:4,553 · 9:4,616 · 10:4,658 · 11:6,466 · 12:6,517 · 13:6,567 · 14:6,616 · 15:6,666 · 16:6,719 · 17:6,772 · 18:6,822 · 19:6,873 · 20:8,682.5 · 21:8,711 · 22:8,754 · 23:8,797 · 24:8,841 · 25:8,885 · 26:8,916.5 · 27:8,948

**1024QAM 표 (Table 5.1.3.1-4, DL 전용)**
0:2,120 · 1:2,193 · 2:2,449 · 3:4,378 · 4:4,490 · 5:4,616 · 6:6,466 · 7:6,517 · 8:6,567 · 9:6,616 · 10:6,666 · 11:6,719 · 12:6,772 · 13:6,822 · 14:6,873 · 15:8,682.5 · 16:8,711 · 17:8,754 · 18:8,797 · 19:8,841 · 20:8,885 · 21:8,916.5 · 22:8,948 · 23:10,805.5 · 24:10,853 · 25:10,900 · 26:10,948

(나머지 index는 재전송용 예약 값이라 사용하지 않는다.)

### 5.2 TBS 표 (Table 5.1.3.2-1, N_info ≤ 3824)

24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120, 128, 136, 144, 152, 160, 168, 176, 184, 192, 208, 224, 240, 256, 272, 288, 304, 320, 336, 352, 368, 384, 408, 432, 456, 480, 504, 528, 552, 576, 608, 640, 672, 704, 736, 768, 808, 848, 888, 928, 984, 1032, 1064, 1128, 1160, 1192, 1224, 1256, 1288, 1320, 1352, 1416, 1480, 1544, 1608, 1672, 1736, 1800, 1864, 1928, 2024, 2088, 2152, 2216, 2280, 2408, 2472, 2536, 2600, 2664, 2728, 2792, 2856, 2976, 3104, 3240, 3368, 3496, 3624, 3752, 3824

### 5.3 대역폭별 최대 RB (보조 입력용)

| SCS | 대역폭(MHz): 최대 RB |
|---|---|
| 15 kHz (FR1) | 5:25, 10:52, 15:79, 20:106, 25:133, 30:160, 35:188, 40:216, 45:242, 50:270 |
| 30 kHz (FR1) | 5:11, 10:24, 15:38, 20:51, 25:65, 30:78, 35:92, 40:106, 45:119, 50:133, 60:162, 70:189, 80:217, 90:245, 100:273 |
| 60 kHz (FR1) | 10:11, 15:18, 20:24, 25:31, 30:38, 35:44, 40:51, 45:58, 50:65, 60:79, 70:93, 80:107, 90:121, 100:135 |
| 60 kHz (FR2) | 50:66, 100:132, 200:264 |
| 120 kHz (FR2) | 50:32, 100:66, 200:132, 400:264 |

---

## 6. 이번 범위에서 제외 (나중에 추가 가능)

- 슬롯 단위 TDD 패턴(DDDSU 등)으로 평균 data rate 계산
- PT-RS, CSI-RS, SSB 등 기타 오버헤드 (xOverhead로 대신 반영)
- UL transform precoding (DFT-s-OFDM), 재전송, LBRM
- Carrier aggregation (여러 반송파 합산)
- Double-symbol DMRS, mapping type B (미니슬롯), dmrs-TypeA-Position = pos3
- 5 layer 이상 (코드워드 2개) — double-symbol DMRS가 필요하므로 함께 제외

---

## 7. 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-11-10 | 최초 작성 |
| v0.2 | 2026-11-10 | Double-symbol DMRS 제거. 심볼 길이와 additional position에 따른 DMRS 심볼 개수 표(§3.2) 추가. DMRS 위치를 결과에 표시. 최소 심볼 길이 검증 추가 |
| v0.3 | 2026-11-10 | 최대 layer를 DL·UL 모두 4로 제한 (규격 준수). 코드워드 2개 계산 규칙 삭제 |
| v1.0 | 2026-11-16 | Python 버전으로 이전 (nr_calc_codetap spec v0.3 기준). 함수 이름 snake_case로 변경, round 구현 주의 추가. 계산 규칙 변경 없음 |
| v1.1 | 2026-11-16 | DMRS configuration type(1/2)과 data 없는 CDM group 수(N_CDM)를 입력에 추가 (D7, D8, §3.3). N_DMRS를 `DMRS 심볼 수 × RE_CDM × N_CDM`으로 변경 (기본값 type 1·CDM 2개는 기존 결과와 같음). 최대 layer에 2 × N_CDM 조건 추가. 입력 창에 CDM group 최대 개수 표시. 제외 범위에서 DMRS type 2 삭제 |
