import streamlit as st
import openai
import os
from dotenv import load_dotenv
import re
import json
from datetime import date as _date, timedelta
import requests


load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_travel_suggestion(mood, companion, location_type, budget, duration, residence, free_request, start_date=None, trip_days=None):
    """3つの旅行先をJSON形式で提案する関数"""
    try:
        system_prompt = (
            "あなたは日本の優れた旅行コンシェルジュです。"
            "ユーザーの要望に基づいて、おすすめの旅行先を「3つ」提案してください。"
            "必ず'suggestions'というキーを持つ単一のJSONオブジェクトとして回答してください。"
            "そのキーの値は、以下のキーを持つオブジェクトのリストです。\n"
            "{\n"
            '  "suggestions": [\n'
            "  {\n"
            '    "場所": "国、都道府県、そして緯度経度が特定しやすい具体的な地名（例：神奈川県 箱根町 箱根湯本、長野県 軽井沢町）",\n'
            '    "概要": "旅行先の特徴や魅力を簡潔に説明(100字程度)",\n'
            '    "理由": "なぜその場所をおすすめするのか、具体的な説明(150字程度)",\n'
            "   }\n"
            "]\n"
            "}\n"
            "説明や前置きは一切不要です。JSONデータのみを出力してください。"
        )

        user_request = (
            f"現在地は「{residence}」です。"
            f"旅行のメンバーは「{companion}」で、期間は「{duration}」、"
            f"一人当たりの予算は「{budget}」です。"
            f"気分は「{mood}」で、場所は「{location_type}」の中からお願いします。"
        )
        if free_request:
            user_request += f"\nその他、以下の具体的な要望があります。「{free_request}」。この要望を最優先してください。"

        user_request += "\nこれらの情報をもとに、最適な旅行先を提案してください。"

        response = openai.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_request}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        response_content = response.choices[0].message.content
        if response_content:
            response_json = json.loads(response_content)
            return response_json.get("suggestions", [])
        else:
             return None

    except Exception as e:
        st.error(f"提案の生成中にエラーが発生しました: {e}")
        return None

def generate_itinerary_response(messages):
    """会話履歴に基づいてプランの応答を生成する関数"""
    try:    
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1500,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"エラーが発生しました: {e}"

WEATHER_MAP = {
     0:"快晴", 1:"ほぼ快晴", 2:"晴れ/薄曇り", 3:"曇り",
     45:"霧", 48:"霧(着氷)", 
     51:"弱い霧雨", 53:"霧雨", 55:"強い霧雨",
     61:"小雨", 63:"雨", 65:"大雨",
     71:"小雪", 73:"雪", 75:"大雪",
     80:"にわか小雨", 81:"にわか雨", 82:"にわか大雨",
     95:"雷雨", 96:"雷雨(雹小)", 99:"雷雨(雹強)",
}

# @st.cache_data(ttl=3600)
# def geocode(place_name: str):
#     try:
#         r = requests.get(
#             "https://geocoding-api.open-meteo.com/v1/search",
#             params={"name": place_name, "count": 1, "language": "ja", "format": "json"},
#             timeout=8,
#         )
#         r.raise_for_status()
#         data = r.json()
#         if not data.get("results"):
#             return None
#         res = data["results"][0]
#         out = {"lat": res["latitude"], "lon": res["longitude"]}
#         st.write({"DEBUG_geocode": {"place": place_name, "result": out}})
#         return out
#     except Exception as e:
#         st.exception(e) #例外内容を表示
#         return None

@st.cache_data(ttl=900)
def fetch_weather(
    lat: float,
    lon: float, 
    days: int = 16,
    start_date: _date | None = None,
    trip_days: int | None = None
    ):

    # Open-Meteo APIのデフォルト仕様：
    # 予報データは「今日から最大7日間」取得可能。  
    # 最大16日先まで取得したい場合は、forecast_days等で指定が必要
    # start_date / end_date を使う場合は forecast_days と併用しない

    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto"
        }
        if start_date:
            span = (trip_days if trip_days and trip_days > 0 else days)
            span = min(span, 16)  # 最大16日まで取得可能
            end_dt = start_date + timedelta(days=span - 1)
              
            params["start_date"] = start_date.isoformat()
            params["end_date"] = end_dt.isoformat()
        else:
            params["forecast_days"] = min(int(days), 16)

        # st.write({"DEBUG_fetch_params": params})
        r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=8)
        # st.write({"DEBUG_status": r.status_code})
        if r.status_code >= 400:
             st.write({"DEBUG_error_body": r.text})
        r.raise_for_status()
        data =  r.json()
        # dailyが無い/空のときも見える化
        if not data.get("daily"):
            st.write({"fetch_weather": "dailyが空/無し"})
        return data
    except Exception as e:
        st.exception(e)
        return None

