# -*- coding: utf-8 -*-
"""우아공매 정적 사이트 생성기 -> _site/.  입력: store/items.json.gz, store/stats.json, store/ranks.json (fetch_data.py 산출)
사용: python scripts/build_site.py"""
import collections, datetime, gzip, json, shutil, sys, time, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
import guides

STORE = ROOT / "store"
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(tzinfo=None)
NOW_ISO = TODAY.strftime("%Y-%m-%dT%H:%M")
EOK, MAN = 100_000_000, 10_000
def k(x): return "{:,}".format(int(round(x)))

def kor(n):
    if n is None: return "-"
    n = int(round(n)); eok, rest = divmod(n, EOK); mn, w = divmod(rest, MAN); p = []
    if eok: p.append("{:,}억".format(eok))
    if mn: p.append("{:,}만".format(mn))
    if w and not eok: p.append("{:,}".format(w))
    return (" ".join(p) or "0") + "원"

def table(heads, rows, num=()):
    th = "".join('<th%s>%s</th>' % (' class="num"' if i in num else "", h) for i, h in enumerate(heads)) if heads else ""
    body = "".join("<tr>%s</tr>" % "".join('<td%s>%s</td>' % (' class="num"' if i in num else "", v) for i, v in enumerate(r)) for r in rows)
    return '<div class="tbl-wrap"><table class="tbl">%s<tbody>%s</tbody></table></div>' % (("<thead><tr>%s</tr></thead>" % th) if th else "", body)
def chips(items): return '<div class="chips">%s</div>' % "".join('<a class="chip" href="%s">%s</a>' % (q(u) if u.startswith("/") else u, esc(t)) for t, u in items)
def slug(s): return (s or "").replace("/", "·").replace(" ", "")
def mlabel(m): return "%d년 %d월" % (int(m[:4]), int(m[4:6]))

def dt(s, fmt="md"):
    if not s: return "-"
    try: d = datetime.datetime.fromisoformat(s)
    except ValueError: return s
    if fmt == "full": return "%d년 %d월 %d일 %02d:%02d" % (d.year, d.month, d.day, d.hour, d.minute) if "T" in s else "%d년 %d월 %d일" % (d.year, d.month, d.day)
    return "%d월 %d일 %02d:%02d" % (d.month, d.day, d.hour, d.minute) if "T" in s else "%d월 %d일" % (d.month, d.day)
def pdt(s):
    try: return datetime.datetime.fromisoformat(s) if s else None
    except ValueError: return None

# ───────────────────────── 데이터 ─────────────────────────
STATE = {"open": ("입찰 중", "green"), "upcoming": ("입찰 예정", "blue"), "nego": ("수의계약 가능", "amber"), "closed": ("입찰 마감", "gray"), "ended": ("공고 종료", "gray")}
LIVE = ("open", "upcoming", "nego")

def load():
    st = json.loads(gzip.open(STORE / "items.json.gz", "rt", encoding="utf-8").read())
    items = list(st["items"].values())
    for it in items:
        for key in ("rent", "rent_period", "status_nm", "thumb", "first_seen", "last_seen"): it.setdefault(key, "")
        it.setdefault("nego", False); it.setdefault("rounds", [])
        it["region"] = " ".join(x for x in (it["sido"], it["sgg"]) if x) or "지역 미상"
        b, e = it["bid_begin"], it["bid_end"]
        if it.get("ended_on"): it["state"] = "ended"
        elif it.get("nego") and (not e or e < NOW_ISO): it["state"] = "nego"
        elif b and b > NOW_ISO: it["state"] = "upcoming"
        elif e and e >= NOW_ISO: it["state"] = "open"
        else: it["state"] = "closed"
        it["live"] = it["state"] in LIVE
    stats = json.loads((STORE / "stats.json").read_text(encoding="utf-8")) if (STORE / "stats.json").exists() else {"region": {}, "usage": {}}
    ranks = json.loads((STORE / "ranks.json").read_text(encoding="utf-8")) if (STORE / "ranks.json").exists() else {}
    return st.get("meta", {}), items, stats, ranks

def where(it): return " ".join(x for x in (it["sido"], it["sgg"], it["emd"]) if x)
def title_core(it): return "%s %s" % (where(it) or it["name"][:20], it["scls"] or it["mcls"] or "부동산")
def dday(it):
    if it["state"] not in ("open", "upcoming"): return ""
    e = pdt(it["bid_end"])
    if not e: return ""
    d = (e.date() - TODAY.date()).days
    return "오늘 마감" if d == 0 else ("D-%d" % d if d > 0 else "")
def full_url(u): return u.replace("&downloadImageKind=THNL_NM", "")

def photo_tag(it, i=0, cls="", full=False):
    ph = it["photos"]
    if not ph: return '<div class="ph noimg"></div>'
    u = ph[i] if i < len(ph) else ph[0]
    if full: u = full_url(u)
    return '<img src="%s" alt="%s 공매 사진" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.parentNode.classList.add(\'noimg\');this.remove()"%s>' % (esc(u), esc(title_core(it)), (' class="%s"' % cls) if cls else "")

def card(it):
    st, col = STATE[it["state"]]; dd = dday(it)
    ratio = ("%.0f%%" % it["ratio"]) if it.get("ratio") else ""
    return ('<a class="item-card" href="%s"><div class="ph">%s<span class="badge %s">%s%s</span></div><div class="ib"><b class="t">%s</b>'
            '<span class="u">%s · %s</span><span class="p">감정가 %s</span><span class="p2">%s %s <em>%s</em></span></div></a>') % (
        q("/item/%s/" % it["id"]), photo_tag(it), col, st, (" · " + dd) if dd else "", esc(where(it) or it["name"][:30]),
        esc(it["mcls"] or "부동산"), esc(it["scls"] or "-"), kor(it["appraisal"]) if it["appraisal"] else "비공개",
        "임대" if it["disp"] == "임대" else "최저", kor(it["min"]) if it["min"] else "-", ratio)
def grid(its): return '<div class="item-grid">%s</div>' % "".join(card(i) for i in its)

# ───────────────────────── 색인 (2만 페이지를 위해 미리 계산) ─────────────────────────
class Idx:
    def __init__(self, items):
        self.live = [x for x in items if x["live"]]
        self.by_sgg = collections.defaultdict(list)
        self.by_sido_m = collections.defaultdict(list)
        self.ratio = collections.defaultdict(list)
        for x in sorted(self.live, key=lambda x: (x["sgg"], x["mcls"], x["bid_end"] or "9", x["id"])):
            self.by_sgg[(x["sido"], x["sgg"])].append(x)
            self.by_sido_m[(x["sido"], x["mcls"])].append(x)
            if x["ratio"] and x["state"] != "nego": self.ratio[(x["sgg"], x["mcls"])].append(x["ratio"])
        self.pos = {}
        for key, lst in self.by_sgg.items():
            for i, x in enumerate(lst): self.pos[x["id"]] = (key, i)
    def peers_avg(self, it):
        r = self.ratio.get((it["sgg"], it["mcls"]), [])
        return (sum(r) / len(r), len(r)) if len(r) >= 3 else None
    def related(self, it, n=6):
        key, i = self.pos.get(it["id"], (None, 0))
        lst = self.by_sgg.get(key, [])
        if len(lst) <= 1:
            m = self.by_sido_m.get((it["sido"], it["mcls"]), [])
            return [x for x in m[:n + 1] if x["id"] != it["id"]][:n]
        out = []
        for d in range(1, len(lst)):
            for j in (i + d, i - d):
                if 0 <= j < len(lst) and lst[j]["id"] != it["id"]: out.append(lst[j])
                if len(out) >= n: return out
        return out

STAT_REGION_OF = {"서울특별시": "서울", "인천광역시": "인천", "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원", "충청북도": "충북", "충청남도": "충남", "대전광역시": "대전", "대구광역시": "대구",
                  "경상북도": "경북", "부산광역시": "부산", "울산광역시": "울산", "경상남도": "경남", "전북특별자치도": "전북", "전라북도": "전북", "광주광역시": "광주", "전라남도": "전남", "제주특별자치도": "제주", "세종특별자치시": "세종특별자치시"}
