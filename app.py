# -*- coding: utf-8 -*-
# hwat25-employed-members (Key 교수님, 2025-11-06)
# - 교수 메시지 3단계 게시 관리 시스템
# - 게시 확정 → 게시 완료 → 수정 게시 자동 전환
# - 한글 파일명 완전 지원 + 파일 미첨부시 "없음"

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import pandas as pd
import os, re
from datetime import datetime
from werkzeug.utils import secure_filename

# ───────────── Flask 설정 ─────────────
app = Flask(__name__)
app.secret_key = "key_flask_secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_MESSAGES = os.path.join(BASE_DIR, "professor_messages.csv")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ───────────── 한글 파일명 보존 ─────────────
def sanitize_filename(filename):
    filename = os.path.basename(filename)
    filename = re.sub(r"[\\/]", "_", filename)
    return filename.strip()


# ───────────── CSV 로드/저장 ─────────────
def load_csv(path):
    if os.path.exists(path):
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except:
            return pd.read_csv(path, encoding="utf-8")
    else:
        if "questions" in path:
            return pd.DataFrame(columns=["id", "email", "title", "content", "files", "date"])
        elif "messages" in path:
            return pd.DataFrame(columns=["id", "content", "date", "status"])
        return pd.DataFrame()


def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ───────────── 로그인 ─────────────
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
            allowed_emails = [line.strip() for line in f if line.strip()]

        if not allowed_emails:
            message = "⚠️ 등록된 이메일이 없습니다."
            return render_template("home.html", message=message)

        professor_email = allowed_emails[0]
        student_emails = allowed_emails[1:]

        if email == professor_email:
            session["email"] = email
            session["role"] = "professor"
            return redirect(url_for("questions"))
        elif email in student_emails:
            session["email"] = email
            session["role"] = "student"
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

    q = load_csv(DATA_QUESTIONS)
    m = load_csv(DATA_MESSAGES)

    # 교수 메시지: status=="done" 중 가장 최신 것만 팝업으로 표시
    popup_msg = None
    if not m.empty:
        latest_done = m[m["status"] == "done"]
        if not latest_done.empty:
            popup_msg = latest_done.iloc[-1]["content"]

    if request.method == "POST":
        content = request.form.get("content")
        email = session.get("email", "익명")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        filenames = []
        uploaded_files = request.files.getlist("files")
        for f in uploaded_files:
            if f and f.filename:
                filename = sanitize_filename(f.filename)
                f.save(os.path.join(UPLOAD_FOLDER, filename))
                filenames.append(filename)
        file_str = ";".join(filenames) if filenames else "없음"

        new_id = q["id"].max() + 1 if not q.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id, "email": email, "title": "",
            "content": content, "files": file_str, "date": date
        }])
        q = pd.concat([q, new_row], ignore_index=True)
        save_csv(DATA_QUESTIONS, q)
        return redirect(url_for("questions"))

    return render_template("questions.html",
                           questions=q.to_dict("records"),
                           popup_msg=popup_msg,
                           role=session.get("role"),
                           email=session.get("email"))


# ───────────── 메시지 관리 ─────────────
@app.route("/message", methods=["GET", "POST"])
def message():
    if session.get("role") != "professor":
        flash("권한이 없습니다.", "danger")
        return redirect(url_for("questions"))

    m = load_csv(DATA_MESSAGES)

    if request.method == "POST":
        content = request.form.get("content")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_id = m["id"].max() + 1 if not m.empty else 1
        new_row = pd.DataFrame([{
            "id": new_id, "content": content, "date": date, "status": "confirmed"
        }])
        m = pd.concat([m, new_row], ignore_index=True)
        save_csv(DATA_MESSAGES, m)
        return redirect(url_for("message"))

    return render_template("message.html", messages=m.to_dict("records"))


# 게시 확정 / 수정 게시 공용 라우트
@app.route("/confirm_message/<int:m_id>", methods=["POST"])
def confirm_message(m_id):
    m = load_csv(DATA_MESSAGES)
    if m_id in m["id"].values:
        m.loc[m["id"] == m_id, "status"] = "done"
        save_csv(DATA_MESSAGES, m)
    return redirect(url_for("message"))


# ───────────── 질문 수정 ─────────────
@app.route("/edit_question/<int:q_id>", methods=["POST"])
def edit_question(q_id):
    q = load_csv(DATA_QUESTIONS)
    if q.empty or q_id not in q["id"].values:
        return redirect(url_for("questions"))

    content = request.form.get("content", "")
    filenames = []
    uploaded_files = request.files.getlist("files")
    for f in uploaded_files:
        if f and f.filename:
            filename = sanitize_filename(f.filename)
            f.save(os.path.join(UPLOAD_FOLDER, filename))
            filenames.append(filename)

    old_files = str(q.loc[q["id"] == q_id, "files"].values[0])
    combined = old_files + (";" if old_files != "없음" and filenames else "") + ";".join(filenames)
    if combined.strip(";") == "":
        combined = "없음"

    q.loc[q["id"] == q_id, ["content", "files"]] = [content, combined]
    save_csv(DATA_QUESTIONS, q)
    return redirect(url_for("questions"))


# ───────────── 질문 삭제 ─────────────
@app.route("/delete_question/<int:q_id>", methods=["POST"])
def delete_question(q_id):
    q = load_csv(DATA_QUESTIONS)
    q = q[q["id"] != q_id]
    save_csv(DATA_QUESTIONS, q)
    return redirect(url_for("questions"))



# ───────────── 파일 보기 ─────────────
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


