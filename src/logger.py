import os
import io
import pandas as pd
from datetime import datetime
import streamlit as st
from streamlit_gsheets import GSheetsConnection

LOGS_DIR = os.path.join("data", "logs_simulaciones")
MASTER_EXCEL_PATH = os.path.join(LOGS_DIR, "Icesi_Writing_Lab_Master_Logs.xlsx")

def ensure_logs_directory():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)

def save_interaction_gsheet(session_id, student_name, student_code, student_profile, turn, user_message, ai_response):
    """Guarda la interacción localmente en Excel y sincroniza directamente con Google Sheets."""
    ensure_logs_directory()
    
    new_record = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Session ID": session_id,
        "Student Name": student_name,
        "Student Code": student_code,
        "Student Profile": student_profile,
        "Interaction Turn": turn,
        "Student Message (Simulated)": user_message,
        "AI Tutor Response": ai_response
    }
    
    df_new = pd.DataFrame([new_record])
    
    # 1. Persistencia local en archivo Excel (para el perfil del Teacher)
    if not os.path.exists(MASTER_EXCEL_PATH):
        df_new.to_excel(MASTER_EXCEL_PATH, index=False, engine="openpyxl")
    else:
        try:
            df_existing = pd.read_excel(MASTER_EXCEL_PATH, engine="openpyxl")
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_excel(MASTER_EXCEL_PATH, index=False, engine="openpyxl")
        except Exception:
            df_new.to_excel(MASTER_EXCEL_PATH, index=False, engine="openpyxl")

    # 2. Persistencia en la nube (Google Sheets con GSheetsConnection)
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Lee los datos actuales desactivando la caché
        existing_data = conn.read(ttl=0)
        
        # Si la hoja está vacía o el DataFrame no contiene datos/columnas
        if existing_data is None or existing_data.empty:
            updated_df = df_new
        else:
            updated_df = pd.concat([existing_data, df_new], ignore_index=True)
        
        # Actualiza la hoja de cálculo
        conn.update(data=updated_df)
    except Exception as e:
        st.warning(f"Note: Cloud backup sync skipped ({e})")


def generate_excel_bytes(dataframe):
    """Genera el archivo de Excel descargable en memoria con dos pestañas para el perfil de Teacher."""
    output = io.BytesIO()
    
    summary_df = dataframe.groupby("Session ID").agg(
        Student_Name=("Student Name", "first"),
        Student_Code=("Student Code", "first"),
        Student_Profile=("Student Profile", "first"),
        Total_Turns=("Interaction Turn", "max"),
        Start_Time=("Timestamp", "min"),
        End_Time=("Timestamp", "max")
    ).reset_index()
    
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Sessions Summary", index=False)
        dataframe.to_excel(writer, sheet_name="Detailed Turn Logs", index=False)
        
    return output.getvalue()