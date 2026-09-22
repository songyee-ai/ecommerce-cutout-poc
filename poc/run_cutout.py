#!/usr/bin/env python3
"""
이커머스 상품 누끼 PoC — 후보 모델을 같은 사진에 나란히 돌려 비교한다.

설계 원칙 (2026-09-22 수업 지침 그대로):
  1. 모델은 전부 가중치가 공개된 것만 쓴다. 사진을 외부 서비스로 전송하지 않는다.
  2. 판정에 쓰는 값은 코드에 박지 않고 전부 인자로 받는다.
  3. 점수와 신뢰도는 반올림하지 않고 그대로 남긴다. 임계값을 정할 때 쓴다.
  4. 중간 산출물을 파일로 남기고, 다시 돌려도 덮어쓰지 않는다 (--run-id 로 분리).
  5. 결과를 눈으로 확인할 수 있는 형태(체크 이미지)로 함께 저장한다.

사용법:
    python run_cutout.py --images data/samples --out outputs --backends sam,u2net,birefnet
"""
from __future__ import annotations

import argparse
import csv
import gc
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from PIL import Image


# ---------------------------------------------------------------- 인자

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="상품 누끼 후보 모델 비교")
    p.add_argument("--images", type=Path, required=True, help="입력 사진 폴더")
    p.add_argument("--out", type=Path, required=True, help="결과를 쓸 폴더")
    p.add_argument("--backends", default="sam,u2net,birefnet",
                   help="쉼표로 구분한 후보 목록 (sam,u2net,isnet,birefnet)")
    p.add_argument("--run-id", default=None,
                   help="결과 하위 폴더 이름. 기본은 실행 시각이라 이전 결과를 덮어쓰지 않는다")

    # SAM 쪽 판정값 — 전부 인자다
    p.add_argument("--sam-model", default="facebook/sam-vit-base",
                   help="Hugging Face 모델 ID")
    p.add_argument("--sam-point", default="center", choices=["center", "center9"],
                   help="상품을 지목하는 방식. center=중앙 1점, center9=중앙 주변 3x3 점")
    p.add_argument("--sam-point-spread", type=float, default=0.12,
                   help="center9 일 때 점을 벌리는 폭 (이미지 짧은 변 대비 비율)")
    p.add_argument("--sam-mask-pick", default="best_iou",
                   choices=["best_iou", "largest", "smallest"],
                   help="SAM이 돌려준 후보 마스크 중 무엇을 고를지")
    p.add_argument("--sam-mask-threshold", type=float, default=0.0,
                   help="마스크 로짓을 이진화하는 경계")
    p.add_argument("--sam-stability-delta", type=float, default=1.0,
                   help="안정도 점수를 잴 때 경계를 흔드는 폭")

    # 누끼 전용 모델 쪽 판정값
    p.add_argument("--alpha-threshold", type=int, default=128,
                   help="알파값을 상품/배경으로 가를 경계 (0-255)")
    p.add_argument("--edge-band", type=int, default=8,
                   help="경계 애매 비율을 잴 때 중간값으로 볼 폭 (알파 기준 +-)")

    p.add_argument("--max-side", type=int, default=1400,
                   help="처리 전에 긴 변을 이 크기로 줄인다 (0이면 원본 유지)")
    p.add_argument("--merge-only", action="store_true",
                   help="모델은 돌리지 않고, 이미 있는 scores_*.csv 만 합친다")
    return p


# ---------------------------------------------------------------- 결과 한 줄

@dataclass
class Result:
    image: str
    backend: str
    seconds: float
    # 신뢰도 계열 — 반올림하지 않는다
    sam_iou: float | None = None          # SAM이 스스로 매긴 마스크 품질 예측
    sam_stability: float | None = None    # 경계를 흔들어도 면적이 유지되는 정도
    coverage: float = 0.0                 # 상품으로 판정된 픽셀 비율
    edge_ambiguity: float = 0.0           # 알파가 중간값인 픽셀 비율 (경계가 애매한 정도)
    touches_border: float = 0.0           # 마스크가 사진 테두리에 닿은 비율
    error: str = ""


# ---------------------------------------------------------------- 공통 계산

def mask_metrics(alpha: np.ndarray, alpha_threshold: int, edge_band: int) -> dict:
    """알파 채널(0-255)에서 신뢰도 대용 지표를 계산한다.

    edge_ambiguity 는 경계가 애매한 정도다. 알파가 0도 255도 아닌 어중간한 값인
    픽셀이 많다는 것은 모델이 그 경계를 확신하지 못했다는 뜻이다.
    """
    total = alpha.size
    solid = alpha >= alpha_threshold
    ambiguous = (alpha > edge_band) & (alpha < 255 - edge_band)

    border = np.zeros_like(solid)
    border[0, :] = True
    border[-1, :] = True
    border[:, 0] = True
    border[:, -1] = True

    return {
        "coverage": float(solid.sum()) / total,
        "edge_ambiguity": float(ambiguous.sum()) / total,
        "touches_border": float((solid & border).sum()) / max(int(border.sum()), 1),
    }


