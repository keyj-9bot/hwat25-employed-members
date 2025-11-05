# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Persistent Popup + Editable Questions Version)
- 교수: 메시지 등록/수정/삭제 + 게시확정 시 팝업 (삭제 전까지 유지)
- 취업생: 질문 등록/수정/삭제, 다중 파일 업로드, 한글 파일명 지원
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import pandas as pd
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "key_flask_secret"

# ───────────── 경로 설정 ─────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATA_EMAILS = os.path.join(BASE_DIR, "employed_allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_PROF_MSG = os.path.join(BASE_DIR, "professor_message.csv")

# ───────────── 유틸 함수 ─────────────
def load_emails():
    if not os.path.exists(DATA_EMAILS):
        return []
    with open(DATA_EMAILS, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_csv(path):
    if os.path.exists(path):
        try:
            return pd.read_csv(path, encoding="utf-8")
        except:
            return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame()

def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8-sig")

allowed_emails = load_emails()
prof_email = allowed_emails[0] if allowed_emails else None

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
        session["role"] = "professor" if email == prof_email else "student"

        flash(f"✅ 로그인 성공: {session['role']}", "success")
        return redirect(url_for("professor_page" if session["role"] == "professor" else "questions_page"))

    return render_template("home.html")

# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))

# ───────────── 교수 메시지 관리 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다.", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_PROF_MSG)
    msg = df.iloc[0].to_dict() if not df.empty else None

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        df = pd.DataFrame([{"message": message, "status": "pending", "date": date}])
        save_csv(DATA_PROF_MSG, df)
        flash("💾 메시지가 저장되었습니다.", "info")
        return redirect(url_for("professor_page"))

    return render_template("professor.html", message=msg)

@app.route("/confirm_message", methods=["POST"])
def confirm_message():
    df = load_csv(DATA_PROF_MSG)
    if not df.empty:
        df.at[0, "status"] = "confirmed"
        save_csv(DATA_PROF_MSG, df)
        flash("✅ 게시 완료", "success")
    return redirect(url_for("professor_page"))

@app.route("/edit_message", methods=["POST"])
def edit_message():
    df = load_csv(DATA_PROF_MSG)
    if not df.empty:
        df.at[0, "status"] = "pending"
        save_csv(DATA_PROF_MSG, df)
    flash("✏️ 수정 가능 상태로 전환되었습니다.", "warning")
    return redirect(url_for("professor_page"))

@app.route("/delete_message", methods=["POST"])
def delete_message():
    if os.path.exists(DATA_PROF_MSG):
        os.remove(DATA_PROF_MSG)
    flash("🗑️ 메시지가 삭제되었습니다.", "info")
    return redirect(url_for("professor_page"))

# ───────────── 질문 게시판 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("⚠ 로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        email = session["email"]
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        uploaded_files = request.files.getlist("files")
        filenames = []
        for f in uploaded_files:
            if f and f.filename:
                fname = secure_filename(f.filename)
                path = os.path.join(UPLOAD_FOLDER, fname)
                f.save(path)
                filenames.append(fname)
        files_str = ";".join(filenames)

        new_id = int(df["id"].max() + 1) if not df.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id, "email": email,
            "title": title, "content": content,
            "files": files_str, "date": date
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df)
        flash("📘 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions_page"))

    msg_df = load_csv(DATA_PROF_MSG)
    popup_msg = msg_df.at[0, "message"] if not msg_df.empty and msg_df.at[0, "status"] == "confirmed" else None
    return render_template("questions.html", questions=df.to_dict("records"), popup_msg=popup_msg, role=session["role"], email=session["email"])

# 질문 수정
@app.route("/edit_question/<int:q_id>", methods=["POST"])
def edit_question(q_id):
    df = load_csv(DATA_QUESTIONS)
    idx = df.index[df["id"] == q_id].tolist()
    if not idx:
        flash("❌ 해당 질문을 찾을 수 없습니다.", "danger")
        return redirect(url_for("questions_page"))
    i = idx[0]
    if session["email"] != df.at[i, "email"]:
        flash("⛔ 본인만 수정 가능합니다.", "danger")
        return redirect(url_for("questions_page"))

    df.at[i, "title"] = request.form.get("title", df.at[i, "title"])
    df.at[i, "content"] = request.form.get("content", df.at[i, "content"])
    save_csv(DATA_QUESTIONS, df)
    flash("✏️ 질문이 수정되었습니다.", "success")
    return redirect(url_for("questions_page"))

# 질문 삭제
@app.route("/delete_question/<int:q_id>", methods=["POST"])
def delete_question(q_id):
    df = load_csv(DATA_QUESTIONS)
    df = df[df["id"] != q_id]
    save_csv(DATA_QUESTIONS, df)
    flash("🗑️ 질문이 삭제되었습니다.", "info")
    return redirect(url_for("questions_page"))

# ───────────── 파일 보기 ─────────────
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename.encode('utf-8').decode('utf-8'))

if __name__ == "__main__":
    app.run(debug=True)
