# A.C.E.3 THE FINAL 한국어 패치

PS2 **『Another Century's Episode 3: The Final』**(SLPS-25784, 반다이남코 × 프롬소프트웨어, 2007)
비공식 한국어 번역 패치입니다.

<div class="badges">

[![Release](https://img.shields.io/github/v/release/kimjh-eclipse/ace3-korean?label=%EC%B5%9C%EC%8B%A0%20%ED%8C%A8%EC%B9%98&color=1d5fd6)](https://github.com/kimjh-eclipse/ace3-korean/releases/latest)
[![GitHub](https://img.shields.io/badge/GitHub-ace3--korean-123f92?logo=github)](https://github.com/kimjh-eclipse/ace3-korean)

</div>

## 다운로드

> **[📦 최신 패치 다운로드 (GitHub Releases)](https://github.com/kimjh-eclipse/ace3-korean/releases/latest)**
>
> zip 안에 xdelta 패치, 적용 안내(README), 검증 해시가 들어 있습니다.
> 원본 게임 ISO는 포함되지 않으며, 본인이 합법적으로 소유한 원본이 필요합니다.

## 적용 방법

xdelta3 호환 도구(xdelta3 CLI, Delta Patcher, xdeltaUI 등)로 일본판 원본 ISO에 적용합니다.

```bash
xdelta3 -d -s "원본.iso" ACE3_kr_patch_v20260712b.xdelta "ACE3_KR.iso"
```

| 검증 | SHA256 |
|---|---|
| 원본 ISO | `5264079d36d953f464b166052e1ddea9be22a84c30a9333da24b8e1471311705` |
| 패치 적용 결과 | `7c4463a15720f9423278b246e818e851b5c9fc58029cb520614edc63ec85f74b` |

## 번역 범위

- 메뉴 · 세이브/로드 · 초기설정 · 인터미션 등 **프론트엔드 전체**
- **스토리 · 브리핑 · 미션 무전(자막) 대사 전체** — 고유 문자열 22,000+ 항목
- 화자명 · 유닛명 · 전투 용어

## 폰트

전 화면의 한글은 바탕(명조)계 **비트맵 글리프**로 주입되어, 원본 영문·숫자와
동일한 높이 · 베이스라인 · 외곽선 스타일로 표시됩니다.

## 알려진 제한

- 일시정지 커맨드 리스트의 일부 무기명은 별도 데이터 경로로 표시되어 원문이 깨져 보일 수 있습니다.
- 전투 후 대화 화면에서 희귀 음절 15자(전체 출현의 약 1%)와 극히 일부 문자열의 쉼표·물음표는 ？로 표시될 수 있습니다.

- 일부 미션의 소형 자막 폰트는 수용 한계로 한글 일부만 표시될 수 있습니다.
- 극소수 장문(4개 섹션)은 컨테이너 용량 한계로 띄어쓰기가 축약됩니다.

## 기술 문서

이 사이트의 왼쪽 목차에서 역공학 문서를 볼 수 있습니다 —
[파일 포맷 명세](formats.md) · [폰트 시스템 지도](fonts.md) ·
[엔진 렌더러 제약](engine-constraints.md) · [한글 글리프 주입 기법](glyph-injection.md) ·
[빌드 파이프라인](pipeline.md)

## 법적 고지

이 패치와 문서는 팬 제작 비공식 번역물이며, 원본 게임에서 추출한 자산(ISO·텍스트·이미지)을
배포하지 않습니다. 게임의 모든 권리는 원 저작권자(반다이남코 엔터테인먼트, 프롬소프트웨어 및
각 참전작 저작권자)에게 있습니다.
