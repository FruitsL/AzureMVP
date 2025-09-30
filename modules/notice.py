import streamlit as st
import time
import json
from pathlib import Path

# 공지사항 영속화를 위한 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent
NOTICES_FILE = BASE_DIR / "data" / "notices.json"

def _load_notices():
    try:
        NOTICES_FILE.parent.mkdir(parents=True, exist_ok=True)
        if NOTICES_FILE.exists():
            with open(NOTICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_notices(notices):
    try:
        NOTICES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTICES_FILE, "w", encoding="utf-8") as f:
            json.dump(notices, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"공지 저장 실패: {e}")

def render_notice_board():
    """공지사항 페이지"""
    st.title("📌 공지사항")
    st.write("팀의 소스 코드 표준 변경 공지를 작성하고 공유하세요.")

    # 최초 로드 시 파일에서 불러오기
    if "notices" not in st.session_state:
        st.session_state["notices"] = _load_notices()

    # 공지사항 목록을 먼저 표시
    col_header, col_clear = st.columns([4, 1])
    with col_header:
        st.subheader("📣 공지 목록")
    with col_clear:
        if st.session_state["notices"]:  # 공지가 있을 때만 표시
            if "clear_all_confirm" not in st.session_state:
                st.session_state["clear_all_confirm"] = False
            
            if st.session_state["clear_all_confirm"]:
                if st.button("⚠️ 전체 삭제 확인", type="primary"):
                    st.session_state["notices"] = []
                    _save_notices(st.session_state["notices"])
                    st.session_state["clear_all_confirm"] = False
                    st.success("모든 공지사항이 삭제되었습니다.")
                    st.rerun()
                if st.button("❌ 취소"):
                    st.session_state["clear_all_confirm"] = False
                    st.rerun()
            else:
                if st.button("🗑️ 전체 삭제"):
                    st.session_state["clear_all_confirm"] = True
                    st.rerun()
    
    if not st.session_state["notices"]:
        st.info("등록된 공지가 없습니다.")
    else:
        # 삭제 확인을 위한 세션 상태 초기화
        if "delete_confirm" not in st.session_state:
            st.session_state["delete_confirm"] = {}
        
        for i, n in enumerate(st.session_state["notices"]):
            with st.expander(f"{n.get('timestamp','')} - {n.get('title','(제목 없음)')}"):
                # 상단에 삭제 버튼 추가
                col_delete, col_empty = st.columns([1, 5])
                with col_delete:
                    delete_key = f"delete_{i}"
                    
                    # 삭제 확인 상태 확인
                    if st.session_state["delete_confirm"].get(delete_key, False):
                        st.error("⚠️ 정말 삭제하시겠습니까?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ 예", key=f"confirm_yes_{i}"):
                                # 실제 삭제 수행
                                st.session_state["notices"].pop(i)
                                _save_notices(st.session_state["notices"])
                                st.session_state["delete_confirm"][delete_key] = False
                                st.success("공지사항이 삭제되었습니다.")
                                st.rerun()
                        with col_no:
                            if st.button("❌ 아니요", key=f"confirm_no_{i}"):
                                st.session_state["delete_confirm"][delete_key] = False
                                st.rerun()
                    else:
                        if st.button("🗑️ 삭제", key=f"delete_btn_{i}"):
                            st.session_state["delete_confirm"][delete_key] = True
                            st.rerun()
                
                # 공지사항 내용
                if n.get("desc"):
                    st.markdown(f"**설명**: {n['desc']}")
                
                # 코드 변경 사항 표시 (기존 형식과 새 형식 모두 지원)
                if n.get("code_changes"):  # 새 형식 (여러 변경사항)
                    for idx, change in enumerate(n["code_changes"]):
                        if len(n["code_changes"]) > 1:
                            st.markdown(f"**변경 사항 {idx + 1}**")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**변경 전 소스**")
                            st.code(change.get("before", ""), language=n.get("lang", "text"))
                        with col2:
                            st.markdown("**변경 후 소스**")
                            st.code(change.get("after", ""), language=n.get("lang", "text"))
                        
                        if idx < len(n["code_changes"]) - 1:
                            st.divider()
                else:  # 기존 형식 (단일 변경사항) - 하위 호환성
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**변경 전 소스**")
                        st.code(n.get("before", ""), language=n.get("lang", "text"))
                    with col2:
                        st.markdown("**변경 후 소스**")
                        st.code(n.get("after", ""), language=n.get("lang", "text"))

    # 구분선 추가
    st.divider()

    # 공지사항 작성 폼 (공지 목록 아래로 이동)
    with st.expander("✍️ 새 공지사항 작성", expanded=False):
        st.write("소스 코드 표준 변경에 대한 공지를 작성하세요.")
        
        # 코드 변경사항을 위한 세션 상태 초기화
        if "new_notice_code_changes" not in st.session_state:
            st.session_state["new_notice_code_changes"] = [{"before": "", "after": ""}]
        
        with st.form("notice_form", clear_on_submit=True):
            title = st.text_input("공지 제목")
            desc = st.text_area("변경 사유/설명 (선택)", height=120)
            lang = st.selectbox("코드 언어", ["python", "json", "yaml", "bash", "powershell", "javascript", "typescript", "text"], index=0)
            
            # 코드 변경사항 섹션
            st.subheader("📝 코드 변경 사항")
            
            # 변경사항 추가/삭제 버튼
            col_add, col_remove, col_info = st.columns([1, 1, 4])
            with col_add:
                add_change = st.form_submit_button("➕ 변경사항 추가", help="새로운 코드 변경사항을 추가합니다")
            with col_remove:
                remove_change = st.form_submit_button("➖ 마지막 삭제", 
                                                    disabled=len(st.session_state["new_notice_code_changes"]) <= 1,
                                                    help="마지막 코드 변경사항을 삭제합니다")
            with col_info:
                st.caption(f"현재 {len(st.session_state['new_notice_code_changes'])}개의 변경사항")
            
            # 변경사항 추가/삭제 처리
            if add_change:
                st.session_state["new_notice_code_changes"].append({"before": "", "after": ""})
                st.rerun()
            
            if remove_change and len(st.session_state["new_notice_code_changes"]) > 1:
                st.session_state["new_notice_code_changes"].pop()
                st.rerun()
            
            # 각 코드 변경사항 입력 필드
            for idx, change in enumerate(st.session_state["new_notice_code_changes"]):
                if len(st.session_state["new_notice_code_changes"]) > 1:
                    st.markdown(f"**변경 사항 {idx + 1}**")
                
                col1, col2 = st.columns(2)
                with col1:
                    before_code = st.text_area(
                        "변경 전 소스", 
                        height=200, 
                        placeholder="변경 전 코드 스니펫을 붙여 넣으세요",
                        key=f"before_code_new_{idx}",
                        value=change["before"]
                    )
                    change["before"] = before_code
                
                with col2:
                    after_code = st.text_area(
                        "변경 후 소스", 
                        height=200, 
                        placeholder="변경 후 코드 스니펫을 붙여 넣으세요",
                        key=f"after_code_new_{idx}",
                        value=change["after"]
                    )
                    change["after"] = after_code
                
                if idx < len(st.session_state["new_notice_code_changes"]) - 1:
                    st.divider()
            
            submitted = st.form_submit_button("📝 공지사항 등록", type="primary")
            
            if submitted:
                # 유효한 변경사항이 있는지 확인
                valid_changes = [
                    change for change in st.session_state["new_notice_code_changes"]
                    if change["before"].strip() or change["after"].strip()
                ]
                
                if not title:
                    st.warning("제목을 입력하세요.")
                elif not valid_changes:
                    st.warning("최소 하나의 변경 전/후 소스를 입력하세요.")
                else:
                    new_item = {
                        "title": title,
                        "desc": desc,
                        "lang": lang,
                        "code_changes": valid_changes,
                        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    st.session_state["notices"].insert(0, new_item)
                    _save_notices(st.session_state["notices"])
                    
                    # 폼 초기화
                    st.session_state["new_notice_code_changes"] = [{"before": "", "after": ""}]
                    
                    st.success("공지사항이 등록되었습니다!")
                    st.info("💡 등록된 공지는 위 공지 목록에서 확인하실 수 있습니다.")
                    st.rerun()