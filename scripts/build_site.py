# -*- coding: utf-8 -*-
"""우아공매 정적 사이트 생성기 -> _site/.  입력: data/items.json (normalize.py 형식의 진행 물건 + 종료 물건)
사용: python scripts/build_site.py"""
import collections, datetime, json, shutil, sys, time, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *
import guides

DATA = ROOT / "data" / "items.json"
TODAY = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(tzinfo=None)
EOK, MAN = 100_000_000, 10_000
def k(x): return "{:,}".format(int(round(x)))

def kor(n):
    if n is None: return "-"
    n = int(round(n)); eok, rest = divmod(n, EOK); mn, w = divmod(rest, MAN); p = []
    if eok: p.append("%d억" % eok)
    if mn: p.append("{:,}만".format(mn))
    if w and not eok: p.append("{:,}".format(w))
    return (" ".join(p) or "0") + "원"

def table(heads, rows, num=()):
    th = "".join('<th%s>%s</th>' % (' class="num"' if i in num else "", h) for i, h in enumerate(heads)) if heads else ""
    body = "".join("<tr>%s</tr>" % "".join('<td%s>%s</td>' % (' class="num"' if i in num else "", v) for i, v in enumerate(r)) for r in rows)
    return '<div class="tbl-wrap"><table class="tbl">%s<tbody>%s</tbody></table></div>' % (("<thead><tr>%s</tr></thead>" % th) if th else "", body)
def chips(items): return '<div class="chips">%s</div>' % "".join('<a class="chip" href="%s">%s</a>' % (q(u) if u.startswith("/") else u, esc(t)) for t, u in items)

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
def load():
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    items = raw["items"]
    for it in items:
        it["region"] = " ".join(x for x in (it["sido"], it["sgg"]) if x) or "지역 미상"
        b, e, o = pdt(it["bid_begin"]), pdt(it["bid_end"]), pdt(it["open_dt"])
        end = o or e
        if it.get("ended") or (end and end < TODAY - datetime.timedelta(hours=6)): it["state"] = "ended"
        elif b and b > TODAY: it["state"] = "upcoming"
        else: it["state"] = "open"
    return raw.get("meta", {}), items

STATE = {"open": ("입찰 중", "green"), "upcoming": ("입찰 예정", "blue"), "ended": ("입찰 종료", "gray")}

def where(it):
    return " ".join(x for x in (it["sido"], it["sgg"], it["emd"]) if x)
def title_core(it):
    use = it["scls"] or it["mcls"] or "부동산"
    return "%s %s" % (where(it) or it["name"][:20], use)
def dday(it):
    e = pdt(it["bid_end"]) or pdt(it["open_dt"])
    if not e: return ""
    d = (e.date() - TODAY.date()).days
    return "오늘 마감" if d == 0 else ("D-%d" % d if d > 0 else "")

def photo_tag(it, i=0, cls="", full=False):
    ph = it["photos"]
    if not ph: return '<div class="ph noimg">사진 없음</div>'
    u = ph[i] if i < len(ph) else ph[0]
    if full: u = u.replace("&downloadImageKind=THNL_NM", "")
    return '<img src="%s" alt="%s" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.parentNode.classList.add(\'noimg\');this.remove()"%s>' % (esc(u), esc(title_core(it) + " 공매 사진"), (' class="%s"' % cls) if cls else "")

def card(it):
    st, col = STATE[it["state"]]
    dd = dday(it)
    ratio = ("%.0f%%" % it["ratio"]) if it.get("ratio") else ""
    return ('<a class="item-card" href="%s"><div class="ph">%s<span class="badge %s">%s%s</span></div><div class="ib"><b class="t">%s</b>'
            '<span class="u">%s · %s</span><span class="p">감정가 %s</span><span class="p2">최저 %s <em>%s</em></span></div></a>') % (
        q("/item/%s/" % it["id"]), photo_tag(it), col, st, (" · " + dd) if dd and it["state"] != "ended" else "", esc(where(it) or it["name"][:30]),
        esc(it["mcls"] or "부동산"), esc(it["scls"] or "-"), kor(it["appraisal"]) if it["appraisal"] else "비공개", kor(it["min"]) if it["min"] else "-", ratio)
def grid(its): return '<div class="item-grid">%s</div>' % "".join(card(i) for i in its)