STAT_TYPES = {"0021": ("seized", "압류재산", "0041"), "0024": ("national", "국유재산", "0044"), "0025": ("entrusted", "수탁·유입자산", "0045")}
KIND_TO_STAT = {"압류재산": "0021", "국유재산": "0024"}

def latest_month(stats, code):
    ms = sorted(m for m, rows in stats["region"].get(code, {}).items() if any((r.get("pbctCltrCnt") or 0) > 0 for r in rows))
    return ms[-1] if ms else None
def stat_row(stats, kind, code, month, name):
    for r in stats[kind].get(code, {}).get(month, []):
        if r["clsCdNm"] == name: return r
    return None

# ───────────────────────── 물건 상세 ─────────────────────────
def tips(it):
    t = []
    nm = it["name"] + " " + " ".join(s["note"] for s in it["sqms"])
    if it["nego"]: t.append(("수의계약 가능 물건", "입찰 회차가 끝난 뒤에도 매각되지 않아 수의계약으로 매수할 수 있는 상태의 물건입니다. 신청 조건·가격·기한은 공고문과 온비드 안내에 따르며, 먼저 신청한 사람 순서 등 방식이 정해져 있을 수 있으니 온비드에서 확인하세요."))
    if "지분" in nm: t.append(("지분 물건입니다", "부동산의 일부 지분만 취득하는 물건입니다. 다른 공유자가 있으면 우선매수 청구나 공유물 분할 문제가 생길 수 있으니 공고문과 등기부등본으로 공유 관계를 확인하세요."))
    if it["scls"] in ("전", "답", "과수원"): t.append(("농지 취득 요건 확인", "농지는 낙찰받더라도 농지취득자격증명이 필요할 수 있습니다. 증명 발급 요건과 기한을 입찰 전에 관할 지자체에서 확인하세요."))
    if it["scls"] == "임야" or (it["mcls"] == "토지" and not it["bld"]): t.append(("현황 확인", "토지는 진입 도로(맹지 여부), 지목과 실제 이용 현황, 경계를 현장과 지적도로 확인하는 것이 중요합니다. 공부상 지목과 실제 이용이 다른 경우가 많습니다."))
    if it["mcls"] in ("주거용건물", "상가용및업무용건물", "용도복합용건물") or it["bld"]: t.append(("임차인·점유 확인", "건물은 임차인이 있으면 보증금 인수 여부와 인도 일정이 비용과 기간에 영향을 줍니다. 공고문의 임차·점유 정보와 현장 상태를 함께 확인하세요."))
    if it["disp"] == "임대": t.append(("임대 물건입니다", "매각이 아니라 일정 기간 빌려 쓰는 대부·임대 물건입니다. 임대 기간(%s)과 사용료 산정 방식, 용도 제한을 공고문에서 확인하세요." % (it["rent_period"] or "공고 참조")))
    if it["usbd"] >= 1: t.append(("유찰 %d회" % it["usbd"], "이전 회차에서 입찰자가 없어 유찰된 물건입니다. 가격이 낮아졌다는 뜻이기도 하지만 부담 요소가 있어서일 수 있으니 이유를 먼저 확인하세요."))
    if it["evict"] and "매수" in it["evict"]: t.append(("명도 책임은 매수인", "낙찰 후 점유자 인도(명도)를 매수인이 책임지는 조건입니다. 명도 비용과 소요 기간을 입찰가에 반영하세요."))
    return t

def span(b, e):
    """회차 입찰 기간을 짧게: 같은 날이면 '11/13 09:00~12:00', 아니면 '11/13 09:00~11/15 12:00'"""
    db, de = pdt(b), pdt(e)
    if not db or not de: return "-"
    f = lambda d: "%d/%d %02d:%02d" % (d.month, d.day, d.hour, d.minute)
    return "%s~%s" % (f(db), ("%02d:%02d" % (de.hour, de.minute)) if db.date() == de.date() else f(de))

def rounds_table(it):
    rs = it["rounds"]
    if len(rs) < 2: return ""
    ap = it["appraisal"]
    def row(r):
        if r["e"] < NOW_ISO: stt = "마감"
        elif r["cond"] == it["cond"] and it["state"] in ("open", "upcoming"): stt = "<b>진행/현재</b>"
        else: stt = "예정"
        ratio = ("%.0f%%" % (r["min"] / ap * 100)) if r["min"] and ap else "-"
        return [esc(r["n"] or "-"), span(r["b"], r["e"]), kor(r["min"]) if r["min"] else "비공개", ratio, stt]
    if len(rs) > 20: show = [row(r) for r in rs[:10]] + [["…", "중간 %d개 회차 생략" % (len(rs) - 16), "", "", ""]] + [row(r) for r in rs[-6:]]
    else: show = [row(r) for r in rs]
    mins = [r["min"] for r in rs if r["min"]]
    note = ""
    if len(mins) >= 2 and mins[0] > mins[-1]:
        note = "<p class=\"note\">회차가 진행될수록 최저입찰가가 단계적으로 낮아지도록 공고된 물건입니다. 첫 회차 %s에서 마지막 회차 %s까지 내려갑니다(총 %d회차). 가격이 내려가기 전에 낙찰되면 이후 회차는 열리지 않습니다.</p>" % (kor(mins[0]), kor(mins[-1]), len(rs))
    return '<h2 class="group-title">📉 회차별 입찰 일정과 최저입찰가</h2>' + table(["회차", "입찰 기간", "최저입찰가", "감정가 대비", "상태"], show, (2, 3)) + note

def stat_box(it, stats):
    code = KIND_TO_STAT.get(it["kind"]); reg = STAT_REGION_OF.get(it["sido"])
    if not code or not reg or not stats["region"].get(code): return ""
    m = latest_month(stats, code)
    if not m: return ""
    rows = []
    r = stat_row(stats, "region", code, m, reg)
    if r and r.get("pbctCltrCnt"): rows.append(["%s %s 지역 전체" % (reg, it["kind"]), "%s건" % k(r["pbctCltrCnt"]), "%s%%" % r["scbrt"], r["compRate"], ("%.1f%%" % r["scfbAmtRto1"]) if r.get("scfbAmtRto1") else "-"])
    u = stat_row(stats, "usage", STAT_TYPES[code][2], m, it["scls"]) or stat_row(stats, "usage", STAT_TYPES[code][2], m, it["mcls"])
    if u and u.get("pbctCltrCnt"): rows.append(["전국 %s %s" % (it["kind"], u["clsCdNm"]), "%s건" % k(u["pbctCltrCnt"]), "%s%%" % u["scbrt"], u["compRate"], ("%.1f%%" % u["scfbAmtRto1"]) if u.get("scfbAmtRto1") else "-"])
    if not rows: return ""
    return ('<h2 class="group-title">📊 최근 낙찰 통계 (%s, 온비드 공식 집계)</h2>' % mlabel(m)) + table(["구분", "입찰 건수", "낙찰률", "경쟁률", "감정가 대비 낙찰가율"], rows, (1, 2, 3, 4)) + '<p class="note">낙찰가율은 감정가 대비 평균 낙찰가 비율입니다. <a href="/stats/%s/">%s 낙찰 통계 전체 보기</a></p>' % (STAT_TYPES[code][0], it["kind"])

