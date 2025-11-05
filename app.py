# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Clean Stable Start)
- 교수/학생 구분 로그인
- 교수: 모든 메뉴 접근
- 학생: 질문 게시판만 접근
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
from datetime import datetime

# 🔹 Render 환경에서도 절대경로로 파일을 인식하도록 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_EMAILS = os.path.join(BASE_DIR, "allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")

app = Flask(__name__)
app.secret_key = "key_flask_secret"

# ───────────── CSV 로드/저장 ─────────────
def load_csv(path):
    if os.path.exists(path):
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except:
            return pd.read_csv(path, encoding="utf-8")
    else:
        return pd.DataFrame(columns=["id", "email", "title", "content", "date"])

def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ───────────── 홈(로그인) ─────────────
@app.route("/", methods=["GET", "POST"])
def home():
    message = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        allowed_file = os.path.join(BASE_DIR, "employed_allowed_emails.txt")

        if not os.path.exists(allowed_file):
            message = "⚠️ 이메일 등록 파일이 없습니다."
            return render_template("home.html", message=message)

        with open(allowed_file, "r", encoding="utf-8") as f:
            emails = [line.strip() for line in f if line.strip()]

        if not emails:
            message = "⚠️ 등록된 이메일이 없습니다."
            return render_template("home.html", message=message)

        professor_email = emails[0]
        student_emails = emails[1:]

        if email == professor_email:
            session["email"] = email
            session["role"] = "professor"
            flash("✅ 교수 계정으로 로그인되었습니다.", "success")
            return redirect(url_for("questions"))
        elif email in student_emails:
            session["email"] = email
            session["role"] = "student"
            flash("✅ 학생 계정으로 로그인되었습니다.", "success")
            return redirect(url_for("questions"))
        else:
            message = "❌ 등록되지 않은 이메일입니다."

    return render_template("home.html", message=message)


# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))


# ───────────── 질문 게시판 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions():
    if "email" not in session:
        flash("로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        email = session["email"]
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        new_id = df["id"].max() + 1 if not df.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id,
            "email": email,
            "title": title,
            "content": content,
            "date": date
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df)
        flash("📘 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions"))

    return render_template("questions.html", questions=df.to_dict("records"), role=session.get("role"))


# ───────────── 실행 ─────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
