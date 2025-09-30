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

def _perform_ai_code_check(notice, notice_index):
    """AI를 통한 코드 준수 점검 수행"""
    if "ai_check_config" not in st.session_state:
        st.error("AI 점검 설정이 없습니다.")
        return
    
    config = st.session_state["ai_check_config"]
    container = config["container"]
    index = config["index"]
    
    try:
        from azureai.aisearch import ask_question_with_container
        
        # 공지사항의 코드 변경사항들 수집
        code_changes = notice.get("code_changes", [])
        if not code_changes and notice.get("before"):  # 기존 형식 지원
            code_changes = [{"before": notice.get("before", ""), "after": notice.get("after", "")}]
        
        if not code_changes:
            st.warning("점검할 코드 변경사항이 없습니다.")
            return
        
        st.info("🤖 AI 점검을 수행 중입니다...")
        
        results = []
        for idx, change in enumerate(code_changes):
            before_code = change.get("before", "").strip()
            after_code = change.get("after", "").strip()
            
            if not before_code and not after_code:
                continue
            
            # AI 질문 생성
            query = f"""
다음 코드 변경사항을 꼼꼼하게 분석해주세요:

변경 전 코드:
```{notice.get('lang', 'text')}
{before_code}
```

변경 후 코드:
```{notice.get('lang', 'text')}
{after_code}
```

현재 인덱스된 코드베이스에서 다음을 철저히 검증해주세요:

**1단계: 변경 전 코드 패턴 검색 (유연한 매칭)**
- 완전히 일치하는 코드 블록 검색
- 공백, 들여쓰기, 줄바꿈이 다른 경우도 포함
- 변수명, 함수명, 클래스명이 다르지만 구조가 같은 경우도 검색
- 주석이 추가되거나 제거된 경우도 포함
- 코드의 핵심 로직이나 패턴이 같은 경우 모두 검색
- 부분적으로 일치하는 코드 조각도 포함 (예: 함수 내 일부 로직만 일치)
- 발견된 모든 위치와 파일명을 구체적으로 나열
- 각 발견 항목의 맥락(주변 코드)과 유사도 설명

**2단계: 변경 후 코드 패턴 검증 (변경 전 코드가 발견된 경우에만)**
- 변경 후 코드와 정확히 일치하는 구현 검색
- 동일한 기능을 수행하는 다른 구현 방식도 확인
- 변경 후 패턴이 적용된 모든 위치 나열
- 변경 전 위치와 변경 후 위치가 일치하는지 대조 분석
- 부분적으로만 적용된 경우 구체적으로 어떤 부분이 누락되었는지 설명

**3단계: 적용 완료도 검증**
- 변경 전 코드가 발견된 위치 중 몇 개나 변경 후 코드로 교체되었는지 정확한 비율 계산
- 아직 교체되지 않은 위치가 있다면 구체적인 파일명과 라인 번호 제시
- 신규로 추가된 변경 후 코드 위치도 확인 (기존 코드 교체가 아닌 추가 구현)

**4단계: 논리적 상태 판단**
- 변경 전 코드 미발견 시 → 변경 후 코드 적용 여부는 "⚪ 해당 없음"
- 변경 전 코드 발견 시 → 실제 교체 비율에 따라 "🟢 적용됨" 또는 "🔴 미적용" 또는 "🟡 부분적용"

상세한 분석 후 준수 상태 요약 표를 생성해주세요.

**꼼꼼한 검증 결과 기반 준수 상태 요약 표:**
| 항목 | 상태 | 설명 |
|------|------|------|
| 변경 전 코드 사용 여부 | 🔴 발견됨 또는 🟢 미발견 | 발견된 정확한 위치와 개수 포함 |
| 변경 후 코드 적용 여부 | 🟢 완전적용, 🟡 부분적용, 🔴 미적용, ⚪ 해당없음 | 적용 비율과 누락 위치 명시 |
| 전반적 준수 상태 | 🟢 준수, 🟡 부분준수, 🔴 미준수, ⚪ 불명확 | 종합적 판단 결과 |
| 상세 분석 결과 | 구체적 검증 내용 | 파일명, 라인번호, 교체비율 등 포함 |

**변경 후 코드 적용 여부 세부 판단 기준:**
- 🟢 완전적용: 변경 전 코드 위치 100% 교체 완료
- � 부분적용: 변경 전 코드 일부만 교체 (비율과 누락 위치 명시)
- 🔴 미적용: 변경 전 코드 발견되었으나 변경 후 코드로 교체 안됨
- ⚪ 해당없음: 변경 전 코드 미발견으로 판단 불가

**분석 품질 요구사항:**
- 모든 발견 항목에 파일명과 대략적 위치 정보 포함
- 교체 비율을 정확한 수치로 제시 (예: "3개 중 2개 교체됨 (66.7%)")
- 누락된 위치가 있다면 구체적으로 어느 파일의 어느 부분인지 명시

**중요: 변경 전 코드 검색 시 유연한 접근 방식 적용**
- 코드의 핵심 의미나 기능이 같으면 발견된 것으로 간주
- 형식적 차이(공백, 줄바꿈, 들여쓰기, 따옴표 종류)는 무시
- 변수명이나 함수명이 달라도 구조와 로직이 같으면 유사 패턴으로 인식
- 주석의 유무나 내용 차이는 무시
- 의심스러운 경우에는 발견된 것으로 처리하고 유사도와 차이점을 상세히 설명
- 너무 엄격한 일치보다는 의미적, 기능적 유사성에 중점을 둘 것

**전반적 준수 상태 판단 로직:**  
- 변경 전 🔴 발견됨 + 변경 후 🟢 적용됨 = 🟡 부분준수 (이전 패턴 제거 필요)
- 변경 전 🔴 발견됨 + 변경 후 🔴 미적용 = 🔴 미준수 (변경 필요)
- 변경 전 🟢 미발견 + 변경 후 ⚪ 해당 없음 = 🟢 준수 (해당 변경사항과 무관)

중요: 위 로직을 정확히 따라 논리적 일관성을 유지해주세요.
"""
            
            try:
                # AI Search를 통한 코드 분석
                response = ask_question_with_container(
                    query=query,
                    container_name=container,
                    search_index=index
                )
                
                results.append({
                    "change_index": idx + 1 if len(code_changes) > 1 else None,
                    "before_code": before_code,
                    "after_code": after_code,
                    "ai_analysis": response.get("content", ""),
                    "citations": response.get("citations", [])
                })
                
            except Exception as e:
                results.append({
                    "change_index": idx + 1 if len(code_changes) > 1 else None,
                    "before_code": before_code,
                    "after_code": after_code,
                    "ai_analysis": f"AI 분석 실패: {str(e)}",
                    "citations": []
                })
        
        # 결과를 세션 상태에 저장
        if "ai_check_results" not in st.session_state:
            st.session_state["ai_check_results"] = {}
        
        st.session_state["ai_check_results"][notice_index] = {
            "container": container,
            "index": index,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "results": results
        }
        
        # AI 점검 결과를 공지사항에 저장 (컨테이너/인덱스별 최신 1건씩 저장)
        notice = st.session_state["notices"][notice_index]
        if "ai_check_results_by_env" not in notice:
            notice["ai_check_results_by_env"] = {}
        
        # 컨테이너/인덱스 조합을 키로 사용
        env_key = f"{container}|{index}"
        notice["ai_check_results_by_env"][env_key] = {
            "container": container,
            "index": index,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "results": results
        }
        
        # 공지사항 파일에 저장
        _save_notices(st.session_state["notices"])
        
        st.success("AI 점검이 완료되었습니다!")
        st.rerun()
        
    except Exception as e:
        st.error(f"AI 점검 실패: {str(e)}")