def page_item(it, idx, stats):
    st, col = STATE[it["state"]]; path = "/item/%s/" % it["id"]
    w = where(it) or it["name"]; use = it["scls"] or it["mcls"] or "부동산"
    ap, mn, r = it["appraisal"], it["min"], it.get("ratio")
    ph = it["photos"]
    if ph:
        thumbs = ""
        if len(ph) > 1:
            thumbs = '<div class="thumbs">%s</div>' % "".join('<a class="th" href="%s" target="_blank" rel="noopener nofollow"><img src="%s" alt="%s 사진 %d" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.remove()"></a>' % (esc(full_url(u)), esc(u), esc(title_core(it)), i + 1) for i, u in enumerate(ph[:14]))
        cap = ("사진 %d장 · 출처 한국자산관리공사 온비드 (사진을 누르면 크게 열립니다)" % len(ph)) if it["detail"] else "대표 사진 · 출처 한국자산관리공사 온비드"
        gal = '<div class="gallery"><div class="main">%s</div>%s<p class="cap">%s</p></div>' % (photo_tag(it, 0, full=True), thumbs, cap)
    else:
        gal = '<div class="gallery"><div class="main"><div class="ph noimg"></div></div></div>'
    deposit = round(mn * 0.1) if mn else None
    unit = "임대료 기준가" if it["disp"] == "임대" else "최저입찰가"
    price = ('<div class="price-box"><div><small>감정가</small><b>%s</b></div><div><small>%s</small><b class="red">%s</b>%s</div><div><small>입찰보증금(통상 10%%)</small><b>%s</b></div></div>'
             % (kor(ap) if ap else "비공개", unit, kor(mn) if mn else "-", ("<em>감정가의 %.0f%%</em>" % r) if r else "", kor(deposit) if deposit else "-"))
    rows = [["물건관리번호", esc(it["id"])], ["소재지", esc(it["addr"])]]
    if it["road"]: rows.append(["도로명주소", esc(it["road"])])
    rows += [["용도", esc(" > ".join(x for x in (it["lcls"], it["mcls"], it["scls"]) if x))], ["재산 유형", esc(it["kind"] or "-") + ((" · " + esc(it["disp"])) if it["disp"] else "")]]
    if it["land"] or it["bld"]:
        f = lambda v: "{:,.2f}".format(v).rstrip("0").rstrip(".")
        rows.append(["면적", " / ".join(x for x in (("토지 %s㎡" % f(it["land"])) if it["land"] else "", ("건물 %s㎡" % f(it["bld"])) if it["bld"] else "") if x)])
    if it["disp"] == "임대": rows.append(["임대 조건", esc(" · ".join(x for x in (it["rent"], it["rent_period"]) if x and x != "-") or "-")])
    rows.append(["입찰 기간(현재 회차)", "%s ~ %s" % (dt(it["bid_begin"], "full"), dt(it["bid_end"], "full"))])
    rows += [["입찰 방식", " · ".join(x for x in (it["bid_div"], it["bid_method"], it["compete"], it["total_unit"]) if x) or "-"],
             ["공동·대리 입찰", " · ".join("%s %s" % (a, "가능" if v == "Y" else "불가") for a, v in (("공동입찰", it["flags"]["joint"]), ("2인 이상 공동", it["flags"]["twtm"]), ("대리입찰", it["flags"]["subst"])) if v) or "-"]]
    if it["evict"]: rows.append(["명도 책임", esc(it["evict"])])
    if it["fee_rate"]: rows.append(["수수료율", "%s%%" % it["fee_rate"]])
    if it["pb"]["name"]: rows.append(["공고", esc(it["pb"]["name"]) + ((" · " + esc(it["pb"]["branch"])) if it["pb"]["branch"] else "")])
    if it["rqst"]: rows.append(["위임기관", esc(it["rqst"])])
    if it["first_pbanc"]: rows.append(["최초 공고일", dt(it["first_pbanc"], "full")])
    info = table(None, rows)
    metrics = []
    area = it["land"] or it["bld"]
    if ap and area and area > 0:
        metrics.append(["㎡당 감정가", kor(ap / area)]); metrics.append(["평당 감정가(1평=3.3058㎡)", kor(ap / area * 3.3058)])
        if mn: metrics.append(["평당 최저입찰가", kor(mn / area * 3.3058)])
    pa = idx.peers_avg(it)
    if r and pa: metrics.append(["같은 시군구 %s 진행 물건 평균 최저가율" % (it["mcls"] or "부동산"), "%.0f%% (%d건 기준, 이 물건 %.0f%%)" % (pa[0], pa[1], r)])
    metr = ('<h2 class="group-title">📐 가격 지표</h2>' + table(None, metrics)) if metrics else ""
    sq = ""
    if it["sqms"]: sq = '<h2 class="group-title">📏 면적 내역</h2>' + table(["구분", "면적", "비고"], [[esc(s["kind"]), esc(s["area"]), esc(s["note"])] for s in it["sqms"]])
    def para(h, t): return ('<h2 class="group-title">%s</h2><p class="lead">%s</p>' % (h, esc(t).replace("\n", "<br>"))) if t else ""
    text = para("📍 위치 및 부근 현황", it["loc_txt"]) + para("🏞️ 이용 현황", it["use_txt"])
    if it["note_txt"]: text += '<h2 class="group-title">⚠️ 유의사항 (공고문)</h2><div class="warn-box">%s</div>' % esc(it["note_txt"]).replace("\n", "<br>")
    text += para("ℹ️ 기타", it["etc_txt"]) + para("📋 입찰 조건", it["cond_txt"]) + para("🔎 참고", it["valid_txt"])
    if not it["detail"]: text += '<div class="warn-box">이 물건의 상세 사진·감정평가서·권리 관계는 아직 정리 중입니다. 입찰 전 온비드 공고문에서 직접 확인하세요. (우아공매는 매일 상세 정보를 순차적으로 추가합니다)</div>'
    appr = ""
    if it["appraisals"]:
        appr = '<h2 class="group-title">🧾 감정평가</h2>' + table(["평가일", "감정평가기관", "감정가", "평가서"], [[dt(a["ymd"], "full"), esc(a["org"] or "-"), kor(a["amt"]) if a["amt"] else "-", ('<a href="%s" target="_blank" rel="noopener nofollow">보기</a>' % esc(a["url"])) if a["url"] else "-"] for a in it["appraisals"][:4]], (2,))
    rt = ""
    if it["rights"] or it["dist"] or it["leases"] or it["occupants"]:
        rr = []
        if it["rights"]: rr.append(["등기사항(권리) 기재", "%d건" % len(it["rights"]), ", ".join(sorted({x["type"] for x in it["rights"] if x["type"]})) or "-"])
        if it["dist"]: rr.append(["배분요구·채권 신고", "%d건" % len(it["dist"]), ", ".join(sorted({x["type"] for x in it["dist"] if x["type"]})) or "-"])
        rr.append(["임차 정보", "%d건" % it["leases"], "임차인이 있으면 보증금 인수 여부 확인" if it["leases"] else "공개된 임차 정보 없음"])
        rr.append(["점유 관계", "%d건" % it["occupants"], "점유자가 있으면 인도 필요" if it["occupants"] else "공개된 점유 정보 없음"])
        rt = '<h2 class="group-title">⚖️ 권리 관계 요약</h2>' + table(["항목", "건수", "내용"], rr) + '<p class="note">온비드가 공개한 정보를 건수 위주로 요약했고 채권자·채무자 이름은 표시하지 않습니다. 낙찰자가 인수할 권리와 배당 순위는 반드시 등기부등본과 공고문 원문으로 확인하세요.</p>'
    tp = tips(it)
    tipbox = ('<h2 class="group-title">💡 이 물건에서 확인할 점</h2><ul class="tips">%s</ul>' % "".join("<li><b>%s</b> — %s</li>" % (esc(a), esc(b)) for a, b in tp)) if tp else ""
    rel = idx.related(it); relh = ('<h2 class="group-title">🏘️ 같은 지역의 다른 공매 물건</h2>' + grid(rel)) if rel else ""
    ended = '<div class="warn-box">이 물건은 온비드 공고 목록에서 확인되지 않아 입찰이 종료된 것으로 보입니다. 낙찰·유찰 결과는 온비드에서 확인하세요.</div>' if it["state"] in ("ended", "closed") else ""
    kakao = "https://map.kakao.com/?q=" + urllib.parse.quote(it["addr"] or w)
    ctas = chips([("온비드에서 확인·입찰", "https://www.onbid.co.kr"), ("지도에서 위치 보기", kakao), ("%s 공매 물건 더 보기" % it["region"], "/region/%s/%s/" % (it["sido"], it["sgg"]) if it["sido"] and it["sgg"] else "/region/"), ("공매 입찰 가이드", "/guide/")])
    cta_note = '<p class="note">온비드 접속 후 상단 검색에서 물건관리번호 <b>%s</b> 로 이 물건을 찾을 수 있습니다. 우아공매는 입찰을 대행하지 않습니다.</p>' % esc(it["id"])
    pay = "임대" if it["disp"] == "임대" else "매각"
    if it["state"] == "nego": when = "입찰 회차는 모두 끝났고 현재 <b>수의계약</b>으로 매수 가능한 상태입니다."
    else: when = "현재 회차 입찰은 %s부터 %s까지입니다." % (dt(it["bid_begin"], "full"), dt(it["bid_end"], "full"))
    lead = "<p class=\"lead\"><b>%s</b> %s %s 공매 물건입니다. 감정가 <b>%s</b>%s. %s%s</p>" % (
        esc(w), esc(use), pay, kor(ap) if ap else "비공개",
        (", %s <b>%s</b>(감정가의 %.0f%%)" % (unit, kor(mn), r)) if mn and r else ((", %s <b>%s</b>" % (unit, kor(mn))) if mn else ""), when,
        (" %d회 유찰된 물건입니다." % it["usbd"]) if it["usbd"] else "")
    kindword = "수의계약 가능" if it["state"] == "nego" else "공매"
    ttl = "%s %s — 감정가 %s, %s %s%s" % (title_core(it), kindword, kor(ap) if ap else "비공개", "최저" if it["disp"] != "임대" else "기준가", kor(mn) if mn else "-", (" (%.0f%%)" % r) if r else "")
    desc = "%s %s 물건. 감정가 %s, %s %s, %s 사진·%s·권리 요약·입찰 시 확인할 점." % (title_core(it), kindword, kor(ap) if ap else "비공개", unit, kor(mn) if mn else "-", "회차별 최저입찰가 일정," if len(it["rounds"]) > 1 else "", "감정평가" if it["detail"] else "입찰 정보")
    dd = dday(it)
    body = f"""
<div class="page-head"><h1>{esc(w)} {esc(use)} {kindword} — {unit} {kor(mn) if mn else '-'}</h1><p><span class="badge {col}">{st}{(' · ' + dd) if dd else ''}</span> {esc(it['kind'])} · {esc(it['mcls'] or '부동산')} · 물건관리번호 {esc(it['id'])}</p></div>
{ended}
{lead}
{gal}
{price}
{ad()}
{rounds_table(it)}
<h2 class="group-title">📌 물건 정보</h2>
{info}
{metr}
{stat_box(it, stats)}
{sq}
{text}
{tipbox}
{appr}
{rt}
{ctas}
{cta_note}
{relh}
<p class="note">데이터: 한국자산관리공사 온비드 공공데이터(물건 정보 갱신 {dt(it['modified'], 'full') if it['modified'] else '-'}, 우아공매 수집 {dt(it['last_seen'])}). 입찰 조건·가격은 정정공고로 바뀔 수 있으니 입찰 전 온비드 공고문을 반드시 확인하세요.</p>
"""
    faq = [(f"{w} {use} 공매 최저입찰가는 얼마인가요?", f"감정가 {kor(ap) if ap else '비공개'}에 대해 {unit}는 {kor(mn) if mn else '공고 참조'}입니다" + (f"(감정가의 {r:.0f}%)." if r else ".")),
           ("공매 입찰보증금은 얼마를 내나요?", "일반적으로 입찰금액의 10%% 를 입찰보증금으로 납부합니다. 이 물건 최저입찰가 기준 약 %s이며 정확한 금액과 납부 방법은 공고문을 확인하세요." % (kor(deposit) if deposit else "공고 참조")),
           ("유찰되면 가격이 내려가나요?", "공고문에 정해진 방식에 따라 다음 회차에 최저입찰가가 낮아질 수 있습니다. 이 물건은 현재 %d회 유찰 상태입니다." % it["usbd"] + (" 회차별 가격은 위 표에서 볼 수 있습니다." if len(it["rounds"]) > 1 else "")),
           ("낙찰받으면 점유자를 내보내는 건 누구 책임인가요?", "공고 조건에 따라 다릅니다. " + ("이 물건은 명도 책임이 %s로 표시되어 있습니다." % it["evict"] if it["evict"] else "명도 책임은 공고문의 유의사항을 확인하세요."))]
    faq[1] = (faq[1][0], faq[1][1].replace("10% 를", "10%를"))
    indexable = it["state"] in LIVE
    write(path, layout(path, ttl, desc, body, faq, [("홈", "/"), ("공매 물건", "/item/"), (it["sido"] or "전국", "/region/%s/" % it["sido"] if it["sido"] else "/region/"), (it["sgg"] or "-", "/region/%s/%s/" % (it["sido"], it["sgg"]) if it["sgg"] else "/region/"), ("물건", path)], noindex=not indexable),
          "0.6" if it["state"] in ("open", "upcoming") else "0.4", sitemap=indexable)

