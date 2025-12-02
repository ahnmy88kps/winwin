from flask import Flask, request, jsonify, render_template
import pandas as pd
from datetime import datetime
import re
import os
import sys

# ----------------------------------------------------
# 1. QNA 데이터 하드코딩
# ----------------------------------------------------
QNA_DATA_SIMPLE = [
    {
        "prefix": "Q1",
        "title": "Q1. 우리 회사의 현재 상황을 가장 잘 설명하는 말은 무엇인가요?",
        "options": [
            {"text": "1. 🌱 이제 막 시작했어요: 설립 7년 미만의 창업기업(스타트업)입니다.", "keywords": ["기업", "스타트업"]},
            {"text": "2. 🏭 7년 넘게 달려왔어요: 어느 정도 자리를 잡은 기존 기업입니다.", "keywords": ["기업"]},
            {"text": "3. ⚡ 한전/KPS와 인연이 있어요: 이미 협력사로 등록되어 있거나 거래 경험이 있습니다.", "keywords": ["기업", "협력업체", "거래경험"]},
            {"text": "4. 📍 지역을 대표해요: 발전소 주변이나 특정 지역(나주 등)에 소재하고 있습니다.", "keywords": ["기업", "지역"]},
        ]
    },
    {
        "prefix": "Q2",
        "title": "Q2. 우리 회사의 주력 '무기(업종)'는 무엇인가요?",
        "options": [
            {"text": "1. ⚙️ 뚝딱뚝딱 제조: 기계, 부품, 장비 등을 직접 생산합니다.", "keywords": ["제조"]},
            {"text": "2. 💻 스마트한 기술: SW, AI, 플랫폼 등 IT/지식서비스 기반입니다.", "keywords": ["IT", "AI", "스마트팜"]},
            {"text": "3. 🔧 꼼꼼한 서비스: 설비 정비, 유지보수, 엔지니어링 용역을 제공합니다.", "keywords": ["서비스", "엔지니어링"]},
            {"text": "4. ⚡ 에너지 특화: 신재생, 발전설비, 에너지 효율화 분야입니다.", "keywords": ["에너지"]},
        ]
    },
    {
        "prefix": "Q3",
        "title": "Q3. 기술 개발(R&D)과 관련해서 지금 가장 필요한 건 무엇인가요?",
        "options": [
            {"text": "1. 💰 개발 자금: 기술 아이디어는 있는데, 자금이 필요해요.", "keywords": ["개발자금", "R&D"]},
            {"text": "2. 🧪 기술 검증/평가: 우리 기술이 좋은지 공신력 있게 확인받고 싶어요.", "keywords": ["기술인증", "R&D"]},
            {"text": "3. 🤝 공동 연구: 큰 기관과 함께 기술을 공동으로 개발하고 싶어요.", "keywords": ["협력", "R&D"]},
            {"text": "4. ⚙️ 시제품 제작/설비: 개발된 기술을 실제 제품으로 만들어보고 싶어요.", "keywords": ["제조", "기술개발"]},
        ]
    },
    {
        "prefix": "Q4",
        "title": "Q4. 사업 추진 시 가장 중요한 목표는 무엇인가요?",
        "options": [
            {"text": "1. 💸 매출/판로 확대: 제품을 팔 곳을 찾고 매출을 올리고 싶어요.", "keywords": ["판로", "해외진출"]},
            {"text": "2. 🔒 안전/품질 확보: 안전 기준을 높이고 인증을 받고 싶어요.", "keywords": ["안전", "품질"]},
            {"text": "3. 👨‍💼 인력/경영 안정: 회사 경영이나 인력 관리에 도움을 받고 싶어요.", "keywords": ["교육지원", "경영지원"]},
            {"text": "4. 🌐 디지털/스마트화: 우리 회사를 스마트 공장/디지털 시스템으로 바꾸고 싶어요.", "keywords": ["디지털전환", "스마트공장"]},
        ]
    },
    {
        "prefix": "Q5",
        "title": "Q5. 주로 원하는 지원 형태는 무엇인가요?",
        "options": [
            {"text": "1. 💰 직접적인 자금(현금): 사업화 자금, 대출 등 현금이 필요해요.", "keywords": ["비용지원", "자금"]},
            {"text": "2. 🛠️ 설비/컨설팅/용역: 특정 설비나 전문 컨설팅을 받고 싶어요.", "keywords": ["컨설팅", "장비지원"]},
            {"text": "3. 🎓 교육/정보: 직원 교육이나 시장 정보 공유가 필요해요.", "keywords": ["교육지원", "문화"]},
            {"text": "4. 🌏 해외 시장 개척: 해외 전시회 참가 등 해외 진출을 돕고 싶어요.", "keywords": ["해외진출", "판로"]},
        ]
    },
]

# QNA 코드별 키워드 매핑 테이블 자동 생성 (서버 시작 시점)
# 예: Q1-1: ["기업", "스타트업"]
QNA_KEYWORD_MAP = {}
for q in QNA_DATA_SIMPLE:
    for i, option in enumerate(q["options"]):
        simple_code = f"{q['prefix']}-{i+1}" 
        QNA_KEYWORD_MAP[simple_code] = option["keywords"]

