# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Final Stable Version)
- 교수: 메시지 등록/수정/삭제 및 게시확정 → 질문 페이지 팝업 표시
- 취업생: 질문 등록/수정/삭제, 파일 다중 업로드 가능
- 모든 기능 Render 환경에서 작동
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
        print(f"[⚠] 이메일 파일 없음: {DATA_EMAILS}")
        return []
    with open(DATA_EMAILS, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path, encoding="utf-8")
    else:
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

        if session["role"] == "professor":
            flash("✅ 교수 로그인 성공", "success")
            return redirect(url_for("professor_page"))
        else:
            flash("✅ 취업생 로그인 성공", "success")
            return redirect(url_for("questions_page"))

    return render_template("home.html")

# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))

# ───────────── 교수 페이지 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다.", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_PROF_MSG)

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        status = "pending"
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        df = pd.DataFrame([{"message": message, "status": status, "date": date}])
        save_csv(DATA_PROF_MSG, df)
        flash("📢 메시지가 저장되었습니다. 게시 확정을 눌러주세요.", "info")
        return redirect(url_for("professor_page"))

    msg = None
    if not df.empty:
        msg = df.iloc[0].to_dict()

    return render_template("professor.html", message=msg)

# 게시 확정
@app.route("/confirm_message", methods=["POST"])
def confirm_message():
    df = load_csv(DATA_PROF_MSG)
    if not df.empty:
        df.at[0, "status"] = "confirmed"
        save_csv(DATA_PROF_MSG, df)
        flash("✅ 게시 완료", "success")
    return redirect(url_for("professor_page"))

# 메시지 수정
@app.route("/edit_message", methods=["POST"])
def edit_message():
    df = load_csv(DATA_PROF_MSG)
    if not df.empty:
        df.at[0, "status"] = "pending"
        save_csv(DATA_PROF_MSG, df)
    flash("✏️ 메시지를 수정할 수 있습니다.", "warning")
    return redirect(url_for("professor_page"))

# 메시지 삭제
@app.route("/delete_message", methods=["POST"])
def delete_message():
    if os.path.exists(DATA_PROF_MSG):
        os.remove(DATA_PROF_MSG)
    flash("🗑️ 메시지가 삭제되었습니다.", "info")
    return redirect(url_for("professor_page"))

# ───────────── 질문 페이지 ─────────────
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

        # 파일 업로드
        uploaded_files = request.files.getlist("files")
        filenames = []
        for f in uploaded_files:
            if f and f.filename:
                fname = secure_filename(f.filename)
                path = os.path.join(UPLOAD_FOLDER, fname)
                f.save(path)
                filenames.append(fname)
        files_str = ";".join(filenames)

        new_id = df["id"].max() + 1 if not df.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id,
            "email": email,
            "title": title,
            "content": content,
            "files": files_str,
            "date": date
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df)
        flash("💬 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions_page"))

    # 팝업 표시 (교수 메시지가 게시 확정된 경우)
    msg_df = load_csv(DATA_PROF_MSG)
    popup_msg = None
    if not msg_df.empty and msg_df.at[0, "status"] == "confirmed":
        popup_msg = msg_df.at[0, "message"]

    return render_template("questions.html", questions=df.to_dict("records"), popup_msg=popup_msg)

# ───────────── 업로드 파일 라우트 ─────────────
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ───────────── 실행 ─────────────
if __name__ == "__main__":
    app.run(debug=True)
