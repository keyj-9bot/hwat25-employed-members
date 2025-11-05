# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (최종 안정판 v2)
- 교수/학생 구분 로그인
- 교수: 메시지 등록/수정/삭제/게시
- 학생: 질문 등록/수정/삭제 (파일 다중 등록)
- 파일명 한글/영문 완전 호환
- UTF-8-SIG 기반 CSV 인코딩
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import pandas as pd
import os
from datetime import datetime

# ───────────── 기본 설정 ─────────────
app = Flask(__name__)
app.secret_key = "key_flask_secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATA_EMAILS = os.path.join(BASE_DIR, "employed_allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_MESSAGES = os.path.join(BASE_DIR, "professor_messages.csv")

# ───────────── CSV 로드/저장 ─────────────
def load_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.read_csv(path, encoding="utf-8")

def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8-sig")

# ───────────── 이메일 목록 로드 ─────────────
def load_allowed_emails():
    if not os.path.exists(DATA_EMAILS):
        print(f"[⚠경고] 이메일 파일 없음: {DATA_EMAILS}")
        return []
    with open(DATA_EMAILS, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

allowed_emails = load_allowed_emails()
professor_email = allowed_emails[0] if allowed_emails else None

# ───────────── 홈/로그인 ─────────────
@app.route("/", methods=["GET", "POST"])
def home():
    if not allowed_emails:
        flash("⚠ 이메일 등록 파일이 없습니다.", "danger")
        return render_template("home.html")

    if request.method == "POST":
        email = request.form["email"].strip()
        if email not in allowed_emails:
            flash("❌ 등록되지 않은 이메일입니다.", "danger")
            return render_template("home.html")

        session["email"] = email
        session["role"] = "professor" if email == professor_email else "student"
        flash(f"✅ 로그인 성공: {email}", "success")

        if session["role"] == "professor":
            return redirect(url_for("professor_page"))
        else:
            return redirect(url_for("questions_page"))

    return render_template("home.html")

# ───────────── 교수 페이지 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다.", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_MESSAGES)

    if request.method == "POST":
        msg = request.form.get("message", "").strip()
        if not msg:
            flash("⚠ 메시지를 입력하세요.", "warning")
            return redirect(url_for("professor_page"))

        new_row = pd.DataFrame([{
            "message": msg,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "confirmed": "no"
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_MESSAGES, df)
        flash("📢 메시지가 등록되었습니다.", "success")
        return redirect(url_for("professor_page"))

    return render_template("professor.html", messages=df.to_dict("records"))

@app.route("/confirm_message/<int:index>", methods=["POST"])
def confirm_message(index):
    df = load_csv(DATA_MESSAGES)
    if index < len(df):
        df.loc[index, "confirmed"] = "yes"
        save_csv(DATA_MESSAGES, df)
    flash("📢 게시 확정 완료", "success")
    return redirect(url_for("professor_page"))

@app.route("/edit_message/<int:index>", methods=["POST"])
def edit_message(index):
    df = load_csv(DATA_MESSAGES)
    new_msg = request.form.get("new_message", "").strip()
    if index < len(df):
        df.loc[index, "message"] = new_msg
        df.loc[index, "confirmed"] = "no"
        save_csv(DATA_MESSAGES, df)
    flash("✏️ 메시지가 수정되었습니다.", "info")
    return redirect(url_for("professor_page"))

@app.route("/delete_message/<int:index>", methods=["POST"])
def delete_message(index):
    df = load_csv(DATA_MESSAGES)
    if index < len(df):
        df = df.drop(index)
        save_csv(DATA_MESSAGES, df)
    flash("🗑️ 메시지가 삭제되었습니다.", "warning")
    return redirect(url_for("professor_page"))

# ───────────── 질문 페이지 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("⚠ 로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)
    popup_msg = None

    df_msg = load_csv(DATA_MESSAGES)
    if not df_msg.empty:
        latest_confirmed = df_msg[df_msg["confirmed"] == "yes"]
        if not latest_confirmed.empty:
            popup_msg = latest_confirmed.iloc[-1]["message"]

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if not content:
            flash("⚠ 내용을 입력하세요.", "warning")
            return redirect(url_for("questions_page"))

        files = request.files.getlist("files")
        saved_files = []

        for file in files:
            if file and file.filename:
                filename = file.filename  # ✅ 한글/영문 파일명 그대로
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(save_path)
                saved_files.append(filename)

        file_str = ";".join(saved_files)
        new_row = pd.DataFrame([{
            "email": session["email"],
            "content": content,
            "files": file_str,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df)
        flash("📘 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions_page"))

    return render_template("questions.html", email=session["email"], questions=df.to_dict("records"), popup_msg=popup_msg)

# ───────────── 질문 수정 ─────────────
@app.route("/edit_question/<int:index>", methods=["POST"])
def edit_question(index):
    df = load_csv(DATA_QUESTIONS)
    if index < len(df):
        new_content = request.form.get("new_content", "").strip()
        files = request.files.getlist("files")

        existing_files = df.at[index, "files"] if not pd.isna(df.at[index, "files"]) else ""
        saved_files = existing_files.split(";") if existing_files else []

        for file in files:
            if file and file.filename:
                filename = file.filename
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(save_path)
                saved_files.append(filename)

        df.loc[index, "content"] = new_content
        df.loc[index, "files"] = ";".join(saved_files)
        df.loc[index, "date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_csv(DATA_QUESTIONS, df)

    flash("✏️ 질문이 수정되었습니다.", "info")
    return redirect(url_for("questions_page"))

# ───────────── 질문 삭제 ─────────────
@app.route("/delete_question/<int:index>", methods=["POST"])
def delete_question(index):
    df = load_csv(DATA_QUESTIONS)
    if index < len(df):
        df = df.drop(index)
        save_csv(DATA_QUESTIONS, df)
    flash("🗑️ 질문이 삭제되었습니다.", "warning")
    return redirect(url_for("questions_page"))

# ───────────── 파일 다운로드 ─────────────
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # ✅ UTF-8 파일명 지원 (quote/unquote 제거)
    return send_from_directory(UPLOAD_FOLDER, filename)

# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