# ───────────────────────── 지역·용도·수의계약·달력 ─────────────────────────
def avg_ratio(its):
    r = [x["ratio"] for x in its if x["ratio"]]
    return sum(r) / len(r) if r else None
def usage_mix(its): return collections.Counter(x["mcls"] or "기타" for x in its).most_common()
def sort_soon(its): return sorted(its, key=lambda x: (x["bid_end"] or "9", x["id"]))
def sort_cheap(its): return sorted(its, key=lambda x: (x["ratio"] is None, x["ratio"] or 0, x["id"]))

def page_region_sgg(sido, sgg, its):
    path = "/region/%s/%s/" % (sido, sgg)
    bids = sort_soon([x for x in its if x["state"] in ("open", "upcoming")]); neg = sort_cheap([x for x in its if x["state"] == "nego"])
    ar = avg_ratio(its); mix = usage_mix(its)
    nego_sec = ""
    if neg: nego_sec = '<h2 class="group-title">🤝 수의계약 가능 물건 (%d건)</h2>%s%s' % (len(neg), grid(neg[:12]), ('<p class="note"><a href="%s">%s %s 수의계약 가능 물건 전체 보기</a></p>' % (q(path + "nego/"), esc(sido), esc(sgg))) if len(neg) > 12 else "")
    bid_sec = ('<h2 class="group-title">⏰ 입찰 중·예정 물건 (%d건)</h2>%s' % (len(bids), grid(bids[:60]))) if bids else ""
    mix_chips = chips([("%s %d건" % (a, b), "/region/%s/%s/%s/" % (sido, sgg, slug(a))) for a, b in mix if b >= 5])
    body = f"""
<div class="page-head"><h1>{esc(sido)} {esc(sgg)} 공매 물건 — {len(its)}건</h1><p>사진·감정가·최저입찰가·입찰 일정 · 한국자산관리공사 온비드</p></div>
<p class="lead"><b>{esc(sido)} {esc(sgg)}</b>의 공매 부동산은 입찰 중·예정 <b>{len(bids)}건</b>, 수의계약 가능 <b>{len(neg)}건</b>입니다. 용도는 {esc(', '.join('%s %d건' % (a, b) for a, b in mix[:4]))} 순이며{(' 평균 최저입찰가율은 감정가의 %.0f%%입니다.' % ar) if ar else '.'} 물건을 누르면 회차별 최저입찰가와 권리 요약, 입찰 시 확인할 점을 볼 수 있습니다.</p>
{ad()}
{mix_chips}
{bid_sec}
{nego_sec}
{chips([(esc(sido) + " 전체", "/region/%s/" % sido), ("지역별 공매", "/region/"), ("공매 입찰 가이드", "/guide/")])}
"""
    faq = [(f"{sido} {sgg} 공매 물건은 몇 건인가요?", f"입찰 중·예정 {len(bids)}건과 수의계약 가능 {len(neg)}건입니다(매일 갱신)."), ("공매 물건은 어디서 입찰하나요?", "한국자산관리공사 온비드(onbid.co.kr)에서 전자입찰로 진행합니다. 우아공매는 정보 제공만 합니다.")]
    write(path, layout(path, f"{sido} {sgg} 공매 물건 {len(its)}건 — 감정가·최저입찰가·사진", f"{sido} {sgg} 온비드 공매 부동산 {len(its)}건(입찰 중·예정 {len(bids)}건, 수의계약 가능 {len(neg)}건)의 사진·감정가·최저입찰가를 매일 갱신해 정리했습니다.", body, faq,
                       [("홈", "/"), ("지역별", "/region/"), (sido, "/region/%s/" % sido), (sgg, path)]), "0.7")