# ───────────────────────── 물건 상세 ─────────────────────────
def tips(it):
    t = []
    nm = it["name"] + " " + " ".join(s["note"] for s in it["sqms"])
    if "지분" in nm: t.append(("지분 물건입니다", "부동산의 일부 지분만 낙찰받는 물건입니다. 다른 공유자가 있으면 우선매수 청구나 공유물 분할 문제가 생길 수 있으니 공고문과 등기부등본으로 공유 관계를 확인하세요."))
    if it["scls"] in ("전", "답", "과수원"): t.append(("농지 취득 요건 확인", "농지는 낙찰받더라도 농지취득자격증명이 필요할 수 있습니다. 증명 발급 요건과 기한을 입찰 전에 관할 지자체에서 확인하세요."))
    if it["scls"] in ("임야",) or it["mcls"] == "토지" and not it["bld"]: t.append(("현황 확인", "토지는 진입 도로(맹지 여부), 지목과 실제 이용 현황, 경계를 현장과 지적도로 확인하는 것이 중요합니다. 공부상 지목과 실제 이용이 다른 경우가 많습니다."))
    if it["mcls"] in ("주거용건물", "상가용및업무용건물") or it["bld"]: t.append(("임차인·점유 확인", "건물은 낙찰 후 임차인이 있으면 보증금 인수 여부와 명도 일정이 비용과 기간에 직접 영향을 줍니다. 공고문의 임차·점유 정보와 현장 상태를 함께 확인하세요."))
    if it["usbd"] >= 1: t.append(("유찰 %d회" % it["usbd"], "이전 회차에서 입찰자가 없어 유찰된 물건입니다. 유찰은 가격이 낮아졌다는 뜻이기도 하지만 물건에 부담 요소가 있어서일 수 있으니 이유를 먼저 확인하세요."))
    if it["evict"] and "매수" in it["evict"]: t.append(("명도 책임은 매수인", "이 물건은 낙찰 후 점유자 인도(명도)를 매수인이 책임지는 조건입니다. 명도 비용과 소요 기간을 입찰가에 반영하세요."))
    return t

def stats_for(it, active):
    peers = [x for x in active if x["sgg"] == it["sgg"] and x["mcls"] == it["mcls"] and x["ratio"] and x["id"] != it["id"]]
    return peers

def related(it, active, n=6):
    same_sgg = [x for x in active if x["sgg"] == it["sgg"] and x["id"] != it["id"] and x["state"] != "ended"]
    same_sgg.sort(key=lambda x: (x["mcls"] != it["mcls"], -len(x["photos"] or [])))
    out = same_sgg[:n]
    if len(out) < n:
        ids = {x["id"] for x in out} | {it["id"]}
        more = [x for x in active if x["sido"] == it["sido"] and x["mcls"] == it["mcls"] and x["id"] not in ids and x["state"] != "ended"]
        out += more[: n - len(out)]
    return out