def _display_ai_check_results(check_result):
    """AI 점검 결과를 표시하는 함수"""
    st.markdown("### 🤖 AI 코드 준수 점검 결과")
    
    # 점검 정보 표시
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("컨테이너", check_result["container"])
    with col2:
        st.metric("인덱스", check_result["index"])
    with col3:
        st.metric("점검 시간", check_result["timestamp"])
    
    # 각 코드 변경사항별 결과 표시
    for result in check_result["results"]:
        if result["change_index"]:
            st.markdown(f"#### 📝 변경사항 {result['change_index']} 점검 결과")
        else:
            st.markdown("#### 📝 점검 결과")
        
        # AI 분석 결과 (OpenAI가 생성한 준수 상태 요약 표 포함)
        with st.container():
            st.markdown("**🧠 AI 분석 결과 및 준수 상태 요약**")
            st.write(result["ai_analysis"])
        
        # 인용 문서가 있는 경우 표시
        if result["citations"]:
            with st.expander("📚 참조된 문서들", expanded=False):
                for idx, citation in enumerate(result["citations"], 1):
                    st.markdown(f"**참조 {idx}**")
                    if hasattr(citation, 'title') or 'title' in citation:
                        st.write(f"**제목**: {citation.get('title', 'N/A')}")
                    if hasattr(citation, 'content') or 'content' in citation:
                        content = citation.get('content', '')[:200] + "..." if len(citation.get('content', '')) > 200 else citation.get('content', '')
                        st.write(f"**내용**: {content}")
                    if hasattr(citation, 'url') or 'url' in citation:
                        st.write(f"**URL**: {citation.get('url', 'N/A')}")
                    st.divider()
        
        if result != check_result["results"][-1]:  # 마지막이 아니면 구분선
            st.divider()