def page_list(path, title_h, sub, lead, its, crumbs, ttl, desc, prio="0.6", limit=100):
    its = its[:limit]
    body = f"""
<div class="page-head"><h1>{title_h}</h1><p>{sub}</p></div>
<p class="lead">{lead}</p>
{ad()}
{grid(its)}
{chips([("지역별 공매", "/region/"), ("수의계약 가능 물건", "/negotiated/"), ("공매 입찰 가이드", "/guide/")])}
"""
    write(path, layout(path, ttl, desc, body, None, crumbs), prio)

def page_region_sido(sido, its, by_sgg):
    path = "/region/%s/" % sido
    bids = sort_soon([x for x in its if x["state"] in ("open", "upcoming")]); neg = [x for x in its if x["state"] == "nego"]
    mix = usage_mix(its); ar = avg_ratio(its)
    sg_rows = [['<a href="%s">%s</a>' % (q("/region/%s/%s/" % (sido, sg)), esc(sg)), "%d건" % sum(1 for x in l if x["state"] in ("open", "upcoming")), "%d건" % sum(1 for x in l if x["state"] == "nego"), ("%.0f%%" % avg_ratio(l)) if avg_ratio(l) else "-"] for sg, l in sorted(by_sgg.items(), key=lambda t: -len(t[1]))]
    reg = STAT_REGION_OF.get(sido); stat_link = (' <a href="%s">%s 압류재산 낙찰가율 추이</a>' % (q("/stats/seized/%s/" % reg), esc(reg))) if reg else ""
    body = f"""
<div class="page-head"><h1>{esc(sido)} 공매 물건 — {len(its):,}건</h1><p>시군구별 현황 · 곧 마감되는 물건</p></div>
<p class="lead"><b>{esc(sido)}</b>의 온비드 공매 부동산은 입찰 중·예정 <b>{len(bids):,}건</b>, 수의계약 가능 <b>{len(neg):,}건</b>이며 {esc(', '.join('%s %d건' % (a, b) for a, b in mix[:4]))} 순입니다.{(' 평균 최저입찰가율은 감정가의 %.0f%%입니다.' % ar) if ar else ''} 시군구를 눌러 물건 목록을 확인하세요.{stat_link}</p>
{ad()}
<h2 class="group-title">🗺️ 시군구별 물건</h2>
{table(['시군구', '입찰 중·예정', '수의계약 가능', '평균 최저가율'], sg_rows, (1, 2, 3))}
<h2 class="group-title">⏰ 곧 마감되는 물건</h2>
{grid(bids[:12])}
{chips([("지역별 공매", "/region/"), ("수의계약 가능 물건", "/negotiated/"), ("공매 입찰 가이드", "/guide/")])}
"""
    faq = [(f"{sido} 공매 부동산은 몇 건인가요?", f"입찰 중·예정 {len(bids):,}건, 수의계약 가능 {len(neg):,}건입니다(매일 갱신).")]
    write(path, layout(path, f"{sido} 공매 부동산 {len(its):,}건 — 시군구별 감정가·최저입찰가", f"{sido} 온비드 공매 부동산 {len(its):,}건. 시군구별 물건 수와 평균 최저가율, 곧 마감되는 물건을 사진과 함께 정리했습니다.", body, faq,
                       [("홈", "/"), ("지역별", "/region/"), (sido, path)]), "0.8")

def page_region_hub(by_sido):
    rows = [['<a href="%s">%s</a>' % (q("/region/%s/" % s), esc(s)), "%d건" % sum(1 for x in l if x["state"] in ("open", "upcoming")), "%d건" % sum(1 for x in l if x["state"] == "nego"), ("%.0f%%" % avg_ratio(l)) if avg_ratio(l) else "-"] for s, l in sorted(by_sido.items(), key=lambda t: -len(t[1]))]
    total = sum(len(l) for l in by_sido.values())
    body = f"""
<div class="page-head"><h1>지역별 공매 부동산 — 시도·시군구별 {total:,}건</h1><p>온비드 입찰 중·예정·수의계약 가능 물건을 지역별로 확인</p></div>
<p class="lead">한국자산관리공사 온비드의 공매 부동산 <b>{total:,}건</b>을 시도별로 정리했습니다. 지역을 누르면 시군구별 물건과 사진을 볼 수 있습니다.</p>
{ad()}
{table(['시도', '입찰 중·예정', '수의계약 가능', '평균 최저가율'], rows, (1, 2, 3))}
{chips([("공매 입찰 가이드", "/guide/"), ("이번 주 마감", "/calendar/"), ("낙찰가율 통계", "/stats/")])}
"""
    write("/region/", layout("/region/", f"지역별 공매 부동산 {total:,}건 — 시도·시군구별 온비드 물건", f"전국 온비드 공매 부동산 {total:,}건을 시도·시군구별로 정리. 사진, 감정가, 최저입찰가, 입찰 일정을 매일 갱신합니다.", body, [("지역별 공매 물건은 어떻게 찾나요?", "시도를 고른 뒤 시군구 페이지에서 사진과 가격을 확인하세요.")], [("홈", "/"), ("지역별", "/region/")], coupang=True), "0.9")

def page_nego_hub(live):
    neg = [x for x in live if x["state"] == "nego"]
    by = collections.defaultdict(list)
    for x in neg: by[x["sido"] or "기타"].append(x)
    rows = [[('<a href="%s">%s</a>' % (q("/region/%s/" % s), esc(s))) if s != "기타" else "지역 미상", "%d건" % len(l), ("%.0f%%" % avg_ratio(l)) if avg_ratio(l) else "-"] for s, l in sorted(by.items(), key=lambda t: -len(t[1]))]
    body = f"""
<div class="page-head"><h1>수의계약 가능 공매 부동산 — {len(neg):,}건</h1><p>입찰이 끝난 뒤에도 매각되지 않아 수의계약으로 매수할 수 있는 물건</p></div>
<p class="lead">온비드에서 입찰 회차를 거쳤지만 낙찰되지 않아 <b>수의계약으로 매수할 수 있는 상태</b>의 부동산 <b>{len(neg):,}건</b>입니다. 입찰과 달리 정해진 조건에서 신청하는 방식이라 가격과 절차는 공고마다 다릅니다. 물건을 누르면 지난 회차의 최저입찰가와 유찰 횟수를 볼 수 있습니다.</p>
{ad()}
<h2 class="group-title">💸 감정가 대비 최저가율이 낮은 순</h2>
{grid(sort_cheap(neg)[:24])}
<h2 class="group-title">🗺️ 지역별 수의계약 가능 물건</h2>
{table(['시도', '물건 수', '평균 최저가율'], rows, (1, 2))}
{chips([("공매 입찰 가이드", "/guide/"), ("지역별 공매", "/region/")])}
"""
    faq = [("수의계약이란 무엇인가요?", "입찰 절차 없이 매도자와 정해진 조건으로 계약하는 방식입니다. 공매에서는 여러 번 유찰된 물건 등에서 가능하며 조건은 공고마다 다릅니다."), ("수의계약은 가격 협상이 되나요?", "가격 결정 방식은 물건과 공고 조건에 따라 다릅니다. 온비드 공고문에서 확인하세요.")]
    write("/negotiated/", layout("/negotiated/", f"수의계약 가능 공매 부동산 {len(neg):,}건 — 유찰 후 매수 가능한 온비드 물건", f"입찰 후 낙찰되지 않아 수의계약으로 매수할 수 있는 온비드 공매 부동산 {len(neg):,}건. 지역별·최저가율별로 사진과 함께 정리했습니다.", body, faq, [("홈", "/"), ("수의계약 가능", "/negotiated/")], coupang=True), "0.9")