def page_item(it, active):
    st, col = STATE[it["state"]]; path = "/item/%s/" % it["id"]
    w = where(it) or it["name"]; use = it["scls"] or it["mcls"] or "부동산"
    ap, mn, r = it["appraisal"], it["min"], it.get("ratio")
    # 사진 갤러리
    ph = it["photos"]
    if ph:
        thumbs = "".join('<a class="th" href="%s" target="_blank" rel="noopener nofollow">%s</a>' % (esc(u.replace("&downloadImageKind=THNL_NM", "")), '<img src="%s" alt="%s 사진 %d" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.remove()">' % (esc(u), esc(title_core(it)), i + 1)) for i, u in enumerate(ph[:14]))
        gal = '<div class="gallery"><div class="main">%s</div><div class="thumbs">%s</div><p class="cap">사진 %d장 · 출처 한국자산관리공사 온비드 (사진을 누르면 크게 열립니다)</p></div>' % (photo_tag(it, 0, full=True), thumbs, len(ph))
    else:
        gal = '<div class="gallery"><div class="main"><div class="ph noimg">등록된 사진이 없습니다</div></div></div>'
    e = pdt(it["bid_end"]); deposit = round(mn * 0.1) if mn else None
    price = ('<div class="price-box"><div><small>감정가</small><b>%s</b></div><div><small>최저입찰가</small><b class="red">%s</b>%s</div><div><small>입찰보증금(통상 10%%)</small><b>%s</b></div></div>'
             % (kor(ap) if ap else "비공개", kor(mn) if mn else "-", ("<em>감정가의 %.0f%%</em>" % r) if r else "", kor(deposit) if deposit else "-"))
    rows = [["물건관리번호", esc(it["id"])], ["소재지", esc(it["addr"])]]
    if it["road"]: rows.append(["도로명주소", esc(it["road"])])
    rows += [["용도", esc(" > ".join(x for x in (it["lcls"], it["mcls"], it["scls"]) if x))], ["재산 유형", esc(it["kind"] or "-") + ((" · " + esc(it["disp"])) if it["disp"] else "")]]
    if it["land"] or it["bld"]:
        rows.append(["면적", " / ".join(x for x in (("토지 %s㎡" % ("{:,.2f}".format(it["land"]).rstrip("0").rstrip("."))) if it["land"] else "", ("건물 %s㎡" % ("{:,.2f}".format(it["bld"]).rstrip("0").rstrip("."))) if it["bld"] else "") if x)])
    rows += [["입찰 기간", "%s ~ %s" % (dt(it["bid_begin"], "full"), dt(it["bid_end"], "full"))]]
    rows.append(["개찰", dt(it["open_dt"], "full") if it["open_dt"] else "입찰 마감 후 개찰 (정확한 시각은 온비드 공고 확인)"])
    rows += [["입찰 방식", " · ".join(x for x in (it["bid_div"], it["bid_method"], it["compete"], it["total_unit"]) if x) or "-"],
             ["공동·대리 입찰", " · ".join("%s %s" % (a, "가능" if v == "Y" else "불가") for a, v in (("공동입찰", it["flags"]["joint"]), ("2인 이상 공동", it["flags"]["twtm"]), ("대리입찰", it["flags"]["subst"])) if v) or "-"]]
    if it["evict"]: rows.append(["명도 책임", esc(it["evict"])])
    if it["fee_rate"]: rows.append(["수수료율", "%s%%" % it["fee_rate"]])
    if it["pb"]["name"]: rows.append(["공고", esc(it["pb"]["name"]) + ((" · " + esc(it["pb"]["branch"])) if it["pb"]["branch"] else "")])
    if it["rqst"]: rows.append(["위임기관", esc(it["rqst"])])
    rows.append(["최초 공고일", dt(it["first_pbanc"], "full")])
    info = table(None, rows)
    # 단가 지표
    metrics = []
    area = it["land"] or it["bld"]
    if ap and area and area > 0:
        metrics.append(["㎡당 감정가", kor(ap / area)]); metrics.append(["평당 감정가(1평=3.3058㎡)", kor(ap / area * 3.3058)])
        if mn: metrics.append(["평당 최저입찰가", kor(mn / area * 3.3058)])
    peers = stats_for(it, active)
    if r and len(peers) >= 3:
        avg = sum(x["ratio"] for x in peers) / len(peers)
        metrics.append(["같은 시군구 %s 진행 물건 평균 최저가율" % (it["mcls"] or "부동산"), "%.0f%% (%d건 기준, 이 물건 %.0f%%)" % (avg, len(peers), r)])
    metr = ('<h2 class="group-title">📐 가격 지표</h2>' + table(None, metrics)) if metrics else ""
    sq = ""
    if it["sqms"]: sq = '<h2 class="group-title">📏 면적 내역</h2>' + table(["구분", "면적", "비고"], [[esc(s["kind"]), esc(s["area"]), esc(s["note"])] for s in it["sqms"]])
    def para(h, t): return ('<h2 class="group-title">%s</h2><p class="lead">%s</p>' % (h, esc(t).replace("\n", "<br>"))) if t else ""
    text = para("📍 위치 및 부근 현황", it["loc_txt"]) + para("🏞️ 이용 현황", it["use_txt"])
    if it["note_txt"]: text += '<h2 class="group-title">⚠️ 유의사항 (공고문)</h2><div class="warn-box">%s</div>' % esc(it["note_txt"]).replace("\n", "<br>")
    text += para("ℹ️ 기타", it["etc_txt"]) + para("📋 입찰 조건", it["cond_txt"]) + para("🔎 참고", it["valid_txt"])
    appr = ""
    if it["appraisals"]:
        appr = '<h2 class="group-title">🧾 감정평가</h2>' + table(["평가일", "감정평가기관", "감정가", "평가서"], [[dt(a["ymd"], "full"), esc(a["org"] or "-"), kor(a["amt"]) if a["amt"] else "-", ('<a href="%s" target="_blank" rel="noopener nofollow">보기</a>' % esc(a["url"])) if a["url"] else "-"] for a in it["appraisals"][:4]], (2,))
    rt = ""
    if it["rights"] or it["dist"] or it["leases"] or it["occupants"]:
        rr = []
        if it["rights"]: rr.append(["등기사항(권리) 기재", "%d건" % len(it["rights"]), ", ".join(sorted({x["type"] for x in it["rights"] if x["type"]})) or "-"])
        if it["dist"]: rr.append(["배분요구·채권 신고", "%d건" % len(it["dist"]), ", ".join(sorted({x["type"] for x in it["dist"] if x["type"]})) or "-"])
        rr.append(["임차 정보", "%d건" % it["leases"], "임차인이 있으면 보증금 인수 여부 확인" if it["leases"] else "공개된 임차 정보 없음"])
        rr.append(["점유 관계", "%d건" % it["occupants"], "점유자가 있으면 명도 필요" if it["occupants"] else "공개된 점유 정보 없음"])
        rt = '<h2 class="group-title">⚖️ 권리 관계 요약</h2>' + table(["항목", "건수", "내용"], rr) + '<p class="note">온비드가 공개한 정보를 건수 위주로 요약했고 채권자·채무자 이름은 표시하지 않습니다. 낙찰자가 인수할 권리와 배당 순위는 반드시 등기부등본과 공고문 원문으로 확인하세요.</p>'
    tp = tips(it)
    tipbox = ('<h2 class="group-title">💡 이 물건에서 확인할 점</h2><ul class="tips">%s</ul>' % "".join("<li><b>%s</b> — %s</li>" % (esc(a), esc(b)) for a, b in tp)) if tp else ""
    rel = related(it, active); relh = ('<h2 class="group-title">🏘️ 같은 지역·용도의 다른 공매 물건</h2>' + grid(rel)) if rel else ""
    ended = '<div class="warn-box">이 물건은 입찰이 종료되었거나 온비드 공고 목록에서 확인되지 않습니다. 낙찰·유찰 결과는 온비드에서 확인하세요.</div>' if it["state"] == "ended" else ""
    kakao = "https://map.kakao.com/?q=" + urllib.parse.quote(it["addr"] or w)
    ctas = chips([("온비드에서 확인·입찰", "https://www.onbid.co.kr"), ("지도에서 위치 보기", kakao), ("%s 공매 물건 더 보기" % it["region"], "/region/%s/%s/" % (it["sido"], it["sgg"]) if it["sido"] and it["sgg"] else "/region/"), ("공매 입찰 가이드", "/guide/")])
    cta_note = '<p class="note">온비드 접속 후 상단 검색에서 물건관리번호 <b>%s</b> 로 이 물건을 찾을 수 있습니다. 우아공매는 입찰을 대행하지 않습니다.</p>' % esc(it["id"])
    lead = ("<p class=\"lead\"><b>%s</b> %s 공매 물건입니다. 감정가 <b>%s</b>%s%s 입찰은 %s부터 %s까지이며%s %s</p>") % (
        esc(w), esc(use), kor(ap) if ap else "비공개", (", 최저입찰가 <b>%s</b>(감정가의 %.0f%%)" % (kor(mn), r)) if mn and r else (", 최저입찰가 <b>%s</b>" % kor(mn) if mn else ""), "입니다." if True else "",
        dt(it["bid_begin"], "full"), dt(it["bid_end"], "full"), ((" 개찰은 %s입니다." % dt(it["open_dt"], "full")) if it["open_dt"] else ""),
        ("%d회 유찰된 물건입니다." % it["usbd"]) if it["usbd"] else "")
    ttl = "%s 공매 — 감정가 %s, 최저 %s%s" % (title_core(it), kor(ap) if ap else "비공개", kor(mn) if mn else "-", (" (%.0f%%)" % r) if r else "")
    desc = "%s 공매 물건. 감정가 %s, 최저입찰가 %s, 입찰 %s~%s. 사진 %d장·감정평가·권리 요약·입찰 시 확인할 점." % (title_core(it), kor(ap) if ap else "비공개", kor(mn) if mn else "-", dt(it["bid_begin"]), dt(it["bid_end"]), len(ph))
    body = f"""
<div class="page-head"><h1>{esc(w)} {esc(use)} 공매 — 최저 {kor(mn) if mn else '-'}</h1><p><span class="badge {col}">{st}{(' · ' + dday(it)) if dday(it) and it['state'] != 'ended' else ''}</span> {esc(it['kind'])} · {esc(it['mcls'] or '부동산')} · 물건관리번호 {esc(it['id'])}</p></div>
{ended}
{lead}
{gal}
{price}
{ad()}
<h2 class="group-title">📌 물건 정보</h2>
{info}
{metr}
{sq}
{text}
{tipbox}
{appr}
{rt}
{ctas}
{cta_note}
{relh}
<p class="note">데이터: 한국자산관리공사 온비드 공공데이터(최종 갱신 {dt(it['modified'], 'full') if it['modified'] else '-'}). 입찰 조건·가격은 정정공고로 바뀔 수 있으니 입찰 전 온비드 공고문을 반드시 확인하세요.</p>
"""
    faq = [(f"{w} {use} 공매 최저입찰가는 얼마인가요?", f"감정가 {kor(ap) if ap else '비공개'}에 대해 최저입찰가는 {kor(mn) if mn else '공고 참조'}입니다" + (f"(감정가의 {r:.0f}%)." if r else ".")),
           ("공매 입찰보증금은 얼마를 내나요?", "일반적으로 입찰금액의 10%%를 입찰보증금으로 납부합니다. 이 물건 최저입찰가 기준 약 %s이며 정확한 금액과 납부 방법은 공고문을 확인하세요." % (kor(deposit) if deposit else "공고 참조")),
           ("유찰되면 가격이 내려가나요?", "공고문에 정해진 방식에 따라 다음 회차에 최저입찰가가 낮아질 수 있습니다. 이 물건은 현재 %d회 유찰 상태이며 회차별 가격은 온비드 공고문에서 확인할 수 있습니다." % it["usbd"]),
           ("낙찰받으면 점유자를 내보내는 건 누구 책임인가요?", "공고 조건에 따라 다릅니다. " + ("이 물건은 명도 책임이 %s로 표시되어 있습니다." % it["evict"] if it["evict"] else "명도 책임은 공고문의 유의사항을 확인하세요."))]
    write(path, layout(path, ttl, desc, body, faq, [("홈", "/"), ("공매 물건", "/item/"), (it["sido"] or "전국", "/region/%s/" % it["sido"] if it["sido"] else "/region/"), (it["sgg"] or "-", "/region/%s/%s/" % (it["sido"], it["sgg"]) if it["sgg"] else "/region/"), ("물건", path)], noindex=(it["state"] == "ended")),
          "0.6" if it["state"] != "ended" else "0.2", sitemap=(it["state"] != "ended"))

