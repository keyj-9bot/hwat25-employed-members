# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Popup Confirmed Version)
- 교수: /professor + /questions 접근 가능
- 학생: /questions만 접근 가능
- 교수 메시지: 게시 확정 시 팝업 표시 / 수정 시 다시 게시 대기
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
import pandas as pd
import os
from datetime import datetime
from werkzeug.utils import secure_filename

# ───────────── 기본 설정 ─────────────
app = Flask(__name__)
app.secret_key = "key_flask_secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATA_EMAILS = os.path.join(BASE_DIR, "allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_PROF_MSGS = os.path.join(BASE_DIR, "professor_msgs.csv")

# ───────────── CSV 유틸 ─────────────
def load_csv(path, columns):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            for c in columns:
                if c not in df.columns:
                    df[c] = ""
            return df
        except Exception as e:
            print(f"[오류] CSV 읽기 실패: {e}")
    return pd.DataFrame(columns=columns)

def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8-sig")

# ───────────── 이메일 로드 ─────────────
def load_allowed_emails():
    if not os.path.exists(DATA_EMAILS):
        print(f"[⚠] allowed_emails.txt 없음 ({DATA_EMAILS})")
        return []
    with open(DATA_EMAILS, "r", encoding="utf-8") as f:
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

# ───────────── 교수 페이지 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다. (교수 전용 페이지)", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_PROF_MSGS, ["id", "title", "content", "date", "status"])

    # 메시지 작성
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        new_id = df["id"].max() + 1 if not df.empty else 1
        new_row = pd.DataFrame([{"id": new_id, "title": title, "content": content, "date": date, "status": "pending"}])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_PROF_MSGS, df)
        flash("📘 메시지가 등록되었습니다. (게시 대기)", "success")
        return redirect(url_for("professor_page"))

    return render_template("professor.html", msgs=df.to_dict("records"))

# 게시 확정
@app.route("/professor/confirm/<int:msg_id>")
def confirm_prof_msg(msg_id):
    df = load_csv(DATA_PROF_MSGS, ["id", "title", "content", "date", "status"])
    df.loc[df["id"] == msg_id, "status"] = "confirmed"
    save_csv(DATA_PROF_MSGS, df)
    flash("📢 게시 확정되었습니다. 질문 페이지에 팝업이 표시됩니다.", "success")
    return redirect(url_for("professor_page"))

# 수정
@app.route("/professor/edit/<int:msg_id>", methods=["POST"])
def edit_prof_msg(msg_id):
    df = load_csv(DATA_PROF_MSGS, ["id", "title", "content", "date", "status"])
    df.loc[df["id"] == msg_id, ["title", "content"]] = [
        request.form.get("title"), request.form.get("content")
    ]
    df.loc[df["id"] == msg_id, "status"] = "pending"  # 수정 시 다시 대기
    save_csv(DATA_PROF_MSGS, df)
    flash("✏️ 수정되었습니다. (다시 게시 확정 필요)", "info")
    return redirect(url_for("professor_page"))

# 삭제
@app.route("/professor/delete/<int:msg_id>")
def delete_prof_msg(msg_id):
    df = load_csv(DATA_PROF_MSGS, ["id", "title", "content", "date", "status"])
    df = df[df["id"] != msg_id]
    save_csv(DATA_PROF_MSGS, df)
    flash("🗑️ 삭제되었습니다.", "danger")
    return redirect(url_for("professor_page"))

# ───────────── 팝업 표시용 API ─────────────
@app.route("/popup_message")
def popup_message():
    df = load_csv(DATA_PROF_MSGS, ["id", "title", "content", "date", "status"])
    confirmed = df[df["status"] == "confirmed"]
    if not confirmed.empty:
        latest = confirmed.sort_values("date", ascending=False).iloc[0]
        return jsonify({"title": latest["title"], "content": latest["content"]})
    return jsonify({})

# ───────────── 질문 공유 (학생) ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("⚠ 로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS, ["id", "email", "title", "content", "files", "date"])

    if request.method == "POST":
        email = session["email"]
        title = request.form.get("title")
        content = request.form.get("content")
        files = request.files.getlist("files")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        file_names = []
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)
                file_names.append(filename)

        new_id = df["id"].max() + 1 if not df.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id,
            "email": email,
            "title": title,
            "content": content,
            "files": ";".join(file_names),
            "date": date
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, df)
        flash("💬 질문이 등록되었습니다.", "success")
        return redirect(url_for("questions_page"))

    return render_template("questions.html", questions=df.to_dict("records"), role=session.get("role"))

@app.route("/uploads/<path:filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route("/questions/edit/<int:q_id>", methods=["POST"])
def edit_question(q_id):
    df = load_csv(DATA_QUESTIONS, ["id", "email", "title", "content", "files", "date"])
    email = session["email"]
    if session.get("role") == "professor" or (df.loc[df["id"] == q_id, "email"].values[0] == email):
        df.loc[df["id"] == q_id, ["title", "content"]] = [
            request.form.get("title"), request.form.get("content")
        ]
        save_csv(DATA_QUESTIONS, df)
        flash("✏️ 수정되었습니다.", "info")
    else:
        flash("⛔ 수정 권한이 없습니다.", "danger")
    return redirect(url_for("questions_page"))

@app.route("/questions/delete/<int:q_id>")
def delete_question(q_id):
    df = load_csv(DATA_QUESTIONS, ["id", "email", "title", "content", "files", "date"])
    email = session["email"]
    if session.get("role") == "professor" or (df.loc[df["id"] == q_id, "email"].values[0] == email):
        df = df[df["id"] != q_id]
        save_csv(DATA_QUESTIONS, df)
        flash("🗑️ 질문이 삭제되었습니다.", "danger")
    else:
        flash("⛔ 삭제 권한이 없습니다.", "danger")
    return redirect(url_for("questions_page"))

@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))

