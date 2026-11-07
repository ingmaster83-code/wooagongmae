# -*- coding: utf-8 -*-
"""한국자산관리공사 '차세대 온비드' 오픈API 클라이언트 (apis.data.go.kr/B010003).
키: 환경변수 DATA_GO_KR_API_KEY (Actions 시크릿) 없으면 ../hosppass/.env 의 API_KEY (로컬 개발용). 키를 저장소에 넣지 말 것.
호출 한도: 개발계정은 API당 일 1,000건 — 목록·통계는 numOfRows=2000 으로 소량 호출, 상세만 물건당 1건 소모."""
import json, os, pathlib, re, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://apis.data.go.kr/B010003/"

def _key():
    k = os.environ.get("DATA_GO_KR_API_KEY")
    if k: return k.strip()
    p = ROOT.parent / "hosppass" / ".env"
    if p.exists():
        m = re.search(r"API_KEY\s*=\s*(\S+)", p.read_text(encoding="utf-8"))
        if m: return m.group(1).strip().strip("\"'")
    sys.exit("DATA_GO_KR_API_KEY 환경변수가 필요합니다(키를 코드에 넣지 마세요).")

KEY = _key()

# 서비스 경로 (서비스명, 오퍼레이션) — 오퍼레이션 이름 끝의 2는 차세대 규격
SVC = {
    "pbanc_list":    ("OnbidPbancListSrvc2", "getPbancList2"),            # 15157216 공고목록
    "pbanc_cltr":    ("OnbidPbancCltrDtlSrvc2", "getPbancCltrInf2"),      # 15157220 공고 물건정보
    "pbanc_detail":  ("OnbidPbancDtlnfSrvc2", "getPbancDtlInf2"),         # 15157218 공고상세
    "rlst_list":     ("OnbidRlstListSrvc2", "getRlstCltrList2"),          # 15157207 부동산 물건목록
    "rlst_detail":   ("OnbidRlstDtlSrvc2", "getRlstDtlInf2"),             # 15157247 부동산 물건상세
    "bid_info":      ("OnbidCltrBidDtlSrvc2", "getCltrBidInf2"),          # 15157251 물건 입찰정보(회차별)
    "result_list":   ("OnbidCltrBidRsltListSrvc2", "getCltrBidRsltList2"),  # 15157252 입찰결과 목록
    "result_detail": ("OnbidCltrBidRsltDtlSrvc2", "getCltrBidRsltDtl2"),  # 15157254 입찰결과 상세
    "stats_region":  ("OnbidClarBidStatsSrvc", "getKamcoCltrClarStats"),  # 15157756 지역별 입찰통계
    "stats_usage":   ("OnbidUsgBidStatsSrvc", "getKamcoCltrUsgStats"),    # 15157757 용도별 입찰통계
    "rank_views":    ("OnbidInqRnkClgSrvc", "getInqRnkClg"),              # 15157704 조회수 순위
    "rank_decr":     ("Onbid50PctDecrCltrSrvc", "get50PctDecrCltr"),      # 15157709 저감률 순위
    "rank_fav":      ("OnbidItrsCltrRnkClgSrvc", "getItrsCltrRnkClg"),    # 15157699 관심물건 순위
}

class ApiError(Exception): pass

def call(name, retries=3, **params):
    """한 번 호출. 반환: (items 리스트, totalCount). NODATA(03)는 빈 결과."""
    svc, op = SVC[name]
    q = dict(params); q.update(serviceKey=KEY, resultType="json")
    q.setdefault("pageNo", 1); q.setdefault("numOfRows", 100)
    url = "%s%s/%s?%s" % (BASE, svc, op, urllib.parse.urlencode(q))
    last = None
    for i in range(retries):
        try:
            raw = urllib.request.urlopen(url, timeout=90).read().decode("utf-8")
            d = json.loads(raw)
            hdr = d.get("header") or d.get("response", {}).get("header") or {}
            code = hdr.get("resultCode")
            if code == "03": return [], 0
            if code not in (None, "00"): raise ApiError("%s %s: %s %s" % (name, code, hdr.get("resultMsg"), ""))
            body = d.get("body") or d.get("response", {}).get("body") or {}
            it = body.get("items") or []
            if isinstance(it, dict): it = it.get("item", [])
            if isinstance(it, dict): it = [it]
            return it, int(body.get("totalCount") or 0)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "ignore")
            if "SERVICE_KEY_IS_NOT_REGISTERED" in msg or "SERVICE ACCESS DENIED" in msg.upper():
                raise ApiError("%s: 활용신청/승인이 필요합니다 (%s)" % (name, svc))
            last = "HTTP %s %s" % (e.code, msg[:120].replace(KEY, "***"))
            if e.code in (400, 401, 403): raise ApiError(last)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = str(e)[:120]
        time.sleep(2 * (i + 1))
    raise ApiError("%s 실패: %s" % (name, last))

def fetch_all(name, per=2000, max_rows=None, **params):
    """페이지 끝까지 전부 가져오기."""
    out, page = [], 1
    while True:
        it, total = call(name, pageNo=page, numOfRows=per, **params)
        out += it
        if not it or len(out) >= total or (max_rows and len(out) >= max_rows): break
        page += 1
    return out
