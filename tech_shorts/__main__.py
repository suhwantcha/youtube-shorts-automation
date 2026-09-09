import argparse
import json
import logging
import os
from pathlib import Path

from .config import Settings
from .service import Service
from .store import make_store


def main():
    parser = argparse.ArgumentParser(description="Tech Shorts Studio — 제작, 검토, 게시")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="로컬 관리 화면 실행")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))
    run = sub.add_parser("run", help="영상 제작 (게시하지 않음)")
    run.add_argument("--topic", default="")
    run.add_argument("--notes", default="")
    run.add_argument("--script", type=Path)
    run.add_argument("--audio", type=Path)
    run.add_argument("--background", type=Path, action="append", default=[])
    run.add_argument("--subtitles", type=Path)
    run.add_argument("--subtitle-mode", choices=["whisper", "script"], default="whisper")
    run.add_argument("--voice", default="onyx")
    run.add_argument("--speed", type=float, default=1.25)
    sub.add_parser("doctor", help="설정과 미디어 실행 환경 확인 (외부 API 호출 없음)")
    sub.add_parser("list", help="저장된 작업 목록")
    sub.add_parser("auto", help="트렌드 기사 한 건으로 자동 제작 (검토 대기까지만 진행)")
    sub.add_parser("recover", help="서버 종료 후 중단 작업 상태 복구")
    retry = sub.add_parser("retry")
    retry.add_argument("id")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.load()
    if args.command == "serve":
        from waitress import serve
        from .web import create_app
        if args.host not in {"127.0.0.1", "localhost", "::1"} and not settings.api_token:
            parser.error("외부 접속에는 SHORTS_API_TOKEN을 먼저 설정해주세요.")
        print(f"Tech Shorts Studio: http://{args.host}:{args.port}", flush=True)
        serve(create_app(settings), host=args.host, port=args.port, threads=8)
        return
    if args.command == "doctor":
        from .media import ffmpeg, korean_font, run
        run(["-version"], timeout=15)
        print(json.dumps({"ffmpeg": ffmpeg(), "korean_font": str(korean_font()), "output": str(settings.output),
                          "backend": settings.backend, "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
                          "pexels_configured": bool(os.getenv("PEXELS_API_KEY"))}, ensure_ascii=False, indent=2))
        return
    service = Service(settings, make_store(settings))
    if args.command == "list":
        result = service.store.list()
    elif args.command == "recover":
        result = service.recover()
    elif args.command == "retry":
        service.retry(args.id)
        result = service.run(args.id)
    elif args.command == "auto":
        job = service.create_auto()
        print(f"자동 제작 작업 ID: {job['id']}", flush=True)
        result = service.run(job["id"]) if job["status"] == "queued" else job
    else:
        data = {"topic": args.topic, "notes": args.notes,
                "script": args.script.read_text(encoding="utf-8-sig") if args.script else "",
                "voice": args.voice, "speed": args.speed, "subtitle_mode": args.subtitle_mode,
                "audio_path": str(args.audio.resolve()) if args.audio else None,
                "background_paths": [str(p.resolve()) for p in args.background],
                "subtitle_path": str(args.subtitles.resolve()) if args.subtitles else None}
        job = service.create(data, allow_local=True)
        print(f"작업 ID: {job['id']}", flush=True)
        result = service.run(job["id"])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
