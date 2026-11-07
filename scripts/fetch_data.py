# -*- coding: utf-8 -*-
"""우아공매 일일 수집: 부동산 물건목록 → 회차 묶기 → 저장소(store/) 갱신 → 상세 보강(일 예산) → 통계·순위.
사용: python scripts/fetch_data.py [--detail-budget 900] [--stats-months 13] [--skip-list]
store/items.json.gz {items:{id:item}, meta}   store/stats.json   store/ranks.json   (Actions에서는 data 브랜치에 보관)"""
import argparse, collections, concurrent.futures, datetime, gzip, json, pathlib, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onbid_api as O
from normalize import norm_list, merge_detail

ROOT = pathlib.Path(__file__).resolve().parent.parent
STORE = ROOT / "store"; STORE.mkdir(exist_ok=True)
KST = datetime.timezone(datetime.timedelta(hours=9))
PRPT = ["0002", "0004", "0005", "0007", "0010", "0013"]        # 공유·불용품·기타일반·압류·국유·파산
KEEP_ENDED_DAYS = 90
DETAIL_THREADS = 4

def now_kst(): return datetime.datetime.now(KST).replace(tzinfo=None)

def load_store():
    p = STORE / "items.json.gz"
    if p.exists(): return json.loads(gzip.open(p, "rt", encoding="utf-8").read())
    return {"meta": {}, "items": {}}

def save_store(st):
    with gzip.open(STORE / "items.json.gz", "wt", encoding="utf-8", compresslevel=6) as f:
        json.dump(st, f, ensure_ascii=False, separators=(",", ":"))

T0 = time.time()

def fetch_list():
    rows = []
    for pr in PRPT:
        for pv in ("N", "Y"):
            got = O.fetch_all("rlst_list", per=2000, prptDivCd=pr, pvctTrgtYn=pv)
            rows += got; print("  list", pr, pv, len(got), "(%.0f초)" % (time.time() - T0), flush=True)
    return rows

LIST_FIELDS = ("cond", "min", "usbd", "bid_begin", "bid_end", "status", "status_nm", "ratio", "appraisal", "rounds", "nego", "modified", "land", "bld", "evict", "rent", "rent_period", "flags", "name")
BASE_FIELDS = ("addr", "sido", "sgg", "emd", "lcls", "mcls", "scls", "kind", "disp", "org", "rqst", "bid_method", "compete", "bid_div", "total_unit", "fee_rate", "pnu")

def update_items(st, rows, now):
    now_iso = now.strftime("%Y-%m-%dT%H:%M"); today = now.strftime("%Y-%m-%d")
    by = collections.defaultdict(list)
    for r in rows: by[r["cltrMngNo"]].append(r)
    items = st["items"]; new = upd = 0
    for mng, rs in by.items():
        fresh = norm_list(rs, now_iso); old = items.get(mng)
        if old is None:
            fresh["first_seen"] = today; fresh["last_seen"] = today; items[mng] = fresh; new += 1
            continue
        for k in LIST_FIELDS: old[k] = fresh[k]
        if not old.get("detail"):                      # 상세 보강 전에는 목록 값으로 기본 필드 유지
            for k in BASE_FIELDS: old[k] = fresh[k]
            old["thumb"] = fresh["thumb"]; old["photos"] = old.get("photos") or fresh["photos"]
        old["last_seen"] = today; old.pop("ended_on", None); upd += 1
    gone = 0
    for mng, it in items.items():
        if mng not in by and not it.get("ended_on"): it["ended_on"] = today; gone += 1
    cutoff = (now - datetime.timedelta(days=KEEP_ENDED_DAYS)).strftime("%Y-%m-%d")
    drop = [m for m, it in items.items() if it.get("ended_on") and it["ended_on"] < cutoff]
    for m in drop: del items[m]
    print("  물건 신규 %d / 갱신 %d / 신규 종료 %d / %d일 경과 삭제 %d / 총 %d" % (new, upd, gone, KEEP_ENDED_DAYS, len(drop), len(items)))

