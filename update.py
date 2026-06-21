"""
update.py - LQ Dashboard GitHub ZIP 자동 업데이트 도구

사용법:
    1. update.bat 더블클릭  -> Downloads 폴더에서 LQ_Dashboard*.zip 자동 탐색
    2. ZIP 파일을 update.bat 위에 드래그&드롭
"""

import sys
import os
import zipfile
import hashlib
import tempfile
import shutil
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────

ZIP_PATTERN = "LQ_Dashboard*.zip"

# 업데이트 시 건너뛸 항목
SKIP_PARTS    = {"__pycache__", ".git", ".claude", "logs"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".pyd"}
SKIP_NAMES    = {"Thumbs.db", ".DS_Store"}

# 덮어쓰지 않는 로컬 전용 파일
PRESERVE_NAMES = {".env"}
PRESERVE_PATHS = {".claude/settings.local.json"}

# ──────────────────────────────────────────────────────────────
# 유틸 함수
# ──────────────────────────────────────────────────────────────

def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(524288), b""):
            h.update(chunk)
    return h.hexdigest()


def should_skip(rel: Path) -> bool:
    for part in rel.parts:
        if part in SKIP_PARTS:
            return True
    if rel.suffix.lower() in SKIP_SUFFIXES:
        return True
    if rel.name in SKIP_NAMES:
        return True
    return False


def should_preserve(rel: Path) -> bool:
    if rel.name in PRESERVE_NAMES:
        return True
    if str(rel).replace("\\", "/") in PRESERVE_PATHS:
        return True
    return False


def detect_zip_root(zf: zipfile.ZipFile) -> str:
    """GitHub ZIP 최상위 폴더(LQ_Dashboard-main/ 등) 자동 감지"""
    entries = [n for n in zf.namelist() if not n.endswith("/")]
    if not entries:
        return ""
    candidate = entries[0].split("/")[0] + "/"
    if "/" in entries[0] and all(n.startswith(candidate) for n in entries):
        return candidate
    return ""


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────

def main():
    # 콘솔 출력 UTF-8 강제
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print()
    print("=" * 42)
    print("   LQ All In One - 자동 업데이트")
    print("=" * 42)
    print()

    script_dir = Path(__file__).parent.resolve()

    # 1. ZIP 경로 결정
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        zip_path = Path(args[0].strip('"'))
        if not zip_path.exists():
            print(f"[오류] ZIP 파일을 찾을 수 없습니다: {zip_path}")
            input("\nEnter를 눌러 종료...")
            sys.exit(1)
        if zip_path.suffix.lower() != ".zip":
            print(f"[오류] ZIP 파일(.zip)만 지원합니다: {zip_path.name}")
            input("\nEnter를 눌러 종료...")
            sys.exit(1)
        print("모드          : 드래그&드롭")
    else:
        print("모드          : 자동 탐색 (Downloads)")
        downloads = Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"
        zips = sorted(downloads.glob(ZIP_PATTERN), key=lambda p: p.stat().st_mtime, reverse=True)
        if not zips:
            print(f"\n[오류] Downloads 폴더에서 '{ZIP_PATTERN}' 파일을 찾지 못했습니다.")
            print("\n사용 방법:")
            print("  방법 1) ZIP 파일을 update.bat 위에 드래그&드롭")
            print("  방법 2) GitHub > Code > Download ZIP 후 update.bat 실행")
            input("\nEnter를 눌러 종료...")
            sys.exit(1)
        zip_path = zips[0]
        if len(zips) > 1:
            print(f"ZIP {len(zips)}개 발견 - 가장 최신 파일 사용:")
            for z in zips:
                marker = "> " if z == zip_path else "  "
                suffix = "" if z == zip_path else " (건너뜀)"
                print(f"    {marker}{z.name}{suffix}")

    root_dir = script_dir
    print(f"대상 폴더     : {root_dir}")
    print(f"ZIP 파일      : {zip_path}")
    print("-" * 42)

    stats = {"신규": [], "업데이트": [], "동일": [], "건너뜀": []}

    # 2. ZIP → 로컬 복사/업데이트
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zip_root = detect_zip_root(zf)
                if zip_root:
                    print(f"ZIP 루트 감지 : '{zip_root}'")
                    print()

                for info in zf.infolist():
                    name = info.filename
                    if name.endswith("/"):
                        continue

                    rel_str = name[len(zip_root):] if (zip_root and name.startswith(zip_root)) else name
                    if not rel_str:
                        continue

                    rel = Path(rel_str)

                    if should_skip(rel) or should_preserve(rel):
                        stats["건너뜀"].append(str(rel))
                        continue

                    zf.extract(info, tmp)
                    src = tmp / name
                    dest = root_dir / rel

                    if dest.exists():
                        if file_md5(src) == file_md5(dest):
                            stats["동일"].append(str(rel))
                        else:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)
                            stats["업데이트"].append(str(rel))
                            print(f"[업데이트]  {rel}")
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dest)
                        stats["신규"].append(str(rel))
                        print(f"[신규]      {rel}")

    except zipfile.BadZipFile:
        print("\n[오류] ZIP 파일이 손상됐거나 완전히 다운로드되지 않았습니다.")
        input("\nEnter를 눌러 종료...")
        sys.exit(1)

    # 3. 결과 출력
    print()
    print("-" * 42)
    print("동기화 완료")
    print()

    changed = stats["신규"] + stats["업데이트"]
    if changed:
        print(f"[변경 적용] {len(changed)}개")
        for f in stats["신규"]:
            print(f"  + {f}")
        for f in stats["업데이트"]:
            print(f"  ~ {f}")
        print()

    print(f"변경 없음 {len(stats['동일'])}개 / 건너뜀 {len(stats['건너뜀'])}개")
    print()
    print(f"신규 {len(stats['신규'])} | 업데이트 {len(stats['업데이트'])} | 삭제 0 | 동일 {len(stats['동일'])}")
    print("-" * 42)

    input("\nEnter를 눌러 종료...")


if __name__ == "__main__":
    main()
