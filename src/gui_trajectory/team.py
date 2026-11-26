"""Small host-side wrapper for team members. Requires only Python's standard library."""

import argparse
import getpass
import json
import os
import signal
import subprocess
import sys
import time
from contextlib import nullcontext
from pathlib import Path

from . import __version__, coordination
from .bundles import bundle_run, release
from .campaign import load_campaign
from .io import load_manifest, read_json, write_json

ROOT = Path(__file__).resolve().parents[2]


def shared_connection():
    """Literal project defaults, restricted to the explicitly shared team connection."""
    values = {}
    path = ROOT / ".env"
    allowed = {"GUI_TEAM_KEY", "GUI_TEAM_URL"}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.strip().partition("=")
            name = name.strip()
            if name not in allowed:
                continue
            value = value.strip()
            if not separator or not value:
                raise ValueError("프로젝트 .env의 팀 연결 설정을 확인하세요.")
            if value[0] in ("'", '"'):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError("프로젝트 .env의 따옴표 형식이 잘못되었습니다.")
                value = value[1:-1]
            values[name] = value
    # Explicit process settings win; do not export file values to teacher subprocesses.
    return {name: os.environ.get(name) or values.get(name) for name in allowed}


def inside(path, base=ROOT):
    resolved = (base / path).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("파일은 배포 폴더 안에 두세요. 외부 데이터는 bundle-data로 가져오세요.")
    return resolved


def settings(path):
    config_path = inside(path)
    config = read_json(config_path)
    allowed = {"schema_version", "provider", "manifest", "output", "model", "timeout", "retries"}
    if not isinstance(config, dict) or set(config) - allowed or config.get("schema_version") != 1:
        raise ValueError("지원하지 않는 job.json 형식입니다. ./team init으로 만드세요.")
    if config.get("provider") not in ("codex", "claude"):
        raise ValueError("provider는 codex 또는 claude여야 합니다.")
    for name in ("manifest", "output"):
        if not isinstance(config.get(name), str) or not config[name]:
            raise ValueError(f"설정에 {name} 경로가 필요합니다.")
        config[name] = str(inside(config[name], config_path.parent))
    if config.get("model") is not None and (
        not isinstance(config["model"], str) or config["model"].startswith("-")
    ):
        raise ValueError("model은 문자열 또는 null이어야 합니다.")
    for name, default, minimum, maximum in (("timeout", 300, 1, None), ("retries", 1, 0, 5)):
        value = config.get(name, default)
        if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
            raise ValueError(f"잘못된 {name} 설정입니다.")
        config[name] = value
    return config


def call(*args, progress=None):
    if progress:
        with subprocess.Popen([str(ROOT / "pipeline"), *map(str, args)], cwd=ROOT) as process:
            try:
                while True:
                    try:
                        return process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        progress()
            except BaseException:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise
    return subprocess.run(
        [str(ROOT / "pipeline"), *map(str, args)], cwd=ROOT, check=False
    ).returncode


def setup(backend=None):
    selection = ROOT / ".pipeline-backend"
    backend = backend or (selection.read_text().strip() if selection.exists() else "docker")
    if backend == "local":
        environment = ROOT / ".venv"
        commands = [
            [sys.executable, "-m", "venv", str(environment)],
            [
                str(environment / "bin/python"),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                "-r",
                str(ROOT / "requirements-local.txt"),
            ],
        ]
    elif backend == "docker":
        commands = [["docker", "build", "-t", "gui-trajectory:0.1", "."]]
    else:
        raise ValueError("./team setup --backend local 또는 docker로 실행 환경을 선택하세요.")
    for command in commands:
        code = subprocess.run(command, cwd=ROOT, check=False).returncode
        if code:
            return code
    selection.write_text(backend + "\n")
    print(f"준비 완료 ({backend}). QUICKSTART.md에 따라 ./team init을 실행하세요.")
    return 0


