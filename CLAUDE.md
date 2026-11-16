# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 현황

- 빈 폴더에서 새로 시작합니다 (2026-11-16). git 초기화는 1단계에서 합니다.
- 만들 앱: 5G NR TB size 계산기. 지난주 TypeScript 버전(nr_calc_codetap)을 Python으로 다시 만드는 연습입니다.
- 계산 규칙과 결정 사항은 `docs/spec.md`를 기준으로 삼습니다(1단계에서 작성). 계산 규칙을 바꿀 때는 spec.md를 먼저 고치고(변경 이력 포함) 코드와 테스트를 맞춥니다.
- 진행 계획(5단계): ① TBS 계산 함수 → ② 골든 벡터 테스트 → ③ 화면 + Pyodide 연결 → ④ PWA로 PC 설치(오프라인 동작) → ⑤ (선택) GitHub Pages 배포. 사용자가 단계마다 검토한 뒤 다음 단계로 넘어갑니다.

## 기술 스택

- 계산: Python 3.11+ (`nr_calc.py`). 화면과 무관하게 동작하며, 같은 파일을 Colab에서도 import해 쓸 수 있게 표준 라이브러리만 사용합니다.
- 테스트: pytest.
- 화면: 프레임워크 없이 HTML/CSS/JavaScript. 브라우저 안에서 Pyodide로 `nr_calc.py`를 불러와 실행합니다.
- 배포 형태: PC에 설치하는 PWA(manifest + service worker, 오프라인 동작).
- 사용자도 VS Code에서 직접 코드를 고칩니다. 작업 전에 파일을 다시 읽고, 사용자가 고친 부분을 덮어쓰지 않습니다.

## 폴더 구조

```
nr_calc.py            계산 모듈 (공개 함수: tbs, dmrs_symbols, dmrs_info, validate, best_tbs, find_resources, data_rate_mbps)
tests/                pytest 골든 벡터 (2단계)
index.html, style.css, app.js        화면 (3단계, 저장소 루트에 둠)
manifest.webmanifest, sw.js, icons/, vendor/pyodide/   PWA (4단계)
docs/spec.md          계산 규칙 기준 문서
```

- `nr_calc.py`의 결과는 dict(JSON으로 넘길 수 있는 기본 타입)이고, 오류는 예외 대신 `errors` 목록으로 돌려줍니다. 코딩레이트는 `fractions.Fraction`으로 계산합니다.

## 명령

- 즉석 확인: `python -c "import nr_calc; print(nr_calc.best_tbs({'dmrs_pos': 0}, 8, 1, 273, 14))"`
- PowerShell에서 한글이 깨지면 `$env:PYTHONIOENCODING='utf-8'`를 먼저 실행합니다.

## 테스트 기준값

- TBS 기대값은 널리 알려진 값과 공식 분기별 손계산 값을 씁니다. 지난 버전에서 쓴 값: 273 RB 256QAM 1 layer 319,784 / 4 layer 1,277,992. 이 두 값은 **14심볼, DMRS pos0(DMRS 1심볼), DMRS type 1, data 없는 CDM group 2개(N'_RE=156), xOverhead 0** 조건입니다. spec 기본값 pos2(DMRS 3심볼)로 계산하면 1 layer 270,576 / 4 layer 1,081,512가 나옵니다.
- 사용자가 아는 값을 골든 벡터로 추가합니다. Claude가 만든 기대값은 출처(스펙 표·절 또는 손계산 과정)를 함께 적습니다.

## 작업 규칙

1. **답변은 항상 한국어로** 합니다.
2. **파일을 바꿀 때마다 무엇을 왜 바꿨는지 요약**해서 알려줍니다 (파일별로 짧게).
3. **환경 설정이 필요하면 설정 방법을 단계별로 설명**합니다: 무엇을 설치/설정하는지, 왜 필요한지, 실행할 명령, 성공 여부 확인 방법. 환경은 Windows 11이며 터미널은 PowerShell / Git Bash입니다.
4. **Git/GitHub 작업을 처음 적용할 때는 개념부터 설명**합니다. commit·push 등은 사용자가 요청할 때만 실행합니다.
5. **코드에 3GPP 스펙의 절·표 번호를 주석으로** 답니다 (예: TS 38.214 5.1.3.2, 표 5.1.3.1-2).