def parse_trip_days(duration_str: str) -> int:
    mapping = {
        "日帰り": 1,
        "1泊2日": 2,
        "2泊3日": 3,
        "3泊4日": 4,
        "4泊5日": 5,
        "5泊6日": 6,
        "一週間以上": 7
    }
    return mapping.get(duration_str, 1)

def _tidy_place(name: str) -> str:
    if not isinstance(name, str):
         return ""
    for sep in ("（", "("):
        if sep in name:
            name = name.split(sep)[0]
    for term in ("周辺", "エリア", "あたり"):
        if term in name:
            name = name.replace(term, "")
    return name.strip()

@st.cache_data(ttl=3600)
def geocode(place_name: str):
    """国土地理院 Address Search API で日本語地名から座標を取得"""
    try:
        q = _tidy_place(place_name)
        if not isinstance(q, str) or not q.strip():
            st.warning({"GEOCODE_INVALID_NAME": str(place_name)})
            return None
        
        r = requests.get(
            "https://msearch.gsi.go.jp/address-search/AddressSearch",
            params={"q": q},
            timeout=8,
        )
        # st.write({"DEBUG_geocode_gsi_status": r.status_code, "q": q})
        if r.status_code >= 400:
            st.write({"DEBUG_geocode_gsi_body": r.text})
        r.raise_for_status()

        data = r.json()

        if not isinstance(data, list) or not data:
            st.info(f"{q}の緯度経度を取得できませんでした。")
            return None
        
        feat = data[0]
        coords = (feat.get("geometry") or {}).get("coordinates")
        if not coords or len(coords) < 2:
            st.info("座標の形式が不正です。")      
            return None
        
        lon, lat = coords[0], coords[1]
        out = {"lat": lat, "lon": lon}
        # st.write({"DEBUG_geocode_gsi_result": {"q": q, "result": out}})
        return out

    except Exception as e:
        st.exception(e)
        return None

def weather_badge(
    place_name: str,
    start_date: _date | None = None,
    trip_days: int = 1,
    days_to_fetch: int = 16,
    days_to_show: int = 3
):

    # st.write({"DEBUG_weather_badge": place_name, "type": str(type(place_name))})
    q = _tidy_place(place_name)
    if not q:
        st.info("地名が空です。")
        return

    geo = geocode(q)
    if not geo:
         st.info(f"{q}の緯度経度を取得できませんでした。")
         return
    
    data = fetch_weather(
        geo["lat"],
        geo["lon"],
        days=days_to_fetch,
        start_date=start_date,
        trip_days=trip_days
    )
    if not data:
         st.info("天気情報を取得できませんでした。")
         return
    
    current = data.get("current", {})
    daily = data.get("daily", {})
    cond = WEATHER_MAP.get(current.get("weather_code"), "不明")

    st.markdown(
         f"**現在の天気**: {cond} **現在気温**: {current.get('temperature_2m')}°C, 風速: {current.get('wind_speed_10m')} m/s"
         )

    all_days = daily.get("time", []) or []
    all_tmax = daily.get("temperature_2m_max", []) or []
    all_tmin = daily.get("temperature_2m_min", []) or []
    all_codes = daily.get("weather_code", []) or []

    n = min(days_to_show, len(all_days), len(all_tmax), len(all_tmin), len(all_codes))
    days = all_days[:n]
    tmax = all_tmax[:n]
    tmin = all_tmin[:n]
    codes = all_codes[:n]

    highlight_set = set()
    if start_date:
        for i in range(max(trip_days, 1)):
            highlight_set.add((start_date + timedelta(days=i)).isoformat())
        if days and not any(d in highlight_set for d in days):
            nearest = min(days, key=lambda d: abs(_date.fromisoformat(d) - start_date))
            highlight_set = {nearest}
    
    rows = []
    for i, d in enumerate(days):
        label = WEATHER_MAP.get(codes[i], "不明")
        line = f"{d} : {label} ({tmin[i]}°C ~ {tmax[i]}°C)"
        line = f"**▶{line} ← 旅行日**" if d in highlight_set else f"- {line}"
        rows.append(line)

    st.markdown(f"**日次予報（表示 {n} 日分）**\n" + "\n".join(rows))
 