def parser():
    root = argparse.ArgumentParser(description="GUI trajectory 팀 실행 도구. 시작: QUICKSTART.md")
    root.add_argument(
        "--config", type=Path, default=Path("job.json"), help="작업 설정 (기본 job.json)"
    )
    sub = root.add_subparsers(dest="command")
    setup_command = sub.add_parser("setup", help="실행 환경 준비 (기본 Docker, 선택 후 기억)")
    setup_command.add_argument(
        "--backend", choices=("docker", "local"), help="local: 저장소의 .venv 사용, Docker 불필요"
    )
    register = sub.add_parser("register", help="담당자: 실험을 공유 시트에 등록")
    register.add_argument("--campaign", type=Path, required=True)
    register.add_argument("--url", help="Apps Script /exec 주소 (기본 공용 .env)")
    join = sub.add_parser("join", help="공유 배정표에 참여, 시트 수동 편집 불필요")
    join.add_argument(
        "--campaign", type=Path, default=Path("data/screenspot-v2/campaign-team8.json")
    )
    join.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/screenspot-v2/manifest.jsonl"),
        help="전체 데이터의 로컬 manifest",
    )
    join.add_argument("--url", help="Apps Script /exec 주소 (기본 공용 .env)")
    join.add_argument("--worker", required=True)
    join.add_argument("--provider", choices=("codex", "claude"), required=True)
    sub.add_parser("acquire", help="미배정 작업 자동 선택, 진행 중이면 같은 작업 재개")
    sub.add_parser("sync", help="진행 상태를 공유 시트에 다시 동기화")
    sub.add_parser("return", help="생성을 시작하지 않은 작업 반납")
    init = sub.add_parser("init", help="교사와 입력을 정해 작업 설정 만들기")
    init.add_argument("--provider", choices=("codex", "claude"), required=True)
    init.add_argument("--manifest", type=Path, required=True)
    init.add_argument("--output", type=Path, help="결과 폴더 (기본 runs/<provider>)")
    sub.add_parser("doctor", help="선택한 교사의 구독 로그인 확인, 생성 없음")
    sub.add_parser("plan", help="입력과 이미지 검증, 생성 없음")
    run = sub.add_parser("run", help="구독으로 생성, 같은 명령으로 재개")
    run.add_argument("--limit", type=int, help="이번에 새로 처리할 최대 입력 수")
    sub.add_parser("review", help="검수 HTML과 점수 CSV 만들기")
    sub.add_parser("status", help="생성 결과 집계")
    submit = sub.add_parser("submit", help="결과와 원본 이미지가 든 제출 ZIP 만들기")
    submit.add_argument(
        "--output", type=Path, help="새 ZIP 경로 (기본 dist/<결과폴더>-results.zip)"
    )
    submit.add_argument("--result-url", help="이미 올린 결과 ZIP 링크를 시트에 자동 기록")
    package = sub.add_parser("release", help="팀에 전달할 프로그램과 매뉴얼 ZIP 만들기")
    package.add_argument(
        "--output", type=Path, default=Path(f"dist/gui-trajectory-team-{__version__}.zip")
    )
    return root