# ───────────────────────── 지역·용도·달력 ─────────────────────────
def avg_ratio(its):
    r = [x["ratio"] for x in its if x["ratio"]]
    return sum(r) / len(r) if r else None

def usage_mix(its):
    c = collections.Counter(x["mcls"] or "기타" for x in its); return c.most_common()

def page_region_sgg(sido, sgg, its):
    path = "/region/%s/%s/" % (sido, sgg)
    its = sorted(its, key=lambda x: (x["bid_end"] or "9"))
    ar = avg_ratio(its); mix = usage_mix(its)
    shown = its[:60]
    body = f"""
<div class="page-head"><h1>{esc(sido)} {esc(sgg)} 공매 물건 — 진행 중 {len(its)}건</h1><p>사진·감정가·최저입찰가·입찰 마감일 · 한국자산관리공사 온비드</p></div>
<p class="lead"><b>{esc(sido)} {esc(sgg)}</b>에서 입찰 중이거나 입찰 예정인 공매 부동산은 현재 <b>{len(its)}건</b>입니다. 용도는 {esc(', '.join('%s %d건' % (a, b) for a, b in mix[:4]))} 순이며{(' 평균 최저입찰가율은 감정가의 %.0f%%입니다.' % ar) if ar else '.'} 물건을 누르면 사진과 감정평가, 권리 요약, 입찰 시 확인할 점을 볼 수 있습니다.</p>
{ad()}
{grid(shown)}
{('<p class="note">상위 60건만 표시했습니다. 전체는 용도별 페이지에서 확인하세요.</p>' if len(its) > 60 else '')}
{chips([(esc(sido) + " 전체", "/region/%s/" % sido), ("지역별 공매", "/region/"), ("공매 입찰 가이드", "/guide/")])}
"""
    faq = [(f"{sido} {sgg} 공매 물건은 몇 건인가요?", f"현재 입찰 중·예정인 부동산 공매가 {len(its)}건입니다(매일 갱신)."), ("공매 물건은 어디서 입찰하나요?", "한국자산관리공사 온비드(onbid.co.kr)에서 전자입찰로 진행합니다. 우아공매는 정보 제공만 합니다.")]
    write(path, layout(path, f"{sido} {sgg} 공매 물건 {len(its)}건 — 감정가·최저입찰가·사진", f"{sido} {sgg} 온비드 공매 부동산 {len(its)}건의 사진·감정가·최저입찰가·입찰 마감일을 매일 갱신해 정리했습니다.", body, faq,
                       [("홈", "/"), ("지역별", "/region/"), (sido, "/region/%s/" % sido), (sgg, path)]), "0.7")