def handle_plan_click(location_name):
     """詳細プランボタンが押されたときの処理"""
     st.session_state.selected_location = location_name
     st.session_state.messages = []

def clean_markdown_for_download(text):
    """ダウンロード用にMarkdown記法をプレーンテキストに変換する"""
    # Markdownリンク[テキスト](URL)をテキスト(URL)に変換
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1 (\2)', text)
    #  見出し記号(#)を削除
    text = re.sub(r'#+\s*', '', text)
    #  太字記号(**)を削除
    text = text.replace('**', '')
    #  箇条書き記号(* or -)を削除
    text = re.sub(r'^\s*[\*\-]\s*', '', text, flags=re.MULTILINE)
    return text


st.title("旅行先提案アプリ")

if 'suggestions' not in st.session_state:
    st.session_state.suggestions = None
if "user_inputs" not in st.session_state:
    st.session_state.user_inputs = {}
if "messages" not in st.session_state:
    st.session_state.messages = []
if 'selected_location' not in st.session_state:
    st.session_state.selected_location = None


with st.sidebar:

    st.header("あなたの希望を教えてください")

    selected_residence = st.text_input("あなたの居住地は？(例：東京都、大阪府など)", "東京都")

    companion_options = ["友人", "家族", "恋人", "一人旅", "ペットと"]
    select_companion = st.selectbox("旅行のメンバーは？", companion_options)

    selected_start_date = st.date_input("旅行の開始日は？", value=_date.today())

    duration_options = ["日帰り", "1泊2日", "2泊3日", "3泊4日", "4泊5日", "5泊6日", "一週間以上"]
    selected_duration = st.selectbox("旅行の期間は？", duration_options)

    trip_days_int = parse_trip_days(selected_duration)

    budget_options = ["気にしない", "1万円以下", "1万円〜3万円", "3万円〜5万円", "5万円～10万円", "10万円以上"]
    selected_budget = st.selectbox("一人当たりの予算はいくら？", budget_options)

    mood_options = ["のんびりリラックス", "アクティブ", "ロマンティック", "文化体験", "自然探索", "食べ歩き"]
    selected_mood = st.selectbox("旅行の気分は？", mood_options)

    location_type = st.radio("行き先のタイプは？", ("国内", "海外"), horizontal=True)

    free_request_text = st.text_area("その他の具体的な要望があれば入力してください（例：〇〇に行きたい、海鮮が美味しい宿がいい、など）", "")

    if st.button("旅行先を提案", type="primary"):
        if not selected_residence:
            st.error("居住地を入力してください。")
        elif not openai.api_key:
            st.error("OpenAIのAPIキーが設定されていません。環境変数を確認してください。")
        else:
            st.session_state.user_inputs = {
                "mood": selected_mood,
                "companion": select_companion,
                "location_type": location_type,
                "budget": selected_budget,
                "duration": selected_duration,
                "residence": selected_residence,
                "free_request": free_request_text,
                "start_date": selected_start_date.isoformat(),
                "trip_days": trip_days_int
            }
            
            with st.spinner("提案を生成中..."):
                suggestion_list = generate_travel_suggestion(**st.session_state.user_inputs)
                st.session_state.suggestions = suggestion_list
                st.session_state.messages = []
                st.session_state.selected_location = None

