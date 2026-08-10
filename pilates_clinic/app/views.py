from flask import Blueprint, render_template

bp = Blueprint("views", __name__)


@bp.route("/")
def login():
    return render_template("index.html")


@bp.route("/cadastro")
def cadastro():
    return render_template("cadastro.html")


@bp.route("/ativar")
def ativar():
    return render_template("ativar.html")


@bp.route("/esqueci-senha")
def esqueci_senha():
    return render_template("esqueci_senha.html")


@bp.route("/primeiro-acesso")
def primeiro_acesso():
    return render_template("primeiro_acesso.html")


@bp.route("/painel")
def painel():
    return render_template("painel.html")


@bp.route("/admin")
def admin():
    return render_template("admin.html")
