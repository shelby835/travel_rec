import streamlit as st
import openai
import os
from dotenv import load_dotenv
import re

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_travel_suggestion(mood, companion, location_type, budget, duration, residence, free_request):
    """3つの旅行先を提案する関数"""
    try:
        system_prompt = (
            "あなたは日本の優れた旅行コンシェルジュです。"
            "ユーザーの要望に基づいて、おすすめの旅行先を「3つ」提案してください。"
            "それぞれの提案には、以下の要素を必ず含めてください。\n"
            "・【場所】：国、都道府県、具体的な地名\n"
            "・【特徴】：その場所の特徴や魅力（100字程度）\n"
            "・【理由】：なぜその場所をおすすめするのか、具体的な説明（150字程度）\n"
            "提案と提案の間は、必ず『---』で区切ってください。"
            "**前置きや説明は一切不要です。**"
        )

        user_request = (
            f"現在地は「{residence}」です。"
            f"旅行のメンバーは「{companion}」で、期間は「{duration}」、"
            f"一人当たりの予算は「{budget}」です。"
            f"気分は「{mood}」で、場所は「{location_type}」の中からお願いします。"
            f"これらの情報をもとに、最適な旅行先を提案してください。"
                      )
        if free_request:
            user_request += f"\nその他、以下の具体的な要望があります。「{free_request}」。この要望を最優先してください。"

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_request}
            ],
            max_tokens=800,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"エラーが発生しました: {e}"

def generate_itinerary_response(messages):
    """会話履歴に基づいてプランの応答を生成する関数"""
    try:    
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"エラーが発生しました: {e}"

st.title("旅行先提案アプリ")

if 'suggestions' not in st.session_state:
    st.session_state.suggestions = None
if "user_inputs" not in st.session_state:
    st.session_state.user_inputs = {}
if "messages" not in st.session_state:
    st.session_state.messages = []


with st.sidebar:

    st.header("あなたの希望を教えてください")

    selected_residence = st.text_input("あなたの居住地は？(例：東京都、大阪府など)", "東京都")

    companion_options = ["友人", "家族", "恋人", "一人旅", "ペットと"]
    select_companion = st.selectbox("旅行のメンバーは？", companion_options)

    duration_options = ["日帰り", "1泊2日", "2泊3日", "3泊4日", "4泊5日", "5泊6日", "一週間以上"]
    selected_duration = st.selectbox("旅行の期間は？", duration_options)

    budget_options = ["気にしない", "1万円以下", "1万円〜3万円", "3万円〜5万円", "5万円～10万円", "10万円以上"]
    selected_budget = st.selectbox("一人当たりの予算はいくら？", budget_options)

    mood_options = ["のんびりリラックス", "アクティブ", "ロマンティック", "文化体験", "自然探索", "食べ歩き"]
    selected_mood = st.selectbox("旅行の気分は？", mood_options)

    location_type = st.radio("行き先のタイプは？", ("国内", "海外"), horizontal=True)

    free_request_text = st.text_area("その他の具体的な要望があれば入力してください（例：〇〇に行きたい、海鮮が美味しい宿がいい、など）", "")

    if st.button("提案を生成", type="primary"):
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
                "free_request": free_request_text
            }
            with st.spinner("提案を生成中..."):
                suggestion_text= generate_travel_suggestion(**st.session_state.user_inputs)
                st.session_state.suggestions = suggestion_text.split("---")
                st.session_state.messages = []

if st.session_state.suggestions:
    st.markdown("### 提案された旅行先")
    for i, suggestion in enumerate(st.session_state.suggestions):
        if suggestion.strip() and "【場所】" in suggestion:
            st.subheader(f"提案 {i + 1}")
            formatted_suggestion = suggestion.strip().replace("\n","\n\n")
            st.markdown(formatted_suggestion)

            match = re.search(r"【場所】\s*[:：]\s*(.*)", suggestion)
            if match:
                location_name = match.group(1).strip()
                if st.button(f"「{location_name}」の詳細プランを見る", key=f"plan_button_{i}"):
                    
                    st.session_state.messages = []
                    user_inputs = st.session_state.user_inputs
                    system_prompt = ("あなたはプロの優れた旅行プランナーです。"
                         "指定された場所と期間で、魅力的で具体的なモデルコースを提案してください。\n"
                        "タイムスケジュール（例：午前9時〜10時、午前10時〜11時など）と、"
                         "各時間帯のアクティビティや訪問地、おすすめの食事場所などを具体的に記載してください。"
                        "**重要**: 提案するレストラン、ホテル、観光施設などの固有名詞には、必ずGoogle検索用のURLをMarkdown形式でリンク付けしてください。例: `[東京スカイツリー](https://www.google.com/search?q=東京スカイツリー)`\n"
                         "箇条書きと見出しを使って、分かりやすく記述してください。"
                    )
                    if user_inputs["companion"] == "ペットと":
                         system_prompt += "\n**重要**: 必ずペット同伴が可能な施設（レストラン、観光地、宿泊施設など）のみを選らんでください。ペット不可の場所は提案に含めないでください。"

                    user_request = (
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

    download_content = ""
    for message in st.session_state.messages:
        if message["role"] == "user":
            download_content += f"ユーザーの入力:\n{message['content']}\n\n"
        if message["role"] == "assistant":
            download_content += f"AIの応答:\n{message['content']}\n\n"

    st.download_button(
        label="旅行プランをダウンロード",
        data=download_content,
        file_name="travel_plan.txt",
        mime="text/plain"
    )