def render_notice_board():
    """공지사항 페이지"""
    st.title("📌 공지사항")
    st.write("팀의 소스 코드 표준 변경 공지를 작성하고 공유하세요.")

    # 최초 로드 시 파일에서 불러오기
    if "notices" not in st.session_state:
        st.session_state["notices"] = _load_notices()

    # AI 점검 설정 섹션
    st.subheader("🔍 AI 코드 준수 점검")
    with st.expander("점검 설정", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**컨테이너 선택**")
            try:
                # AI Chat 모듈의 실제 Blob Storage 컨테이너 조회 함수 사용
                import sys
                from pathlib import Path
                sys.path.append(str(Path(__file__).resolve().parent))
                from ai_chat import get_azure_storage_containers
                
                containers_data = get_azure_storage_containers()
                if containers_data:
                    container_names = [container['name'] for container in containers_data]
                    
                    # 컨테이너별 인덱스 정보도 함께 표시
                    container_options = []
                    for container_name in container_names:
                        try:
                            from azureai.aisearch import get_indexes_for_container
                            indexes = get_indexes_for_container(container_name)
                            index_count = len(indexes) if indexes else 0
                            if index_count > 0:
                                container_options.append(f"{container_name} 🔍 ({index_count}개 인덱스)")
                            else:
                                container_options.append(f"{container_name} (인덱스 없음)")
                        except:
                            container_options.append(f"{container_name}")
                    
                    selected_container_display = st.selectbox(
                        "컨테이너를 선택하세요:",
                        options=container_options,
                        key="ai_check_container"
                    )
                    
                    # 실제 컨테이너 이름 추출
                    selected_container = selected_container_display.split(" ")[0] if selected_container_display else None
                else:
                    st.info("Azure Storage 컨테이너가 없거나 조회할 수 없습니다.")
                    selected_container = None
            except Exception as e:
                st.error(f"컨테이너 목록 조회 실패: {e}")
                selected_container = None
        
        with col2:
            st.markdown("**인덱스 선택**")
            if selected_container:
                try:
                    from azureai.aisearch import get_indexes_for_container
                    indexes = get_indexes_for_container(selected_container)
                    if indexes:
                        selected_index = st.selectbox(
                            "인덱스를 선택하세요:",
                            options=[idx['name'] for idx in indexes],
                            format_func=lambda x: f"{x} ({next((idx['description'] for idx in indexes if idx['name'] == x), '')})",
                            key="ai_check_index"
                        )
                    else:
                        st.info("해당 컨테이너에 인덱스가 없습니다.")
                        selected_index = None
                except Exception as e:
                    st.error(f"인덱스 목록 조회 실패: {e}")
                    selected_index = None
            else:
                selected_index = None
                st.info("먼저 컨테이너를 선택하세요.")
        
        # 선택된 설정 저장
        if selected_container and selected_index:
            st.session_state["ai_check_config"] = {
                "container": selected_container,
                "index": selected_index
            }
        else:
            st.session_state.pop("ai_check_config", None)

    st.divider()

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
                # 상단에 버튼들 추가
                col_delete, col_ai_check, col_empty = st.columns([1, 1, 4])
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
                
                with col_ai_check:
                    # AI 점검 버튼
                    ai_check_disabled = "ai_check_config" not in st.session_state
                    if st.button("🤖 AI 점검하기", key=f"ai_check_{i}", disabled=ai_check_disabled,
                                help="선택된 인덱스에서 코드 준수 여부를 점검합니다" if not ai_check_disabled else "먼저 컨테이너와 인덱스를 선택하세요"):
                        _perform_ai_code_check(n, i)
                
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
                
                # AI 점검 결과 표시 (컨테이너/인덱스 매칭 확인)
                current_config = st.session_state.get("ai_check_config", {})
                current_container = current_config.get("container")
                current_index = current_config.get("index")
                
                result_displayed = False
                
                # 현재 세션 결과 확인 (컨테이너/인덱스 일치 시에만 표시)
                if ("ai_check_results" in st.session_state and 
                    i in st.session_state["ai_check_results"]):
                    session_check = st.session_state["ai_check_results"][i]
                    if (session_check.get("container") == current_container and 
                        session_check.get("index") == current_index):
                        st.divider()
                        _display_ai_check_results(session_check)
                        result_displayed = True
                
                # 저장된 최신 AI 점검 결과 표시 (세션 결과가 없거나 매칭되지 않을 때만)
                if not result_displayed and n.get("ai_check_results_by_env") and current_container and current_index:
                    env_key = f"{current_container}|{current_index}"
                    if env_key in n["ai_check_results_by_env"]:
                        latest_check = n["ai_check_results_by_env"][env_key]
                        st.divider()
                        st.markdown("### 🤖 최근 AI 점검 결과")
                        st.info(f"**{latest_check.get('container')}** 컨테이너의 **{latest_check.get('index')}** 인덱스에서 점검한 결과입니다.")
                        _display_ai_check_results(latest_check)

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