def page_region_sido(sido, its, by_sgg):
    path = "/region/%s/" % sido
    its_sorted = sorted(its, key=lambda x: (x["bid_end"] or "9"))
    mix = usage_mix(its); ar = avg_ratio(its)
    sg_rows = [['<a href="%s">%s</a>' % (q("/region/%s/%s/" % (sido, sg)), esc(sg)), "%d건" % len(l), ("%.0f%%" % avg_ratio(l)) if avg_ratio(l) else "-"] for sg, l in sorted(by_sgg.items(), key=lambda t: -len(t[1]))]
    body = f"""
<div class="page-head"><h1>{esc(sido)} 공매 물건 — 진행 중 {len(its)}건</h1><p>시군구별 현황 · 곧 마감되는 물건</p></div>
<p class="lead"><b>{esc(sido)}</b>의 온비드 공매 부동산은 현재 입찰 중·예정 <b>{len(its)}건</b>이며 {esc(', '.join('%s %d건' % (a, b) for a, b in mix[:4]))} 순입니다.{(' 평균 최저입찰가율은 감정가의 %.0f%%입니다.' % ar) if ar else ''} 시군구를 눌러 물건 목록을 확인하세요.</p>
{ad()}
<h2 class="group-title">🗺️ 시군구별 물건</h2>
{table(['시군구', '진행 물건', '평균 최저가율'], sg_rows, (1, 2))}
<h2 class="group-title">⏰ 곧 마감되는 물건</h2>
{grid(its_sorted[:12])}
{chips([("지역별 공매", "/region/"), ("공매 입찰 가이드", "/guide/")])}
"""
    faq = [(f"{sido} 공매 부동산은 몇 건인가요?", f"입찰 중·예정 {len(its)}건입니다(매일 갱신).")]
    write(path, layout(path, f"{sido} 공매 부동산 {len(its)}건 — 시군구별 감정가·최저입찰가", f"{sido} 온비드 공매 부동산 {len(its)}건. 시군구별 물건 수와 평균 최저가율, 곧 마감되는 물건을 사진과 함께 정리했습니다.", body, faq,
                       [("홈", "/"), ("지역별", "/region/"), (sido, path)]), "0.8")

