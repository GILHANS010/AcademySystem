import json
import os
from datetime import datetime
import uuid

STUDENTS_FILE = 'students.json'

# 학생 데이터 불러오기
def load_students():
    if not os.path.exists(STUDENTS_FILE):
        return []
    with open(STUDENTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# 학생 데이터 저장하기
def save_students(students):
    with open(STUDENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(students, f, ensure_ascii=False, indent=2)

# 고유 ID 생성
def generate_id():
    return str(uuid.uuid4())

# 오늘 날짜 반환
def today_str():
    return datetime.now().strftime('%Y-%m-%d')

# 오늘 요일 반환
def today_weekday():
    return ['월','화','수','목','금','토','일'][datetime.now().weekday()]

# 날짜 포맷 변환 (YYYY-MM-DD)
def format_date(date):
    if isinstance(date, datetime):
        return date.strftime('%Y-%m-%d')
    return date

# 회차 증감 (학생, 과목, 증감값)
def update_sessions(student, subject, delta):
    for lesson in student['lessons']:
        if lesson['subject'] == subject:
            lesson['remaining_sessions'] += delta
            if lesson['remaining_sessions'] < 0:
                lesson['remaining_sessions'] = 0
            break

# 학생 찾기 (id)
def find_student(students, student_id):
    for s in students:
        if s['id'] == student_id:
            return s
    return None

# 과목 찾기 (student, subject)
def find_lesson(student, subject):
    for lesson in student['lessons']:
        if lesson['subject'] == subject:
            return lesson
    return None 