def enrich(st, budget, now):
    if budget <= 0: return
    now_iso = now.strftime("%Y-%m-%dT%H:%M")
    live = [it for it in st["items"].values() if not it.get("ended_on")]
    def prio(it):
        act = 0 if it["bid_end"] >= now_iso else 1               # 입찰 중·예정 먼저, 마감 임박 순
        return (act, it["bid_end"] if act == 0 else "", -len(it["rounds"]))
    todo = sorted([it for it in live if not it["detail"] and it.get("detail_miss", 0) < 3], key=prio)
    todo += [it for it in live if it["detail"] and it.get("modified") and it["modified"] > it.get("detail_mdfcn", "")]   # 변경분 재보강은 맨 뒤
    done = miss = fail = 0
    batch = todo[:budget]
    t0 = time.time()
    def one(it):
        try: return it, O.call("rlst_detail", cltrMngNo=it["id"], pbctCdtnNo=it["cond"])[0], None
        except O.ApiError as e: return it, None, e
    stop = False
    with concurrent.futures.ThreadPoolExecutor(DETAIL_THREADS) as ex:
        for n, (it, rs, err) in enumerate(ex.map(one, batch), 1):
            if err is not None:
                fail += 1
                if "승인" in str(err) or fail > 20:
                    print("  상세 중단:", err, flush=True); stop = True
            elif not rs:
                miss += 1; it["detail_miss"] = it.get("detail_miss", 0) + 1
            else:
                merged = merge_detail(it, rs[0]); merged["detail_mdfcn"] = it.get("modified", ""); st["items"][it["id"]] = merged; done += 1
            if n % 100 == 0: print("  ... 상세 %d/%d (%.0f초)" % (n, len(batch), time.time() - t0), flush=True)
            if stop: break
    print("  상세 보강 %d건 (데이터 없음 %d, 오류 %d, 대기 %d건, %.0f초)" % (done, miss, fail, max(0, len(todo) - done - miss - fail), time.time() - t0), flush=True)

STAT_REGION = {"0021": "압류재산", "0024": "국유재산", "0025": "수탁·유입자산", "0026": "공유재산"}
STAT_USAGE = {"0041": "압류재산", "0044": "국유재산", "0045": "수탁·유입자산", "0046": "공유재산"}

def months_back(now, n):
    y, m = now.year, now.month; out = []
    for _ in range(n):
        m -= 1
        if m == 0: y, m = y - 1, 12
        out.append("%04d%02d" % (y, m))
    return out

def fetch_stats(now, n):
    p = STORE / "stats.json"
    s = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"region": {}, "usage": {}}
    months = months_back(now, n)
    for kind, codes, op in (("region", STAT_REGION, "stats_region"), ("usage", STAT_USAGE, "stats_usage")):
        for code in codes:
            for i, mth in enumerate(months):
                if s[kind].get(code, {}).get(mth) is not None and i >= 2: continue      # 최근 2개월만 매번 새로 받음
                try: rows, _ = O.call(op, numOfRows=200, statsTypeCd=code, inqPerd=mth)
                except O.ApiError as e: print("  통계 오류", kind, code, mth, e); continue
                s[kind].setdefault(code, {})[mth] = rows
    p.write_text(json.dumps(s, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("  통계 저장 (지역 %d유형, 용도 %d유형, 최근 %d개월)" % (len(s["region"]), len(s["usage"]), n))

def fetch_ranks():
    out = {}
    for name in ("rank_views", "rank_decr", "rank_fav"):
        try: out[name], _ = O.call(name, numOfRows=50, cltrDivNm="부동산")
        except O.ApiError as e: print("  순위 오류", name, e); out[name] = []
    (STORE / "ranks.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("  순위", {k: len(v) for k, v in out.items()})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail-budget", type=int, default=900); ap.add_argument("--stats-months", type=int, default=13); ap.add_argument("--skip-list", action="store_true")
    a = ap.parse_args()
    now = now_kst(); t0 = time.time(); st = load_store()
    if not a.skip_list:
        print("1) 물건 목록"); update_items(st, fetch_list(), now)
    print("2) 상세 보강"); enrich(st, a.detail_budget, now)
    st["meta"] = {"updated": now.strftime("%Y-%m-%dT%H:%M"), "items": len(st["items"])}
    save_store(st)
    print("3) 통계"); fetch_stats(now, a.stats_months)
    print("4) 순위"); fetch_ranks()
    print("완료 %.0f초" % (time.time() - t0))

if __name__ == "__main__":
    main()
