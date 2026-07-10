# A.C.E.3 THE FINAL 한국어화 — 기술 문서

PS2 『Another Century's Episode 3: The Final』(SLPS-25784) 비공식 한국어화 과정에서
역공학으로 규명한 파일 포맷, 폰트 시스템, 엔진 렌더러의 제약과 이를 우회한 주입 기법을 정리한다.

- 패치 배포: [Releases](https://github.com/kimjh-eclipse/ace3-korean/releases/latest)
- 도구 소스: [저장소 루트](https://github.com/kimjh-eclipse/ace3-korean)

## 문서 구성

| 문서 | 내용 |
|---|---|
| [파일 포맷 명세](formats.md) | ISO / BND3 아카이브 / 텍스트 컨테이너(00010000) 바이너리 레이아웃 |
| [폰트 시스템 지도](fonts.md) | 폰트 14종의 위치·구조, GS 스위즐, 팔레트, 메트릭 |
| [엔진 렌더러 제약](engine-constraints.md) | 실기(GS 덤프·크래시)로 확정한 폰트 테이블 취급 규칙 |
| [한글 글리프 주입 기법](glyph-injection.md) | donor 코드 방식, 비트맵 렌더링, 공백/특수문자 처리 |
| [빌드 파이프라인](pipeline.md) | 추출→번역→재조립→패치 생성→인게임 검증 절차 |

## 법적 고지

이 문서와 저장소는 **원본 게임에서 추출한 텍스트·이미지·번역 대역 데이터를 포함하지 않는다**.
문서 내 바이너리 오프셋/구조 명세는 상호운용을 위한 사실 정보이다. 패치 적용에는
본인이 합법적으로 소유한 원본 ISO가 필요하다.