def page_calendar(live):
    days = collections.defaultdict(list)
    for it in live:
        if it["state"] not in ("open", "upcoming"): continue
        e = pdt(it["bid_end"])
        if e and TODAY.date() <= e.date() <= (TODAY + datetime.timedelta(days=14)).date(): days[e.date()].append(it)
    secs = ""
    for d in sorted(days):
        l = sorted(days[d], key=lambda x: (x["bid_end"], x["id"]))
        secs += '<h2 class="group-title">📅 %d월 %d일 (%s) · %d건 마감</h2>%s' % (d.month, d.day, "월화수목금토일"[d.weekday()], len(l), grid(l[:12]))
    body = f"""
<div class="page-head"><h1>이번 주·다음 주 공매 입찰 마감 일정</h1><p>온비드 공매 부동산 입찰 마감일별 물건</p></div>
<p class="lead">앞으로 14일 안에 현재 회차 입찰이 마감되는 공매 부동산을 날짜별로 모았습니다. 마감 직전에는 정정공고가 나올 수 있으니 입찰 전 온비드에서 다시 확인하세요.</p>
{ad()}
{secs or '<p class="lead">표시할 일정이 없습니다.</p>'}
{chips([("지역별 공매", "/region/"), ("공매 입찰 가이드", "/guide/")])}
"""
    write("/calendar/", layout("/calendar/", "이번 주 공매 입찰 마감 일정 — 온비드 부동산 마감 임박 물건", "앞으로 14일 안에 입찰이 마감되는 온비드 공매 부동산을 날짜별로 사진과 함께 정리했습니다. 매일 갱신.", body, None, [("홈", "/"), ("이번 주 마감", "/calendar/")]), "0.8")

def rank_cards(ranks, key, by_id, n=8):
    out = []
    for r in ranks.get(key, []):
        it = by_id.get(r.get("cltrMngNo"))
        if it and it["live"]: out.append(it)
        if len(out) >= n: break
    return out

def page_item_hub(live, ranks, by_id):
    op = [x for x in live if x["state"] in ("open", "upcoming")]
    soon = sort_soon(op)[:12]; cheap = sort_cheap([x for x in op if x["ratio"]])[:12]
    photo = sorted([x for x in op if x["detail"]], key=lambda x: -len(x["photos"]))[:12]
    pop, decr, fav = rank_cards(ranks, "rank_views", by_id), rank_cards(ranks, "rank_decr", by_id), rank_cards(ranks, "rank_fav", by_id)
    mc = collections.Counter(x["mcls"] or "기타" for x in live)
    def sec(h, its): return ('<h2 class="group-title">%s</h2>%s' % (h, grid(its))) if its else ""
    body = f"""
<div class="page-head"><h1>온비드 공매 부동산 — 입찰 중·예정 {len(op):,}건</h1><p>한국자산관리공사 공매 물건을 사진과 함께 · 매일 갱신</p></div>
<p class="lead">입찰 중이거나 예정인 공매 부동산 <b>{len(op):,}건</b>과 수의계약 가능 물건 <b>{len(live) - len(op):,}건</b>을 지역·용도별로 정리했습니다. 각 물건 페이지에서 사진, 감정가, 회차별 최저입찰가, 권리 요약, 입찰 시 확인할 점을 볼 수 있습니다.</p>
{ad()}
{sec('🔥 조회수 많은 물건 (온비드 순위)', pop)}
{sec('📉 최저가가 많이 내려간 물건 (저감률 순위)', decr)}
{sec('⭐ 관심 많은 물건', fav)}
{sec('⏰ 곧 마감되는 물건', soon)}
{sec('💸 감정가 대비 최저가율이 낮은 물건', cheap)}
{sec('📷 사진이 많은 물건', photo)}
{chips([("%s %d건" % (a, b), "/usage/%s/" % slug(a)) for a, b in mc.most_common()] + [("지역별", "/region/"), ("수의계약 가능", "/negotiated/"), ("이번 주 마감", "/calendar/")])}
"""
    write("/item/", layout("/item/", f"온비드 공매 부동산 {len(op):,}건 — 사진·감정가·최저입찰가", f"입찰 중·예정 온비드 공매 부동산 {len(op):,}건. 인기·저감률·마감 임박·최저가율 낮은 물건을 매일 갱신해 보여드립니다.", body, None, [("홈", "/"), ("공매 물건", "/item/")], coupang=True), "0.9")

def page_home(live, meta):
    op = [x for x in live if x["state"] in ("open", "upcoming")]
    soon = sort_soon(op)[:8]
    new = sorted(op, key=lambda x: (x["first_seen"], x["id"]), reverse=True)[:8]
    by_sido = collections.Counter(x["sido"] for x in live if x["sido"])
    body = f"""
<div class="hero"><h1>🔨 우아공매 — 온비드 공매 부동산을 사진과 함께</h1><p>입찰 중·예정 {len(op):,}건 · 수의계약 가능 {len(live) - len(op):,}건 · 낙찰가율 통계 · 매일 갱신</p></div>
<div class="tool-box"><div class="tool-row"><div style="flex:1;min-width:220px"><label for="q">지역·주소·용도로 검색</label><input id="q" type="search" placeholder="예) 평택 임야, 강남 아파트, 상가" style="width:100%"></div></div><div id="res" class="item-grid"></div></div>
{ad()}
<h2 class="group-title">⏰ 곧 마감되는 물건</h2>{grid(soon)}
<h2 class="group-title">🆕 새로 올라온 물건</h2>{grid(new)}
<h2 class="group-title">🗺️ 지역별 공매</h2>{chips([("%s %d건" % (s, n), "/region/%s/" % s) for s, n in by_sido.most_common()])}
{chips([("수의계약 가능 물건", "/negotiated/"), ("낙찰가율 통계", "/stats/"), ("이번 주 마감", "/calendar/"), ("공매 입찰 가이드", "/guide/"), ("용어 사전", "/guide/glossary/")])}
<p class="lead">우아공매는 한국자산관리공사(KAMCO) 온비드의 공공데이터를 바탕으로 공매 부동산의 사진, 감정가, 회차별 최저입찰가, 권리 요약과 낙찰가율 통계를 보기 쉽게 정리한 사이트입니다. 입찰은 온비드에서만 가능하며 우아공매는 입찰 대행이나 투자 권유를 하지 않습니다.</p>
<script src="/assets/js/search.js"></script>
"""
    faq = [("공매와 경매는 무엇이 다른가요?", "공매는 한국자산관리공사 온비드에서 전자입찰로 진행하고, 경매는 법원이 진행합니다. 우아공매는 온비드 공매 물건을 다룹니다."), ("입찰은 어디서 하나요?", "온비드(onbid.co.kr)에서 회원 가입 후 전자입찰로 합니다.")]
    write("/", layout("/", "우아공매 — 온비드 공매 부동산 사진·감정가·낙찰가율 (매일 갱신)", f"한국자산관리공사 온비드 공매 부동산 {len(live):,}건의 사진, 감정가, 회차별 최저입찰가, 낙찰가율 통계를 지역·용도별로 매일 갱신해 보여드립니다.", body, faq), "1.0")

def search_index(live):
    rows = [[it["id"], where(it) or it["name"][:30], it["mcls"] or "", it["scls"] or "", it["min"] or 0, it["appraisal"] or 0] for it in live]
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "search_index.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

# ───────────────────────── 낙찰 통계 ─────────────────────────
def trend_bars(rows, key="scfbAmtRto1", label="감정가 대비 낙찰가율"):
    vals = [(m, r.get(key)) for m, r in rows if r and r.get(key)]
    if not vals: return ""
    mx = max(v for _, v in vals) or 1
    bars = "".join('<div class="bar"><div class="fill" style="height:%d%%"></div><b>%.0f</b><span>%s</span></div>' % (max(4, int(v / mx * 100)), v, "%d월" % int(m[4:6])) for m, v in vals)
    return '<div class="bars" aria-label="%s 월별 추이">%s</div><p class="note">%s (%%) · 월별 추이</p>' % (label, bars, label)

def stat_cells(r):
    return [k(r["pbctCltrCnt"]) + "건", k(r["mtSumCnt"]) + "건", "%s%%" % r["scbrt"], r["compRate"], ("%.1f%%" % r["scfbAmtRto1"]) if r.get("scfbAmtRto1") else "-", ("%.1f%%" % r["scfbAmtRto2"]) if r.get("scfbAmtRto2") else "-"]
STAT_HEADS = ["입찰 건수", "낙찰 건수", "낙찰률", "경쟁률", "감정가 대비 낙찰가율", "최저가 대비 낙찰가율"]
STAT_NOTE = "한국자산관리공사 온비드 입찰통계(공공데이터)를 월 단위로 정리한 값입니다. 낙찰률은 입찰 건수 대비 낙찰 건수, 낙찰가율은 평균 낙찰가를 감정가(또는 최저입찰가)로 나눈 값이며 지역·용도 구분은 온비드 기준을 따릅니다."