def page_region_hub(by_sido):
    rows = [['<a href="%s">%s</a>' % (q("/region/%s/" % s), esc(s)), "%d건" % len(l), ("%.0f%%" % avg_ratio(l)) if avg_ratio(l) else "-"] for s, l in sorted(by_sido.items(), key=lambda t: -len(t[1]))]
    total = sum(len(l) for l in by_sido.values())
    body = f"""
<div class="page-head"><h1>지역별 공매 부동산 — 시도·시군구별 {total}건</h1><p>온비드 입찰 중·예정 물건을 지역별로 확인</p></div>
<p class="lead">한국자산관리공사 온비드에서 입찰 중이거나 예정인 공매 부동산 <b>{total}건</b>을 시도별로 정리했습니다. 지역을 누르면 시군구별 물건과 사진을 볼 수 있습니다.</p>
{ad()}
{table(['시도', '진행 물건', '평균 최저가율'], rows, (1, 2))}
{chips([("공매 입찰 가이드", "/guide/"), ("이번 주 개찰", "/calendar/")])}
"""
    write("/region/", layout("/region/", f"지역별 공매 부동산 {total}건 — 시도·시군구별 온비드 물건", f"전국 온비드 공매 부동산 {total}건을 시도·시군구별로 정리. 사진, 감정가, 최저입찰가, 입찰 마감일을 매일 갱신합니다.", body, [("지역별 공매 물건은 어떻게 찾나요?", "시도를 고른 뒤 시군구 페이지에서 사진과 가격을 확인하세요.")], [("홈", "/"), ("지역별", "/region/")], coupang=True), "0.9")

def page_usage(mcls, its):
    path = "/usage/%s/" % mcls
    its = sorted(its, key=lambda x: (x["bid_end"] or "9"))
    body = f"""
<div class="page-head"><h1>{esc(mcls)} 공매 물건 — 진행 중 {len(its)}건</h1><p>용도별 온비드 공매 부동산</p></div>
<p class="lead">입찰 중·예정인 <b>{esc(mcls)}</b> 공매 물건은 <b>{len(its)}건</b>입니다.{(' 평균 최저입찰가율은 감정가의 %.0f%%입니다.' % avg_ratio(its)) if avg_ratio(its) else ''}</p>
{ad()}
{grid(its[:60])}
{chips([("지역별 공매", "/region/"), ("공매 입찰 가이드", "/guide/")])}
"""
    write(path, layout(path, f"{mcls} 공매 물건 {len(its)}건 — 감정가·최저입찰가·사진", f"온비드 {mcls} 공매 {len(its)}건. 감정가와 최저입찰가, 입찰 마감일을 사진과 함께 매일 갱신합니다.", body, None, [("홈", "/"), ("공매 물건", "/item/"), (mcls, path)]), "0.7")

