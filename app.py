# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (UTF-8 Safe Final)
- 교수: 메시지 등록/수정/삭제 및 게시 확정 → 팝업 표시
- 취업생: 질문 등록/수정/삭제 및 파일 첨부 가능
- 모든 한글 데이터 UTF-8-SIG로 인코딩하여 깨짐 방지
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import pandas as pd
import os
from datetime import datetime
from werkzeug.utils import secure_filename

# ───────────── 기본 설정 ─────────────
app = Flask(__name__)
app.secret_key = "key_flask_secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_EMAILS = os.path.join(BASE_DIR, "employed_allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_MESSAGES = os.path.join(BASE_DIR, "professor_messages.csv")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ───────────── CSV 로드/저장 함수 (UTF-8-SIG) ─────────────
def load_csv(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.read_csv(path, encoding="utf-8")


def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ───────────── 이메일 파일 로드 ─────────────
def load_allowed_emails():
    if not os.path.exists(DATA_EMAILS):
        print(f"[⚠경고] 이메일 등록 파일 없음: {DATA_EMAILS}")
        return []
    with open(DATA_EMAILS, "r", encoding="utf-8-sig") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


allowed_emails = load_allowed_emails()
professor_email = allowed_emails[0] if allowed_emails else None


# ───────────── 홈 (로그인) ─────────────
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

        if session["role"] == "professor":
            flash(f"✅ 교수 로그인 성공: {email}", "success")
            return redirect(url_for("professor_page"))
        else:
            flash(f"✅ 취업생 로그인 성공: {email}", "success")
            return redirect(url_for("questions_page"))

    return render_template("home.html")


# ───────────── 교수 메시지 페이지 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다. (교수 전용 페이지)", "danger")
        return redirect(url_for("home"))

    df_msg = load_csv(DATA_MESSAGES)

    # 🔹 메시지 등록
    if request.method == "POST":
        message = request.form.get("message", "").strip()
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        df_msg = pd.DataFrame([{"message": message, "date": date, "confirmed": "no"}])
        save_csv(DATA_MESSAGES, df_msg)
        flash("📢 교수 메시지가 등록되었습니다.", "success")
        return redirect(url_for("professor_page"))

    return render_template("professor.html", messages=df_msg.to_dict("records"))


# 🔹 교수 메시지 게시 확정
@app.route("/confirm_message/<int:index>", methods=["POST"])
def confirm_message(index):
    df = load_csv(DATA_MESSAGES)
    if index < len(df):
        df.at[index, "confirmed"] = "yes"
        save_csv(DATA_MESSAGES, df)
        flash("✅ 메시지가 게시되었습니다.", "success")
    return redirect(url_for("professor_page"))


# 🔹 교수 메시지 수정
@app.route("/edit_message/<int:index>", methods=["POST"])
def edit_message(index):
    df = load_csv(DATA_MESSAGES)
    if index < len(df):
        new_msg = request.form.get("new_message", "").strip()
        df.at[index, "message"] = new_msg
        df.at[index, "confirmed"] = "no"
        save_csv(DATA_MESSAGES, df)
        flash("✏️ 메시지가 수정되었습니다.", "info")
    return redirect(url_for("professor_page"))


# 🔹 교수 메시지 삭제
@app.route("/delete_message/<int:index>", methods=["POST"])
def delete_message(index):
    df = load_csv(DATA_MESSAGES)
    if index < len(df):
        df = df.drop(index)
        save_csv(DATA_MESSAGES, df)
        flash("🗑️ 메시지가 삭제되었습니다.", "info")
    return redirect(url_for("professor_page"))


# ───────────── 질문 페이지 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("⚠ 로그인 후 접근 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)
    popup_msg = None

    # 🔹 팝업 표시용 교수 메시지
    df_msg = load_csv(DATA_MESSAGES)
    confirmed_msgs = df_msg[df_msg.get("confirmed") == "yes"]
    if not confirmed_msgs.empty:
        popup_msg = confirmed_msgs.iloc[-1]["message"]

    # 🔹 질문 등록
    if request.method == "POST":
        content = request.form.get("content", "")
        files = request.files.getlist("files")
        email = session["email"]
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        filenames = []
        for f in files:
            if f and f.filename:
                fname = secure_filename(f.filename)
                f.save(os.path.join(UPLOAD_FOLDER, fname))
                filenames.append(fname)

        file_str = ";".join(filenames)
        new_row = pd.DataFrame(
            [{"email": email, "content": content, "files": file_str, "date": date}]
        )

        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df)
        flash("💬 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions_page"))

    return render_template(
        "questions.html",
        email=session["email"],
        questions=df.to_dict("records"),
        popup_msg=popup_msg,
    )


# 🔹 질문 수정
@app.route("/edit_question/<int:index>", methods=["POST"])
def edit_question(index):
    df = load_csv(DATA_QUESTIONS)
    if index < len(df):
        new_content = request.form.get("new_content", "")
        existing_files = str(df.at[index, "files"]) if not pd.isna(df.at[index, "files"]) else ""
        files = request.files.getlist("files")

        for f in files:
            if f and f.filename:
                fname = secure_filename(f.filename)
                f.save(os.path.join(UPLOAD_FOLDER, fname))
                existing_files += ";" + fname

        df.at[index, "content"] = new_content
        df.at[index, "files"] = existing_files
        save_csv(DATA_QUESTIONS, df)
        flash("✏️ 질문이 수정되었습니다.", "info")
    return redirect(url_for("questions_page"))


# 🔹 질문 삭제
@app.route("/delete_question/<int:index>", methods=["POST"])
def delete_question(index):
    df = load_csv(DATA_QUESTIONS)
    if index < len(df):
        df = df.drop(index)
        save_csv(DATA_QUESTIONS, df)
        flash("🗑️ 질문이 삭제되었습니다.", "info")
    return redirect(url_for("questions_page"))


# 🔹 업로드된 파일 접근
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))


# ───────────── 실행 ─────────────
if __name__ == "__main__":
    app.run(debug=True)