# ----------------------------------------------------
# 2. 환경 설정 및 Category 데이터 로드 (CSV 사용)
# ----------------------------------------------------
CATEGORY_CSV_FILE = "category.csv"
TODAY = datetime.now().date()
app = Flask(__name__) 

def load_and_preprocess_category_data(csv_file):
    """Category CSV 파일을 로드하고 전처리하여 DataFrame으로 반환합니다."""
    try:
        # UnicodeDecodeError 해결을 위해 encoding='cp949' 사용
        category_df = pd.read_csv(csv_file, encoding='cp949')
        
        # --- Category 데이터 전처리 ---
        def is_terminated(deadline_str):
            if not deadline_str or pd.isna(deadline_str) or str(deadline_str).strip() in ('상시', '별도공지'):
                return False
            try:
                deadline = datetime.strptime(str(deadline_str).strip(), '%Y-%m-%d').date()
                return deadline < TODAY
            except ValueError:
                return False

        category_df['종료여부'] = category_df['기한'].apply(is_terminated)
        category_df['사업_키워드'] = category_df['키워드(관련도 순으로)'].apply(
            lambda x: [k.strip() for k in str(x).split(',') if k.strip()] if pd.notna(x) else []
        )
        
        print(f"✅ Category 파일 로드 및 전처리 성공: {csv_file}")
        return category_df

    except FileNotFoundError:
        print(f"❌ 오류: Category 파일 '{csv_file}'을 찾을 수 없습니다.")
        sys.exit()
    except Exception as e:
        print(f"❌ 데이터 로드/전처리 오류: {e}")
        sys.exit()

# 서버 시작 시 Category 데이터 로드 및 전처리
CATEGORY_DF = load_and_preprocess_category_data(CATEGORY_CSV_FILE)

# ----------------------------------------------------
# 3. 핵심 추천 로직
# ----------------------------------------------------
def get_recommendations(category_data, user_keywords):
    user_keywords_set = set(k for k in user_keywords if k)

    def calculate_match_score(business_keywords):
        business_keywords_set = set(business_keywords)
        match_count = len(user_keywords_set.intersection(business_keywords_set))
        return match_count

    category_data['일치점수'] = category_data['사업_키워드'].apply(calculate_match_score)
    
    sorted_recommendations = category_data.sort_values(
        by=['종료여부', '일치점수'],
        ascending=[True, False]
    ).reset_index(drop=True)
    
    return sorted_recommendations

# ----------------------------------------------------
# 4. 웹 API 및 화면 라우트
# ----------------------------------------------------
@app.route('/')
def index():
    questions_for_template = []
    
    for q_data in QNA_DATA_SIMPLE:
        question = {
            "prefix": q_data["prefix"],
            "title": q_data["title"],
            "options": []
        }
        for i, option in enumerate(q_data["options"]):
            simple_code = f"{q_data['prefix']}-{i+1}"
            question["options"].append({
                "code": simple_code, 
                "text": option["text"]
            })
        questions_for_template.append(question)

    return render_template('index.html', questions=questions_for_template)

@app.route('/api/recommend', methods=['POST'])
def recommend_businesses():
    data = request.get_json()
    user_qna_codes = data.get('qna_codes', [])
    
    if not user_qna_codes:
        return jsonify({"error": "QNA 코드가 제공되지 않았습니다."}), 400

    user_keywords = []
    for code in user_qna_codes:
        keywords = QNA_KEYWORD_MAP.get(code) 
        if keywords:
            user_keywords.extend(keywords)
            
    recommended_businesses = get_recommendations(CATEGORY_DF.copy(), user_keywords)
    
    results_list = []
    user_keywords_set = set(user_keywords)
    
    for rank, row in recommended_businesses.iterrows():
        status = "진행 중" if not row['종료여부'] else "종료됨 (후순위)"
        matched_keywords = user_keywords_set.intersection(set(row['사업_키워드']))

        results_list.append({
            'rank': rank + 1,
            'status': status,
            'score': int(row['일치점수']),
            'name': row['사업명'],
            'deadline': row['기한'],
            'link': row['링크'],
            'keywords': row['키워드(관련도 순으로)'],
            'matched_keywords': sorted(list(matched_keywords))
        })
        
    return jsonify({
        'total_count': len(results_list),
        'user_keywords': sorted(list(user_keywords_set)),
        'recommendations': results_list
    })

# ----------------------------------------------------
# 5. 서버 실행
# ----------------------------------------------------
if __name__ == '__main__':
    # ⚠️ 주피터 환경에서는 이 부분이 바로 실행되지 않으므로, 
    # 터미널에서 'python app.py' 명령으로 실행해야 합니다.
    # 로컬에서 테스트하려면 이 셀이 아닌 터미널에서 실행해 주세요.
    print("\n--- Flask 서버 구동 스크립트가 app.py 파일로 저장되었습니다. ---")
    
    app.run(host='0.0.0.0', debug=True) # 서버 실행 코드는 주석 처리