def page_calendar(active):
    days = collections.defaultdict(list)
    for it in active:
        o = pdt(it["open_dt"]) or pdt(it["bid_end"])
        if o and TODAY.date() <= o.date() <= (TODAY + datetime.timedelta(days=14)).date(): days[o.date()].append(it)
    secs = ""
    for d in sorted(days):
        l = sorted(days[d], key=lambda x: x["open_dt"] or x["bid_end"] or "")
        secs += '<h2 class="group-title">📅 %d월 %d일 (%s) · %d건</h2>%s' % (d.month, d.day, "월화수목금토일"[d.weekday()], len(l), grid(l[:12]))
    body = f"""
<div class="page-head"><h1>이번 주·다음 주 공매 개찰 일정</h1><p>온비드 공매 부동산 개찰·입찰 마감일별 물건</p></div>
<p class="lead">앞으로 14일 안에 개찰하거나 입찰이 마감되는 공매 부동산을 날짜별로 모았습니다. 마감 직전에는 정정공고가 나올 수 있으니 입찰 전 온비드에서 다시 확인하세요.</p>
{ad()}
{secs or '<p class="lead">표시할 일정이 없습니다.</p>'}
{chips([("지역별 공매", "/region/"), ("공매 입찰 가이드", "/guide/")])}
"""
    write("/calendar/", layout("/calendar/", "이번 주 공매 개찰 일정 — 온비드 부동산 마감 임박 물건", "앞으로 14일 안에 개찰·마감되는 온비드 공매 부동산을 날짜별로 사진과 함께 정리했습니다. 매일 갱신.", body, None, [("홈", "/"), ("이번 주 개찰", "/calendar/")]), "0.8")

def page_item_hub(active):
    op = [x for x in active if x["state"] != "ended"]
    soon = sorted(op, key=lambda x: x["bid_end"] or "9")[:12]
    cheap = sorted([x for x in op if x["ratio"]], key=lambda x: x["ratio"])[:12]
    photo = sorted(op, key=lambda x: -len(x["photos"]))[:12]
    mc = collections.Counter(x["mcls"] or "기타" for x in op)
    body = f"""
<div class="page-head"><h1>온비드 공매 부동산 — 진행 중 {len(op):,}건</h1><p>한국자산관리공사 공매 물건을 사진과 함께 · 매일 갱신</p></div>
<p class="lead">입찰 중이거나 예정인 공매 부동산 <b>{len(op):,}건</b>을 지역·용도별로 정리했습니다. 각 물건 페이지에서 사진, 감정가, 최저입찰가, 감정평가, 권리 요약, 입찰 시 확인할 점을 볼 수 있습니다.</p>
{ad()}
<h2 class="group-title">⏰ 곧 마감되는 물건</h2>{grid(soon)}
<h2 class="group-title">💸 감정가 대비 최저가율이 낮은 물건</h2>{grid(cheap)}
<h2 class="group-title">📷 사진이 많은 물건</h2>{grid(photo)}
{chips([("%s %d건" % (a, b), "/usage/%s/" % a) for a, b in mc.most_common()] + [("지역별", "/region/"), ("이번 주 개찰", "/calendar/")])}
"""
    write("/item/", layout("/item/", f"온비드 공매 부동산 {len(op):,}건 — 사진·감정가·최저입찰가", f"입찰 중·예정 온비드 공매 부동산 {len(op):,}건. 곧 마감, 최저가율 낮은 순, 사진 많은 물건을 매일 갱신해 보여드립니다.", body, None, [("홈", "/"), ("공매 물건", "/item/")], coupang=True), "0.9")

