# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Professor Message Popup Version)
- 교수: 메시지 작성·수정·삭제, 게시 확정/완료 상태 관리
- 학생: 질문 공유 게시판 접근
- 질문페이지: 게시 완료된 교수 메시지 팝업 표시
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "key_flask_secret"

# ───────────── 경로 설정 ─────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_EMAILS = os.path.join(BASE_DIR, "employed_allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_PROF_MSG = os.path.join(BASE_DIR, "professor_message.csv")

# ───────────── 파일 유틸 ─────────────
def load_allowed_emails():
    if not os.path.exists(DATA_EMAILS):
        print(f"[⚠] 이메일 파일 없음: {DATA_EMAILS}")
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

allowed_emails = load_allowed_emails()
professor_email = allowed_emails[0] if allowed_emails else None

# ───────────── 홈(로그인) ─────────────
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
            return redirect(url_for("professor_page"))
        else:
            return redirect(url_for("questions"))
    return render_template("home.html")

# ───────────── 교수 페이지 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다.", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_PROF_MSG)

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        if message:
            df = pd.DataFrame([{
                "message": message,
                "status": "confirmed",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            save_csv(DATA_PROF_MSG, df)
            flash("✅ 메시지가 게시되었습니다.", "success")
        return redirect(url_for("professor_page"))

    # 교수 메시지 로드
    if df.empty:
        message, status = "", "pending"
    else:
        message = df.iloc[-1]["message"]
        status = df.iloc[-1]["status"]

    return render_template("professor.html", email=session["email"], message=message, status=status)

# ───────────── 메시지 수정 ─────────────
@app.route("/professor/edit", methods=["POST"])
def edit_message():
    if session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다.", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_PROF_MSG)
    if not df.empty:
        df.at[df.index[-1], "message"] = request.form.get("message", "").strip()
        df.at[df.index[-1], "status"] = "pending"
        save_csv(DATA_PROF_MSG, df)
        flash("✏ 메시지가 수정되었습니다. (게시 확정 필요)", "info")
    return redirect(url_for("professor_page"))

# ───────────── 질문 페이지 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions():
    if "email" not in session:
        flash("⚠ 로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df_q = load_csv(DATA_QUESTIONS)
    df_m = load_csv(DATA_PROF_MSG)

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        email = session["email"]
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_id = df_q["id"].max() + 1 if not df_q.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id, "email": email, "title": title,
            "content": content, "date": date
        }])
        df_q = pd.concat([df_q, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df_q)
        flash("📘 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions"))

    popup_message = None
    if not df_m.empty and df_m.iloc[-1]["status"] == "confirmed":
        popup_message = df_m.iloc[-1]["message"]

    return render_template("questions.html",
                           questions=df_q.to_dict("records"),
                           role=session.get("role"),
                           popup_message=popup_message)

# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))


