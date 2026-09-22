#!/usr/bin/env python3
"""실행 환경과 라이선스를 확인해 기록으로 남긴다.

수업 지침: 라이선스는 저장소 첫 화면 표시가 아니라 설치한 패키지의 배포 정보에서
확인하는 편이 정확하다. 한 저장소 안에서 코드와 가중치의 조건이 다르게 붙어 있기도 하다.
"""
from __future__ import annotations

import json
import platform
import sys
from importlib import metadata


PACKAGES = ["torch", "transformers", "rembg", "onnxruntime", "numpy", "pillow"]


def pkg_info(name: str) -> dict:
    try:
        md = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return {"name": name, "installed": False}

    lic = md.get("License") or ""
    classifiers = [c for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
    if not lic or lic.lower() in {"unknown", ""}:
        lic = "; ".join(c.split("::")[-1].strip() for c in classifiers) or "(배포 정보에 없음)"

    return {
        "name": name,
        "installed": True,
        "version": md.get("Version"),
        "license": lic.strip().splitlines()[0][:120],
        "license_classifiers": classifiers,
        "home": md.get("Home-page") or md.get("Project-URL", ""),
    }


def main() -> int:
    report: dict = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": [pkg_info(p) for p in PACKAGES],
    }

    try:
        import torch
        report["torch_cuda_available"] = torch.cuda.is_available()
        report["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        if torch.cuda.is_available():
            report["gpu_vram_gb"] = round(
                torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
    except Exception as exc:                                       # noqa: BLE001
        report["torch_error"] = str(exc)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
