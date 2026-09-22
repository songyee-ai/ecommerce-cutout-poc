#!/usr/bin/env bash
# 후보를 하나씩 별도 프로세스로 돌린다.
#
# 왜 한 프로세스에 몰아넣지 않는가:
# 2026-09-22 첫 실행에서 세 후보를 같은 프로세스에 올렸다가 메모리 11.7GB를 써서
# 무료 Colab 한도(약 13GB)를 넘겼고, 커널이 OOM으로 프로세스를 죽였다.
# 후보마다 프로세스를 나누면 앞 후보가 쓰던 메모리가 확실히 반납된다.
#
# 사용법: bash run_all.sh <run-id> [이미지폴더] [결과폴더]

set -u

RUN_ID="${1:-run2}"
IMAGES="${2:-samples}"
OUT="${3:-outputs}"
LOG="/content/${RUN_ID}.log"

cd /content || exit 1
rm -rf "${OUT:?}/${RUN_ID}"
: > "$LOG"

for b in sam u2net birefnet; do
  echo "=== $b 시작 $(date +%T) ===" >> "$LOG"
  python run_cutout.py --images "$IMAGES" --out "$OUT" --backends "$b" --run-id "$RUN_ID" >> "$LOG" 2>&1
  echo "=== $b 종료 rc=$? $(date +%T) ===" >> "$LOG"
done

python run_cutout.py --images "$IMAGES" --out "$OUT" --run-id "$RUN_ID" --merge-only >> "$LOG" 2>&1
echo "ALL_DONE $(date +%T)" >> "$LOG"
