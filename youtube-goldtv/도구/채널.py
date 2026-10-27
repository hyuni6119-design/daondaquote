# -*- coding: utf-8 -*-
r"""
채널 설정 읽기

도구는 하나인데 채널이 둘입니다. 채널마다 다른 값(유튜브 채널 번호, 작업
폴더, 캡컷 본 프로젝트, 자막을 넣는지 마는지)은 `도구/채널/*.json` 에
따로 적어 두고, 스크립트는 `--채널` 로 어느 것을 쓸지 고릅니다.

같은 코드를 두 벌로 복사해 두면 한쪽만 고치는 일이 반드시 생깁니다.
그래서 코드는 한 벌만 두고 설정만 나눕니다.

쓰는 법
    from 채널 import 설정읽기, 인자붙이기

    파서 = argparse.ArgumentParser()
    인자붙이기(파서)                 # --채널 을 달아 줍니다
    args = 파서.parse_args()
    ch = 설정읽기(args.채널)
    print(ch["표시이름"], ch["폴더"]["작업"])

기본값은 황금주파수입니다. 지금까지 쓰던 명령이 그대로 돌아가야 하기
때문입니다.
"""

import io
import json
from pathlib import Path

설정폴더 = Path(__file__).resolve().parent / "채널"
기본채널 = "황금주파수"


def 목록():
    """쓸 수 있는 채널 이름들"""
    return sorted(p.stem for p in 설정폴더.glob("*.json"))


def 설정읽기(이름=None):
    이름 = 이름 or 기본채널
    경로 = 설정폴더 / (이름 + ".json")
    if not 경로.exists():
        raise SystemExit(
            "[실패] 그런 채널이 없습니다: %s\n        쓸 수 있는 것: %s"
            % (이름, ", ".join(목록())))
    설정 = json.load(io.open(경로, encoding="utf-8"))
    설정["_이름"] = 이름
    return 설정


def 인자붙이기(파서):
    """스크립트마다 똑같이 생긴 --채널 인자를 답니다."""
    파서.add_argument("--채널", default=기본채널,
                     choices=목록(),
                     help="어느 채널의 설정으로 돌릴지 (기본: %s)" % 기본채널)
    return 파서


def 토큰경로(설정):
    """인증토큰 파일은 채널마다 다릅니다. 도구 폴더 안에 둡니다."""
    return Path(__file__).resolve().parent / 설정["유튜브"]["토큰파일"]


def 클라이언트경로(설정):
    """OAuth 클라이언트 비밀 파일. 채널마다 구글 계정이 달라서 따로입니다.

    황금주파수는 gmahyun0915 계정의 프로젝트, 불심명언은 lovezzang915
    계정의 프로젝트에서 받은 것입니다. 둘 다 저장소에 올리지 않습니다.
    """
    이름 = 설정["유튜브"].get("클라이언트파일", "client_secret.json")
    return Path(__file__).resolve().parent / 이름


def 글작업폴더(설정):
    """가사·기획 같은 글이 있는 저장소 안 폴더"""
    return Path(__file__).resolve().parent.parent.parent / 설정["폴더"]["글작업"]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for 이름 in 목록():
        c = 설정읽기(이름)
        print("%-8s  %-12s  %s  %s" % (
            이름, c["표시이름"], c["유튜브"]["채널번호"], c["폴더"]["작업"]))
