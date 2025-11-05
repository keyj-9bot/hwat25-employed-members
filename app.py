# -*- coding: utf-8 -*-
"""
📘 hwat25-employed-members (Enhanced Stable Version)
- 교수: 메시지 등록 / 수정 / 삭제 / 게시 확정 기능
- 학생: 질문 등록 / 수정 / 삭제 / 다중 파일 첨부 (한글 파일명 정상 표시)
- 게시 확정 시 질문 페이지 팝업 표시
작성자: Key 교수님
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
import pandas as pd
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from urllib.parse import unquote

# ───────────── Flask 기본 설정 ─────────────
app = Flask(__name__)
app.secret_key = "key_flask_secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATA_EMAILS = os.path.join(BASE_DIR, "employed_allowed_emails.txt")
DATA_QUESTIONS = os.path.join(BASE_DIR, "questions.csv")
DATA_PROF_MSG = os.path.join(BASE_DIR, "professor_messages.csv")


# ───────────── CSV 관련 함수 ─────────────
def load_csv(path):
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, encoding="utf-8")
        except:
            df = pd.read_csv(path, encoding="cp949")
    else:
        df = pd.DataFrame()
    return df


def save_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8-sig")


# ───────────── 이메일 로드 ─────────────
def load_allowed_emails():
    if not os.path.exists(DATA_EMAILS):
        print(f"[⚠경고] 이메일 파일 누락: {DATA_EMAILS}")
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
            flash("✅ 교수 로그인 성공", "success")
            return redirect(url_for("professor_page"))
        else:
            flash("✅ 취업생 로그인 성공", "success")
            return redirect(url_for("questions_page"))

    return render_template("home.html")


# ───────────── 교수 페이지 ─────────────
@app.route("/professor", methods=["GET", "POST"])
def professor_page():
    if "email" not in session or session.get("role") != "professor":
        flash("⛔ 접근 권한이 없습니다.", "danger")
        return redirect(url_for("home"))

    df = load_csv(DATA_PROF_MSG)

    # 등록 또는 수정
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        status = "pending"
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        if "edit_id" in request.form and request.form["edit_id"]:
            edit_id = int(request.form["edit_id"])
            df.loc[df["id"] == edit_id, ["title", "content", "status", "date"]] = [title, content, "pending", date]
            flash("✏️ 메시지가 수정되었습니다.", "info")
        else:
            new_id = df["id"].max() + 1 if not df.empty else 1
            new_row = pd.DataFrame([{
                "id": new_id,
                "title": title,
                "content": content,
                "status": status,
                "date": date
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            flash("📢 메시지가 등록되었습니다.", "success")

        save_csv(DATA_PROF_MSG, df)
        return redirect(url_for("professor_page"))

    # 삭제
    del_id = request.args.get("delete")
    if del_id:
        df = df[df["id"] != int(del_id)]
        save_csv(DATA_PROF_MSG, df)
        flash("🗑️ 메시지가 삭제되었습니다.", "danger")
        return redirect(url_for("professor_page"))

    # 게시 확정
    confirm_id = request.args.get("confirm")
    if confirm_id:
        df.loc[df["id"] == int(confirm_id), "status"] = "confirmed"
        save_csv(DATA_PROF_MSG, df)
        flash("✅ 게시가 확정되었습니다.", "success")
        return redirect(url_for("professor_page"))

    return render_template("professor.html", email=session["email"], messages=df.to_dict("records"))


# ───────────── 질문 페이지 ─────────────
@app.route("/questions", methods=["GET", "POST"])
def questions_page():
    if "email" not in session:
        flash("⚠ 로그인 후 이용 가능합니다.", "warning")
        return redirect(url_for("home"))

    df = load_csv(DATA_QUESTIONS)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # 등록/수정 처리
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        email = session["email"]
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 파일 업로드
        filenames = []
        files = request.files.getlist("files")
        for file in files:
            if file and file.filename:
                filename = unquote(file.filename)
                path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(path)
                filenames.append(filename)

        if "edit_id" in request.form and request.form["edit_id"]:
            edit_id = int(request.form["edit_id"])
            df.loc[df["id"] == edit_id, ["title", "content", "files", "date"]] = [
                title,
                content,
                ";".join(filenames),
                date
            ]
            flash("✏️ 질문이 수정되었습니다.", "info")
        else:
            new_id = df["id"].max() + 1 if not df.empty else 1
            new_row = pd.DataFrame([{
                "id": new_id,
                "email": email,
                "title": title,
                "content": content,
                "files": ";".join(filenames),
                "date": date
            }])
            df = pd.concat([df, new_row], ignore_index=True)
            flash("📘 질문이 등록되었습니다.", "success")

        save_csv(DATA_QUESTIONS, df)
        return redirect(url_for("questions_page"))

    # 삭제 처리
    del_id = request.args.get("delete")
    if del_id:
        df = df[df["id"] != int(del_id)]
        save_csv(DATA_QUESTIONS, df)
        flash("🗑️ 질문이 삭제되었습니다.", "danger")
        return redirect(url_for("questions_page"))

    # 교수 팝업 메시지 로드
    prof_df = load_csv(DATA_PROF_MSG)
    popup_msg = None
    if not prof_df.empty:
        confirmed = prof_df[prof_df["status"] == "confirmed"]
        if not confirmed.empty:
            popup_msg = confirmed.iloc[-1]["content"]

    return render_template("questions.html", email=session["email"], questions=df.to_dict("records"), popup_msg=popup_msg)


# ───────────── 파일 다운로드 ─────────────
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    safe_name = unquote(filename)
    return send_from_directory(UPLOAD_FOLDER, safe_name)


# ───────────── 로그아웃 ─────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("👋 로그아웃되었습니다.", "info")
    return redirect(url_for("home"))


# ───────────── 메인 ─────────────
if __name__ == "__main__":
    app.run(debug=True)
