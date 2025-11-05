# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Stable Enhanced Version)
- 교수: 메시지 작성, 수정, 삭제 (팝업 게시)
- 학생: 질문 작성, 수정, 삭제, 다중 파일 업로드
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
DATA_MESSAGES = os.path.join(BASE_DIR, "professor_message.csv")

# ───────────── 헬퍼 함수 ─────────────
def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path, encoding="utf-8")
    return pd.DataFrame(columns=["id", "email", "title", "content", "files", "date"])

def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8")

def load_allowed_emails():
    if not os.path.exists(DATA_EMAILS):
        return []
    with open(DATA_EMAILS, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

allowed_emails = load_allowed_emails()
professor_email = allowed_emails[0] if allowed_emails else None

# ───────────── 라우팅 ─────────────
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
        title = request.form.get("title", "")
        content = request.form.get("content", "")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        df = pd.DataFrame([{
            "id": 1,
            "email": session["email"],
            "title": title,
            "content": content,
            "date": date,
            "status": "pending"
        }])
        save_csv(DATA_MESSAGES, df)
        flash("📢 메시지가 저장되었습니다. '게시 확정'을 눌러 공개할 수 있습니다.", "success")

    return render_template("professor.html", messages=df.to_dict("records"))

@app.route("/confirm_message", methods=["POST"])
def confirm_message():
    df = load_csv(DATA_MESSAGES)
    if not df.empty:
        df.at[0, "status"] = "confirmed"
        save_csv(DATA_MESSAGES, df)
        flash("✅ 게시 확정되었습니다.", "success")
    return redirect(url_for("professor_page"))

@app.route("/delete_message", methods=["POST"])
def delete_message():
    if os.path.exists(DATA_MESSAGES):
        os.remove(DATA_MESSAGES)
    flash("🗑️ 메시지가 삭제되었습니다.", "info")
    return redirect(url_for("professor_page"))

# ───────────── 질문 페이지 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("⚠ 로그인 후 접근 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)

    # 🔹 등록 또는 수정 처리
    if request.method == "POST":
        qid = request.form.get("id")
        title = request.form.get("title")
        content = request.form.get("content")
        email = session["email"]
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 파일 업로드 처리
        files = request.files.getlist("files")
        saved_files = []
        for f in files:
            if f.filename:
                filename = secure_filename(f.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                f.save(filepath)
                saved_files.append(filename)
        file_list = ";".join(saved_files)

        # 수정인 경우
        if qid:
            idx = df.index[df["id"] == int(qid)].tolist()
            if idx:
                i = idx[0]
                if file_list:
                    df.at[i, "files"] = df.at[i, "files"] + ";" + file_list if df.at[i, "files"] else file_list
                df.at[i, "title"] = title
                df.at[i, "content"] = content
                df.at[i, "date"] = date
                save_csv(DATA_QUESTIONS, df)
                flash("✏️ 질문이 수정되었습니다.", "success")
                return redirect(url_for("questions_page"))

        # 신규 등록
        new_id = int(df["id"].max()) + 1 if not df.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id,
            "email": email,
            "title": title,
            "content": content,
            "files": file_list,
            "date": date
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df)
        flash("📘 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions_page"))

    df_msg = load_csv(DATA_MESSAGES)
    message = None
    if not df_msg.empty and df_msg.iloc[0]["status"] == "confirmed":
        message = df_msg.iloc[0].to_dict()

    return render_template("questions.html", questions=df.to_dict("records"), message=message)

@app.route("/delete_question/<int:q_id>", methods=["POST"])
def delete_question(q_id):
    df = load_csv(DATA_QUESTIONS)
    df = df[df["id"] != q_id]
    save_csv(DATA_QUESTIONS, df)
    flash("🗑️ 질문이 삭제되었습니다.", "info")
    return redirect(url_for("questions_page"))

# ───────────── 파일 다운로드 ─────────────
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=False)

# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
