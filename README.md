# ace3-korean

**A.C.E.3 THE FINAL** (PS2, 일본판 SLPS_257.84) 비공식 한국어화 파이프라인 도구 모음.

> **📦 한국어 패치 다운로드: [Releases](https://github.com/kimjh-eclipse/ace3-korean/releases/latest)**
> — xdelta 패치 + 적용법 + 검증 해시 동봉. 원본 ISO는 포함되지 않습니다.
>
> **📖 기술 문서: [book/](book/SUMMARY.md)** (포맷 명세 · 폰트 시스템 · 엔진 제약 · 주입 기법) — GitHub Wiki에도 동일 게재.

ISO를 직접 파싱해 BND3 아카이브 → 텍스트 컨테이너 → 폰트(메인/셸 13종)를 역공학하고,
번역 삽입 → 폰트 글리프 재생성 → 안전 슬롯 할당 → ISO 재조립 → xdelta 패치 생성까지의
파이프라인을 제공합니다.

> 이 저장소에는 **원본 게임에서 추출한 텍스트/이미지/번역 데이터는 포함되어 있지 않습니다.**
> 저작권 있는 원본 게임 자산(ISO, 추출 텍스트, 번역 대역표)은 별도 비공개로 관리합니다.
> 실행하려면 본인이 합법적으로 소유한 ISO 파일이 필요합니다.

## 구조

### 공용 라이브러리
- `ace3lib.py` — BND3/텍스트 컨테이너 파싱, SJIS 구조 검증(`try_parse`), `⟦XXXX⟧` 커스텀 코덱
- `shellfont.py` — 셸/HUD 폰트 파싱·재작성(PSMT32 스위즐, 글리프 드로잉, 메트릭 재계산)
- `deswz_tables.py` — PSMT32 업로드 4bpp GS 스위즐/디스위즐 변환 테이블
- `emu.py` — PCSX2 자동 조작(창 탐색, 키 입력, 스크린샷 캡처) — 인게임 검증용
- `build.py` — 최종 ISO 빌더: 번역 로드 → 한글 음절 안전 슬롯 할당(동적 회수 포함) → 폰트 글리프 주입 → ISO 패치

### 추출/분석 파이프라인
| 스크립트 | 역할 |
|---|---|
| `03_bnd_toc.py` | ISO → BND3 TOC 추출 |
| `25_build_db.py` | TOC → 텍스트 컨테이너 DB 빌드 |
| `51_kanji_usage.py` | 메인 폰트 한자 사용량 분석 → 안전 슬롯 계산 |
| `86_iso_fontscan.py` / `87_newfonts.py` | 셸/HUD 폰트 13종 스캔 및 메타데이터 생성 |
| `99_shell_used_kanji.py` / `100_shell_strings_full.py` / `101_check_coverage.py` | 셸 문자열 전수 추출/커버리지 검증 |
| `105_scan_badchars.py` / `109_why_reject.py` / `110_relax_impact.py` | 텍스트 컨테이너 파서 검증 완화 영향 분석 |

### 번역 배치/병합 도구
| 스크립트 | 역할 |
|---|---|
| `103_make_batches.py` / `104_merge_tl.py` | 셸 UI 번역 배치 생성/병합 |
| `111_new_untranslated.py` / `112_font_budget.py` / `113_extract_ui.py` | UI 단문 추출 및 폰트 예산(안전 슬롯) 측정 |
| `120_story_budget.py` / `121_main_donor.py` | 스토리(인게임 대사) 전량 번역 시 폰트 예산 타당성 검증 |
| `122_story_batches.py` / `123_merge_story.py` | 스토리 배치 생성 및 병합(태그·개행 하드 검증 포함) |
| `124_glossary_cand.py` | 스토리 고유명사 후보(빈도) 추출 |
| `130_export_csv.py` | 번역 자산 CSV 내보내기 |

## 파이프라인 개요

1. `03_bnd_toc.py` → `25_build_db.py`: 원본 ISO에서 텍스트 DB(`db.json`) 구축
2. `51_kanji_usage.py`, `86_iso_fontscan.py`, `87_newfonts.py`: 폰트 구조 및 안전 슬롯 분석
3. 번역 대상 문자열을 배치(JSON)로 분할 → 번역(LLM 서브에이전트 또는 수작업) → 병합 도구로 하드 검증
4. `build.py`: 번역 반영, 한글 글리프 생성, 안전 슬롯 우선 배정, ISO 재조립
5. xdelta3로 원본↔패치본 델타 생성 → 배포
6. PCSX2로 인게임 렌더링 검증

## 핵심 설계: 안전 슬롯(safe-slot) 할당

메인/셸 폰트 모두 원본 일본어 한자 영역 중 **게임이 실제로 쓰지 않는 칸**을 우선 계산해
한글 글리프를 배정합니다. 번역이 끝난 문자열이 쓰던 한자 칸은 매 빌드마다 동적으로
회수(freeable)되어 추가 여유분으로 편입되므로, 미번역 텍스트를 손상시키지 않으면서
점진적으로 번역 범위를 넓힐 수 있습니다. 단, 안전 슬롯 총량보다 신규 한글 음절 수요가
큰 상태에서 부분 배포하면 미번역 문자열이 깨질 수 있으므로, 대량 텍스트(스토리 등)는
전량 번역 완료 후 일괄 반영하는 것이 안전합니다.


### 캡션(무전 자막)·최종 폰트 마감 (2026-07)
| 스크립트 | 역할 |
|---|---|
| `220_patch_radio_space5f.py` | 라디오 섹션 텍스트 재인코딩(공백 0x5F/0x8140 분기, 장 치환) + 반각 부호 |
| `222_patch_caption_batang.py` | 캡션폰트 8종에 바탕 내장 비트맵 글리프 주입(균일 14px, 베이스라인 정렬, halo 규칙) |
| `223_shell_batang_unify.py` | 셸 폰트 6종 + 경보 HUD 폰트 재주입 — 전 화면 폰트 스타일 통일 |

엔진의 폰트 테이블 제약(레인지 추가 불가, 재정렬 시 크래시)과 팔레트 규칙(idx10~15 투명),
비트맵 글리프 렌더링 근거는 [book/](book/SUMMARY.md) 문서를 참고하십시오.
