// 유튜브 스튜디오 동영상 세부정보 화면(studio.youtube.com/video/<ID>/edit)에서 실행
// 제품이 이미 태그돼 있으면 그대로 두고, 없으면 ‘최근 태그된 제품’ 4개를 태그하고 저장합니다.
// 결과: { 상태: '이미있음' | '완료' | '실패', 개수, 이유 }
// 탭이 화면에 떠 있어야 제품 창이 열립니다 (숨은 탭에서는 안 열림)
(async () => {
  const 쉬기 = (ms) => new Promise((r) => setTimeout(r, ms));
  const 기다리기 = async (찾기, 초 = 20) => {
    for (let i = 0; i < 초 * 4; i++) { const x = 찾기(); if (x) return x; await 쉬기(250); }
    return null;
  };
  if (document.body.innerText.includes('권한이 없습니다')) return { 상태: '실패', 이유: '이 계정으로는 이 영상을 볼 수 없어요 (authuser 확인)' };
  const 접이 = await 기다리기(() => document.querySelector('#shopping-toolbar-collapse'));
  if (!접이) return { 상태: '실패', 이유: '제품 칸을 못 찾았어요 (화면이 덜 열렸거나 스튜디오 화면이 바뀜)' };
  const 지금 = () => (document.querySelector('[aria-label*="태그된 제품"]') || {}).getAttribute?.('aria-label') || '';
  const 있음 = 지금().match(/태그된 제품 (\d+)개/);
  if (있음 && +있음[1] >= 4) return { 상태: '이미있음', 개수: +있음[1] };

  접이.opened = true; 접이.show && 접이.show();
  await 쉬기(800);
  const 수정 = document.querySelector('[aria-label="제품 수정"]');
  if (!수정) return { 상태: '실패', 이유: '‘제품 수정’ 버튼이 없어요 (쇼핑 자격 확인)' };
  수정.scrollIntoView({ block: 'center' });
  await 쉬기(400);
  수정.click();
  const 창 = await 기다리기(() => [...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog')].find((d) => d.innerText.includes('제품 태그하기') && d.querySelector('ytcp-icon-button[aria-label="태그"]')));
  if (!창) {
    if ([...document.querySelectorAll('tp-yt-paper-dialog, ytcp-dialog')].some((d) => d.innerText.includes('본인 인증'))) return { 상태: '실패', 이유: '구글 본인 인증을 요구해요' };
    return { 상태: '실패', 이유: '제품 창이 안 열렸어요 (탭이 화면 앞에 있어야 해요)' };
  }
  const 더하기 = [...창.querySelectorAll('ytcp-icon-button[aria-label="태그"]')].slice(0, 4);
  for (const b of 더하기) { b.scrollIntoView({ block: 'center' }); b.click(); await 쉬기(1500); }
  const 수 = (창.innerText.match(/태그된 제품\s*(\d+)개/) || [])[1];
  const 완료 = [...창.querySelectorAll('ytcp-button')].find((b) => b.innerText.trim() === '완료');
  if (!완료) return { 상태: '실패', 이유: '‘완료’ 버튼이 없어요' };
  완료.click();
  await 쉬기(2500);
  const 저장 = document.querySelector('ytcp-button#save');
  if (저장 && !저장.hasAttribute('disabled')) { 저장.click(); }
  const 저장됨 = await 기다리기(() => { const s = document.querySelector('ytcp-button#save'); return s && s.hasAttribute('disabled'); }, 20);
  return 저장됨 ? { 상태: '완료', 개수: +(수 || 0) } : { 상태: '실패', 이유: '저장이 끝나지 않았어요' };
})();
