# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Final Stable Fix)
- 교수: 메시지 작성, 수정, 삭제, 게시 확정 → 질문 페이지 팝업 표시
- 학생: 질문 등록, 파일 다중 업로드/수정/삭제
- 본인 글만 수정/삭제 가능
- 파일명 한글 처리 및 NaN 오류 수정
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
DATA_EMAILS = os.path.join(BASE_DIR, "employed_allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_MESSAGES = os.path.join(BASE_DIR, "professor_messages.csv")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ───────────── CSV 로드/저장 ─────────────
def load_csv(path):
    if os.path.exists(path):
        df = pd.read_csv(path, encoding="utf-8")
        # ✅ NaN 처리 (핵심 수정)
        df = df.fillna({'files': '', 'content': '', 'title': ''})
        return df
    return pd.DataFrame(columns=["id", "email", "content", "files", "date"])

def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8")

# ───────────── 이메일 로드 ─────────────
def load_allowed_emails():
    if not os.path.exists(DATA_EMAILS):
        print(f"[⚠경고] 이메일 등록파일 없음: {DATA_EMAILS}")
        return []
    with open(DATA_EMAILS, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

allowed_emails = load_allowed_emails()
professor_email = allowed_emails[0] if allowed_emails else None

# ───────────── 홈 (로그인) ─────────────
@app.route("/", methods=["GET", "POST"])
def home():
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
        return redirect(url_for("questions_page"))
    return render_template("home.html")

# ───────────── 교수 전용 페이지 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다. (교수 전용)", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_MESSAGES)

    if request.method == "POST":
        content = request.form.get("content")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_id = df["id"].max() + 1 if not df.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id,
            "email": session["email"],
            "content": content,
            "confirmed": "no",
            "date": date
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_MESSAGES, df)
        flash("📢 메시지가 등록되었습니다.", "success")
        return redirect(url_for("professor_page"))

    return render_template("professor.html", messages=df.to_dict("records"))

# ✅ 교수 메시지 게시 확정
@app.route("/confirm_message/<int:index>", methods=["POST"])
def confirm_message(index):
    df = load_csv(DATA_MESSAGES)
    if 0 <= index < len(df):
        df.at[index, "confirmed"] = "yes"
        save_csv(DATA_MESSAGES, df)
        flash("✅ 게시 확정되었습니다.", "success")
    return redirect(url_for("professor_page"))

# ✅ 교수 메시지 수정
@app.route("/edit_message/<int:index>", methods=["POST"])
def edit_message(index):
    df = load_csv(DATA_MESSAGES)
    if 0 <= index < len(df):
        new_content = request.form.get("content")
        df.at[index, "content"] = new_content
        df.at[index, "confirmed"] = "no"
        save_csv(DATA_MESSAGES, df)
        flash("✏️ 메시지가 수정되었습니다.", "info")
    return redirect(url_for("professor_page"))

# ✅ 교수 메시지 삭제
@app.route("/delete_message/<int:index>", methods=["POST"])
def delete_message(index):
    df = load_csv(DATA_MESSAGES)
    if 0 <= index < len(df):
        df = df.drop(index).reset_index(drop=True)
        save_csv(DATA_MESSAGES, df)
        flash("🗑️ 메시지가 삭제되었습니다.", "warning")
    return redirect(url_for("professor_page"))

# ───────────── 질문 공유 페이지 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("⚠ 로그인 후 접근 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)

    # 🔹 등록
    if request.method == "POST":
        content = request.form.get("content", "")
        email = session["email"]
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        uploaded_files = request.files.getlist("files")
        filenames = []
        for f in uploaded_files:
            if f and f.filename:
                fname = secure_filename(f.filename)
                save_path = os.path.join(UPLOAD_FOLDER, fname)
                f.save(save_path)
                filenames.append(fname)
        file_str = ";".join(filenames)

        new_id = df["id"].max() + 1 if not df.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id,
            "email": email,
            "content": content,
            "files": file_str,
            "date": date
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df)
        flash("📘 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions_page"))

    # 🔹 교수 팝업 메시지 표시
    popup_msg = None
    if os.path.exists(DATA_MESSAGES):
        df_msg = pd.read_csv(DATA_MESSAGES, encoding="utf-8").fillna('')
        confirmed_msgs = df_msg[df_msg["confirmed"] == "yes"]
        if not confirmed_msgs.empty:
            popup_msg = confirmed_msgs.iloc[-1]["content"]

    return render_template(
        "questions.html",
        email=session["email"],
        questions=df.to_dict("records"),
        popup_msg=popup_msg
    )

# ✅ 질문 수정
@app.route("/edit_question/<int:index>", methods=["POST"])
def edit_question(index):
    df = load_csv(DATA_QUESTIONS)
    if 0 <= index < len(df):
        if df.at[index, "email"] == session["email"] or session.get("role") == "professor":
            df.at[index, "content"] = request.form.get("content")

            uploaded_files = request.files.getlist("files")
            filenames = [secure_filename(f.filename) for f in uploaded_files if f.filename]
            if filenames:
                df.at[index, "files"] = ";".join(filenames)
            save_csv(DATA_QUESTIONS, df)
            flash("✏️ 질문이 수정되었습니다.", "info")
        else:
            flash("⛔ 본인 또는 교수만 수정 가능합니다.", "danger")
    return redirect(url_for("questions_page"))

# ✅ 질문 삭제
@app.route("/delete_question/<int:index>", methods=["POST"])
def delete_question(index):
    df = load_csv(DATA_QUESTIONS)
    if 0 <= index < len(df):
        if df.at[index, "email"] == session["email"] or session.get("role") == "professor":
            df = df.drop(index).reset_index(drop=True)
            save_csv(DATA_QUESTIONS, df)
            flash("🗑️ 질문이 삭제되었습니다.", "warning")
        else:
            flash("⛔ 본인 또는 교수만 삭제 가능합니다.", "danger")
    return redirect(url_for("questions_page"))

# ✅ 업로드된 파일 제공
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ✅ 로그아웃
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
