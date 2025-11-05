# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Final Stable + UTF-8 Safe)
- 교수: 메시지 작성·수정·삭제 + 게시확정 시 팝업 표시
- 취업생: 질문 등록·수정·삭제 + 복수 파일 등록
- 한글 완전호환 (UTF-8-SIG 저장 / chardet 감지 읽기)
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
from datetime import datetime
import chardet

# ───────────── Flask 기본 설정 ─────────────
app = Flask(__name__)
app.secret_key = "key_flask_secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_EMAILS = os.path.join(BASE_DIR, "employed_allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_PROF_MSG = os.path.join(BASE_DIR, "professor_message.csv")

# ───────────── CSV 안정 입출력 ─────────────
def load_csv(path):
    """CSV 파일을 UTF-8로 안정적으로 읽기"""
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        with open(path, "rb") as f:
            raw = f.read(2048)
            enc = chardet.detect(raw)["encoding"] or "utf-8"
        df = pd.read_csv(path, encoding=enc)
        df = df.fillna("").astype(str)
        return df
    except Exception as e:
        print(f"[CSV LOAD ERROR] {path} / {e}")
        return pd.DataFrame()

def save_csv(path, df):
    """CSV를 항상 UTF-8-SIG로 저장 (Excel 및 한글 완전호환)"""
    try:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    except Exception as e:
        print(f"[CSV SAVE ERROR] {path} / {e}")

# ───────────── 이메일 로드 ─────────────
def load_allowed_emails():
    if not os.path.exists(DATA_EMAILS):
        print(f"[⚠] 이메일 파일 없음: {DATA_EMAILS}")
        return []
    with open(DATA_EMAILS, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

allowed_emails = load_allowed_emails()
prof_email = allowed_emails[0] if allowed_emails else None

# ───────────── 로그인 페이지 ─────────────
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
        flash(f"✅ 로그인 성공: {email}", "success")

        if session["role"] == "professor":
            return redirect(url_for("professor_page"))
        return redirect(url_for("questions_page"))

    return render_template("home.html")

# ───────────── 교수 페이지 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다. (교수 전용 페이지)", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_PROF_MSG)

    # 메시지 등록 또는 수정
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if not content:
            flash("⚠ 메시지를 입력하세요.", "warning")
            return redirect(url_for("professor_page"))

        msg_id = request.form.get("msg_id")
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        if msg_id:  # 수정
            df.loc[df["id"] == msg_id, ["content", "date", "status"]] = [content, date, "pending"]
            flash("✏️ 메시지가 수정되었습니다.", "info")
        else:  # 신규 등록
            new_id = str(int(df["id"].max()) + 1) if not df.empty else "1"
            new_row = pd.DataFrame([{
                "id": new_id, "content": content, "date": date, "status": "pending"
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            flash("📩 메시지가 등록되었습니다.", "success")

        save_csv(DATA_PROF_MSG, df)
        return redirect(url_for("professor_page"))

    return render_template("professor.html", email=session["email"], messages=df.to_dict("records"))

# 게시 확정
@app.route("/confirm_prof/<msg_id>", methods=["POST"])
def confirm_prof(msg_id):
    df = load_csv(DATA_PROF_MSG)
    df.loc[df["id"] == msg_id, "status"] = "confirmed"
    save_csv(DATA_PROF_MSG, df)
    flash("✅ 게시 확정되었습니다.", "success")
    return redirect(url_for("professor_page"))

# 메시지 삭제
@app.route("/delete_prof/<msg_id>", methods=["POST"])
def delete_prof(msg_id):
    df = load_csv(DATA_PROF_MSG)
    df = df[df["id"] != msg_id]
    save_csv(DATA_PROF_MSG, df)
    flash("🗑️ 메시지가 삭제되었습니다.", "info")
    return redirect(url_for("professor_page"))

# ───────────── 질문 페이지 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("⚠ 로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)
    if "files" in df.columns:
        df["files"] = df["files"].fillna("").astype(str)

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        email = session["email"]
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 파일 처리
        uploaded_files = request.files.getlist("files")
        filenames = []
        upload_dir = os.path.join(BASE_DIR, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        for file in uploaded_files:
            if file and file.filename:
                safe_name = file.filename
                file.save(os.path.join(upload_dir, safe_name))
                filenames.append(safe_name)

        if request.form.get("edit_id"):  # 수정
            edit_id = request.form.get("edit_id")
            old_files = df.loc[df["id"] == edit_id, "files"].iloc[0] if not df.empty else ""
            combined_files = ";".join(filter(None, [old_files, ";".join(filenames)]))
            df.loc[df["id"] == edit_id, ["content", "files", "date"]] = [content, combined_files, date]
            flash("✏️ 질문이 수정되었습니다.", "info")
        else:  # 신규 등록
            new_id = str(int(df["id"].max()) + 1) if not df.empty else "1"
            new_row = pd.DataFrame([{
                "id": new_id, "email": email, "content": content,
                "files": ";".join(filenames), "date": date
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            flash("📘 질문이 등록되었습니다.", "success")

        save_csv(DATA_QUESTIONS, df)
        return redirect(url_for("questions_page"))

    # 교수 메시지 팝업 (오른쪽 상단 중간)
    df_msg = load_csv(DATA_PROF_MSG)
    popup_msg = df_msg[df_msg["status"] == "confirmed"]["content"].iloc[-1] if not df_msg.empty and "confirmed" in df_msg["status"].values else ""

    return render_template("questions.html", email=session["email"], questions=df.to_dict("records"), popup_msg=popup_msg)

# 질문 삭제
@app.route("/delete_question/<qid>", methods=["POST"])
def delete_question(qid):
    df = load_csv(DATA_QUESTIONS)
    df = df[df["id"] != qid]
    save_csv(DATA_QUESTIONS, df)
    flash("🗑️ 질문이 삭제되었습니다.", "info")
    return redirect(url_for("questions_page"))

# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)

