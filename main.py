import streamlit as st
import pandas as pd
import datetime
import time
from supabase import create_client, Client
from st_supabase_connection import SupabaseConnection

# Supabaseの設定
# Initialize connection.
# Uses st.cache_resource to only run once.
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)
#    return st.connection("supabase",type=SupabaseConnection)

# データを読み込む関数
def load_data(conn,TABLE_NAME):
    response = conn.table(TABLE_NAME).select("*").execute()
    df = pd.DataFrame(data = response.data)
    df["LastAsked"] = pd.to_datetime(df["LastAsked"])
    return df
    
    
# データを保存する関数
def save_data(df,conn,TABLE_NAME):
    df_tmp = df.copy()
    df_tmp["LastAsked"] = df_tmp["LastAsked"].astype(str)
    df_tmp = df_tmp.astype({
    "id": "int64",
    "level": "int64",
    "question": "string",  # 文字列型を明示
    "answer": "int64",
    "correct": "int64",
    "incorrect": "int64",
    "AverageTime": "float64",
    "LastAsked": "string",  # ISO 8601 形式に変換済みの文字列
    "Accuracy": "float64"
    })
    for _, row in df_tmp.iterrows():
        #st.write(row.to_dict())
        conn.table(TABLE_NAME).upsert(row.to_dict()).execute()

# 出題順の並び替え
def sort_priority(sub_df):
    # (1) 出題回数 0 のものを最優先（出題日が古い順）
    pri_1 = sub_df[sub_df["TimesAsked"] == 0].sort_values(by=["DaysSinceLastAsked"])

    # (2) 出題回数 2 回以下のもの（出題日が古い順）
    pri_2 = sub_df[(sub_df["TimesAsked"] > 0) & (sub_df["TimesAsked"] <= 2)].sort_values(by=["DaysSinceLastAsked"])

    # (3) 出題回数 3 回以上のもの（Accuracy が低く、出題日が古い順）
    pri_3 = sub_df[sub_df["TimesAsked"] >= 3].sort_values(by=["Accuracy", "DaysSinceLastAsked"], ascending=[True, True])

    # 優先順位で結合
    return pd.concat([pri_1, pri_2, pri_3])

#回答結果を更新
def update_data(rec,df):
    # 更新前のデータ型を保存
    rec["LastAsked"] = datetime.datetime.now()
    df = df.astype(str)
    update_row = pd.DataFrame(rec,index = rec.index).T.astype(str)
    df = pd.concat([df,update_row])
    return df

def prioritize_questions(df):
    now = datetime.datetime.now()
    df["TimesAsked"] = df["correct"] + df["incorrect"]
    df["DaysSinceLastAsked"] = df["LastAsked"].apply(lambda x: (now - x).days if pd.notnull(x) else float("inf"))
    
    df_top = pd.DataFrame()
    df_left = pd.DataFrame()
    for level in df["level"].unique():
        df_tmp = sort_priority(df[df["level"] == level])
        df_top = pd.concat([df_top, df_tmp.head(10)])
        df_left = pd.concat([df_left, df_tmp.iloc[10:]])
    
    df = pd.concat([df_top, df_left])
    df = df.drop(columns=["DaysSinceLastAsked", "TimesAsked"])
    return df

# Streamlitアプリのメイン部分
def main():
    st.title("計算力強化アプリ")
    
    #初期化
    if "read_file" not in st.session_state:
        st.session_state.read_file = False
    if "data" not in st.session_state:
        st.session_state.data = None
    if "start_time" not in st.session_state:
        st.session_state.start_time = None
    if "current_index" not in st.session_state:
        st.session_state.current_index = 0
    if "Asked_time" not in st.session_state:
        st.session_state.Asked_time = 0
    if "update_data" not in st.session_state:
        st.session_state.update_data = pd.DataFrame(columns=['id','level','question','answer','correct','incorrect','AverageTime','LastAsked','Accuracy'])
    
    #データベースから取得
    conn = init_connection()
    TABLE_NAME = "flashcards"
    #データベースから取得して初期ロード
    if st.session_state.read_file == False:
        st.session_state.data = load_data(conn,TABLE_NAME)
        st.session_state.data = prioritize_questions(st.session_state.data)
        st.session_state.read_file = True
    #問題の優先順を変更して出題する    
    if (st.session_state.current_index < len(st.session_state.data)) & (st.session_state.Asked_time < 31):
        current_question = st.session_state.data.iloc[st.session_state.current_index]
        st.write(f"**問題:** {current_question['question']}")
        st.session_state.start_time = time.time()
               
        with st.form(key='input_answer', clear_on_submit=True):
            answer = st.text_input("答えを入力してください")
            submit_button = st.form_submit_button("回答を送信")
            
            if submit_button:
                end_time = time.time()
                response_time = end_time - st.session_state.start_time
                
                if str(answer) == str(current_question["answer"]):
                    st.success("正解！")
                    current_question["correct"] += 1
                    time.sleep(1)
                else:
                    st.error(f"不正解！正解は {current_question['answer']} です。")
                    current_question["incorrect"] += 1
                    time.sleep(2)
                
                current_avg_time = current_question["AverageTime"]
                current_question["AverageTime"] = (
                    (current_avg_time * (current_question["correct"] + current_question["incorrect"] ) + response_time)
                    / (current_question["correct"] + current_question["incorrect"])
                )
                st.session_state.Asked_time += 1
                st.session_state.update_data = update_data(current_question,st.session_state.update_data)
                st.session_state.current_index += 1
                st.rerun()
    else:
        st.write("すべての問題が終了しました！終了ボタンを押してください。")

    #finish
    if st.button("終了"):
        save_data(st.session_state.update_data,conn,TABLE_NAME)
        st.session_state.read_file = False
        st.success("記録を保存しました！お疲れ様でした。")
        st.stop()
    
    st.write("--------メンテナンス----------------")
    #ファイルのアップロード
    uploaded_file = st.file_uploader("データを更新するときはファイルをアップロードしてください", type=["csv"])
        
    #uploadファイルがあるときはそのファイルでデフォルトデータを更新する。    
    if  uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        save_data(df,conn,TABLE_NAME)
        st.success("ファイルがアップロードされ、データが更新されました。")
        
    st.download_button(
        label="結果をダウンロード",
        data=st.session_state.data.to_csv(index=False).encode("utf-8"),
        file_name="updated_questions.csv",
        mime="text/csv"
    )
    
if __name__ == "__main__":
    main()