def trend_rows(stats, kind, code, name):
    out = []
    for m in sorted(stats[kind].get(code, {})):
        r = stat_row(stats, kind, code, m, name)
        if r and (r.get("pbctCltrCnt") or 0) > 0: out.append((m, r))
    return out

def page_stats(stats):
    hubrows = []; made = 0
    for code, (slg, label, ucode) in STAT_TYPES.items():
        m = latest_month(stats, code)
        if not m: continue
        allr = stat_row(stats, "region", code, m, "전체")
        regs = [r for r in stats["region"][code][m] if r["clsCdNm"] != "전체" and (r.get("pbctCltrCnt") or 0) > 0]
        usg = [r for r in stats["usage"].get(ucode, {}).get(m, []) if r["clsCdNm"] != "전체" and (r.get("pbctCltrCnt") or 0) > 0]
        hubrows.append(['<a href="/stats/%s/">%s</a>' % (slg, label), mlabel(m)] + stat_cells(allr))
        reg_rows = [['<a href="%s">%s</a>' % (q("/stats/%s/%s/" % (slg, slug(r["clsCdNm"]))), esc(r["clsCdNm"]))] + stat_cells(r) for r in regs]
        usg_rows = [['<a href="%s">%s</a>' % (q("/stats/%s/usage/%s/" % (slg, slug(r["clsCdNm"]))), esc(r["clsCdNm"]))] + stat_cells(r) for r in usg]
        tr = trend_rows(stats, "region", code, "전체")
        trend_tbl = table(["월"] + STAT_HEADS, [[mlabel(mm)] + stat_cells(r) for mm, r in reversed(tr)], tuple(range(1, 7)))
        a1 = allr.get("scfbAmtRto1")
        path = "/stats/%s/" % slg
        body = f"""
<div class="page-head"><h1>{label} 공매 낙찰가율·낙찰률 통계 — 지역·용도별 ({mlabel(m)})</h1><p>온비드 입찰통계 · 월별 추이</p></div>
<p class="lead">{mlabel(m)} 온비드 {label} 입찰은 <b>{k(allr['pbctCltrCnt'])}건</b>이었고 이 가운데 <b>{k(allr['mtSumCnt'])}건</b>이 낙찰되어 낙찰률은 <b>{allr['scbrt']}%</b>, 경쟁률은 <b>{allr['compRate']}</b>였습니다.{(' 감정가 대비 평균 낙찰가율은 <b>%.1f%%</b>입니다.' % a1) if a1 else ''} 아래에서 지역별·용도별 수치를 확인하세요.</p>
{ad()}
{trend_bars(tr)}
<h2 class="group-title">🗺️ 지역별 ({mlabel(m)})</h2>
{table(['지역'] + STAT_HEADS, reg_rows, tuple(range(1, 7)))}
{('<h2 class="group-title">🏷️ 용도별 (%s)</h2>' % mlabel(m)) + table(['용도'] + STAT_HEADS, usg_rows, tuple(range(1, 7))) if usg_rows else ''}
<h2 class="group-title">📈 월별 추이 (전체)</h2>
{trend_tbl}
<p class="note">{STAT_NOTE} 이 통계에는 부동산 외 물건이 포함될 수 있습니다.</p>
{chips([("낙찰 통계 전체", "/stats/"), ("공매 물건", "/item/"), ("낙찰가율 읽는 법", "/guide/ratio/")])}
"""
        faq = [(f"{label} 낙찰가율은 얼마인가요?", f"{mlabel(m)} 기준 감정가 대비 평균 낙찰가율은 {('%.1f%%' % a1) if a1 else '집계 없음'}입니다."), ("낙찰률은 무엇인가요?", "입찰이 진행된 건수 중 낙찰된 건수의 비율입니다.")]
        write(path, layout(path, f"{label} 낙찰가율·낙찰률 통계 ({mlabel(m)}) — 지역·용도별", f"{mlabel(m)} 온비드 {label} 낙찰률 {allr['scbrt']}%, 경쟁률 {allr['compRate']}{(', 감정가 대비 낙찰가율 %.1f%%' % a1) if a1 else ''}. 지역별·용도별 낙찰 통계와 월별 추이.", body, faq,
                           [("홈", "/"), ("낙찰 통계", "/stats/"), (label, path)]), "0.8"); made += 1
        for kind, names in (("region", [r["clsCdNm"] for r in regs]), ("usage", [r["clsCdNm"] for r in usg])):
            cd = code if kind == "region" else ucode
            for nm in names:
                rows_t = trend_rows(stats, kind, cd, nm)
                if not rows_t: continue
                lm, lr = rows_t[-1]
                p2 = "/stats/%s/%s/" % (slg, slug(nm)) if kind == "region" else "/stats/%s/usage/%s/" % (slg, slug(nm))
                sub = label + (" " if kind == "region" else " 용도 ") + nm
                a1x = ("%.1f%%" % lr["scfbAmtRto1"]) if lr.get("scfbAmtRto1") else "-"
                b2 = f"""
<div class="page-head"><h1>{esc(sub)} 낙찰가율 통계 — {mlabel(lm)} {a1x}</h1><p>월별 낙찰률·경쟁률·낙찰가율 추이</p></div>
<p class="lead"><b>{esc(sub)}</b>의 {mlabel(lm)} 온비드 입찰은 <b>{k(lr['pbctCltrCnt'])}건</b>, 낙찰은 <b>{k(lr['mtSumCnt'])}건</b>(낙찰률 {lr['scbrt']}%)이고 경쟁률은 {lr['compRate']}입니다.{(' 감정가 대비 평균 낙찰가율은 %.1f%%, 최저입찰가 대비로는 %.1f%%입니다.' % (lr['scfbAmtRto1'], lr['scfbAmtRto2'])) if lr.get('scfbAmtRto1') and lr.get('scfbAmtRto2') else ''}</p>
{ad()}
{trend_bars(rows_t)}
{table(['월'] + STAT_HEADS, [[mlabel(mm)] + stat_cells(r) for mm, r in reversed(rows_t)], tuple(range(1, 7)))}
<p class="note">{STAT_NOTE}</p>
{chips([(label + " 낙찰 통계", "/stats/%s/" % slg), ("낙찰 통계 전체", "/stats/"), ("공매 물건", "/item/")])}
"""
                f2 = [(f"{sub} 낙찰가율은 얼마인가요?", f"{mlabel(lm)} 기준 감정가 대비 평균 낙찰가율은 {a1x if a1x != '-' else '집계 없음'}입니다.")]
                write(p2, layout(p2, f"{sub} 낙찰가율·낙찰률 ({mlabel(lm)})", f"{sub} 온비드 낙찰 통계. {mlabel(lm)} 입찰 {k(lr['pbctCltrCnt'])}건·낙찰률 {lr['scbrt']}%·경쟁률 {lr['compRate']}{(', 낙찰가율 ' + a1x) if a1x != '-' else ''}. 월별 추이.", b2, f2,
                                   [("홈", "/"), ("낙찰 통계", "/stats/"), (label, "/stats/%s/" % slg), (nm, p2)]), "0.5"); made += 1
    if not hubrows: return 0
    body = f"""
<div class="page-head"><h1>공매 낙찰가율·낙찰률 통계 — 재산 유형별·지역별·용도별</h1><p>한국자산관리공사 온비드 입찰통계 · 월별 갱신</p></div>
<p class="lead">감정가 대비 몇 %에 낙찰되는지, 입찰 대비 몇 건이 낙찰되는지, 경쟁률은 얼마인지를 재산 유형별로 정리했습니다. 유형을 눌러 지역별·용도별 수치와 월별 추이를 확인하세요.</p>
{ad()}
{table(['재산 유형', '기준월'] + STAT_HEADS, hubrows, tuple(range(2, 8)))}
<p class="note">{STAT_NOTE}</p>
{chips([("낙찰가율 읽는 법", "/guide/ratio/"), ("공매 물건", "/item/"), ("지역별 공매", "/region/")])}
"""
    faq = [("낙찰가율이 높은 지역은 어디인가요?", "재산 유형별 페이지의 지역별 표에서 월별 낙찰가율을 비교할 수 있습니다."), ("통계는 얼마나 자주 갱신되나요?", "온비드가 월 단위로 공개하는 입찰통계를 반영합니다.")]
    write("/stats/", layout("/stats/", "공매 낙찰가율·낙찰률 통계 — 압류재산·국유재산 지역별·용도별", "온비드 공매 낙찰가율, 낙찰률, 경쟁률을 재산 유형별·지역별·용도별로 월별 정리. 감정가 대비 몇 %에 낙찰되는지 확인하세요.", body, faq, [("홈", "/"), ("낙찰 통계", "/stats/")], coupang=True), "0.9")
    return made