def load_image(path: Path, max_side: int) -> Image.Image:
    img = Image.open(path).convert("RGB")
    if max_side and max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    return img


def checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    """투명 영역을 눈으로 보려면 체커보드 위에 얹어야 한다."""
    w, h = size
    ys, xs = np.mgrid[0:h, 0:w]
    pattern = (((ys // cell) + (xs // cell)) % 2)[..., None]
    board = np.where(pattern, 235, 200).astype(np.uint8)
    board = np.repeat(board, 3, axis=2)
    return Image.fromarray(board)


def save_check_image(original: Image.Image, alpha: np.ndarray, dest: Path, caption: str) -> None:
    """원본 | 마스크 | 체커보드 합성 을 가로로 붙여 저장한다.

    수업 지침: 숫자만 보고 판단하면 값이 의도한 것을 재고 있지 않은 경우를 놓친다.
    """
    from PIL import ImageDraw

    w, h = original.size
    mask_img = Image.fromarray(alpha).convert("RGB")

    cut = original.copy()
    cut.putalpha(Image.fromarray(alpha))
    comp = checkerboard((w, h)).convert("RGBA")
    comp.alpha_composite(cut)
    comp = comp.convert("RGB")

    bar = 26
    sheet = Image.new("RGB", (w * 3, h + bar), "#111111")
    sheet.paste(original, (0, bar))
    sheet.paste(mask_img, (w, bar))
    sheet.paste(comp, (w * 2, bar))
    ImageDraw.Draw(sheet).text((6, 6), caption, fill="#ffffff")
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, quality=90)


# ---------------------------------------------------------------- 후보 1: SAM

class SamBackend:
    """범용 분할 모델. 상품을 지목해 주어야 하고, 신뢰도 점수를 함께 돌려준다."""

    def __init__(self, args):
        import torch
        from transformers import SamModel, SamProcessor

        self.torch = torch
        self.args = args
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = SamProcessor.from_pretrained(args.sam_model)
        self.model = SamModel.from_pretrained(args.sam_model).to(self.device).eval()

    def _points(self, w: int, h: int) -> list[list[float]]:
        cx, cy = w / 2, h / 2
        if self.args.sam_point == "center":
            return [[cx, cy]]
        d = min(w, h) * self.args.sam_point_spread
        return [[cx + dx * d, cy + dy * d] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]

    def run(self, img: Image.Image) -> tuple[np.ndarray, dict]:
        torch = self.torch
        pts = self._points(*img.size)
        inputs = self.processor(img, input_points=[[pts]], return_tensors="pt").to(self.device)

        with torch.no_grad():
            out = self.model(**inputs, multimask_output=True)

        # 원본 해상도로 되돌린 로짓 (이진화 전이라 임계값을 흔들어 볼 수 있다)
        logits = self.processor.image_processor.post_process_masks(
            out.pred_masks.float().cpu(),
            inputs["original_sizes"].cpu(),
            inputs["reshaped_input_sizes"].cpu(),
            binarize=False,
        )[0][0]                                    # (후보 수, H, W)
        ious = out.iou_scores[0][0].float().cpu().numpy()

        thr = self.args.sam_mask_threshold
        masks = (logits > thr).numpy()

        if self.args.sam_mask_pick == "best_iou":
            idx = int(np.argmax(ious))
        elif self.args.sam_mask_pick == "largest":
            idx = int(np.argmax(masks.reshape(len(masks), -1).sum(1)))
        else:
            idx = int(np.argmin(masks.reshape(len(masks), -1).sum(1)))

        # 안정도: 경계를 +-delta 흔들었을 때 면적이 얼마나 유지되는가
        d = self.args.sam_stability_delta
        hi = int((logits[idx] > thr + d).numpy().sum())
        lo = int((logits[idx] > thr - d).numpy().sum())
        stability = float(hi) / float(lo) if lo > 0 else 0.0

        alpha = masks[idx].astype(np.uint8) * 255
        return alpha, {"sam_iou": float(ious[idx]), "sam_stability": stability}


# ---------------------------------------------------------------- 후보 2·3: 누끼 전용 모델

class RembgBackend:
    """배경 제거만 하도록 만들어진 전용 모델. 신뢰도 점수는 내주지 않는다."""

    # birefnet-general(전체 판본)은 무료 Colab 메모리 한도를 넘겨 죽는다(2026-09-22 확인).
    # 가벼운 판본 birefnet-general-lite 를 쓴다.
    MODELS = {
        "u2net": "u2net",
        "isnet": "isnet-general-use",
        "birefnet": "birefnet-general",
        "birefnet-lite": "birefnet-general-lite",
    }

    def __init__(self, key: str):
        from rembg import new_session, remove

        self.name = key
        self._remove = remove
        self.session = new_session(self.MODELS[key])

    def run(self, img: Image.Image) -> tuple[np.ndarray, dict]:
        out = self._remove(img, session=self.session)
        alpha = np.array(out.convert("RGBA"))[..., 3]
        return alpha, {}


# ---------------------------------------------------------------- 실행

FIELDS = list(Result.__dataclass_fields__.keys())


def write_scores(dest: Path, rows: list[Result]) -> None:
    """점수는 반올림하지 않고 그대로 남긴다. 임계값을 정할 때 쓴다."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(asdict(r))
    print(f"  -> {dest.name} ({len(rows)}줄)")


def merge_scores(root: Path) -> int:
    """후보별로 남긴 scores_*.csv 를 하나로 합치고, 빈 채점표를 만든다.

    후보를 각각 다른 프로세스로 돌려도 이 단계에서 합쳐진다.
    """
    parts = sorted(root.glob("scores_*.csv"))
    if not parts:
        print(f"합칠 scores_*.csv 가 없습니다: {root}", file=sys.stderr)
        return 1

    merged: list[dict] = []
    for part in parts:
        with part.open(encoding="utf-8") as fh:
            merged.extend(csv.DictReader(fh))

    with (root / "scores.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(merged)

    # 사람이 채울 채점표 — 결과를 보기 전에는 비어 있다.
    # 이미 채워 둔 것이 있으면 덮어쓰지 않는다.
    scoring = root / "scoring.csv"
    if scoring.exists():
        print(f"  scoring.csv 가 이미 있어 그대로 둡니다")
    else:
        with scoring.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["image", "backend", "pass_fail", "failure_reason"])
            for r in merged:
                w.writerow([r["image"], r["backend"], "", ""])

    print(f"  합침: {[p.name for p in parts]} -> scores.csv ({len(merged)}줄)")
    return 0


def make_backend(key: str, args):
    if key == "sam":
        return SamBackend(args)
    if key in RembgBackend.MODELS:
        return RembgBackend(key)
    raise ValueError("모르는 후보: " + key)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    run_id = args.run_id or time.strftime("%Y%m%d-%H%M%S")
    root = args.out / run_id
    root.mkdir(parents=True, exist_ok=True)

    images = sorted(p for p in args.images.iterdir()
                    if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not images:
        print("입력 사진이 없습니다: " + str(args.images), file=sys.stderr)
        return 1

    keys = [k.strip() for k in args.backends.split(",") if k.strip()]
    print(f"[설정] 사진 {len(images)}장 · 후보 {keys} · 결과 -> {root}")
    (root / "config.json").write_text(
        json.dumps({k: str(v) for k, v in vars(args).items()}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    if args.merge_only:
        return merge_scores(root)

    rows: list[Result] = []

    for key in keys:
        print(f"\n=== 후보: {key} ===")
        try:
            t0 = time.perf_counter()
            backend = make_backend(key, args)
            print(f"  모델 준비 {time.perf_counter() - t0:.1f}초")
        except Exception as exc:                                   # noqa: BLE001
            print(f"  준비 실패: {exc}", file=sys.stderr)
            failed = [Result(p.name, key, 0.0, error="load_failed: " + str(exc))
                      for p in images]
            rows.extend(failed)
            write_scores(root / f"scores_{key}.csv", failed)
            continue

        backend_rows: list[Result] = []
        for path in images:
            img = load_image(path, args.max_side)
            rec = Result(path.name, key, 0.0)
            try:
                t0 = time.perf_counter()
                alpha, extra = backend.run(img)
                rec.seconds = time.perf_counter() - t0

                for k, v in extra.items():
                    setattr(rec, k, v)
                for k, v in mask_metrics(alpha, args.alpha_threshold, args.edge_band).items():
                    setattr(rec, k, v)

                cut = img.copy()
                cut.putalpha(Image.fromarray(alpha))
                png_dir = root / key / "png"
                png_dir.mkdir(parents=True, exist_ok=True)
                cut.save(png_dir / (path.stem + ".png"))

                caption = (f"{key} | {path.name} | {rec.seconds:.2f}s | "
                           f"iou={rec.sam_iou} stab={rec.sam_stability} "
                           f"cov={rec.coverage:.4f} edge={rec.edge_ambiguity:.4f}")
                save_check_image(img, alpha, root / key / "check" / (path.stem + ".jpg"), caption)
                print(f"  {path.name:32s} {rec.seconds:6.2f}s  cov={rec.coverage:.4f}")
            except Exception as exc:                               # noqa: BLE001
                rec.error = str(exc)
                print(f"  {path.name:32s} 실패: {exc}", file=sys.stderr)
            rows.append(rec)
            backend_rows.append(rec)

        # 후보 하나가 끝날 때마다 바로 파일로 남긴다.
        # 뒤 후보가 죽어도 앞 결과를 잃지 않는다 (2026-09-22 OOM 사고로 추가).
        write_scores(root / f"scores_{key}.csv", backend_rows)

        # 다음 후보를 올리기 전에 이 후보를 메모리에서 내린다.
        # 세 후보를 동시에 올려 두면 무료 Colab 한도(약 13GB)를 넘겨 프로세스가 죽는다.
        del backend
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:                                          # noqa: BLE001
            pass

    merge_scores(root)
    print(f"\n완료. scores.csv / scoring.csv / png / check -> {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
