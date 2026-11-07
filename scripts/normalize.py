# -*- coding: utf-8 -*-
"""온비드 부동산 물건상세(15157247)·목록 응답 → 사이트용 간결한 item dict. 페이지 주소의 ID는 물건관리번호(cltrMngNo)로 고정한다
(회차마다 바뀌는 공매조건번호 pbctCdtnNo 는 최신 회차 값을 item 안에 보관)."""
import json, re, datetime

def num(x):
    if x in (None, "", "None", "-"): return None
    try: return int(float(str(x).replace(",", "")))
    except ValueError: return None

def flt(x):
    try: return float(str(x).replace(",", ""))
    except (TypeError, ValueError): return None

def jl(x):
    """목록형 필드가 문자열(JSON)로 오는 경우까지 리스트로"""
    if isinstance(x, list): return x
    if isinstance(x, str) and x.strip().startswith("["):
        try: return json.loads(x)
        except ValueError: return []
    return []

def txt(x):
    if x in (None, "None", "-", "null"): return ""
    return re.sub(r"[ \t]+", " ", str(x)).strip()

def iso(s):
    """'202611091400' → '2026-11-09T14:00', '20261109' → '2026-11-09'"""
    s = txt(s)
    if len(s) >= 12: return "%s-%s-%sT%s:%s" % (s[:4], s[4:6], s[6:8], s[8:10], s[10:12])
    if len(s) >= 8: return "%s-%s-%s" % (s[:4], s[4:6], s[6:8])
    return ""

def norm_detail(d, pb=None, row=None):
    """d: getRlstDtlInf2 한 건, pb: 공고 dict(선택), row: 목록/공고물건 한 줄(선택)"""
    pb = pb or {}; row = row or {}
    # 공고/목록 행은 같은 공고(onbidPbancNo)·같은 회차(pbctCdtnNo)일 때만 신뢰한다 — 개찰일·공고명이 다른 회차 것으로 섞이는 것을 막는다.
    if pb and txt(pb.get("onbidPbancNo")) and txt(pb.get("onbidPbancNo")) != txt(d.get("onbidPbancNo")): pb = {}
    if row and txt(row.get("pbctCdtnNo")) and txt(row.get("pbctCdtnNo")) != txt(d.get("pbctCdtnNo")): row = {}
    photos = [p.get("urlAdr") for p in jl(d.get("potoUrlList")) if p.get("urlAdr")]
    appr = [{"ymd": iso(a.get("apslEvlYmd")), "org": txt(a.get("apslEvlOrgNm")), "amt": num(a.get("apslEvlAmt")), "url": a.get("urlAdr") or ""}
            for a in jl(d.get("apslEvlClgList"))]
    rights = [{"type": txt(r.get("irstDivNm")), "ymd": iso(r.get("rgstYmd")), "amt": num(r.get("inprStngAmt"))} for r in jl(d.get("rgstPrmrInfList"))]
    dist = [{"type": txt(r.get("rgtRelCdNm")), "ymd": iso(r.get("stngYmd")), "amt": num(r.get("bondDclrStngAmt"))} for r in jl(d.get("dtbtRqrMtrsList"))]
    sq = [{"kind": txt(s.get("clandCont")), "area": txt(s.get("sqmsCont")), "note": txt(s.get("dtlCltrNm"))} for s in jl(d.get("sqmsList"))]
    low = num(d.get("lowstBidPrcIndctCont"))
    it = {
        "id": txt(d.get("cltrMngNo")),
        "cond": txt(d.get("pbctCdtnNo")),
        "name": txt(d.get("onbidCltrNm")),
        "addr": txt(d.get("zadrNm")) or txt(d.get("onbidCltrNm")),
        "road": txt(d.get("cltrRadr")),
        "sido": txt(d.get("lctnSdnm")), "sgg": txt(d.get("lctnSggnm")), "emd": txt(d.get("lctnEmdNm")),
        "lcls": txt(d.get("cltrUsgLclsCtgrNm")), "mcls": txt(d.get("cltrUsgMclsCtgrNm")), "scls": txt(d.get("cltrUsgSclsCtgrNm")),
        "kind": txt(d.get("prptDivNm")), "disp": txt(d.get("dspsMthodNm")), "org": txt(d.get("orgNm")), "rqst": txt(d.get("rqstOrgNm")),
        "bid_method": txt(d.get("bidMthodNm")), "compete": txt(d.get("cptnMthodNm")), "bid_div": txt(d.get("bidDivNm")), "total_unit": txt(d.get("totalamtUnpcDivNm")),
        "land": flt(d.get("landSqms")), "bld": flt(d.get("bldSqms")), "sqms": sq,
        "appraisal": num(d.get("apslEvlAmt")), "min": low, "first_bid": num(d.get("frstBidPrc")),
        "usbd": num(d.get("usbdNft")) or 0, "prgn": num(d.get("bidPrgnNft")) or 0,
        "bid_begin": iso(d.get("cltrBidBgngDt")), "bid_end": iso(d.get("cltrBidEndDt")),
        "open_dt": iso(row.get("cltrOpbdDt")) or (iso(pb.get("cltrOpbdDt")) if txt(pb.get("pbctNo")) == txt(d.get("pbctNo")) else ""),   # 공고 목록의 개찰일은 첫 회차 것이라 회차(pbctNo)가 같을 때만
        "status": txt(d.get("pbctStatCd")),
        "fee_rate": flt(d.get("feeRate")),
        "flags": {"joint": txt(d.get("collbBidPsblYn")), "twtm": txt(d.get("twtmGthrBidPsblYn")), "subst": txt(d.get("subtBidPsblYn")), "elec_grp": txt(d.get("eltrGrprUseYn")), "batch": txt(d.get("batcBidYn")), "share": txt(d.get("pvctTrgtYn"))},
        "evict": txt(d.get("evcRsbyTrgtCont")),
        "loc_txt": txt(d.get("locVntyPscdCont")), "use_txt": txt(d.get("utlzPscdCont")), "note_txt": txt(d.get("pytnMtrsCont")),
        "etc_txt": txt(d.get("cltrEtcCont")), "cond_txt": txt(d.get("icdlCdtnCont")), "valid_txt": txt(d.get("dsplVldCont")), "qual_txt": txt(d.get("purrQlfcCont")),
        "photos": photos,
        "photo360": [p.get("urlAdr") for p in jl(d.get("poto360DgrUrlList")) if isinstance(p, dict) and p.get("urlAdr")],
        "appraisals": appr, "rights": rights, "dist": dist,
        "leases": len(jl(d.get("leasInfList"))), "occupants": len(jl(d.get("ocpyRelList"))),
        "first_pbanc": iso(d.get("frstPbancYmd")), "modified": iso(d.get("mdfcnDt")),
        "pb": {"no": txt(pb.get("pbancMngNo") or d.get("pbctNo")), "name": txt(pb.get("onbidPbancNm")), "branch": txt(pb.get("rspbSbrNm")), "ymd": iso(pb.get("pbancYmd"))},
        "pnu": txt(d.get("ltnoPnu")),
    }
    # 입찰금액이 텍스트가 아니면 최저가율
    it["ratio"] = round(it["min"] / it["appraisal"] * 100, 1) if it["min"] and it["appraisal"] else None
    return it
