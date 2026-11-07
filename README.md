# 우아공매 (wooagongmae.wooahouse.com)
한국자산관리공사 온비드 공매 부동산을 사진·감정가·최저입찰가·권리 요약과 함께 보여주는 정적 사이트. 매일 갱신 목표.
- 데이터: 공공데이터포털 '차세대 온비드' 오픈API(B010003). 클라이언트 `scripts/onbid_api.py`(키는 환경변수 DATA_GO_KR_API_KEY, 로컬은 ../hosppass/.env 폴백), 정규화 `scripts/normalize.py`, 생성 `scripts/build_site.py`(입력 data/items.json), 가이드 `scripts/guides.py`.
- 오퍼레이션 이름은 끝에 2가 붙음(getPbancList2 등). numOfRows 2000까지 가능. 개발계정은 API당 일 1,000건 → 목록·통계는 대량 호출, 상세(15157247)는 물건당 1건.
- 사진은 온비드 원본 URL 직접 연결(THNL_NM=178x134 썸네일, 파라미터 제거 시 원본). 응답이 octet-stream+nosniff지만 <img>로 정상 표시됨(2026-11-08 확인). referrerpolicy=no-referrer.
- 페이지 ID는 물건관리번호(cltrMngNo). 회차별 공매조건번호(pbctCdtnNo)는 최신 값만 보관. 공고(onbidPbancNo) 목록의 개찰일은 첫 회차 것이라 회차(pbctNo)가 같을 때만 사용.
- 신청 필요 API: 15157216·15157220·15157247·15157252(+251·254·218·233·248·232·245) 승인됨 / 15157207(부동산 물건목록)·15157756·15157757(지역·용도별 입찰통계)·15157704·15157709·15157699(순위)·15157768(코드·주소) 신청 필요.
