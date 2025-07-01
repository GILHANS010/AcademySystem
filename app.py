import streamlit as st
st.set_page_config(layout='wide')
from utils import load_students, save_students, today_str, today_weekday, generate_id
import os
from datetime import datetime
import pandas as pd
import io
import json
import glob
import shutil

# 커스텀 CSS 적용
with open('style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# 세션 상태 초기화
def init_session():
    if 'page' not in st.session_state:
        st.session_state['page'] = '출석 체크'
    if 'selected_student_id' not in st.session_state:
        st.session_state['selected_student_id'] = None
    if 'edit_mode' not in st.session_state:
        st.session_state['edit_mode'] = False
    if 'edit_payment_id' not in st.session_state:
        st.session_state['edit_payment_id'] = None
    if 'edit_attendance_id' not in st.session_state:
        st.session_state['edit_attendance_id'] = None
init_session()

# 사이드바 메뉴
def sidebar():
    # st.sidebar.title('국악학원 출결 시스템')  # 타이틀 제거
    menu_list = ['출석 체크', '학생 관리', '결제 관리', '데이터 관리']
    if 'page' not in st.session_state:
        st.session_state['page'] = '출석 체크'
    menu = st.sidebar.radio(
        '고율국악학원',  # 네모칸 안 텍스트 변경
        menu_list,
        index=menu_list.index(st.session_state['page']) if st.session_state['page'] in menu_list else 0,
        key='menu_radio'
    )
    if menu != st.session_state['page']:
        st.session_state['page'] = menu
        st.rerun()
    st.sidebar.markdown('---')
    st.sidebar.info('Made with ❤️ by 국악학원')
sidebar()

# --- 결제수단 옵션 ---
PAY_METHODS = ['현금', '카드', '기타']

# 메인 화면: 오늘의 출석 & 간편 조회
def update_attendance(student_id, subject, date, action):
    students = load_students()
    student = next((s for s in students if s['id'] == student_id), None)
    if not student:
        return
    lesson = next((l for l in student['lessons'] if l['subject'] == subject), None)
    if not lesson:
        return
    if action == 'add':
        att_id = generate_id()
        lesson.setdefault('attendance_history', []).append({
            'id': att_id,
            'date': str(date),
            'status': '출석'
        })
        lesson['remaining_sessions'] -= 1  # 음수 허용
    elif action == 'remove':
        lesson['attendance_history'] = [a for a in lesson['attendance_history'] if not (a['date'] == str(date))]
        lesson['remaining_sessions'] += 1
    save_students(students)

def update_payment(student_id, subject, pay_id=None, date=None, amount=None, sessions=None, method=None, action='add'):
    students = load_students()
    student = next((s for s in students if s['id'] == student_id), None)
    if not student:
        return
    lesson = next((l for l in student['lessons'] if l['subject'] == subject), None)
    if not lesson:
        return
    if action == 'add':
        new_id = generate_id()
        lesson['payment_history'].append({
            'id': new_id,
            'date': str(date),
            'amount': amount,
            'sessions_added': sessions,
            'method': method or '현금'
        })
        lesson['remaining_sessions'] += sessions
    elif action == 'edit' and pay_id:
        pay = next((p for p in lesson['payment_history'] if p['id'] == pay_id), None)
        if pay:
            lesson['remaining_sessions'] -= pay['sessions_added']
            pay['date'] = str(date)
            pay['amount'] = amount
            pay['sessions_added'] = sessions
            pay['method'] = method or pay.get('method', '현금')
            lesson['remaining_sessions'] += sessions
    elif action == 'delete' and pay_id:
        pay = next((p for p in lesson['payment_history'] if p['id'] == pay_id), None)
        if pay:
            lesson['remaining_sessions'] -= pay['sessions_added']
            lesson['payment_history'] = [p for p in lesson['payment_history'] if p['id'] != pay_id]
    save_students(students)

def main_page():
    from datetime import datetime as dt
    st.title('출석 체크')
    students = load_students()
    # --- 결제 필요 학생 정보 계산 ---
    total_students = len(students)
    need_pay = []
    for s in students:
        for l in s['lessons']:
            if l['remaining_sessions'] <= 1:
                need_pay.append(f"{s['name']}({l['subject']})")
    st.sidebar.markdown('---')
    st.sidebar.info(f"총 학생 수: {total_students}\n\n결제 필요 학생 수: {len(need_pay)}\n\n" + ("\n".join(need_pay) if need_pay else ""))
    # --- B: 검색/필터 ---
    with st.expander('검색/필터', expanded=False):
        search_name = st.text_input('이름 검색')
        search_subject = st.text_input('과목 검색')
        search_phone = st.text_input('연락처 검색')
        only_low = st.checkbox('남은 회차 2회 이하만 보기')
    filtered_students = []
    for s in students:
        if search_name and search_name not in s['name']:
            continue
        if search_phone and search_phone not in s['phone']:
            continue
        lessons = []
        for l in s['lessons']:
            if search_subject and search_subject not in l['subject']:
                continue
            if only_low and l['remaining_sessions'] > 2:
                continue
            lessons.append(l)
        if lessons:
            s_copy = s.copy()
            s_copy['lessons'] = lessons
            filtered_students.append(s_copy)
    # --- 기준 출석 날짜 선택 ---
    st.markdown('#### 기준 출석 날짜')
    base_att_date = st.date_input('출석일', value=dt.now().date(), key='base_att_date')
    # 테이블 헤더
    cols = st.columns([2, 2, 2, 2, 2])
    cols[0].markdown('**이름**')
    cols[1].markdown('**과목**')
    cols[2].markdown('**남은 회차**')
    cols[3].markdown('**출석 체크**')
    for student in filtered_students:
        for idx, lesson in enumerate(student['lessons']):
            display_sessions = lesson['remaining_sessions']
            if display_sessions <= 0:
                session_html = f'<span class="session-low">{display_sessions}</span> <span style="color:#E06C75;font-weight:bold;">결제 필요!</span>'
            elif display_sessions <= 2:
                session_html = f'<span class="session-low">{display_sessions}</span>'
            else:
                session_html = f'<span class="session-ok">{display_sessions}</span>'
            key_prefix = f"{student['id']}_{lesson['subject']}"
            row_cols = st.columns([2, 2, 2, 2, 2])
            # 이름을 버튼으로 만들어 클릭 시 상세로 이동
            if row_cols[0].button(student['name'], key=f'goto_detail_{student["id"]}_{lesson["subject"]}'):
                st.session_state['selected_student_id'] = student['id']
                st.session_state['selected_subject'] = lesson['subject']
                st.session_state['page'] = '학생 관리'
                st.rerun()
            row_cols[1].write(lesson['subject'])
            row_cols[2].markdown(session_html, unsafe_allow_html=True)
            # --- F: 중복 출석 방지 ---
            already_attend = any(att['date'] == str(base_att_date) for att in lesson.get('attendance_history', []))
            if not already_attend:
                if row_cols[3].button('출석 체크', key=f'attend_{key_prefix}'):
                    update_attendance(student['id'], lesson['subject'], base_att_date, 'add')
                    st.rerun()
            else:
                col_done, col_cancel = row_cols[3].columns([1.5,0.5])
                col_done.markdown(f'<span style="color:#98C379;font-weight:bold;white-space:nowrap;">출석</span>', unsafe_allow_html=True)
                if col_cancel.button('X', key=f'cancel_{key_prefix}'):
                    update_attendance(student['id'], lesson['subject'], base_att_date, 'remove')
                    st.rerun()
            # 행 아래 구분선 추가
            st.markdown('<div class="attendance-row"></div>', unsafe_allow_html=True)

# 학생 관리 페이지
def student_manage_page():
    import copy
    students = load_students()
    student_id = st.session_state.get('selected_student_id')
    subject = st.session_state.get('selected_subject')
    student = None
    lesson = None
    if student_id:
        student = next((s for s in students if s['id'] == student_id), None)
        if student and subject:
            lesson = next((l for l in student['lessons'] if l['subject'] == subject), None)
    
    if student and lesson:
        if st.button('← 학생 목록으로 돌아가기', key='back_to_list'):
            st.session_state['selected_student_id'] = None
            st.session_state['selected_subject'] = None
            st.rerun()
        st.title(f"학생 상세 관리: {student['name']} ({lesson['subject']})")
        # 상단: 기본 정보 (수정 모드)
        st.subheader('기본 정보')
        edit_mode = st.session_state.get('edit_basic', False)
        col1, col2, col3, col4 = st.columns([2,2,2,2])
        if not edit_mode:
            col1.markdown(f"**이름:** {student['name']}")
            col2.markdown(f"**연락처:** {student['phone']}")
            col3.markdown(f"**등록일:** {student['registered_date']}")
            if col4.button('수정', key='edit_basic_btn'):
                st.session_state['edit_basic'] = True
                st.rerun()
        else:
            new_name = col1.text_input('이름', value=student['name'], key='edit_name')
            new_phone = col2.text_input('연락처', value=student['phone'], key='edit_phone')
            new_date = col3.date_input('등록일', value=student['registered_date'], key='edit_regdate')
            if col4.button('저장', key='save_basic_btn'):
                student['name'] = new_name
                student['phone'] = new_phone
                student['registered_date'] = str(new_date)
                save_students(students)
                st.session_state['edit_basic'] = False
                st.rerun()
            if col4.button('취소', key='cancel_basic_btn'):
                st.session_state['edit_basic'] = False
                st.rerun()
        st.markdown('---')
        # 탭 구조
        tab1, tab2, tab3, tab4 = st.tabs(['수강 과목/결제', '결제 이력', '출석 이력', '메모'])
        # 1) 수강 과목 및 결제
        with tab1:
            st.markdown(f"**과목:** {lesson['subject']}")
            st.markdown(f"**남은 회차:** <span class='{'session-low' if lesson['remaining_sessions'] <= 2 else 'session-ok'}'>{lesson['remaining_sessions']}</span>", unsafe_allow_html=True)
            # 과목 삭제 버튼 (과목이 2개 이상일 때만)
            if len(student['lessons']) > 1:
                if st.button(f"이 과목({lesson['subject']}) 삭제", key=f'del_subject_{student["id"]}_{lesson["subject"]}'):
                    student['lessons'] = [l for l in student['lessons'] if l['subject'] != lesson['subject']]
                    save_students(students)
                    st.success(f'과목({lesson["subject"]})이 삭제되었습니다.')
                    st.session_state['selected_subject'] = student['lessons'][0]['subject']
                    st.rerun()
            else:
                st.info('수강 과목이 1개일 때는 삭제할 수 없습니다.')
            # 회차 추가(결제)
            with st.expander('회차 추가 (결제)', expanded=False):
                add_date = st.date_input('결제 날짜', value=None, key='pay_date')
                add_amount = st.number_input('결제 금액', min_value=0, step=1000, key='pay_amount')
                add_sessions = st.number_input('추가 회차', min_value=1, step=1, key='pay_sessions')
                add_method = st.selectbox('결제 수단', PAY_METHODS, key='pay_method')
                if st.button('회차 추가', key='add_sessions_btn'):
                    update_payment(student['id'], lesson['subject'], date=add_date, amount=add_amount, sessions=add_sessions, method=add_method, action='add')
                    st.success('회차가 추가되었습니다.')
                    st.rerun()
            # 과목 추가
            with st.expander('과목 추가', expanded=False):
                all_subjects = ['가야금', '거문고', '해금', '대금', '단소', '소금', '장구', '판소리', '민요']
                available_subjects = [s for s in all_subjects if s not in [l['subject'] for l in student['lessons']]]
                new_subject = st.selectbox('새 과목 선택', available_subjects, key='new_subject')
                new_pay_date = st.date_input('초기 결제 날짜', value=None, key='new_pay_date')
                new_amount = st.number_input('초기 결제 금액', min_value=0, step=1000, key='new_amount')
                new_sessions = st.number_input('초기 회차', min_value=1, step=1, key='new_sessions')
                if st.button('과목 추가', key='add_subject_btn') and new_subject:
                    student['lessons'].append({
                        'subject': new_subject,
                        'remaining_sessions': new_sessions,
                        'payment_history': [{
                            'id': generate_id(),
                            'date': str(new_pay_date),
                            'amount': new_amount,
                            'sessions_added': new_sessions
                        }],
                        'attendance_history': []
                    })
                    save_students(students)
                    st.success('새 과목이 추가되었습니다.')
                    st.rerun()
        # 2) 결제 이력
        with tab2:
            st.markdown('**결제 이력**')
            import pandas as pd
            pay_df = copy.deepcopy(lesson['payment_history'])
            if pay_df:
                for pay in sorted(pay_df, key=lambda x: x['date'], reverse=True):
                    c1, c2, c3, c4, c5, c6 = st.columns([2,2,2,2,2,2])
                    c1.write(pay['date'])
                    c2.write(f"{pay['amount']:,}원")
                    c3.write(f"{pay['sessions_added']}회")
                    c4.write(pay.get('method', '현금'))
                    # 수정/삭제 버튼
                    if st.session_state.get(f'edit_pay_{pay["id"]}', False):
                        new_date = c1.date_input('날짜', value=pay['date'], key=f'pay_date_edit_{pay["id"]}')
                        new_amount = c2.number_input('금액', value=pay['amount'], min_value=0, step=1000, key=f'pay_amount_edit_{pay["id"]}')
                        new_sessions = c3.number_input('회차', value=pay['sessions_added'], min_value=1, step=1, key=f'pay_sessions_edit_{pay["id"]}')
                        method_val = str(pay.get('method', '현금') or '현금')
                        new_method = c4.selectbox('결제 수단', PAY_METHODS, index=PAY_METHODS.index(method_val), key=f'pay_method_edit_{pay["id"]}')
                        if c5.button('저장', key=f'save_pay_{pay["id"]}'):
                            update_payment(student['id'], lesson['subject'], pay_id=pay['id'], date=new_date, amount=new_amount, sessions=new_sessions, method=new_method, action='edit')
                            st.session_state[f'edit_pay_{pay["id"]}'] = False
                            st.rerun()
                        if c6.button('수정 취소', key=f'cancel_pay_{pay["id"]}'):
                            st.session_state[f'edit_pay_{pay["id"]}'] = False
                            st.rerun()
                    else:
                        if c5.button('수정', key=f'edit_pay_{pay["id"]}'):
                            st.session_state[f'edit_pay_{pay["id"]}'] = True
                            st.rerun()
                        if c6.button('삭제', key=f'del_pay_{pay["id"]}'):
                            update_payment(student['id'], lesson['subject'], pay_id=pay['id'], action='delete')
                            st.rerun()
            else:
                st.info('결제 이력이 없습니다.')
            # 결제 추가 폼 (key 고유화)
            add_date = st.date_input('결제 날짜', value=datetime.now().date(), key=f'pay_date_add_{student["id"]}_{lesson["subject"]}')
            add_amount = st.number_input('결제 금액', min_value=0, step=1000, key=f'pay_amount_add_{student["id"]}_{lesson["subject"]}')
            add_sessions = st.number_input('추가 회차', min_value=1, step=1, key=f'pay_sessions_add_{student["id"]}_{lesson["subject"]}')
            add_method = st.selectbox('결제 수단', PAY_METHODS, key=f'pay_method_add_{student["id"]}_{lesson["subject"]}')
            if st.button('회차 추가', key=f'add_sessions_btn_{student["id"]}_{lesson["subject"]}'):
                update_payment(student['id'], lesson['subject'], date=add_date, amount=add_amount, sessions=add_sessions, method=add_method, action='add')
                st.success('회차가 추가되었습니다.')
                st.rerun()
        # 3) 출석 이력
        with tab3:
            st.markdown('**출석 이력**')
            import pandas as pd
            att_df = copy.deepcopy(lesson['attendance_history'])
            if att_df:
                for att in sorted(att_df, key=lambda x: x['date'], reverse=True):
                    c1, c2, c3 = st.columns([3,3,2])
                    c1.write(att['date'])
                    c2.write('출석')
                    if c3.button('삭제', key=f'del_att_{att["id"]}'):
                        update_attendance(student['id'], lesson['subject'], att['date'], 'remove')
                        st.rerun()
            else:
                st.info('출석 이력이 없습니다.')
            # 출석 추가 폼 (key 고유화)
            new_att_date = st.date_input('출석 날짜', value=datetime.now().date(), key=f'new_att_date_{student["id"]}_{lesson["subject"]}')
            if st.button('출석 추가', key=f'add_att_btn_{student["id"]}_{lesson["subject"]}'):
                if any(a['date'] == str(new_att_date) for a in lesson['attendance_history']):
                    st.warning('이미 출석 체크된 날짜입니다.')
                else:
                    update_attendance(student['id'], lesson['subject'], new_att_date, 'add')
                    st.success('출석이 추가되었습니다.')
                    st.rerun()
        # 4) 메모 관리
        with tab4:
            st.markdown('**메모**')
            memo_val = st.text_area('메모', value=student.get('memo', ''), key='memo_area')
            if st.button('메모 저장', key='save_memo'):
                student['memo'] = memo_val
                save_students(students)
                st.success('메모가 저장되었습니다.')
                st.rerun()
    else:
        st.title('학생 관리')
        st.subheader('학생 등록')
        with st.form('add_student_form', clear_on_submit=True):
            new_name = st.text_input('이름')
            new_phone = st.text_input('연락처')
            all_subjects = ['가야금', '거문고', '해금', '대금', '단소', '소금', '장구', '판소리', '민요']
            new_subjects = st.multiselect('수강 과목', all_subjects)
            new_memo = st.text_area('메모')
            submitted = st.form_submit_button('학생 등록')
            if submitted:
                if not new_name or not new_subjects:
                    st.warning('이름과 과목을 입력하세요.')
                else:
                    new_id = generate_id()
                    new_student = {
                        'id': new_id,
                        'name': new_name,
                        'phone': new_phone,
                        'registered_date': today_str(),
                        'lessons': [
                            {
                                'subject': subj,
                                'remaining_sessions': 0,
                                'payment_history': [],
                                'attendance_history': []
                            } for subj in new_subjects
                        ],
                        'memo': new_memo
                    }
                    students.append(new_student)
                    save_students(students)
                    st.success('학생이 등록되었습니다.')
                    st.rerun()
        st.markdown('---')
        st.subheader('전체 학생 목록')
        for s in students:
            c1, c2, c3, c4, c5 = st.columns([2,2,2,2,2])
            c1.write(s['name'])
            c2.write(s['phone'])
            c3.write(s['registered_date'])
            # 과목별 상세보기 버튼
            for l in s['lessons']:
                if c4.button(f"상세({l['subject']})", key=f'detail_{s["id"]}_{l["subject"]}'):
                    st.session_state['selected_student_id'] = s['id']
                    st.session_state['selected_subject'] = l['subject']
                    st.rerun()
            # 삭제 버튼
            if c5.button('삭제', key=f'del_{s["id"]}'):
                st.session_state['delete_student_id'] = s['id']
                st.session_state['delete_student_name'] = s['name']
                st.session_state['show_delete_confirm'] = True
                st.rerun()
        # 삭제 확인 경고 및 버튼
        if st.session_state.get('show_delete_confirm', False):
            st.warning(f"정말로 {st.session_state.get('delete_student_name', '')} 학생을 삭제하시겠습니까?")
            colA, colB = st.columns(2)
            if colA.button('삭제 확정', key='confirm_delete_btn'):
                # 삭제 전 자동 백업
                backup_name = f'students_autobackup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                shutil.copy('students.json', backup_name)
                students = [stu for stu in students if stu['id'] != st.session_state['delete_student_id']]
                save_students(students)
                st.success(f'학생이 삭제되었습니다. (자동 백업: {backup_name})')
                st.session_state['show_delete_confirm'] = False
                st.rerun()
            if colB.button('취소', key='cancel_delete_btn'):
                st.session_state['show_delete_confirm'] = False
                st.rerun()

# 결제 관리 페이지
def payment_manage_page():
    st.title('결제 관리')
    students = load_students()
    # 결제 이력 전체 리스트 생성
    payment_rows = []
    for s in students:
        for l in s['lessons']:
            for pay in l.get('payment_history', []):
                payment_rows.append({
                    'student_id': s['id'],
                    'student_name': s['name'],
                    'subject': l['subject'],
                    'pay_id': pay['id'],
                    'date': pay['date'],
                    'amount': pay['amount'],
                    'sessions_added': pay['sessions_added'],
                    'method': pay.get('method', '현금')
                })
    # --- 매출 통계 ---
    import pandas as pd
    from datetime import datetime
    if payment_rows:
        df = pd.DataFrame(payment_rows)
        # 이번달 매출
        now = datetime.now()
        this_month = now.strftime('%Y-%m')
        df['월'] = df['date'].astype(str).str[:7]
        this_month_sales = df[df['월'] == this_month]['amount'].sum()
        st.subheader(f'이번달 매출: {int(this_month_sales):,}원')
        # 월별 매출 표
        month_sales = df.groupby('월')['amount'].sum().reset_index().sort_values('월', ascending=False)
        month_sales['amount'] = month_sales['amount'].apply(lambda x: f"{int(x):,}원")
        st.markdown('**월별 매출 통계**')
        st.table(month_sales.rename(columns={'월':'월(YYYY-MM)','amount':'매출'}))
    # 결제 이력 테이블 표시
    if payment_rows:
        df = pd.DataFrame(payment_rows)
        df = df.sort_values(by=['date'], ascending=False)
        for idx, row in df.iterrows():
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([2,2,2,2,2,2,1,1])
            c1.write(row['student_name'])
            c2.write(row['subject'])
            c3.write(row['date'])
            c4.write(f"{int(row['amount']):,}원")
            c5.write(f"{int(row['sessions_added'])}회")
            c6.write(row.get('method', '현금'))
            # 수정/삭제 버튼
            edit_key = f"edit_pay_global_{row['pay_id']}"
            if st.session_state.get(edit_key, False):
                date_val = str(row['date'])
                amount_val = int(row['amount'])
                sessions_val = int(row['sessions_added'])
                method_val = str(row.get('method', '현금') or '현금')
                pay_id_val = row['pay_id']
                new_date = c3.date_input('날짜', value=date_val, key=f'pay_date_edit_global_{pay_id_val}')
                new_amount = c4.number_input('금액', value=amount_val, min_value=0, step=1000, key=f'pay_amount_edit_global_{pay_id_val}')
                new_sessions = c5.number_input('회차', value=sessions_val, min_value=1, step=1, key=f'pay_sessions_edit_global_{pay_id_val}')
                new_method = c6.selectbox('결제 수단', PAY_METHODS, index=PAY_METHODS.index(method_val), key=f'pay_method_edit_global_{pay_id_val}')
                if c7.button('저장', key=f'save_pay_global_{pay_id_val}'):
                    update_payment(row['student_id'], row['subject'], pay_id=pay_id_val, date=new_date, amount=new_amount, sessions=new_sessions, method=new_method, action='edit')
                    st.session_state[edit_key] = False
                    st.rerun()
                if c8.button('취소', key=f'cancel_pay_global_{pay_id_val}'):
                    st.session_state[edit_key] = False
                    st.rerun()
            else:
                pay_id_val = row['pay_id']
                if c7.button('수정', key=f'edit_pay_global_{pay_id_val}'):
                    st.session_state[edit_key] = True
                    st.rerun()
                if c8.button('삭제', key=f'del_pay_global_{pay_id_val}'):
                    update_payment(row['student_id'], row['subject'], pay_id=pay_id_val, action='delete')
                    st.rerun()
    else:
        st.info('결제 이력이 없습니다.')

# 데이터 관리 페이지
def data_manage_page():
    import io
    import json
    from datetime import datetime
    import glob
    st.title('데이터 관리')
    st.subheader('데이터 백업')
    students = load_students()
    backup_bytes = io.BytesIO(json.dumps(students, ensure_ascii=False, indent=2).encode('utf-8'))
    backup_filename = f'students_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    st.download_button('데이터 백업 파일 다운로드', data=backup_bytes, file_name=backup_filename, mime='application/json')

    # 출석 이력 표로 다운로드 기능(학생별로 출석일을 가로로)
    import pandas as pd
    attendance_rows = []
    for s in students:
        for l in s['lessons']:
            for att in l.get('attendance_history', []):
                attendance_rows.append({
                    '학생명': s['name'],
                    '연락처': s['phone'],
                    '과목': l['subject'],
                    '출석일': att['date'],
                })
    if attendance_rows:
        att_df = pd.DataFrame(attendance_rows)
        # 학생+과목별로 출석일을 가로로 펼치기
        att_df = att_df.sort_values(by=['학생명', '과목', '출석일'])
        grouped = att_df.groupby(['학생명', '연락처', '과목'])['출석일'].apply(list).reset_index()
        # 출석일을 열로 펼치기
        max_att = int(grouped['출석일'].apply(len).max())
        for i in range(max_att):
            grouped[f'출석{i+1}'] = grouped['출석일'].apply(lambda x: x[i] if i < len(x) else '')
        grouped = grouped.drop(columns=['출석일'])
        att_csv = grouped.to_csv(index=False, encoding='utf-8-sig')
        att_filename = f'attendance_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        st.download_button('출석 이력 표(CSV, 학생별 가로정리) 다운로드', data=att_csv, file_name=att_filename, mime='text/csv')
    else:
        st.info('출석 이력이 없습니다.')

    st.markdown('---')
    st.subheader('데이터 복원')
    uploaded = st.file_uploader('복원할 students.json 파일 선택', type='json')
    if uploaded:
        try:
            data = json.load(uploaded)
            if isinstance(data, list):
                save_students(data)
                st.success('데이터가 성공적으로 복원되었습니다. 새로고침 해주세요.')
            else:
                st.error('올바른 students.json 형식이 아닙니다.')
        except Exception as e:
            st.error(f'복원 실패: {e}')
    st.markdown('---')
    st.subheader('자동 백업 복원')
    backup_files = sorted(glob.glob('students_autobackup_*.json'), reverse=True)
    if backup_files:
        for f in backup_files:
            col1, col2 = st.columns([4,1])
            col1.write(f)
            if col2.button('이 백업으로 복원', key=f'restore_{f}'):
                with open(f, 'r', encoding='utf-8') as bf:
                    data = json.load(bf)
                    if isinstance(data, list):
                        save_students(data)
                        st.success(f'{f} 파일로 복원되었습니다. 새로고침 해주세요.')
                    else:
                        st.error('올바른 students.json 형식이 아닙니다.')
    else:
        st.info('자동 백업 파일이 없습니다.')

# 페이지 라우팅
if st.session_state['page'] in ['출석 체크', 'Home']:
    main_page()
elif st.session_state['page'] == '학생 관리':
    student_manage_page()
elif st.session_state['page'] == '결제 관리':
    payment_manage_page()
else:
    data_manage_page() 