def page_home(active, meta):
    op = [x for x in active if x["state"] != "ended"]
    soon = sorted(op, key=lambda x: x["bid_end"] or "9")[:8]
    new = sorted(op, key=lambda x: x["first_pbanc"] or "", reverse=True)[:8]
    by_sido = collections.Counter(x["sido"] for x in op if x["sido"])
    body = f"""
<div class="hero"><h1>🔨 우아공매 — 온비드 공매 부동산을 사진과 함께</h1><p>입찰 중·예정 {len(op):,}건 · 감정가·최저입찰가·낙찰가율 · 매일 갱신</p></div>
<div class="tool-box"><div class="tool-row"><div style="flex:1;min-width:220px"><label for="q">지역·주소·용도로 검색</label><input id="q" type="search" placeholder="예) 평택 임야, 강남 아파트, 상가" style="width:100%"></div></div><div id="res" class="item-grid"></div></div>
{ad()}
<h2 class="group-title">⏰ 곧 마감되는 물건</h2>{grid(soon)}
<h2 class="group-title">🆕 새로 올라온 물건</h2>{grid(new)}
<h2 class="group-title">🗺️ 지역별 공매</h2>{chips([("%s %d건" % (s, n), "/region/%s/" % s) for s, n in by_sido.most_common()])}
{chips([("이번 주 개찰", "/calendar/"), ("공매 입찰 가이드", "/guide/"), ("용어 사전", "/guide/glossary/")])}
<p class="lead">우아공매는 한국자산관리공사(KAMCO) 온비드의 공공데이터를 바탕으로 공매 부동산의 사진, 감정가, 최저입찰가, 입찰 일정, 권리 요약을 보기 쉽게 정리한 사이트입니다. 입찰은 온비드에서만 가능하며 우아공매는 입찰 대행이나 투자 권유를 하지 않습니다.</p>
<script src="/assets/js/search.js"></script>
"""
    faq = [("공매와 경매는 무엇이 다른가요?", "공매는 한국자산관리공사 온비드에서 전자입찰로 진행하고, 경매는 법원이 진행합니다. 우아공매는 온비드 공매 물건을 다룹니다."), ("입찰은 어디서 하나요?", "온비드(onbid.co.kr)에서 회원 가입 후 전자입찰로 합니다.")]
    write("/", layout("/", "우아공매 — 온비드 공매 부동산 사진·감정가·최저입찰가 (매일 갱신)", f"한국자산관리공사 온비드 공매 부동산 {len(op):,}건의 사진, 감정가, 최저입찰가, 입찰 일정을 지역·용도별로 매일 갱신해 보여드립니다.", body, faq), "1.0")

def search_index(active):
    rows = [[it["id"], where(it) or it["name"][:30], it["mcls"] or "", it["scls"] or "", it["min"] or 0, it["appraisal"] or 0, (it["photos"][0] if it["photos"] else "")] for it in active if it["state"] != "ended"]
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / "search_index.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

def page_guides():
    for slug, g in guides.GUIDES.items():
        path = "/guide/%s/" % slug if slug else "/guide/"
        write(path, layout(path, g["title"], g["desc"], g["body"](ad()), g["faq"], [("홈", "/"), ("공매 가이드", "/guide/")] + ([(g["short"], path)] if slug else [])), "0.7" if slug else "0.8")

def page_about_privacy():
    write("/privacy/", layout("/privacy/", "개인정보처리방침", "우아공매 개인정보처리방침", '<div class="page-head"><h1>개인정보처리방침</h1></div><p class="lead">우아공매(wooagongmae.wooahouse.com)는 회원가입을 요구하지 않으며 이용자의 개인정보를 직접 수집하지 않습니다. 방문자 통계를 위해 Google Analytics를, 광고를 위해 Google AdSense와 쿠팡 파트너스를 사용하며 이들은 쿠키를 사용할 수 있습니다. 쿠키는 브라우저 설정에서 비활성화할 수 있습니다. 문의: <a href="mailto:ingmaster83@gmail.com">ingmaster83@gmail.com</a></p><p class="note">최종 수정일: 2026년 11월 8일</p>', None, [("홈", "/"), ("개인정보처리방침", "/privacy/")]), sitemap=False)

def main():
    t0 = time.time()
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "assets", OUT / "assets", dirs_exist_ok=True)
    for nf in ROOT.glob("naver*.html"): shutil.copy(nf, OUT / nf.name)
    meta, items = load()
    active = items
    by_region = collections.defaultdict(lambda: collections.defaultdict(list))
    by_usage = collections.defaultdict(list)
    for it in items:
        if it["state"] != "ended" and it["sido"]:
            by_region[it["sido"]][it["sgg"] or "기타"].append(it)
        if it["state"] != "ended": by_usage[it["mcls"] or "기타"].append(it)
    for it in items: page_item(it, active)
    for sido, d in by_region.items():
        sidolist = [x for l in d.values() for x in l]
        page_region_sido(sido, sidolist, d)
        for sgg, l in d.items(): page_region_sgg(sido, sgg, l)
    page_region_hub({s: [x for l in d.values() for x in l] for s, d in by_region.items()})
    for m, l in by_usage.items(): page_usage(m, l)
    page_calendar([x for x in items if x["state"] != "ended"]); page_item_hub(items); page_home(items, meta); page_guides(); page_about_privacy()
    search_index(items)
    today = TODAY.strftime("%Y-%m-%d")
    urls = [(p, pr) for p, pr in WRITTEN]
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
    print("pages", len(WRITTEN), "items", len(items), "elapsed", round(time.time() - t0, 1), "s")

if __name__ == "__main__":
    main()
