import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import streamlit as st
from groq import Groq
import uuid
import pandas as pd

from prompt_builder import build_system_prompt
from logger import save_interaction_gsheet

st.set_page_config(
    page_title="Icesi Writing Lab", 
    page_icon="📝", 
    layout="wide"
)


try:
    api_key = st.secrets["GROQ_API_KEY"].strip()
    model_name = st.secrets.get("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
except Exception:
    api_key = ""
    model_name = "qwen/qwen3.8-27b"

if not api_key:
    st.error("GROQ_API_KEY is missing or invalid in `.streamlit/secrets.toml`.")
    st.stop()

client = Groq(api_key=api_key)

st.sidebar.title("Navigation")
app_mode = st.sidebar.radio("Go to:", ["Student Writing Lab", "Teacher Dashboard (Admin)"])

# MODE 1: STUDENT WRITING LAB

if app_mode == "Student Writing Lab":
    st.title("Icesi Writing Lab")
    st.caption("AI-Powered English Writing Feedback & Simulation Environment")

    st.sidebar.header("Student / Simulation Setup")
    
    # 1. Student Identification Form
    student_name = st.sidebar.text_input("Student / Evaluator Full Name:", value=st.session_state.get("student_name", ""))
    student_code = st.sidebar.text_input("Student ID / Code:", value=st.session_state.get("student_code", ""))
    
    student_profile = st.sidebar.selectbox(
        "Select Student Profile:",
        [
            "Profile A: Basic / Subject-Verb Agreement Errors", 
            "Profile B: Intermediate / Verb Tense Errors", 
            "Profile C: Persistent / Repeated Errors"
        ]
    )

    if "session_id" not in st.session_state:
        st.session_state.session_id = f"sim_{uuid.uuid4().hex[:8]}"

    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.turn = 0

    st.session_state.student_name = student_name
    st.session_state.student_code = student_code

    st.sidebar.info(
        f"**Session ID:** `{st.session_state.session_id}`\n\n"
        f"**Current Turn:** {st.session_state.turn}"
    )

    if st.sidebar.button("Reset Session"):
        st.session_state.session_id = f"sim_{uuid.uuid4().hex[:8]}"
        st.session_state.messages = []
        st.session_state.turn = 0
        st.rerun()

    # Require student identification before starting chat
    if not student_name or not student_code:
        st.warning("Please enter your Full Name and Student ID in the sidebar to begin the session.")
        st.stop()

    # Render Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    if prompt := st.chat_input("Type your draft or simulated student response here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        st.session_state.turn += 1
        
        system_prompt = build_system_prompt()
        conversation_history = [{"role": "system", "content": system_prompt}] + [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
        ]
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing text and generating pedagogical feedback..."):
                response = client.chat.completions.create(
                    model=model_name,
                    messages=conversation_history,
                    temperature=0.3,
                    max_tokens=500,
                )
                ai_response = response.choices[0].message.content
                st.markdown(ai_response)
        
        st.session_state.messages.append({"role": "assistant", "content": ai_response})
        
        save_interaction_gsheet(
            session_id=st.session_state.session_id,
            student_name=student_name,
            student_code=student_code,
            student_profile=student_profile,
            turn=st.session_state.turn,
            user_message=prompt,
            ai_response=ai_response
        )


# MODE 2: TEACHER DASHBOARD (ADMIN)

elif app_mode == "Teacher Dashboard (Admin)":
    st.title("Teacher Dashboard")
    st.caption("Review all student simulation sessions and export formatted Excel reports.")
    
    admin_password = st.text_input("Enter Teacher Admin Password:", type="password")
    expected_password = st.secrets.get("TEACHER_PASSWORD", "Icesiadmins2027")
    
    if admin_password == expected_password:
        st.success("Authenticated successfully as Course Teacher.")
        
        from logger import generate_excel_bytes, MASTER_EXCEL_PATH
        
        if os.path.exists(MASTER_EXCEL_PATH):
            full_df = pd.read_excel(MASTER_EXCEL_PATH, engine="openpyxl")
            
            
            view_type = st.radio("Select View:", ["Session Summary (1 Row per Session)", "Detailed Turn Logs"])
            
            
            selected_profile = st.selectbox("Filter by Profile:", ["All"] + list(full_df["Student Profile"].unique()))
            filtered_df = full_df if selected_profile == "All" else full_df[full_df["Student Profile"] == selected_profile]
            
            if view_type == "Session Summary (1 Row per Session)":
                summary_view = filtered_df.groupby("Session ID").agg(
                    Student_Name=("Student Name", "first"),
                    Student_Code=("Student Code", "first"),
                    Student_Profile=("Student Profile", "first"),
                    Total_Turns=("Interaction Turn", "max"),
                    Start_Time=("Timestamp", "min"),
                    End_Time=("Timestamp", "max")
                ).reset_index()
                st.subheader("Recorded Student Sessions Summary")
                st.dataframe(summary_view, use_container_width=True)
            else:
                st.subheader("Detailed Interaction Logs")
                st.dataframe(filtered_df, use_container_width=True)
            
            
            excel_data = generate_excel_bytes(filtered_df)
            st.download_button(
                label="Download Report .xlsx Excel File",
                data=excel_data,
                file_name="Icesi_Writing_Lab_Sessions_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No student sessions recorded yet.")
            
    elif admin_password:
        st.error("Incorrect password. Please try again.")