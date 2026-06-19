#Requires -Version 5.1
<#
.SYNOPSIS
    LQ All In One - GitHub ZIP 자동 업데이트 스크립트
.DESCRIPTION
    GitHub 에서 다운로드한 ZIP 파일과 로컬 프로젝트를 비교하여
    변경된 파일만 대치합니다. 로컬 전용 파일(.env 등)은 삭제하지 않습니다.
.HOW TO USE
    방법 1) ZIP 파일을 update.bat 아이콘 위에 드래그 앤 드랍
    방법 2) update.bat 를 더블클릭 -> Downloads 폴더에서 자동 탐색
#>
param(
    # 드래그 앤 드랍으로 전달되는 ZIP 파일 경로 (비어 있으면 Downloads 자동 탐색)
    [string]$ZipPath = "",
    # update.bat 에서 전달되는 스크립트 폴더 경로 (-Command 방식은 $PSScriptRoot 가 비어 있음)
    [string]$ScriptDir = ""
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

# ══════════════════════════════════════════════════
# [설정] 필요 시 수정
# ══════════════════════════════════════════════════

# Downloads 폴더 자동 탐색 시 사용할 파일명 패턴
$ZIP_PATTERN = "LQ_Dashboard*.zip"

# 업데이트 시 건너뛸 경로 패턴 (정규식, 대소문자 무시)
$SKIP_PATTERNS = @(
    '(^|[\\/])\.git([\\/]|$)',
    '(^|[\\/])__pycache__([\\/]|$)',
    '(^|[\\/])\.env($|\.)',
    '(^|[\\/])\.claude[\\/]settings\.local\.json$',
    '(^|[\\/])logs([\\/]|$)',
    '\.pyc$',
    '\.pyo$',
    '\.pyd$',
    'Thumbs\.db$',
    '\.DS_Store$',
)

# ══════════════════════════════════════════════════
# 내부 함수
# ══════════════════════════════════════════════════

function Should-Skip([string]$relPath) {
    foreach ($pat in $SKIP_PATTERNS) {
        if ($relPath -imatch $pat) { return $true }
    }
    return $false
}

function Get-MD5([string]$path) {
    return (Get-FileHash $path -Algorithm MD5).Hash
}

function Write-Sep { Write-Host ("-" * 42) -ForegroundColor DarkGray }

# ══════════════════════════════════════════════════
# 헤더
# ══════════════════════════════════════════════════
$TARGET    = if ($ScriptDir) { $ScriptDir } else { $PSScriptRoot }
$DOWNLOADS = "$env:USERPROFILE\Downloads"

Write-Host ""
Write-Host ("=" * 42) -ForegroundColor Cyan
Write-Host "   LQ All In One - 자동 업데이트" -ForegroundColor Cyan
Write-Host ("=" * 42) -ForegroundColor Cyan
Write-Host ""

# ══════════════════════════════════════════════════
# ZIP 파일 결정 (드래그 앤 드랍 우선, 없으면 Downloads 탐색)
# ══════════════════════════════════════════════════
if ($ZipPath) {
    # -- 드래그 앤 드랍으로 파일이 지정된 경우 --
    if (-not (Test-Path $ZipPath)) {
        Write-Host "오류: 파일을 찾을 수 없습니다." -ForegroundColor Red
        Write-Host "  경로: $ZipPath" -ForegroundColor DarkGray
        exit 1
    }
    if (-not $ZipPath.ToLower().EndsWith('.zip')) {
        Write-Host "오류: ZIP 파일(.zip)만 지원합니다." -ForegroundColor Red
        Write-Host "  전달된 파일: $(Split-Path $ZipPath -Leaf)" -ForegroundColor DarkGray
        exit 1
    }
    $zip = Get-Item $ZipPath
    Write-Host "모드          : 드래그 앤 드랍" -ForegroundColor Cyan
} else {
    # -- 직접 실행 - Downloads 폴더에서 자동 탐색 --
    Write-Host "모드          : 자동 탐색 (Downloads)" -ForegroundColor DarkGray

    $zips = @(Get-ChildItem "$DOWNLOADS\$ZIP_PATTERN" -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending)

    if ($zips.Count -eq 0) {
        Write-Host ""
        Write-Host "오류: Downloads 폴더에서 '$ZIP_PATTERN' 파일을 찾지 못했습니다." -ForegroundColor Red
        Write-Host ""
        Write-Host "사용 방법:" -ForegroundColor Yellow
        Write-Host "  방법 1) ZIP 파일을 update.bat 아이콘 위에 드래그 앤 드랍"
        Write-Host "  방법 2) GitHub > Code > Download ZIP 후 update.bat 실행"
        Write-Host "          (파일명 예시: LQ_Dashboard-main.zip)"
        Write-Host ""
        exit 1
    }

    $zip = $zips[0]

    if ($zips.Count -gt 1) {
        Write-Host "ZIP 파일 $($zips.Count)개 발견 - 가장 최신 파일 사용:" -ForegroundColor Yellow
        foreach ($z in $zips) {
            $marker = if ($z.FullName -eq $zip.FullName) { "> " } else { "  " }
            $suffix = if ($z.FullName -eq $zip.FullName) { "" } else { " (건너뜀)" }
            Write-Host "  $marker$($z.Name)$suffix"
        }
        Write-Host ""
    }
}

Write-Host "대상 폴더     : $TARGET"
Write-Host "ZIP 파일      : $($zip.FullName)"

# ══════════════════════════════════════════════════
# ZIP 압축 해제 (임시 폴더)
# ══════════════════════════════════════════════════
$TEMP_DIR = Join-Path $env:TEMP "lq_update_$(Get-Random)"

try {
    Expand-Archive -Path $zip.FullName -DestinationPath $TEMP_DIR -Force
} catch {
    Write-Host ""
    Write-Host "오류: ZIP 파일 압축 해제에 실패했습니다 - $_" -ForegroundColor Red
    Write-Host "ZIP 파일이 완전히 다운로드되었는지 확인하세요." -ForegroundColor Yellow
    exit 1
}

# GitHub ZIP 루트 폴더 자동 감지 (예: LQ_Dashboard-main/)
$roots = @(Get-ChildItem $TEMP_DIR -Directory)
if ($roots.Count -eq 1) {
    $SRC = $roots[0].FullName
    Write-Host "ZIP 루트 감지 : '$($roots[0].Name)/'"
} else {
    $SRC = $TEMP_DIR
}

Write-Host ""
Write-Sep

# ══════════════════════════════════════════════════
# 파일 비교 및 동기화
# ══════════════════════════════════════════════════
$new_count    = 0
$update_count = 0
$same_count   = 0
$skip_count   = 0
$new_files     = [System.Collections.Generic.List[string]]::new()
$updated_files = [System.Collections.Generic.List[string]]::new()

Get-ChildItem $SRC -Recurse -File | ForEach-Object {
    $rel  = $_.FullName.Substring($SRC.Length).TrimStart('\', '/')
    $dest = Join-Path $TARGET $rel

    # 건너뜀 대상
    if (Should-Skip $rel) {
        $script:skip_count++
        return
    }

    # 대상 디렉터리가 없으면 생성
    $destDir = Split-Path $dest -Parent
    if (-not (Test-Path $destDir)) {
        New-Item $destDir -ItemType Directory -Force | Out-Null
    }

    if (-not (Test-Path $dest)) {
        # 신규 파일
        Copy-Item $_.FullName $dest -Force
        $script:new_count++
        $script:new_files.Add($rel)
        Write-Host "[신규]      $rel" -ForegroundColor Cyan

    } else {
        # 기존 파일 - MD5 비교
        $src_hash  = Get-MD5 $_.FullName
        $dest_hash = Get-MD5 $dest

        if ($src_hash -ne $dest_hash) {
            Copy-Item $_.FullName $dest -Force
            $script:update_count++
            $script:updated_files.Add($rel)
            Write-Host "[업데이트]  $rel" -ForegroundColor Yellow
        } else {
            $script:same_count++
        }
    }
}

# 로컬 전용 파일 수 집계 (삭제하지 않음 - 정보용)
$local_only = 0
Get-ChildItem $TARGET -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($TARGET.Length).TrimStart('\', '/')
    if (Should-Skip $rel) { return }
    if (-not (Test-Path (Join-Path $SRC $rel))) {
        $script:local_only++
    }
}

# ══════════════════════════════════════════════════
# 임시 폴더 정리
# ══════════════════════════════════════════════════
Remove-Item $TEMP_DIR -Recurse -Force -ErrorAction SilentlyContinue

# ══════════════════════════════════════════════════
# 결과 출력
# ══════════════════════════════════════════════════
Write-Host ""
Write-Sep
Write-Host "동기화 완료" -ForegroundColor Green
Write-Host ""

$changed_total = $new_count + $update_count
if ($changed_total -gt 0) {
    Write-Host "[변경 적용] ${changed_total}개"
    foreach ($f in $new_files)     { Write-Host "  + $f" -ForegroundColor Cyan }
    foreach ($f in $updated_files) { Write-Host "  ~ $f" -ForegroundColor Yellow }
    Write-Host ""
}

if ($local_only -gt 0) {
    Write-Host "[보존 유지] ${local_only}개 (로컬 전용)"
}
Write-Host "변경 없음 ${same_count}개 / 건너뜀 ${skip_count}개"
Write-Host ""
Write-Host "신규 $new_count | 업데이트 $update_count | 삭제 0 | 동일 $same_count" -ForegroundColor White
Write-Sep
Write-Host ""