def page_guides():
    for slg, g in guides.GUIDES.items():
        path = "/guide/%s/" % slg if slg else "/guide/"
        write(path, layout(path, g["title"], g["desc"], g["body"](ad()), g["faq"], [("홈", "/"), ("공매 가이드", "/guide/")] + ([(g["short"], path)] if slg else [])), "0.7" if slg else "0.8")

def page_privacy():
    write("/privacy/", layout("/privacy/", "개인정보처리방침", "우아공매 개인정보처리방침", '<div class="page-head"><h1>개인정보처리방침</h1></div><p class="lead">우아공매(wooagongmae.wooahouse.com)는 회원가입을 요구하지 않으며 이용자의 개인정보를 직접 수집하지 않습니다. 방문자 통계를 위해 Google Analytics를, 광고를 위해 Google AdSense와 쿠팡 파트너스를 사용하며 이들은 쿠키를 사용할 수 있습니다. 쿠키는 브라우저 설정에서 비활성화할 수 있습니다. 문의: <a href="mailto:ingmaster83@gmail.com">ingmaster83@gmail.com</a></p><p class="note">최종 수정일: 2026년 11월 8일</p>', None, [("홈", "/"), ("개인정보처리방침", "/privacy/")]), sitemap=False)

def main():
    t0 = time.time()
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "assets", OUT / "assets", dirs_exist_ok=True)
    for nf in ROOT.glob("naver*.html"): shutil.copy(nf, OUT / nf.name)
    meta, items, stats, ranks = load()
    idx = Idx(items); live = idx.live; by_id = {x["id"]: x for x in items}
    print("items", len(items), "live", len(live), dict(collections.Counter(x["state"] for x in items)))
    for i, it in enumerate(items):
        page_item(it, idx, stats)
        if i % 5000 == 0: print(" item", i, round(time.time() - t0), "s", flush=True)
    by_region = collections.defaultdict(lambda: collections.defaultdict(list))
    for it in live:
        if it["sido"]: by_region[it["sido"]][it["sgg"] or "기타"].append(it)
    for sido, d in by_region.items():
        sl = [x for l in d.values() for x in l]
        page_region_sido(sido, sl, d)
        for sgg, l in d.items():
            page_region_sgg(sido, sgg, l)
            neg = sort_cheap([x for x in l if x["state"] == "nego"])
            if len(neg) > 12:
                page_list("/region/%s/%s/nego/" % (sido, sgg), "%s %s 수의계약 가능 물건 — %d건" % (esc(sido), esc(sgg), len(neg)), "수의계약으로 매수 가능한 공매 부동산", "%s %s에서 수의계약으로 매수할 수 있는 공매 부동산 %d건입니다. 감정가 대비 최저가율이 낮은 순으로 정렬했습니다." % (esc(sido), esc(sgg), len(neg)), neg,
                          [("홈", "/"), ("지역별", "/region/"), (sido, "/region/%s/" % sido), (sgg, "/region/%s/%s/" % (sido, sgg)), ("수의계약", "/region/%s/%s/nego/" % (sido, sgg))],
                          "%s %s 수의계약 가능 공매 부동산 %d건" % (sido, sgg, len(neg)), "%s %s 온비드 수의계약 가능 공매 부동산 %d건. 감정가 대비 최저가율 낮은 순, 사진 포함." % (sido, sgg, len(neg)), prio="0.5")
            by_m = collections.defaultdict(list)
            for x in l: by_m[x["mcls"] or "기타"].append(x)
            for m, ml in by_m.items():
                if len(ml) >= 5:
                    page_list("/region/%s/%s/%s/" % (sido, sgg, slug(m)), "%s %s %s 공매 — %d건" % (esc(sido), esc(sgg), esc(m), len(ml)), "용도별 공매 부동산", "%s %s의 %s 공매 물건 %d건입니다(입찰 중·예정·수의계약 가능 포함)." % (esc(sido), esc(sgg), esc(m), len(ml)), sort_soon(ml),
                              [("홈", "/"), ("지역별", "/region/"), (sido, "/region/%s/" % sido), (sgg, "/region/%s/%s/" % (sido, sgg)), (m, "/region/%s/%s/%s/" % (sido, sgg, slug(m)))],
                              "%s %s %s 공매 %d건 — 감정가·최저입찰가" % (sido, sgg, m, len(ml)), "%s %s %s 온비드 공매 %d건의 사진·감정가·최저입찰가·입찰 일정." % (sido, sgg, m, len(ml)), prio="0.5")
    page_region_hub({s: [x for l in d.values() for x in l] for s, d in by_region.items()})
    by_usage = collections.defaultdict(list)
    for it in live: by_usage[it["mcls"] or "기타"].append(it)
    for m, l in by_usage.items():
        op = [x for x in l if x["state"] in ("open", "upcoming")]
        page_list("/usage/%s/" % slug(m), "%s 공매 물건 — %d건" % (esc(m), len(l)), "용도별 온비드 공매 부동산", "%s 공매 물건은 입찰 중·예정 %d건, 수의계약 가능 %d건입니다.%s" % (esc(m), len(op), len(l) - len(op), (" 평균 최저입찰가율은 감정가의 %.0f%%입니다." % avg_ratio(l)) if avg_ratio(l) else ""), sort_soon(op) + sort_cheap([x for x in l if x["state"] == "nego"]),
                  [("홈", "/"), ("공매 물건", "/item/"), (m, "/usage/%s/" % slug(m))], "%s 공매 물건 %d건 — 감정가·최저입찰가·사진" % (m, len(l)), "온비드 %s 공매 %d건. 감정가와 최저입찰가, 입찰 일정을 사진과 함께 매일 갱신합니다." % (m, len(l)), prio="0.7")
    page_nego_hub(live); page_calendar(live); page_item_hub(live, ranks, by_id); page_home(live, meta)
    nst = page_stats(stats); page_guides(); page_privacy()
    search_index(live)
    today = TODAY.strftime("%Y-%m-%d")
    urls = list(WRITTEN)
    chunks = [urls[i:i + 40000] for i in range(0, len(urls), 40000)] or [[]]
    def xml(chunk): return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>\n' % "".join("<url><loc>%s%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>" % (BASE, q(p), today, pr) for p, pr in chunk)
    if len(chunks) == 1: (OUT / "sitemap.xml").write_text(xml(chunks[0]), encoding="utf-8")
    else:
        for i, c in enumerate(chunks): (OUT / ("sitemap-%d.xml" % (i + 1))).write_text(xml(c), encoding="utf-8")
        (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</sitemapindex>\n' % "".join("<sitemap><loc>%s/sitemap-%d.xml</loc></sitemap>" % (BASE, i + 1) for i in range(len(chunks))), encoding="utf-8")
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % BASE, encoding="utf-8")
    (OUT / "CNAME").write_text("wooagongmae.wooahouse.com\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    nf = layout("/404.html", "페이지를 찾을 수 없습니다", "요청한 페이지를 찾을 수 없습니다.", '<div class="page-head"><h1>페이지를 찾을 수 없습니다</h1></div><p class="lead">종료된 공매 물건이거나 주소가 바뀌었을 수 있습니다.</p><div class="chips"><a class="chip" href="/">홈</a><a class="chip" href="/item/">공매 물건</a><a class="chip" href="/region/">지역별</a></div>', None, None, noindex=True)
    (OUT / "404.html").write_text(nf, encoding="utf-8")
    print("pages", len(WRITTEN), "stats pages", nst, "elapsed", round(time.time() - t0, 1), "s")

if __name__ == "__main__":
    main()
