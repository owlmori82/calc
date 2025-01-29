import streamlit as st
import pandas as pd
import datetime
import time
import os


# データを読み込む関数
def load_data(file_name):
    if os.path.exists(file_name):
        return pd.read_csv(file_name, parse_dates=["LastAsked"])
    else:
        return pd.DataFrame(columns=["question", "answer", "correct", "incorrect", "AverageTime", "LastAsked"])


# データを保存する関数
def save_data(df, file_name):
    df.to_csv(file_name, index=False)


# 出題順の決定
def prioritize_questions(df):
    now = datetime.datetime.now()
    df["DaysSinceLastAsked"] = df["LastAsked"].apply(
        lambda x: (now - pd.to_datetime(x)).days if pd.notnull(x) else float("inf")
    )
    df["Accuracy"] = df["correct"] / (df["correct"] + df["incorrect"])
    df["Accuracy"] = df["Accuracy"].fillna(0)
    df = df.sort_values(
        by=["level","DaysSinceLastAsked", "Accuracy", "AverageTime"], ascending=[True,False, True, False]
    ).drop(columns=["DaysSinceLastAsked"])
    return df

# Streamlitアプリのメイン部分
def main():
    st.title("計算力強化アプリ")
 
    uploaded_file = st.file_uploader("ファイルをアップロードしてください（例: flash_card.csv）", type=["csv"])
    data_path = "./data/flash_card.csv"
    
    if "read_file" not in st.session_state:
        st.session_state.read_file = False
        
    if (uploaded_file is not None) & (st.session_state.read_file == False):
        st.success("ファイルがアップロードされました。")
        df = pd.read_csv(uploaded_file)
        save_data(df,data_path)
        st.session_state.read_file = True
    else:
        st.info("デフォルトのファイル (./data/flash_card.csv) を使用します。")
        try:
            df = load_data(data_path)
        except FileNotFoundError:
            st.error("デフォルトのファイルが見つかりません。アプリを終了します。")
            st.stop()

    # セッション状態の初期化
    if "start_time" not in st.session_state:
        st.session_state.start_time = None
    if "current_index" not in st.session_state:
        st.session_state.current_index = 0
        df = prioritize_questions(df)
    if "Asked_time" not in st.session_state:
        st.session_state.Asked_time = 0
    
    # 問題の出題
    if (st.session_state.current_index < len(df)) & (st.session_state.Asked_time < 21):
        current_question = df.iloc[st.session_state.current_index]
        st.write(f"**問題:** {current_question['question']}")
        st.session_state.start_time = time.time()
        st.session_state.Asked_time += 1
        
        # 回答入力
        with st.form(key = 'input_answer',clear_on_submit=True):
            answer = st.text_input("答えを入力してください")
    
            submit_button = st.form_submit_button("回答を送信")
            if submit_button:
                end_time = time.time()
                response_time = end_time - st.session_state.start_time
            
                if str(answer) == str(current_question["answer"]):
                    st.success("正解！")
                    df.loc[st.session_state.current_index, "correct"] += 1
                    time.sleep(1)
                else:
                    st.error(f"不正解！正解は {current_question['answer']} です。")
                    df.loc[st.session_state.current_index, "incorrect"] += 1
                    time.sleep(2)
                # 平均時間の更新
                current_avg_time = df.loc[st.session_state.current_index, "AverageTime"]
                df.loc[st.session_state.current_index, "AverageTime"] = (
                    (current_avg_time * (df.loc[st.session_state.current_index, "correct"] +
                                        df.loc[st.session_state.current_index, "incorrect"] ) + response_time)
                    / (df.loc[st.session_state.current_index, "correct"] + df.loc[st.session_state.current_index, "incorrect"])
                )
                df.loc[st.session_state.current_index, "LastAsked"] = datetime.datetime.now()
                save_data(df, data_path)
                st.session_state.current_index += 1
                st.rerun()    
    else:
        st.write("すべての問題が終了しました！")

    # 結果のダウンロード
    st.download_button(
        label="結果をダウンロード",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="updated_questions.csv",
        mime="text/csv"
    )

    # 終了ボタン
    if st.button("終了"):
        save_data(df, data_path)
        st.session_state.read_file = False
        st.success("記録を保存しました！お疲れ様でした。")
        st.stop()


if __name__ == "__main__":
    main()
