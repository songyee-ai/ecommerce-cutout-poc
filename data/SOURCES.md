# 샘플 이미지 출처와 라이선스

확인 날짜: **2026-09-22**

전 이미지 출처: [Pexels](https://www.pexels.com). Pexels License — 무료 사용, 상업적 사용 허용,
출처 표기 의무 없음, 재판매·타 스톡 플랫폼 재배포 금지.
(라이선스 원문: https://www.pexels.com/license/ · 2026-09-22 확인)

이 PoC는 이미지를 판매하거나 스톡 플랫폼에 재배포하지 않고, 배경 제거 성능 비교 목적으로만 사용한다.

## 난이도 구성

수업 지침(자료 10~20건, 그중 3~4건은 어려운 것)에 따라 **쉬운 7장 + 어려운 5장**으로 구성했다.
쉬운 것만 모으면 후보 모델들이 전부 비슷해 보여 비교표가 아무것도 알려주지 않는다.

### 쉬운 것 (기본 동작 확인용)

| 파일 | 상품 | 배경 | 출처 |
|---|---|---|---|
| `e01_sneaker_black.jpg` | 검정 스니커즈 (끈으로 매달림) | 밝은 회색 벽 | https://www.pexels.com/photo/black-shoes-on-a-white-background-8079829/ |
| `e02_sneaker_white_dark.jpg` | 흰 스니커즈 2짝 | 어두운 남색 | https://www.pexels.com/photo/pair-of-new-white-snickers-from-nike-12628400/ |
| `e03_watch_analog.jpg` | 검정 손목시계 | 흰 배경 | https://www.pexels.com/photo/minimalist-black-and-white-analog-wristwatch-33524465/ |
| `e04_headphones_black.jpg` | 검정 헤드폰 | 연분홍-흰 | https://www.pexels.com/photo/black-headphones-on-white-surface-7772548/ |
| `e05_lotion_bottle.jpg` | 흰 로션 튜브 | 분홍 | https://www.pexels.com/photo/close-up-shot-of-a-lotion-bottle-on-pink-surface-8533228/ |
| `e06_mug_coffee.jpg` | 흰 머그 + 커피 | 연분홍 | https://www.pexels.com/photo/white-cup-of-black-coffee-26985929/ |
| `e07_perfume_wood.jpg` | 검정 향수병 (나무 받침 위) | 어두운 실내 | https://www.pexels.com/photo/perfume-15096784/ |

### 어려운 것 (모델 간 차이가 갈리는 지점)

| 파일 | 어려운 이유 | 출처 |
|---|---|---|
| `h01_white_on_white_mugs.jpg` | **흰 상품 + 흰 배경** — 경계 대비가 거의 없음 | https://www.pexels.com/photo/white-mugs-on-white-surface-6312178/ |
| `h02_glass_perfume.jpg` | **투명** — 배경이 상품을 통과해 보이고 반사면까지 있음 | https://www.pexels.com/photo/close-up-of-a-simple-glass-perfume-bottle-7364096/ |
| `h03_furry_teddy.jpg` | **털** — 경계가 수천 갈래로 갈라짐 | https://www.pexels.com/photo/brown-bear-plush-toy-on-white-surface-5786759/ |
| `h04_thin_frame_glasses.jpg` | **얇은 금속테 + 렌즈 속이 배경** — 가는 선과 구멍을 동시에 처리해야 함 | https://www.pexels.com/photo/gold-framed-eyeglasses-on-white-surface-1499480/ |
| `h05_multi_object_bags.jpg` | **소품 여럿** — 가방 2개 외에 화병·선반·사람 손·휴대폰이 함께 있음. 무엇이 상품인지 모델이 알 수 없음 | https://www.pexels.com/photo/person-taking-a-picture-of-leather-handbags-5717972/ |

## 실제 업무 사진을 쓰지 않은 이유

제출물이 공개 GitHub 저장소이므로 미공개 상품 사진을 넣으면 그대로 공개된다.
공개 이미지를 쓰면 다른 사람이 클론해서 같은 결과를 재현할 수 있고(평가 항목 3),
보안 문제도 발생하지 않는다.