if st.session_state.suggestions:
    st.markdown("### 提案された旅行先")
    for i, suggestion in enumerate(st.session_state.suggestions):
        st.subheader(f"提案 {i + 1}")

        st.markdown(f"**場所**: {suggestion.get('場所', 'N/A')}")
        st.markdown(f"**概要**: {suggestion.get('概要', 'N/A')}")
        st.markdown(f"**理由**: {suggestion.get('理由', 'N/A')}")

        location_name = suggestion.get("場所")
        if location_name:
            with st.expander("現地の天気（先3日）を表示", expanded=False):
                weather_badge(
                    location_name,
                    start_date=selected_start_date,
                    trip_days=trip_days_int,
                    days_to_fetch=16,
                    days_to_show=3  
                )
                
            st.button(f"「{location_name}」の詳細プランを見る",
                       key=f"plan_button_{i}",
                       on_click=handle_plan_click,
                         args=(location_name,)
                     )
            
if st.session_state.selected_location and not st.session_state.messages:
            location_name = st.session_state.selected_location
            user_inputs = st.session_state.user_inputs

            start_dt = _date.fromisoformat(user_inputs["start_date"])
            trip_days_int = user_inputs.get("trip_days", parse_trip_days(user_inputs["duration"]))

            st.markdown("#### 現地の天気（参考）")
            weather_badge(
                location_name,
                start_date=start_dt,
                trip_days=trip_days_int,
                days_to_fetch=16,
                days_to_show=3
            )

            system_prompt = ("あなたはプロの優れた旅行プランナーです。"
                             "**これから指定する「旅行先」は絶対に遵守してください。他の場所のプランを提案してはいけません。**\n"
                 "指定された場所と期間で、魅力的で具体的なモデルコースを提案してください。\n"
                "タイムスケジュール（例：午前9時〜10時、午前10時〜11時など）と、"
                 "各時間帯のアクティビティや訪問地、おすすめの食事場所などをその魅力が伝わるように詳しく、そして具体的に記載してください。"
                        "**重要**: 提案するレストラン、ホテル、観光施設などの固有名詞には、必ずGoogle検索用のURLをMarkdown形式でリンク付けしてください。例: `[東京スカイツリー](https://www.google.com/search?q=東京スカイツリー)`\n"
                         "箇条書きと見出しを使って、分かりやすく記述してください。"
                    )
            if user_inputs["companion"] == "ペットと":
                         system_prompt += "\n**重要**: 必ずペット同伴が可能な施設（レストラン、観光地、宿泊施設など）のみを選らんでください。ペット不可の場所は提案に含めないでください。"

            user_request = (
                        f"旅行先は「{location_name}」に決定しました。"
                        f"現在地は「{user_inputs['residence']}」です。"
                        f"旅行のメンバーは「{user_inputs['companion']}」で、期間は「{user_inputs['duration']}」、"
                        f"一人当たりの予算は「{user_inputs['budget']}」です。"
                        f"気分は「{user_inputs['mood']}」で、場所は「{user_inputs['location_type']}」の中からお願いします。"
                    )
            if user_inputs["free_request"]:
                        user_request += f"\nその他、以下の具体的な要望があります。「{user_inputs['free_request']}」。この要望を最優先してください。"

            st.session_state.messages.append({"role": "system", "content": system_prompt})
            st.session_state.messages.append({"role": "user", "content": user_request})

            with st.spinner(f"「{location_name}」のプランを生成中..."):
                ai_response = generate_itinerary_response(st.session_state.messages)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                st.rerun()

if st.session_state.messages:
    st.markdown("### 詳細な旅行プラン（AIと相談）")
    for message in st.session_state.messages:
        if message["role"] != "system":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    if prompt := st.chat_input("AIに質問やリクエストを入力してください。(例: 「もっとアクティブな予定にして」など)"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("プランを修正中です..."):
            ai_response = generate_itinerary_response(st.session_state.messages)
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            st.rerun()
    st.divider()

    final_plan = ""
    for message in reversed(st.session_state.messages):
         if message["role"] == "assistant":
            final_plan = message["content"]
            break
    
    if final_plan:
         download_content = clean_markdown_for_download(final_plan)

    st.download_button(
        label="旅行プランをダウンロード",
        data=download_content,
        file_name="travel_plan.txt",
        mime="text/plain"
    )