def main():
    root = parser()
    args = root.parse_args()
    if not args.command:
        root.print_help()
        return
    if sys.version_info < (3, 10):  # noqa: UP036 - source wrapper can run before installation
        root.exit(2, "Python 3.10 이상이 필요합니다.\n")
    try:
        config_path = inside(args.config)
        needs_lock = (
            args.command in ("join", "acquire", "sync", "return")
            or coordination.state_path(ROOT, config_path).exists()
        )
        with coordination.session_lock(ROOT, config_path) if needs_lock else nullcontext():
            if args.command in ("register", "join"):
                connection = shared_connection()
                endpoint = args.url or connection["GUI_TEAM_URL"]
                if not endpoint:
                    raise ValueError("공용 .env의 GUI_TEAM_URL 또는 --url 주소가 필요합니다.")
                key = connection["GUI_TEAM_KEY"] or getpass.getpass(
                    "참여 코드 (화면에 표시되지 않음): "
                )
                if not key:
                    raise ValueError("참여 코드가 필요합니다.")
                if args.command == "register":
                    catalog = load_campaign(inside(args.campaign))
                    tasks = [
                        {
                            "batch_id": b["batch_id"],
                            "provider": provider,
                            "total": len(b["sample_ids"]),
                        }
                        for b in catalog["batches"]
                        for provider in catalog["providers"]
                    ]
                    result = coordination.request(
                        endpoint,
                        key,
                        "register",
                        campaign_id=catalog["campaign_id"],
                        fingerprint=catalog["fingerprint"],
                        tasks=tasks,
                    )
                else:
                    result = coordination.join(
                        ROOT,
                        inside(args.config),
                        inside(args.campaign),
                        inside(args.manifest),
                        endpoint,
                        args.worker,
                        args.provider,
                        key,
                    )
                print(json.dumps(result, ensure_ascii=False, indent=2))
                code = 0
            elif args.command in ("acquire", "sync", "return"):
                function = {
                    "acquire": coordination.acquire,
                    "sync": coordination.synchronize,
                    "return": coordination.relinquish,
                }[args.command]
                print(json.dumps(function(ROOT, inside(args.config)), ensure_ascii=False, indent=2))
                code = 0
            elif args.command == "setup":
                code = setup(args.backend)
            elif args.command == "release":
                print(json.dumps(release(ROOT, inside(args.output)), ensure_ascii=False, indent=2))
                code = 0
            elif args.command == "init":
                config_path = inside(args.config)
                if config_path.exists():
                    raise ValueError(
                        "설정 파일이 이미 있습니다. --config로 다른 이름을 지정하세요."
                    )
                manifest = inside(args.manifest)
                rows = load_manifest(manifest)
                if not rows:
                    raise ValueError("입력이 비어 있습니다.")
                for row in rows:
                    inside(row["image"]["path"], manifest.parent)
                output = inside(args.output or Path("runs") / args.provider)
                write_json(
                    config_path,
                    {
                        "schema_version": 1,
                        "provider": args.provider,
                        "manifest": os.path.relpath(manifest, config_path.parent),
                        "output": os.path.relpath(output, config_path.parent),
                        "model": None,
                        "timeout": 300,
                        "retries": 1,
                    },
                )
                print(f"설정 저장: {config_path}\n다음: ./team --config {args.config} plan")
                code = 0
            else:
                config = settings(args.config)
                output = Path(config["output"])
                managed = coordination.state_path(ROOT, inside(args.config)).exists()
                if managed:
                    coordination.validate_assignment(ROOT, inside(args.config))
                if args.command == "doctor":
                    code = call("doctor", "--provider", config["provider"])
                elif args.command in ("plan", "run"):
                    options = [
                        "generate",
                        "--manifest",
                        config["manifest"],
                        "--provider",
                        config["provider"],
                        "--output",
                        output,
                        "--timeout",
                        config["timeout"],
                        "--retries",
                        config["retries"],
                    ]
                    if config.get("model"):
                        options.extend(["--model", config["model"]])
                    if args.command == "plan":
                        options.append("--dry-run")
                    elif args.limit is not None:
                        options.extend(["--limit", args.limit])
                    if args.command == "run" and managed:
                        coordination.synchronize(ROOT, inside(args.config), phase="running")
                        try:
                            code = call(
                                *options, progress=coordination.heartbeat(ROOT, inside(args.config))
                            )
                        finally:
                            coordination.synchronize(ROOT, inside(args.config), phase="paused")
                    else:
                        code = call(*options)
                elif args.command == "review":
                    code = call("review", "--run", output, "--output", output / "review")
                    if not code:
                        print(f"검수 화면: {output / 'review/review.html'}")
                elif args.command == "status":
                    code = call("summary", "--run", output)
                else:
                    suffix = f"-{time.time_ns()}" if managed else ""
                    destination = inside(
                        args.output or Path("dist") / f"{output.name}-results{suffix}.zip"
                    )
                    packaged = bundle_run(output, destination)
                    print(json.dumps(packaged, ensure_ascii=False, indent=2))
                    if managed:
                        coordination.synchronize(
                            ROOT,
                            inside(args.config),
                            phase="submitted",
                            archive={"name": destination.name, "sha256": packaged["sha256"]},
                            result_url=args.result_url,
                        )
                    elif args.result_url:
                        raise ValueError("--result-url은 공유 배정 작업에서 사용하세요.")
                    code = 0
    except (OSError, ValueError, KeyError, TypeError, EOFError) as exc:
        root.exit(2, f"오류: {exc}\nQUICKSTART.md와 docs/agent-manual.md를 확인하세요.\n")
    except KeyboardInterrupt:
        root.exit(130, "\n중단했습니다. 같은 run 명령으로 재개할 수 있습니다.\n")
    if code:
        root.exit(code)


if __name__ == "__main__":
    main()
