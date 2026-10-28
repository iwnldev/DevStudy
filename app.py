
from flask import Flask, Response, render_template, request, redirect, url_for, abort, flash, session, g
from flask_wtf.csrf import CSRFProtect
import csv
import io
import json
import os
import uuid
import calendar
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import unicodedata
import re
import secrets
import threading
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

from database import (conexao_aberta, criar_tabelas, inicializar_contas,
                      conectar_contas, criar_banco_usuario, definir_usuario_banco,
                      restaurar_usuario_banco, popular_conteudo_inicial)

app = Flask(__name__)
_chave_configurada = os.environ.get("DEVSTUDY_SECRET_KEY")
_arquivo_chave_local = Path(__file__).resolve().parent / "instance" / "devstudy_secret_key"
if not _chave_configurada:
    _arquivo_chave_local.parent.mkdir(parents=True, exist_ok=True)
    if _arquivo_chave_local.exists():
        _chave_configurada = _arquivo_chave_local.read_text(encoding="utf-8").strip()
    else:
        _chave_configurada = secrets.token_hex(32)
        _arquivo_chave_local.write_text(_chave_configurada, encoding="utf-8")
app.config["SECRET_KEY"] = _chave_configurada

csrf = CSRFProtect(app)

_bootstrap_lock = threading.Lock()
_bootstrap_pronto = False


def _garantir_base_inicial():
    global _bootstrap_pronto
    if _bootstrap_pronto:
        return
    with _bootstrap_lock:
        if not _bootstrap_pronto:
            criar_tabelas()
            popular_conteudo_inicial()
            inicializar_contas()
            _bootstrap_pronto = True


@app.before_request
def exigir_conta_e_selecionar_banco():
    if app.config.get("TESTING"):
        return None
    _garantir_base_inicial()
    if request.endpoint in {"login", "registrar", "static"}:
        return None
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return redirect(url_for("login", proxima=request.full_path if request.query_string else request.path))
    g.db_context_token = definir_usuario_banco(usuario_id)


@app.teardown_request
def restaurar_contexto_banco(_erro=None):
    token = getattr(g, "db_context_token", None)
    if token is not None:
        restaurar_usuario_banco(token)


@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    _garantir_base_inicial()
    if request.method == "GET":
        return render_template("registrar.html")
    nome = (request.form.get("nome") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""
    confirmar = request.form.get("confirmar_senha") or ""
    if not nome or len(nome) > 80 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        flash("Informe um nome e um e-mail válidos.", "erro")
        return render_template("registrar.html"), 400
    if len(senha) < 10 or len(senha) > 200 or senha != confirmar:
        flash("Use uma senha com pelo menos 10 caracteres e confirme-a corretamente.", "erro")
        return render_template("registrar.html"), 400
    contas = conectar_contas()
    try:
        cursor = contas.execute("INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
                                (nome, email, generate_password_hash(senha)))
        usuario_id = cursor.lastrowid
        contas.commit()
    except sqlite3.IntegrityError:
        flash("Este e-mail já possui uma conta.", "erro")
        return render_template("registrar.html"), 409
    finally:
        contas.close()
    criar_banco_usuario(usuario_id)
    token = definir_usuario_banco(usuario_id)
    try:
        criar_tabelas()
        popular_conteudo_inicial()
    finally:
        restaurar_usuario_banco(token)
    session.clear()
    session["usuario_id"] = usuario_id
    session["usuario_nome"] = nome
    flash("Conta criada. Seus estudos ficam em um espaço privado.", "sucesso")
    return redirect(url_for("inicio"))


@app.route("/login", methods=["GET", "POST"])
def login():
    _garantir_base_inicial()
    if request.method == "GET":
        return render_template("login.html")
    email = (request.form.get("email") or "").strip().lower()
    senha = request.form.get("senha") or ""
    contas = conectar_contas()
    usuario = contas.execute("SELECT id, nome, senha_hash FROM usuarios WHERE email = ?", (email,)).fetchone()
    contas.close()
    if usuario is None or not check_password_hash(usuario["senha_hash"], senha):
        flash("E-mail ou senha incorretos.", "erro")
        return render_template("login.html"), 401
    criar_banco_usuario(usuario["id"])
    session.clear()
    session["usuario_id"] = usuario["id"]
    session["usuario_nome"] = usuario["nome"]
    destino = request.args.get("proxima", "")
    if destino.startswith("/") and not destino.startswith("//"):
        return redirect(destino)
    return redirect(url_for("inicio"))


@app.route("/sair", methods=["POST"])
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("login"))

# ==========================================
# CONFIGURAÇÕES
# ==========================================

CATEGORIAS = [
    "Programação",
    "Banco de dados",
    "Redes de computadores",
    "Faculdade - ADS",
    "Geral",
    "Outros"
]

# ==========================================
# FUNÇÕES DE VALIDAÇÃO
# ==========================================

def validar_texto(valor, limite):
    """Valida um texto e remove espaços desnecessários."""
    if not isinstance(valor, str):
        return None

    texto = valor.strip()

    if not texto or len(texto) > limite:
        return None

    return texto


def validar_inteiro(valor, minimo, maximo):
    """Converte e valida um número inteiro recebido como texto."""
    if not isinstance(valor, str):
        return None

    valor = valor.strip()

    if not valor or not valor.isdecimal():
        return None

    numero = int(valor)

    if not minimo <= numero <= maximo:
        return None

    return numero


def buscar_materias(conexao):
    """Retorna as matérias cadastradas em ordem alfabética."""
    return conexao.execute("""
        SELECT id, nome, descricao, semestre
        FROM materias
        ORDER BY nome COLLATE NOCASE
    """).fetchall()


def buscar_assuntos(conexao):
    """Retorna assuntos com a matéria à qual cada um pertence."""
    return conexao.execute("""
        SELECT
            assuntos.id,
            assuntos.nome,
            assuntos.materia_id,
            materias.nome AS materia
        FROM assuntos
        JOIN materias ON materias.id = assuntos.materia_id
        ORDER BY materias.nome COLLATE NOCASE, assuntos.nome COLLATE NOCASE
    """).fetchall()


def normalizar_nome_materia(nome):
    """Normaliza um nome para comparação sem diferenças de caixa."""
    return unicodedata.normalize("NFC", nome).casefold()


def validar_assunto_da_materia(conexao, valor, materia):
    """Confirma que o assunto escolhido pertence à matéria informada."""
    if not valor:
        return None, None

    assunto_id = validar_inteiro(valor, 1, 2147483647)
    if assunto_id is None:
        return None, "Selecione um assunto válido."

    assunto = conexao.execute("""
        SELECT assuntos.id, materias.nome AS materia
        FROM assuntos
        JOIN materias ON materias.id = assuntos.materia_id
        WHERE assuntos.id = ?
    """, (assunto_id,)).fetchone()

    if (
        assunto is None
        or normalizar_nome_materia(assunto["materia"])
        != normalizar_nome_materia(materia)
    ):
        return None, "O assunto selecionado não pertence a essa matéria."

    return assunto_id, None


def valor_csv_seguro(valor):
    """Evita que textos exportados sejam interpretados como fórmulas."""
    if not isinstance(valor, str):
        return valor

    texto_sem_espacos = valor.lstrip(" \t\r\n")
    if texto_sem_espacos.startswith(("=", "+", "-", "@")):
        return "'" + valor

    return valor


def criar_resposta_csv(nome_arquivo, cabecalhos, linhas):
    """Gera um CSV UTF-8 com BOM e delimitador compatível com Excel local."""
    arquivo = io.StringIO(newline="")
    escritor = csv.writer(arquivo, delimiter=";", lineterminator="\r\n")
    escritor.writerow(cabecalhos)

    for linha in linhas:
        escritor.writerow([valor_csv_seguro(valor) for valor in linha])

    return Response(
        "\ufeff" + arquivo.getvalue(),
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nome_arquivo}"'
        }
    )


@app.route("/exportar/anotacoes.csv")
def exportar_anotacoes():
    """Baixa todas as anotações em formato CSV."""
    with conexao_aberta() as conexao:
        anotacoes = conexao.execute("""
            SELECT
                anotacoes.id,
                anotacoes.titulo,
                anotacoes.materia,
                anotacoes.categoria,
                anotacoes.conteudo,
                anotacoes.favorita,
                anotacoes.criado_em,
                assuntos.nome AS assunto
            FROM anotacoes
            LEFT JOIN assuntos ON assuntos.id = anotacoes.assunto_id
            ORDER BY anotacoes.criado_em DESC, anotacoes.id DESC
        """).fetchall()

    return criar_resposta_csv(
        "devstudy-anotacoes.csv",
        ["ID", "Título", "Matéria", "Assunto", "Categoria", "Conteúdo", "Favorita", "Criada em"],
        anotacoes
    )


@app.route("/exportar/sessoes.csv")
def exportar_sessoes():
    """Baixa o histórico de sessões de estudo em formato CSV."""
    with conexao_aberta() as conexao:
        sessoes = conexao.execute("""
            SELECT id, materia, duracao_minutos, data_estudo, criado_em
            FROM sessoes_estudo
            ORDER BY data_estudo DESC, id DESC
        """).fetchall()

    return criar_resposta_csv(
        "devstudy-sessoes-estudo.csv",
        ["ID", "Matéria", "Duração (minutos)", "Data do estudo", "Registrada em"],
        sessoes
    )


# ==========================================
# MATÉRIAS DE ESTUDO
# ==========================================

@app.route("/materias", methods=["GET", "POST"])
def gerenciar_materias():
    erro = None

    if request.method == "POST":
        nome = validar_texto(
            request.form.get("nome", ""),
            60
        )

        descricao = request.form.get("descricao", "").strip()

        if nome is None:
            erro = "Informe um nome de matéria com até 60 caracteres."

        elif len(descricao) > 300:
            erro = "A descrição deve ter no máximo 300 caracteres."

        else:
            with conexao_aberta() as conexao:
                materias_existentes = conexao.execute("""
                    SELECT id, nome
                    FROM materias
                """).fetchall()

                nome_normalizado = normalizar_nome_materia(nome)

                materia_existente = any(
                    normalizar_nome_materia(materia["nome"])
                    == nome_normalizado
                    for materia in materias_existentes
                )

                if materia_existente:
                    erro = "Já existe uma matéria com esse nome."
                else:
                    conexao.execute("""
                        INSERT INTO materias (nome, descricao)
                        VALUES (?, ?)
                    """, (nome, descricao))

                    flash("Matéria cadastrada com sucesso!", "sucesso")
                    return redirect(url_for("gerenciar_materias"))

    with conexao_aberta() as conexao:
        materias = [dict(materia) for materia in buscar_materias(conexao)]
        materias_por_id = {materia["id"]: materia for materia in materias}
        for materia in materias:
            materia["assuntos"] = []

        assuntos = conexao.execute("""
            SELECT id, materia_id, nome
            FROM assuntos
            ORDER BY nome COLLATE NOCASE, id
        """).fetchall()

        for assunto in assuntos:
            materia = materias_por_id.get(assunto["materia_id"])
            if materia is not None:
                materia["assuntos"].append(assunto)

    return render_template(
        "materias.html",
        materias=materias,
        erro=erro
    )


@app.route("/disciplinas")
def listar_disciplinas():
    """Exibe a grade curricular e o progresso real de cada disciplina."""
    pesquisa = request.args.get("pesquisa", "").strip()[:100]
    semestre_texto = request.args.get("semestre", "").strip()
    status_selecionado = request.args.get("status", "").strip()

    semestre_selecionado = None
    if semestre_texto:
        semestre_selecionado = validar_inteiro(semestre_texto, 1, 20)
        if semestre_selecionado is None:
            semestre_texto = ""

    with conexao_aberta() as conexao:
        disciplinas = conexao.execute("""
            SELECT
                materias.id,
                materias.nome,
                materias.descricao,
                materias.semestre,
                COALESCE(progresso.total_cursos, 0) AS total_cursos,
                COALESCE(progresso.total_modulos, 0) AS total_modulos,
                COALESCE(progresso.total_aulas, 0) AS total_aulas,
                COALESCE(progresso.aulas_concluidas, 0) AS aulas_concluidas,
                (SELECT COUNT(*) FROM questoes
                 WHERE questoes.materia_id = materias.id) AS total_questoes,
                (SELECT COUNT(*) FROM tentativas_questoes
                 JOIN questoes ON questoes.id = tentativas_questoes.questao_id
                 WHERE questoes.materia_id = materias.id) AS total_tentativas,
                (SELECT COUNT(*) FROM tentativas_questoes
                 JOIN questoes ON questoes.id = tentativas_questoes.questao_id
                 WHERE questoes.materia_id = materias.id
                   AND tentativas_questoes.acertou = 1) AS total_acertos,
                (SELECT COUNT(*) FROM flashcards
                 WHERE flashcards.materia_id = materias.id
                   AND flashcards.proxima_revisao <= date('now', 'localtime'))
                    AS revisoes_pendentes
            FROM materias
            LEFT JOIN (
                SELECT
                    cursos.materia_id,
                    COUNT(DISTINCT cursos.id) AS total_cursos,
                    COUNT(DISTINCT modulos.id) AS total_modulos,
                    COUNT(DISTINCT aulas.id) AS total_aulas,
                    COUNT(DISTINCT CASE
                        WHEN aulas.concluida = 1 THEN aulas.id
                    END) AS aulas_concluidas
                FROM cursos
                LEFT JOIN modulos ON modulos.curso_id = cursos.id
                LEFT JOIN aulas ON aulas.modulo_id = modulos.id
                WHERE cursos.materia_id IS NOT NULL
                GROUP BY cursos.materia_id
            ) AS progresso ON progresso.materia_id = materias.id
            ORDER BY
                CASE WHEN materias.semestre IS NULL THEN 1 ELSE 0 END,
                materias.semestre,
                materias.nome COLLATE NOCASE
        """).fetchall()

        proximas_aulas = conexao.execute("""
            SELECT
                cursos.materia_id,
                aulas.id AS aula_id,
                aulas.titulo AS aula_titulo,
                modulos.titulo AS modulo_titulo,
                cursos.titulo AS curso_titulo
            FROM cursos
            JOIN modulos ON modulos.curso_id = cursos.id
            JOIN aulas ON aulas.modulo_id = modulos.id
            WHERE cursos.materia_id IS NOT NULL
              AND aulas.concluida = 0
            ORDER BY
                cursos.id,
                modulos.ordem,
                modulos.id,
                aulas.ordem,
                aulas.id
        """).fetchall()

    proximas_por_disciplina = {}
    for aula in proximas_aulas:
        proximas_por_disciplina.setdefault(aula["materia_id"], aula)

    cartoes = []
    for disciplina in disciplinas:
        total_aulas = disciplina["total_aulas"]
        aulas_concluidas = disciplina["aulas_concluidas"]
        if total_aulas == 0 or aulas_concluidas == 0:
            status = "nao_iniciada"
        elif aulas_concluidas == total_aulas:
            status = "concluida"
        else:
            status = "em_andamento"

        cartao = dict(disciplina)
        cartao["status"] = status
        cartao["status_label"] = {
            "nao_iniciada": "Não iniciada",
            "em_andamento": "Em andamento",
            "concluida": "Concluída"
        }[status]
        cartao["progresso"] = (
            round(aulas_concluidas / total_aulas * 100)
            if total_aulas else 0
        )
        cartao["proxima_aula"] = proximas_por_disciplina.get(
            disciplina["id"]
        )
        cartao["percentual_acerto"] = (
            round(disciplina["total_acertos"] / disciplina["total_tentativas"] * 100)
            if disciplina["total_tentativas"] else None
        )

        if pesquisa and normalizar_nome_materia(pesquisa) not in normalizar_nome_materia(disciplina["nome"]):
            continue
        if semestre_selecionado and disciplina["semestre"] != semestre_selecionado:
            continue
        if status_selecionado in {
            "nao_iniciada", "em_andamento", "concluida"
        } and status != status_selecionado:
            continue
        cartoes.append(cartao)

    return render_template(
        "disciplinas.html",
        disciplinas=cartoes,
        pesquisa=pesquisa,
        semestre_selecionado=semestre_texto,
        status_selecionado=status_selecionado,
        total_disciplinas=len(disciplinas),
        total_com_conteudo=sum(1 for item in disciplinas if item["total_aulas"]),
        total_concluidas=sum(
            1 for item in disciplinas
            if item["total_aulas"] > 0
            and item["aulas_concluidas"] == item["total_aulas"]
        )
    )


@app.route("/disciplinas/nova", methods=["POST"])
def nova_disciplina():
    nome = validar_texto(request.form.get("nome", ""), 100)
    descricao = request.form.get("descricao", "").strip()
    semestre_texto = request.form.get("semestre", "").strip()
    semestre = None

    if nome is None or len(descricao) > 300:
        flash("Informe um nome válido e uma descrição de até 300 caracteres.", "erro")
        return redirect(url_for("listar_disciplinas"))

    if semestre_texto:
        semestre = validar_inteiro(semestre_texto, 1, 20)
        if semestre is None:
            flash("O semestre deve ser um número entre 1 e 20.", "erro")
            return redirect(url_for("listar_disciplinas"))

    with conexao_aberta() as conexao:
        existentes = conexao.execute("SELECT id, nome FROM materias").fetchall()
        if any(
            normalizar_nome_materia(item["nome"]) == normalizar_nome_materia(nome)
            for item in existentes
        ):
            flash("Já existe uma disciplina com esse nome.", "erro")
            return redirect(url_for("listar_disciplinas"))

        cursor = conexao.execute("""
            INSERT INTO materias (nome, descricao, semestre)
            VALUES (?, ?, ?)
        """, (nome, descricao, semestre))
        disciplina_id = cursor.lastrowid

    flash("Disciplina adicionada com sucesso!", "sucesso")
    return redirect(url_for("visualizar_disciplina", materia_id=disciplina_id))


@app.route("/disciplina/<int:materia_id>/semestre", methods=["POST"])
def definir_semestre_disciplina(materia_id):
    semestre_texto = request.form.get("semestre", "").strip()
    semestre = None
    if semestre_texto:
        semestre = validar_inteiro(semestre_texto, 1, 20)
        if semestre is None:
            flash("O semestre deve ser um número entre 1 e 20.", "erro")
            return redirect(url_for("listar_disciplinas"))

    with conexao_aberta() as conexao:
        cursor = conexao.execute(
            "UPDATE materias SET semestre = ? WHERE id = ?",
            (semestre, materia_id)
        )
        if cursor.rowcount == 0:
            abort(404)

    flash("Semestre atualizado.", "sucesso")
    return redirect(url_for("listar_disciplinas"))


@app.route("/disciplina/<int:materia_id>")
def visualizar_disciplina(materia_id):
    with conexao_aberta() as conexao:
        disciplina = conexao.execute("""
            SELECT id, nome, descricao, semestre
            FROM materias
            WHERE id = ?
        """, (materia_id,)).fetchone()
        if disciplina is None:
            abort(404)

        cursos = conexao.execute("""
            SELECT
                cursos.id,
                cursos.titulo,
                cursos.descricao,
                COUNT(DISTINCT modulos.id) AS total_modulos,
                COUNT(DISTINCT aulas.id) AS total_aulas,
                COUNT(DISTINCT CASE
                    WHEN aulas.concluida = 1 THEN aulas.id
                END) AS aulas_concluidas
            FROM cursos
            LEFT JOIN modulos ON modulos.curso_id = cursos.id
            LEFT JOIN aulas ON aulas.modulo_id = modulos.id
            WHERE cursos.materia_id = ?
            GROUP BY cursos.id
            ORDER BY cursos.id
        """, (materia_id,)).fetchall()

        anotacoes = conexao.execute("""
            SELECT
                anotacoes.id,
                anotacoes.titulo,
                anotacoes.categoria,
                anotacoes.criado_em,
                assuntos.nome AS assunto_nome
            FROM anotacoes
            LEFT JOIN assuntos ON assuntos.id = anotacoes.assunto_id
            WHERE anotacoes.materia = ? COLLATE NOCASE
            ORDER BY anotacoes.criado_em DESC, anotacoes.id DESC
        """, (disciplina["nome"],)).fetchall()

        sessoes = conexao.execute("""
            SELECT id, duracao_minutos, data_estudo
            FROM sessoes_estudo
            WHERE materia = ? COLLATE NOCASE
            ORDER BY data_estudo DESC, id DESC
            LIMIT 10
        """, (disciplina["nome"],)).fetchall()

        materiais = conexao.execute("""
            SELECT materiais_estudo.*, modulos.titulo AS modulo_titulo
            FROM materiais_estudo
            LEFT JOIN modulos ON modulos.id = materiais_estudo.modulo_id
            WHERE materiais_estudo.materia_id = ?
            ORDER BY materiais_estudo.criado_em DESC, materiais_estudo.id DESC
        """, (materia_id,)).fetchall()
        modulos = conexao.execute("""
            SELECT modulos.id, modulos.titulo
            FROM modulos
            JOIN cursos ON cursos.id = modulos.curso_id
            WHERE cursos.materia_id = ?
            ORDER BY modulos.ordem, modulos.titulo COLLATE NOCASE
        """, (materia_id,)).fetchall()
        questoes = conexao.execute("""
            SELECT
                questoes.*,
                modulos.titulo AS modulo_titulo,
                COUNT(tentativas_questoes.id) AS total_tentativas,
                COALESCE(SUM(tentativas_questoes.acertou), 0) AS total_acertos
            FROM questoes
            LEFT JOIN modulos ON modulos.id = questoes.modulo_id
            LEFT JOIN tentativas_questoes
                ON tentativas_questoes.questao_id = questoes.id
            WHERE questoes.materia_id = ?
            GROUP BY questoes.id
            ORDER BY questoes.criado_em DESC, questoes.id DESC
        """, (materia_id,)).fetchall()
        flashcards = conexao.execute("""
            SELECT flashcards.*, modulos.titulo AS modulo_titulo
            FROM flashcards
            LEFT JOIN modulos ON modulos.id = flashcards.modulo_id
            WHERE flashcards.materia_id = ?
            ORDER BY flashcards.proxima_revisao, flashcards.id
        """, (materia_id,)).fetchall()

    questoes_exibicao = []
    total_tentativas = 0
    total_acertos = 0
    for questao in questoes:
        item = dict(questao)
        try:
            item["alternativas_lista"] = json.loads(item["alternativas"])
        except (TypeError, json.JSONDecodeError):
            item["alternativas_lista"] = []
        item["percentual_acerto"] = (
            round(item["total_acertos"] / item["total_tentativas"] * 100)
            if item["total_tentativas"] else None
        )
        questoes_exibicao.append(item)
        total_tentativas += item["total_tentativas"]
        total_acertos += item["total_acertos"]

    total_cards_pendentes = sum(
        1 for card in flashcards
        if card["proxima_revisao"] <= date.today().isoformat()
    )
    percentual_acerto = (
        round(total_acertos / total_tentativas * 100)
        if total_tentativas else None
    )
    if total_cards_pendentes:
        recomendacao = (
            f"Você tem {total_cards_pendentes} flashcard(s) aguardando revisão. "
            "Revise-os para reforçar a memória."
        )
    elif percentual_acerto is not None and percentual_acerto < 70:
        recomendacao = (
            "Sua taxa de acerto está abaixo de 70%. Releia as explicações "
            "das questões erradas e tente novamente."
        )
    elif questoes and total_tentativas:
        recomendacao = "Bom ritmo. Continue praticando e mantenha suas revisões em dia."
    elif materiais:
        recomendacao = "Estude um material cadastrado e depois pratique uma questão."
    else:
        recomendacao = "Comece adicionando um material ou uma questão para esta disciplina."

    return render_template(
        "disciplina.html",
        disciplina=disciplina,
        cursos=cursos,
        anotacoes=anotacoes,
        sessoes=sessoes,
        materiais=materiais,
        modulos=modulos,
        questoes=questoes_exibicao,
        flashcards=flashcards,
        today=date.today().isoformat(),
        total_tentativas=total_tentativas,
        total_acertos=total_acertos,
        percentual_acerto=percentual_acerto,
        total_cards_pendentes=total_cards_pendentes,
        recomendacao=recomendacao,
        ai_configurada=bool(os.environ.get("OPENAI_API_KEY"))
    )


@app.route("/disciplina/<int:materia_id>/novo-curso", methods=["POST"])
def novo_curso_da_disciplina(materia_id):
    titulo = validar_texto(request.form.get("titulo", ""), 120)
    descricao = request.form.get("descricao", "").strip()
    if titulo is None or len(descricao) > 1000:
        flash("Informe um título válido e uma descrição de até 1.000 caracteres.", "erro")
        return redirect(url_for("visualizar_disciplina", materia_id=materia_id))

    with conexao_aberta() as conexao:
        disciplina = conexao.execute(
            "SELECT id FROM materias WHERE id = ?",
            (materia_id,)
        ).fetchone()
        if disciplina is None:
            abort(404)
        conexao.execute("""
            INSERT INTO cursos (titulo, descricao, materia_id)
            VALUES (?, ?, ?)
        """, (titulo, descricao, materia_id))

    flash("Conteúdo criado. Agora você pode organizar módulos e aulas.", "sucesso")
    return redirect(url_for("visualizar_disciplina", materia_id=materia_id))


@app.route("/disciplina/<int:materia_id>/materiais/novo", methods=["POST"])
def novo_material_estudo(materia_id):
    titulo = validar_texto(request.form.get("titulo", ""), 140)
    tipo = request.form.get("tipo", "resumo")
    conteudo = validar_texto(request.form.get("conteudo", ""), 12000)
    link = request.form.get("link", "").strip()
    autor = request.form.get("autor", "").strip()
    licenca = request.form.get("licenca", "").strip()
    modulo_texto = request.form.get("modulo_id", "").strip()
    validado = 1 if request.form.get("validado") == "on" else 0
    tipos_validos = {"resumo", "explicacao", "exemplo", "referencia"}

    if (
        titulo is None or conteudo is None or tipo not in tipos_validos
        or len(link) > 500 or len(autor) > 160 or len(licenca) > 120
        or (link and not link.startswith(("https://", "http://")))
    ):
        flash("Confira o título, tipo, conteúdo e link do material.", "erro")
        return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#materiais")

    with conexao_aberta() as conexao:
        if conexao.execute("SELECT id FROM materias WHERE id = ?", (materia_id,)).fetchone() is None:
            abort(404)
        modulo_id = None
        if modulo_texto:
            modulo_id = validar_inteiro(modulo_texto, 1, 2147483647)
            modulo = conexao.execute("""
                SELECT modulos.id FROM modulos
                JOIN cursos ON cursos.id = modulos.curso_id
                WHERE modulos.id = ? AND cursos.materia_id = ?
            """, (modulo_id, materia_id)).fetchone()
            if modulo is None:
                flash("Selecione um módulo desta disciplina.", "erro")
                return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#materiais")
        conexao.execute("""
            INSERT INTO materiais_estudo
                (materia_id, modulo_id, titulo, tipo, conteudo, link,
                 autor, licenca, validado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            materia_id, modulo_id, titulo, tipo, conteudo, link,
            autor, licenca, validado
        ))

    flash("Material adicionado à disciplina.", "sucesso")
    return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#materiais")


@app.route("/disciplina/<int:materia_id>/materiais/<int:material_id>/excluir", methods=["POST"])
def excluir_material_estudo(materia_id, material_id):
    with conexao_aberta() as conexao:
        cursor = conexao.execute(
            "DELETE FROM materiais_estudo WHERE id = ? AND materia_id = ?",
            (material_id, materia_id)
        )
        if cursor.rowcount == 0:
            abort(404)
    flash("Material removido.", "sucesso")
    return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#materiais")


@app.route("/disciplina/<int:materia_id>/questoes/nova", methods=["POST"])
def nova_questao(materia_id):
    enunciado = validar_texto(request.form.get("enunciado", ""), 3000)
    explicacao = request.form.get("explicacao", "").strip()
    tipo = request.form.get("tipo", "multipla_escolha")
    dificuldade = request.form.get("dificuldade", "media")
    modulo_texto = request.form.get("modulo_id", "").strip()
    dificuldade_validas = {"facil", "media", "dificil"}
    if enunciado is None or len(explicacao) > 3000 or dificuldade not in dificuldade_validas:
        flash("Confira o enunciado, a explicação e a dificuldade.", "erro")
        return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#exercicios")

    alternativas = []
    if tipo == "multipla_escolha":
        alternativas = [
            validar_texto(request.form.get(f"alternativa_{i}", ""), 300)
            for i in range(1, 5)
        ]
        correta = request.form.get("resposta_correta", "")
        if any(item is None for item in alternativas) or correta not in {"1", "2", "3", "4"}:
            flash("Preencha as quatro alternativas e selecione o gabarito.", "erro")
            return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#exercicios")
    elif tipo == "vf":
        alternativas = ["Verdadeiro", "Falso"]
        correta = request.form.get("resposta_correta", "")
        if correta not in {"1", "2"}:
            flash("Selecione a resposta correta.", "erro")
            return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#exercicios")
    elif tipo == "numerica":
        correta = request.form.get("resposta_correta", "").strip().replace(",", ".")
        try:
            Decimal(correta)
            if len(correta) > 50:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            flash("Informe uma resposta numérica válida.", "erro")
            return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#exercicios")
    else:
        flash("Tipo de questão inválido.", "erro")
        return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#exercicios")

    with conexao_aberta() as conexao:
        if conexao.execute("SELECT id FROM materias WHERE id = ?", (materia_id,)).fetchone() is None:
            abort(404)
        modulo_id = None
        if modulo_texto:
            modulo_id = validar_inteiro(modulo_texto, 1, 2147483647)
            modulo = conexao.execute("""
                SELECT modulos.id FROM modulos
                JOIN cursos ON cursos.id = modulos.curso_id
                WHERE modulos.id = ? AND cursos.materia_id = ?
            """, (modulo_id, materia_id)).fetchone()
            if modulo is None:
                flash("Selecione um módulo desta disciplina.", "erro")
                return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#exercicios")
        conexao.execute("""
            INSERT INTO questoes
                (materia_id, modulo_id, enunciado, tipo, alternativas,
                 resposta_correta, explicacao, dificuldade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            materia_id, modulo_id, enunciado, tipo,
            json.dumps(alternativas, ensure_ascii=False), correta,
            explicacao, dificuldade
        ))
    flash("Questão adicionada. O gabarito será conferido no servidor.", "sucesso")
    return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#exercicios")


def normalizar_resposta_numerica(valor):
    try:
        numero = Decimal(valor.strip().replace(",", "."))
        return format(numero.normalize(), "f")
    except (InvalidOperation, ValueError, AttributeError):
        return None


@app.route("/disciplina/<int:materia_id>/questoes/<int:questao_id>/responder", methods=["POST"])
def responder_questao(materia_id, questao_id):
    resposta = request.form.get("resposta", "").strip()
    with conexao_aberta() as conexao:
        questao = conexao.execute("""
            SELECT id, tipo, alternativas, resposta_correta
            FROM questoes WHERE id = ? AND materia_id = ?
        """, (questao_id, materia_id)).fetchone()
        if questao is None:
            abort(404)
        if questao["tipo"] == "numerica":
            correta = normalizar_resposta_numerica(questao["resposta_correta"])
            resposta_normalizada = normalizar_resposta_numerica(resposta)
            resposta_valida = resposta_normalizada is not None
            acertou = resposta_valida and resposta_normalizada == correta
        else:
            try:
                opcoes = json.loads(questao["alternativas"])
            except json.JSONDecodeError:
                opcoes = []
            resposta_valida = resposta in {str(i) for i in range(1, len(opcoes) + 1)}
            acertou = resposta_valida and resposta == questao["resposta_correta"]

        if not resposta_valida:
            flash("Escolha uma alternativa ou informe uma resposta numérica válida.", "erro")
            return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + f"#questao-{questao_id}")
        conexao.execute("""
            INSERT INTO tentativas_questoes (questao_id, resposta, acertou)
            VALUES (?, ?, ?)
        """, (questao_id, resposta, int(acertou)))

    flash(
        "Resposta correta!" if acertou else "Ainda não. Confira o gabarito e a explicação.",
        "sucesso" if acertou else "erro"
    )
    return redirect(
        url_for("visualizar_disciplina", materia_id=materia_id,
                gabarito=questao_id) + f"#questao-{questao_id}"
    )


@app.route("/disciplina/<int:materia_id>/flashcards/novo", methods=["POST"])
def novo_flashcard(materia_id):
    frente = validar_texto(request.form.get("frente", ""), 1000)
    verso = validar_texto(request.form.get("verso", ""), 3000)
    modulo_texto = request.form.get("modulo_id", "").strip()
    if frente is None or verso is None:
        flash("Preencha frente e verso do flashcard.", "erro")
        return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#revisoes")
    with conexao_aberta() as conexao:
        if conexao.execute("SELECT id FROM materias WHERE id = ?", (materia_id,)).fetchone() is None:
            abort(404)
        modulo_id = None
        if modulo_texto:
            modulo_id = validar_inteiro(modulo_texto, 1, 2147483647)
            modulo = conexao.execute("""
                SELECT modulos.id FROM modulos
                JOIN cursos ON cursos.id = modulos.curso_id
                WHERE modulos.id = ? AND cursos.materia_id = ?
            """, (modulo_id, materia_id)).fetchone()
            if modulo is None:
                flash("Selecione um módulo desta disciplina.", "erro")
                return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#revisoes")
        conexao.execute("""
            INSERT INTO flashcards (materia_id, modulo_id, frente, verso)
            VALUES (?, ?, ?, ?)
        """, (materia_id, modulo_id, frente, verso))
    flash("Flashcard criado. A primeira revisão já está disponível.", "sucesso")
    return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#revisoes")


@app.route("/disciplina/<int:materia_id>/flashcards/<int:flashcard_id>/revisar", methods=["POST"])
def revisar_flashcard(materia_id, flashcard_id):
    lembrou = request.form.get("lembrou") == "1"
    with conexao_aberta() as conexao:
        card = conexao.execute("""
            SELECT id, intervalo_dias FROM flashcards
            WHERE id = ? AND materia_id = ?
        """, (flashcard_id, materia_id)).fetchone()
        if card is None:
            abort(404)
        intervalo = min(card["intervalo_dias"] * 2, 90) if lembrou else 1
        proxima = (date.today() + timedelta(days=intervalo)).isoformat()
        conexao.execute("""
            INSERT INTO revisoes_flashcards (flashcard_id, lembrou)
            VALUES (?, ?)
        """, (flashcard_id, int(lembrou)))
        conexao.execute("""
            UPDATE flashcards SET intervalo_dias = ?, proxima_revisao = ?
            WHERE id = ?
        """, (intervalo, proxima, flashcard_id))
    flash(
        f"Revisão registrada. Próxima revisão em {intervalo} dia(s).",
        "sucesso"
    )
    return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#revisoes")


@app.route("/disciplina/<int:materia_id>/tutor-ia", methods=["POST"])
def perguntar_tutor_ia(materia_id):
    pergunta = validar_texto(request.form.get("pergunta", ""), 2000)
    if pergunta is None:
        flash("Escreva uma dúvida com até 2.000 caracteres.", "erro")
        return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#tutor-ia")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        flash(
            "O tutor de IA ainda não está configurado. Defina OPENAI_API_KEY no ambiente e reinicie o DevStudy.",
            "erro"
        )
        return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#tutor-ia")

    # Limite por conta para evitar consumo inesperado da chave compartilhada do servidor.
    contas = conectar_contas()
    try:
        contas.execute("BEGIN IMMEDIATE")
        uso = contas.execute("""SELECT COUNT(*) FROM uso_tutor_ia
            WHERE usuario_id = ? AND date(usado_em) = date('now')""",
            (session.get("usuario_id"),)).fetchone()[0]
        if uso >= 10:
            contas.rollback()
            flash("Você atingiu o limite de 10 perguntas ao tutor por dia.", "erro")
            return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#tutor-ia")
        contas.execute("INSERT INTO uso_tutor_ia (usuario_id) VALUES (?)", (session.get("usuario_id"),))
        contas.commit()
    finally:
        contas.close()

    with conexao_aberta() as conexao:
        disciplina = conexao.execute(
            "SELECT nome FROM materias WHERE id = ?", (materia_id,)
        ).fetchone()
        if disciplina is None:
            abort(404)

    dados = json.dumps({
        "model": os.environ.get("OPENAI_MODEL", "gpt-6-luna"),
        "instructions": (
            "Você é o tutor do DevStudy. Responda em português do Brasil, "
            "com clareza e tom acolhedor. Explique passo a passo, faça perguntas "
            "para estimular o raciocínio e indique quando houver incerteza. "
            "Não afirme que conhece a ementa oficial da faculdade."
        ),
        "input": (
            f"Disciplina: {disciplina['nome']}{chr(10)}"
            f"Dúvida do estudante: {pergunta}"
        ),
        "max_output_tokens": 700,
        "store": False
    }).encode("utf-8")
    req = Request(
        "https://api.openai.com/v1/responses",
        data=dados,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urlopen(req, timeout=35) as response:
            retorno = json.loads(response.read().decode("utf-8"))
        texto = str(retorno.get("output_text") or "").strip()
        if not texto:
            partes = []
            for item in retorno.get("output", []):
                for bloco in item.get("content", []):
                    if bloco.get("type") == "output_text":
                        partes.append(bloco.get("text", ""))
            texto = (chr(10) * 2).join(partes).strip()
        if not texto:
            raise ValueError("Resposta vazia do tutor")
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        flash(
            "Não foi possível obter resposta do tutor agora. Confira a configuração da API e tente novamente.",
            "erro"
        )
        return redirect(url_for("visualizar_disciplina", materia_id=materia_id) + "#tutor-ia")

    return render_template(
        "resposta_tutor.html",
        disciplina_nome=disciplina["nome"],
        pergunta=pergunta,
        resposta=texto,
        materia_id=materia_id
    )


@app.route("/materia/<int:materia_id>/assuntos", methods=["POST"])
def novo_assunto(materia_id):
    """Cadastra um assunto dentro de uma matéria existente."""
    nome = validar_texto(request.form.get("nome", ""), 80)

    if nome is None:
        flash("Informe um assunto com até 80 caracteres.", "erro")
        return redirect(url_for("gerenciar_materias"))

    with conexao_aberta() as conexao:
        materia = conexao.execute(
            "SELECT id FROM materias WHERE id = ?",
            (materia_id,)
        ).fetchone()

        if materia is None:
            abort(404)

        assuntos_existentes = conexao.execute("""
            SELECT nome
            FROM assuntos
            WHERE materia_id = ?
        """, (materia_id,)).fetchall()

        nome_normalizado = normalizar_nome_materia(nome)
        duplicado = any(
            normalizar_nome_materia(assunto["nome"]) == nome_normalizado
            for assunto in assuntos_existentes
        )

        if duplicado:
            flash("Esse assunto já existe nesta matéria.", "erro")
        else:
            conexao.execute("""
                INSERT INTO assuntos (materia_id, nome)
                VALUES (?, ?)
            """, (materia_id, nome))
            flash("Assunto cadastrado com sucesso!", "sucesso")

    return redirect(url_for("gerenciar_materias"))


@app.route("/assunto/<int:assunto_id>/excluir", methods=["POST"])
def excluir_assunto(assunto_id):
    """Remove um assunto sem afetar a matéria ou seus outros dados."""
    with conexao_aberta() as conexao:
        assunto = conexao.execute(
            "SELECT id FROM assuntos WHERE id = ?",
            (assunto_id,)
        ).fetchone()

        if assunto is None:
            abort(404)

        conexao.execute(
            "DELETE FROM assuntos WHERE id = ?",
            (assunto_id,)
        )

    flash("Assunto removido com sucesso.", "sucesso")
    return redirect(url_for("gerenciar_materias"))


# ==========================================
# CURSOS
# ==========================================

@app.route("/cursos")
def listar_cursos():
    """Lista os cursos cadastrados e suas matérias."""
    with conexao_aberta() as conexao:
        cursos = conexao.execute("""
            SELECT
                cursos.id,
                cursos.titulo,
                cursos.descricao,
                cursos.criado_em,
                materias.nome AS materia_nome,
                COUNT(DISTINCT modulos.id) AS total_modulos
            FROM cursos
            LEFT JOIN materias
                ON materias.id = cursos.materia_id
            LEFT JOIN modulos
                ON modulos.curso_id = cursos.id
            GROUP BY cursos.id
            ORDER BY cursos.id DESC
        """).fetchall()

        materias = buscar_materias(conexao)

    return render_template(
        "cursos.html",
        cursos=cursos,
        materias=materias,
        erro=None
    )


@app.route("/novo-curso", methods=["POST"])
def novo_curso():
    """Cadastra um curso e associa uma matéria opcional."""
    titulo = validar_texto(
        request.form.get("titulo", ""),
        120
    )

    descricao = request.form.get("descricao", "").strip()
    materia_id_texto = request.form.get("materia_id", "").strip()

    if titulo is None:
        flash("Informe um título de curso com até 120 caracteres.", "erro")
        return redirect(url_for("listar_cursos"))

    if len(descricao) > 1000:
        flash("A descrição do curso deve ter até 1.000 caracteres.", "erro")
        return redirect(url_for("listar_cursos"))

    materia_id = None

    if materia_id_texto:
        materia_id = validar_inteiro(
            materia_id_texto,
            1,
            2147483647
        )

        if materia_id is None:
            flash("Selecione uma matéria válida.", "erro")
            return redirect(url_for("listar_cursos"))

    with conexao_aberta() as conexao:
        if materia_id is not None:
            materia = conexao.execute("""
                SELECT id
                FROM materias
                WHERE id = ?
            """, (materia_id,)).fetchone()

            if materia is None:
                flash("A matéria selecionada não existe.", "erro")
                return redirect(url_for("listar_cursos"))

        conexao.execute("""
            INSERT INTO cursos (titulo, descricao, materia_id)
            VALUES (?, ?, ?)
        """, (titulo, descricao, materia_id))

    flash("Curso cadastrado com sucesso!", "sucesso")
    return redirect(url_for("listar_cursos"))


@app.route("/curso/<int:curso_id>")
def visualizar_curso(curso_id):
    """Exibe os detalhes do curso e o progresso dos módulos."""
    with conexao_aberta() as conexao:
        curso = conexao.execute("""
            SELECT
                cursos.id,
                cursos.titulo,
                cursos.descricao,
                cursos.criado_em,
                materias.nome AS materia_nome
            FROM cursos
            LEFT JOIN materias
                ON materias.id = cursos.materia_id
            WHERE cursos.id = ?
        """, (curso_id,)).fetchone()

        if curso is None:
            abort(404)

        modulos = conexao.execute("""
            SELECT
                modulos.id,
                modulos.curso_id,
                modulos.titulo,
                modulos.descricao,
                modulos.ordem,
                modulos.criado_em,
                COUNT(aulas.id) AS total_aulas,
                COALESCE(
                    SUM(
                        CASE
                            WHEN aulas.concluida = 1 THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS aulas_concluidas
            FROM modulos
            LEFT JOIN aulas
                ON aulas.modulo_id = modulos.id
            WHERE modulos.curso_id = ?
            GROUP BY
                modulos.id,
                modulos.curso_id,
                modulos.titulo,
                modulos.descricao,
                modulos.ordem,
                modulos.criado_em
            ORDER BY modulos.ordem, modulos.id
        """, (curso_id,)).fetchall()

        modulos_com_progresso = []
        total_aulas_curso = 0
        aulas_concluidas_curso = 0

        for modulo in modulos:
            total_aulas = modulo["total_aulas"]
            aulas_concluidas = modulo["aulas_concluidas"]

            percentual = (
                round(aulas_concluidas / total_aulas * 100)
                if total_aulas > 0 else 0
            )

            modulo_dict = dict(modulo)
            modulo_dict["percentual_progresso"] = percentual
            modulos_com_progresso.append(modulo_dict)

            total_aulas_curso += total_aulas
            aulas_concluidas_curso += aulas_concluidas

        percentual_curso = (
            round(aulas_concluidas_curso / total_aulas_curso * 100)
            if total_aulas_curso > 0 else 0
        )

        materias = buscar_materias(conexao)

    return render_template(
        "curso.html",
        curso=curso,
        modulos=modulos_com_progresso,
        materias=materias,
        erro=None,
        total_aulas_curso=total_aulas_curso,
        aulas_concluidas_curso=aulas_concluidas_curso,
        percentual_curso=percentual_curso
    )


@app.route("/curso/<int:curso_id>/novo-modulo", methods=["POST"])
def novo_modulo(curso_id):
    """Adiciona um módulo a um curso existente."""
    titulo = validar_texto(
        request.form.get("titulo", ""),
        120
    )

    descricao = request.form.get("descricao", "").strip()
    ordem = validar_inteiro(
        request.form.get("ordem", "1"),
        1,
        10000
    )

    if titulo is None:
        flash("Informe um título de módulo com até 120 caracteres.", "erro")
        return redirect(url_for("visualizar_curso", curso_id=curso_id))

    if len(descricao) > 1000:
        flash("A descrição do módulo deve ter até 1.000 caracteres.", "erro")
        return redirect(url_for("visualizar_curso", curso_id=curso_id))

    if ordem is None:
        flash("A ordem deve ser um inteiro entre 1 e 10.000.", "erro")
        return redirect(url_for("visualizar_curso", curso_id=curso_id))

    with conexao_aberta() as conexao:
        curso = conexao.execute(
            "SELECT id FROM cursos WHERE id = ?",
            (curso_id,)
        ).fetchone()

        if curso is None:
            abort(404)

        conexao.execute("""
            INSERT INTO modulos (curso_id, titulo, descricao, ordem)
            VALUES (?, ?, ?, ?)
        """, (curso_id, titulo, descricao, ordem))

    flash("Módulo cadastrado com sucesso!", "sucesso")
    return redirect(url_for("visualizar_curso", curso_id=curso_id))


# ==========================================
# EXCLUIR MÓDULO
# ==========================================

@app.route("/modulo/<int:modulo_id>/excluir", methods=["POST"])
def excluir_modulo(modulo_id):
    """Exclui um módulo específico."""
    with conexao_aberta() as conexao:
        modulo = conexao.execute("""
            SELECT curso_id
            FROM modulos
            WHERE id = ?
        """, (modulo_id,)).fetchone()

        if modulo is None:
            abort(404)

        curso_id = modulo["curso_id"]

        conexao.execute("""
            DELETE FROM modulos
            WHERE id = ?
        """, (modulo_id,))

    flash("Módulo excluído com sucesso!", "sucesso")
    return redirect(url_for("visualizar_curso", curso_id=curso_id))


# ==========================================
# VISUALIZAR MÓDULO E AULAS
# ==========================================

@app.route("/modulo/<int:modulo_id>")
def visualizar_modulo(modulo_id):
    """Exibe um módulo e suas aulas."""
    with conexao_aberta() as conexao:
        modulo = conexao.execute("""
            SELECT
                modulos.*,
                cursos.titulo AS curso_titulo,
                cursos.id AS curso_id
            FROM modulos
            JOIN cursos ON cursos.id = modulos.curso_id
            WHERE modulos.id = ?
        """, (modulo_id,)).fetchone()

        if modulo is None:
            abort(404)

        aulas = conexao.execute("""
            SELECT *
            FROM aulas
            WHERE modulo_id = ?
            ORDER BY ordem ASC, id ASC
        """, (modulo_id,)).fetchall()

    return render_template(
        "modulo.html",
        modulo=modulo,
        aulas=aulas
    )


# ==========================================
# CADASTRAR AULA
# ==========================================

@app.route("/modulo/<int:modulo_id>/nova-aula", methods=["POST"])
def nova_aula(modulo_id):
    """Cadastra uma aula em um módulo existente."""
    titulo = validar_texto(
        request.form.get("titulo", ""),
        200
    )
    conteudo = request.form.get("conteudo", "").strip()
    ordem = validar_inteiro(
        request.form.get("ordem", ""),
        1,
        10000
    )

    if titulo is None:
        flash("Informe um título com até 200 caracteres.", "erro")
        return redirect(url_for(
            "visualizar_modulo",
            modulo_id=modulo_id
        ))

    if len(conteudo) > 20000:
        flash(
            "O conteúdo da aula deve ter no máximo 20.000 caracteres.",
            "erro"
        )
        return redirect(url_for(
            "visualizar_modulo",
            modulo_id=modulo_id
        ))

    if ordem is None:
        flash(
            "A ordem deve ser um número inteiro entre 1 e 10.000.",
            "erro"
        )
        return redirect(url_for(
            "visualizar_modulo",
            modulo_id=modulo_id
        ))

    with conexao_aberta() as conexao:
        modulo = conexao.execute(
            "SELECT id FROM modulos WHERE id = ?",
            (modulo_id,)
        ).fetchone()

        if modulo is None:
            abort(404)

        conexao.execute("""
            INSERT INTO aulas (modulo_id, titulo, conteudo, ordem)
            VALUES (?, ?, ?, ?)
        """, (modulo_id, titulo, conteudo, ordem))

    flash("Aula cadastrada com sucesso!", "sucesso")
    return redirect(url_for(
        "visualizar_modulo",
        modulo_id=modulo_id
    ))


# ==========================================
# EDITAR AULA
# ==========================================

@app.route("/aula/<int:aula_id>/editar", methods=["GET", "POST"])
def editar_aula(aula_id):
    """Edita uma aula existente."""
    with conexao_aberta() as conexao:
        aula = conexao.execute("""
            SELECT
                aulas.*,
                modulos.id AS modulo_id
            FROM aulas
            JOIN modulos ON modulos.id = aulas.modulo_id
            WHERE aulas.id = ?
        """, (aula_id,)).fetchone()

        if aula is None:
            abort(404)

        if request.method == "POST":
            titulo = validar_texto(
                request.form.get("titulo", ""),
                200
            )
            conteudo = request.form.get("conteudo", "").strip()
            ordem = validar_inteiro(
                request.form.get("ordem", ""),
                1,
                10000
            )

            if titulo is None:
                flash("Informe um título com até 200 caracteres.", "erro")
                return redirect(url_for(
                    "editar_aula",
                    aula_id=aula_id
                ))

            if len(conteudo) > 20000:
                flash(
                    "O conteúdo da aula deve ter no máximo 20.000 caracteres.",
                    "erro"
                )
                return redirect(url_for(
                    "editar_aula",
                    aula_id=aula_id
                ))

            if ordem is None:
                flash(
                    "A ordem deve ser um número inteiro entre 1 e 10.000.",
                    "erro"
                )
                return redirect(url_for(
                    "editar_aula",
                    aula_id=aula_id
                ))

            modulo_id = aula["modulo_id"]

            conexao.execute("""
                UPDATE aulas
                SET titulo = ?, conteudo = ?, ordem = ?
                WHERE id = ?
            """, (titulo, conteudo, ordem, aula_id))

            flash("Aula atualizada com sucesso!", "sucesso")
            return redirect(url_for(
                "visualizar_modulo",
                modulo_id=modulo_id
            ))

        return render_template("editar_aula.html", aula=aula)


# ==========================================
# EXCLUIR AULA
# ==========================================

@app.route("/aula/<int:aula_id>/excluir", methods=["POST"])
def excluir_aula(aula_id):
    """Exclui uma aula existente."""
    with conexao_aberta() as conexao:
        aula = conexao.execute("""
            SELECT id, modulo_id
            FROM aulas
            WHERE id = ?
        """, (aula_id,)).fetchone()

        if aula is None:
            abort(404)

        modulo_id = aula["modulo_id"]

        conexao.execute("""
            DELETE FROM aulas
            WHERE id = ?
        """, (aula_id,))

    flash("Aula excluída com sucesso!", "sucesso")
    return redirect(url_for(
        "visualizar_modulo",
        modulo_id=modulo_id
    ))


# ==========================================
# CONCLUIR OU REABRIR AULA
# ==========================================

@app.route("/aula/<int:aula_id>/concluir", methods=["POST"])
def alternar_conclusao_aula(aula_id):
    """Alterna o status de conclusão de uma aula."""
    with conexao_aberta() as conexao:
        aula = conexao.execute("""
            SELECT id, modulo_id, concluida
            FROM aulas
            WHERE id = ?
        """, (aula_id,)).fetchone()

        if aula is None:
            abort(404)

        novo_status = 0 if aula["concluida"] else 1

        conexao.execute("""
            UPDATE aulas
            SET concluida = ?
            WHERE id = ?
        """, (novo_status, aula_id))

        modulo_id = aula["modulo_id"]

    if novo_status:
        flash("Aula marcada como concluída!", "sucesso")
    else:
        flash("Aula reaberta para estudo.", "sucesso")

    return redirect(url_for(
        "visualizar_modulo",
        modulo_id=modulo_id
    ))


# ==========================================
# PÁGINA INICIAL
# ==========================================

@app.route("/")
def inicio():
    pesquisa = request.args.get("pesquisa", "").strip()[:200]
    materia_selecionada = request.args.get("materia", "").strip()
    categoria_selecionada = request.args.get("categoria", "").strip()
    somente_favoritas = request.args.get("favoritas") == "1"
    ordenacao = request.args.get("ordenar", "recentes")

    ordenacoes_permitidas = {
        "recentes": "criado_em DESC, id DESC",
        "antigas": "criado_em ASC, id ASC",
        "titulo_az": "titulo COLLATE NOCASE ASC, id DESC",
        "titulo_za": "titulo COLLATE NOCASE DESC, id DESC",
        "favoritas": "favorita DESC, criado_em DESC, id DESC",
    }
    if ordenacao not in ordenacoes_permitidas:
        ordenacao = "recentes"

    sql = """
        SELECT anotacoes.*,
            (SELECT nome FROM assuntos
             WHERE assuntos.id = anotacoes.assunto_id) AS assunto_nome
        FROM anotacoes
    """
    condicoes = []
    parametros = []

    if pesquisa:
        condicoes.append(
            "(titulo LIKE ? OR conteudo LIKE ? OR materia LIKE ? "
            "OR categoria LIKE ?)"
        )
        termo = f"%{pesquisa}%"
        parametros.extend([termo, termo, termo, termo])

    if materia_selecionada:
        condicoes.append("materia = ?")
        parametros.append(materia_selecionada)

    if categoria_selecionada:
        condicoes.append("categoria = ?")
        parametros.append(categoria_selecionada)

    if somente_favoritas:
        condicoes.append("favorita = 1")

    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)

    sql += f" ORDER BY {ordenacoes_permitidas[ordenacao]}"

    with conexao_aberta() as conexao:
        anotacoes = conexao.execute(sql, parametros).fetchall()

        materias_cadastradas = [
            materia["nome"] for materia in buscar_materias(conexao)
        ]
        assuntos_disponiveis = buscar_assuntos(conexao)

        metas_materias = conexao.execute("""
            SELECT
                materias.id,
                materias.nome,
                COALESCE(metas_semanais.minutos_meta, 0) AS minutos_meta,
                COALESCE(estudos.minutos_estudados, 0) AS minutos_estudados
            FROM materias
            LEFT JOIN metas_semanais
                ON metas_semanais.materia_id = materias.id
            LEFT JOIN (
                SELECT materia, SUM(duracao_minutos) AS minutos_estudados
                FROM sessoes_estudo
                WHERE data_estudo BETWEEN
                    date('now', 'localtime', '-6 days')
                    AND date('now', 'localtime')
                GROUP BY materia
            ) AS estudos
                ON estudos.materia = materias.nome
            ORDER BY materias.nome COLLATE NOCASE
        """).fetchall()

        materias = conexao.execute("""
            SELECT DISTINCT materia
            FROM anotacoes
            ORDER BY materia
        """).fetchall()

        total_anotacoes = conexao.execute(
            "SELECT COUNT(*) FROM anotacoes"
        ).fetchone()[0]

        total_materias = conexao.execute(
            "SELECT COUNT(DISTINCT materia) FROM anotacoes"
        ).fetchone()[0]

        total_favoritas = conexao.execute(
            "SELECT COUNT(*) FROM anotacoes WHERE favorita = 1"
        ).fetchone()[0]

        total_categorias = conexao.execute(
            "SELECT COUNT(DISTINCT categoria) FROM anotacoes"
        ).fetchone()[0]

        meta = conexao.execute("""
            SELECT minutos_meta
            FROM meta_diaria
            WHERE id = 1
        """).fetchone()

        minutos_meta = meta["minutos_meta"] if meta else 60

        minutos_estudados = conexao.execute("""
            SELECT COALESCE(SUM(duracao_minutos), 0)
            FROM sessoes_estudo
            WHERE data_estudo = date('now', 'localtime')
        """).fetchone()[0]

        sessoes_semana = conexao.execute("""
            WITH RECURSIVE dias(data_estudo, indice) AS (
                SELECT date('now', 'localtime', '-6 days'), 0
                UNION ALL
                SELECT date(data_estudo, '+1 day'), indice + 1
                FROM dias
                WHERE indice < 6
            )
            SELECT
                dias.data_estudo,
                COALESCE(SUM(sessoes_estudo.duracao_minutos), 0) AS minutos
            FROM dias
            LEFT JOIN sessoes_estudo
                ON sessoes_estudo.data_estudo = dias.data_estudo
            GROUP BY dias.data_estudo, dias.indice
            ORDER BY dias.indice
        """).fetchall()

        comparativo_semanal = conexao.execute("""
            WITH limites AS (
                SELECT
                    date('now', 'localtime', 'weekday 0', '-6 days') AS inicio_atual,
                    date('now', 'localtime', 'weekday 0', '-13 days') AS inicio_anterior,
                    (CAST(strftime('%w', 'now', 'localtime') AS INTEGER) + 6) % 7
                        AS dias_decorridos,
                    date('now', 'localtime') AS hoje
            )
            SELECT
                COALESCE(SUM(CASE
                    WHEN sessoes_estudo.data_estudo
                        BETWEEN limites.inicio_atual AND limites.hoje
                    THEN sessoes_estudo.duracao_minutos
                    ELSE 0
                END), 0) AS minutos_atuais,
                COALESCE(SUM(CASE
                    WHEN sessoes_estudo.data_estudo >= limites.inicio_anterior
                        AND sessoes_estudo.data_estudo < date(
                            limites.inicio_anterior,
                            '+' || (limites.dias_decorridos + 1) || ' days'
                        )
                    THEN sessoes_estudo.duracao_minutos
                    ELSE 0
                END), 0) AS minutos_anterior
            FROM limites
            LEFT JOIN sessoes_estudo
                ON sessoes_estudo.data_estudo >= limites.inicio_anterior
                AND sessoes_estudo.data_estudo <= limites.hoje
        """).fetchone()

        materia_destaque_semana = conexao.execute("""
            SELECT materia, SUM(duracao_minutos) AS minutos
            FROM sessoes_estudo
            WHERE data_estudo BETWEEN
                date('now', 'localtime', 'weekday 0', '-6 days')
                AND date('now', 'localtime')
            GROUP BY materia
            ORDER BY minutos DESC, materia COLLATE NOCASE
            LIMIT 1
        """).fetchone()

        total_cursos = conexao.execute(
            "SELECT COUNT(*) FROM cursos"
        ).fetchone()[0]

        total_modulos = conexao.execute(
            "SELECT COUNT(*) FROM modulos"
        ).fetchone()[0]

        total_aulas = conexao.execute(
            "SELECT COUNT(*) FROM aulas"
        ).fetchone()[0]

        aulas_concluidas = conexao.execute("""
            SELECT COUNT(*)
            FROM aulas
            WHERE concluida = 1
        """).fetchone()[0]

        cursos_painel = conexao.execute("""
            SELECT
                cursos.id,
                cursos.titulo,
                cursos.descricao,
                materias.nome AS materia_nome,
                COUNT(DISTINCT modulos.id) AS total_modulos,
                COUNT(DISTINCT aulas.id) AS total_aulas,
                COUNT(
                    DISTINCT CASE
                        WHEN aulas.concluida = 1 THEN aulas.id
                    END
                ) AS aulas_concluidas
            FROM cursos
            LEFT JOIN materias
                ON materias.id = cursos.materia_id
            LEFT JOIN modulos
                ON modulos.curso_id = cursos.id
            LEFT JOIN aulas
                ON aulas.modulo_id = modulos.id
            GROUP BY
                cursos.id,
                cursos.titulo,
                cursos.descricao,
                materias.nome
            ORDER BY cursos.id DESC
            LIMIT 6
        """).fetchall()

        proxima_aula = conexao.execute("""
            SELECT
                cursos.id AS curso_id,
                cursos.titulo AS curso_titulo,
                modulos.id AS modulo_id,
                modulos.titulo AS modulo_titulo,
                aulas.id AS aula_id,
                aulas.titulo AS aula_titulo
            FROM cursos
            JOIN modulos
                ON modulos.curso_id = cursos.id
            JOIN aulas
                ON aulas.modulo_id = modulos.id
            WHERE aulas.concluida = 0
            ORDER BY
                cursos.id DESC,
                modulos.ordem,
                modulos.id,
                aulas.ordem,
                aulas.id
            LIMIT 1
        """).fetchone()

    progresso_cursos = (
        round(aulas_concluidas / total_aulas * 100)
        if total_aulas > 0 else 0
    )

    progresso = (
        min(round(minutos_estudados / minutos_meta * 100), 100)
        if minutos_meta > 0 else 0
    )

    minutos_restantes = max(minutos_meta - minutos_estudados, 0)

    nomes_dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    minutos_por_dia = [sessao["minutos"] for sessao in sessoes_semana]
    maior_dia = max(minutos_por_dia, default=0)
    estudo_semana = [
        {
            "data": sessao["data_estudo"],
            "rotulo": nomes_dias[date.fromisoformat(sessao["data_estudo"]).weekday()],
            "minutos": sessao["minutos"],
            "percentual": round(sessao["minutos"] / maior_dia * 100) if maior_dia else 0,
        }
        for sessao in sessoes_semana
    ]
    minutos_semana = sum(minutos_por_dia)
    dias_ativos_semana = sum(1 for minutos in minutos_por_dia if minutos > 0)
    minutos_semana_atual = comparativo_semanal["minutos_atuais"]
    minutos_semana_anterior = comparativo_semanal["minutos_anterior"]
    diferenca_semanal = minutos_semana_atual - minutos_semana_anterior
    variacao_semanal = (
        round(diferenca_semanal / minutos_semana_anterior * 100)
        if minutos_semana_anterior > 0 else None
    )
    progresso_metas_materias = []
    for meta_materia in metas_materias:
        minutos_meta_materia = meta_materia["minutos_meta"]
        minutos_estudados_materia = meta_materia["minutos_estudados"]
        progresso_meta_materia = (
            min(round(minutos_estudados_materia / minutos_meta_materia * 100), 100)
            if minutos_meta_materia > 0 else 0
        )
        progresso_metas_materias.append({
            **dict(meta_materia),
            "progresso": progresso_meta_materia,
            "minutos_restantes": max(
                minutos_meta_materia - minutos_estudados_materia,
                0
            ),
        })

    return render_template(
        "index.html",
        anotacoes=anotacoes,
        materias=materias,
        materias_cadastradas=materias_cadastradas,
        assuntos_disponiveis=assuntos_disponiveis,
        progresso_metas_materias=progresso_metas_materias,
        categorias=CATEGORIAS,
        pesquisa=pesquisa,
        materia_selecionada=materia_selecionada,
        categoria_selecionada=categoria_selecionada,
        somente_favoritas=somente_favoritas,
        ordenacao=ordenacao,
        total_anotacoes=total_anotacoes,
        total_materias=total_materias,
        total_favoritas=total_favoritas,
        total_categorias=total_categorias,
        minutos_meta=minutos_meta,
        minutos_estudados=minutos_estudados,
        progresso=progresso,
        minutos_restantes=minutos_restantes,
        estudo_semana=estudo_semana,
        minutos_semana=minutos_semana,
        dias_ativos_semana=dias_ativos_semana,
        minutos_semana_atual=minutos_semana_atual,
        minutos_semana_anterior=minutos_semana_anterior,
        diferenca_semanal=diferenca_semanal,
        variacao_semanal=variacao_semanal,
        materia_destaque_semana=materia_destaque_semana,
        total_cursos=total_cursos,
        total_modulos=total_modulos,
        total_aulas=total_aulas,
        aulas_concluidas=aulas_concluidas,
        progresso_cursos=progresso_cursos,
        cursos_painel=cursos_painel,
        proxima_aula=proxima_aula
    )


# ==========================================
# CADASTRAR ANOTAÇÃO
# ==========================================

@app.route("/nova-anotacao", methods=["POST"])
def nova_anotacao():
    titulo = validar_texto(request.form.get("titulo", ""), 100)
    materia = validar_texto(request.form.get("materia", ""), 60)
    conteudo = validar_texto(request.form.get("conteudo", ""), 10000)
    categoria = validar_texto(
        request.form.get("categoria", "Geral"),
        60
    )
    assunto_id_texto = request.form.get("assunto_id", "").strip()

    if (
        titulo is None
        or materia is None
        or conteudo is None
        or categoria not in CATEGORIAS
    ):
        flash("Confira os campos da anotação e tente novamente.", "erro")
        return redirect(url_for("inicio"))

    with conexao_aberta() as conexao:
        assunto_id, erro_assunto = validar_assunto_da_materia(
            conexao,
            assunto_id_texto,
            materia
        )
        if erro_assunto:
            flash(erro_assunto, "erro")
            return redirect(url_for("inicio") + "#nova-anotacao")

        conexao.execute("""
            INSERT INTO anotacoes
                (titulo, materia, conteudo, categoria, assunto_id)
            VALUES (?, ?, ?, ?, ?)
        """, (titulo, materia, conteudo, categoria, assunto_id))

    flash("Anotação cadastrada com sucesso!", "sucesso")
    return redirect(url_for("inicio"))


# ==========================================
# REGISTRAR SESSÃO DE ESTUDO
# ==========================================

@app.route("/registrar-estudo", methods=["POST"])
def registrar_estudo():
    materia = validar_texto(
        request.form.get("materia", ""),
        60
    )

    duracao_texto = request.form.get("duracao_minutos", "")
    identificador_texto = request.form.get("identificador", "").strip()

    with conexao_aberta() as conexao:
        materias_cadastradas = {
            item["nome"] for item in buscar_materias(conexao)
        }

    if materia not in materias_cadastradas:
        flash("Selecione uma matéria válida.", "erro")
        return redirect(url_for("inicio"))

    duracao = validar_inteiro(duracao_texto, 1, 1440)

    if duracao is None:
        flash("A duração deve ser entre 1 e 1.440 minutos.", "erro")
        return redirect(url_for("inicio"))

    try:
        identificador = str(uuid.UUID(identificador_texto))
    except (ValueError, TypeError, AttributeError):
        flash("Identificador da sessão inválido.", "erro")
        return redirect(url_for("inicio"))

    with conexao_aberta() as conexao:
        conexao.execute("""
            INSERT INTO sessoes_estudo
                (materia, duracao_minutos, identificador)
            VALUES (?, ?, ?)
            ON CONFLICT(identificador) DO NOTHING
        """, (materia, duracao, identificador))

    flash("Sessão de estudo registrada!", "sucesso")
    return redirect(url_for("inicio"))


# ==========================================
# EDITAR SESSÃO DE ESTUDO
# ==========================================

@app.route("/editar-sessao/<int:id>", methods=["GET", "POST"])
def editar_sessao(id):
    with conexao_aberta() as conexao:
        sessao = conexao.execute("""
            SELECT id, materia, duracao_minutos, data_estudo
            FROM sessoes_estudo
            WHERE id = ?
        """, (id,)).fetchone()

        if sessao is None:
            abort(404)

        materias_cadastradas = [
            materia["nome"] for materia in buscar_materias(conexao)
        ]
        # Mantém editáveis as sessões históricas de matérias removidas da grade.
        if sessao["materia"] not in materias_cadastradas:
            materias_cadastradas.append(sessao["materia"])

        if request.method == "POST":
            materia = validar_texto(
                request.form.get("materia", ""),
                60
            )

            duracao = validar_inteiro(
                request.form.get("duracao_minutos", ""),
                1,
                1440
            )

            if materia not in materias_cadastradas or duracao is None:
                return render_template(
                    "editar_sessao.html",
                    sessao=sessao,
                    materias=materias_cadastradas,
                    erro=(
                        "Selecione uma matéria válida e informe "
                        "uma duração entre 1 e 1.440 minutos."
                    )
                ), 400

            conexao.execute("""
                UPDATE sessoes_estudo
                SET materia = ?,
                    duracao_minutos = ?
                WHERE id = ?
            """, (materia, duracao, id))

            flash("Sessão de estudo atualizada!", "sucesso")
            return redirect(url_for("historico") + "#sessoes")

    return render_template(
        "editar_sessao.html",
        sessao=sessao,
        materias=materias_cadastradas,
        erro=None
    )


# ==========================================
# EXCLUIR SESSÃO DE ESTUDO
# ==========================================

@app.route("/excluir-sessao/<int:id>", methods=["POST"])
def excluir_sessao(id):
    with conexao_aberta() as conexao:
        sessao = conexao.execute("""
            SELECT id
            FROM sessoes_estudo
            WHERE id = ?
        """, (id,)).fetchone()

        if sessao is None:
            abort(404)

        conexao.execute("""
            DELETE FROM sessoes_estudo
            WHERE id = ?
        """, (id,))

    flash("Sessão de estudo excluída!", "sucesso")
    return redirect(url_for("historico") + "#sessoes")


# ==========================================
# DEFINIR META DIÁRIA
# ==========================================

@app.route("/definir-meta", methods=["POST"])
def definir_meta():
    minutos = validar_inteiro(
        request.form.get("minutos_meta", ""),
        1,
        1440
    )

    if minutos is None:
        flash("A meta deve ser entre 1 e 1.440 minutos.", "erro")
        return redirect(url_for("inicio"))

    with conexao_aberta() as conexao:
        conexao.execute("""
            INSERT INTO meta_diaria (id, minutos_meta)
            VALUES (1, ?)
            ON CONFLICT(id)
            DO UPDATE SET minutos_meta = excluded.minutos_meta
        """, (minutos,))

    flash("Meta diária atualizada!", "sucesso")
    return redirect(url_for("inicio"))


@app.route("/meta-semanal", methods=["POST"])
def definir_meta_semanal():
    """Cria, atualiza ou remove a meta semanal de uma matéria."""
    materia_id = validar_inteiro(
        request.form.get("materia_id", ""),
        1,
        2147483647
    )
    minutos = validar_inteiro(
        request.form.get("minutos_meta", ""),
        0,
        10080
    )

    if materia_id is None or minutos is None:
        flash(
            "Informe uma matéria válida e uma meta entre 0 e 10.080 minutos.",
            "erro"
        )
        return redirect(url_for("inicio") + "#metas-materias")

    with conexao_aberta() as conexao:
        materia = conexao.execute(
            "SELECT id FROM materias WHERE id = ?",
            (materia_id,)
        ).fetchone()

        if materia is None:
            flash("A matéria selecionada não existe.", "erro")
            return redirect(url_for("inicio") + "#metas-materias")

        if minutos == 0:
            conexao.execute(
                "DELETE FROM metas_semanais WHERE materia_id = ?",
                (materia_id,)
            )
            mensagem = "Meta semanal removida."
        else:
            conexao.execute("""
                INSERT INTO metas_semanais (materia_id, minutos_meta)
                VALUES (?, ?)
                ON CONFLICT(materia_id)
                DO UPDATE SET minutos_meta = excluded.minutos_meta
            """, (materia_id, minutos))
            mensagem = "Meta semanal salva!"

    flash(mensagem, "sucesso")
    return redirect(url_for("inicio") + "#metas-materias")


# ==========================================
# EDITAR ANOTAÇÃO
# ==========================================

@app.route("/editar-anotacao/<int:id>", methods=["GET", "POST"])
def editar_anotacao(id):
    with conexao_aberta() as conexao:
        anotacao = conexao.execute("""
            SELECT *
            FROM anotacoes
            WHERE id = ?
        """, (id,)).fetchone()

        if anotacao is None:
            abort(404)

        assuntos_disponiveis = buscar_assuntos(conexao)

        if request.method == "POST":
            titulo = validar_texto(
                request.form.get("titulo", ""),
                100
            )
            materia = validar_texto(
                request.form.get("materia", ""),
                60
            )
            conteudo = validar_texto(
                request.form.get("conteudo", ""),
                10000
            )
            categoria = validar_texto(
                request.form.get("categoria", ""),
                60
            )
            assunto_id_texto = request.form.get("assunto_id", "").strip()

            if (
                titulo is None
                or materia is None
                or conteudo is None
                or categoria not in CATEGORIAS
            ):
                return render_template(
                    "editar.html",
                    anotacao=anotacao,
                    categorias=CATEGORIAS,
                    assuntos_disponiveis=assuntos_disponiveis,
                    erro="Confira os campos e tente novamente."
                ), 400

            assunto_id, erro_assunto = validar_assunto_da_materia(
                conexao,
                assunto_id_texto,
                materia
            )
            if erro_assunto:
                return render_template(
                    "editar.html",
                    anotacao=anotacao,
                    categorias=CATEGORIAS,
                    assuntos_disponiveis=assuntos_disponiveis,
                    erro=erro_assunto
                ), 400

            conexao.execute("""
                UPDATE anotacoes
                SET titulo = ?,
                    materia = ?,
                    conteudo = ?,
                    categoria = ?,
                    assunto_id = ?
                WHERE id = ?
            """, (
                titulo,
                materia,
                conteudo,
                categoria,
                assunto_id,
                id
            ))

            flash("Anotação atualizada com sucesso!", "sucesso")
            return redirect(url_for("inicio"))

    return render_template(
        "editar.html",
        anotacao=anotacao,
        categorias=CATEGORIAS,
        assuntos_disponiveis=assuntos_disponiveis,
        erro=None
    )


# ==========================================
# EXCLUIR ANOTAÇÃO
# ==========================================

@app.route("/excluir-anotacao/<int:id>", methods=["POST"])
def excluir_anotacao(id):
    with conexao_aberta() as conexao:
        anotacao = conexao.execute("""
            SELECT id
            FROM anotacoes
            WHERE id = ?
        """, (id,)).fetchone()

        if anotacao is None:
            abort(404)

        conexao.execute("""
            DELETE FROM anotacoes
            WHERE id = ?
        """, (id,))

    flash("Anotação excluída com sucesso!", "sucesso")
    return redirect(url_for("inicio"))


# ==========================================
# FAVORITAR OU DESFAVORITAR ANOTAÇÃO
# ==========================================

@app.route("/favoritar-anotacao/<int:id>", methods=["POST"])
def favoritar_anotacao(id):
    with conexao_aberta() as conexao:
        anotacao = conexao.execute("""
            SELECT id, favorita
            FROM anotacoes
            WHERE id = ?
        """, (id,)).fetchone()

        if anotacao is None:
            abort(404)

        nova_favorita = 0 if anotacao["favorita"] else 1

        conexao.execute("""
            UPDATE anotacoes
            SET favorita = ?
            WHERE id = ?
        """, (nova_favorita, id))

    if nova_favorita:
        flash("Anotação adicionada aos favoritos!", "sucesso")
    else:
        flash("Anotação removida dos favoritos!", "sucesso")

    return redirect(url_for("inicio"))


# ==========================================
# HISTÓRICO DE ESTUDOS
# ==========================================

@app.route("/historico")
def historico():
    with conexao_aberta() as conexao:
        sessoes = conexao.execute("""
            SELECT
                id,
                materia,
                duracao_minutos,
                data_estudo,
                criado_em
            FROM sessoes_estudo
            ORDER BY data_estudo DESC, id DESC
        """).fetchall()

        total_minutos = conexao.execute("""
            SELECT COALESCE(SUM(duracao_minutos), 0)
            FROM sessoes_estudo
        """).fetchone()[0]

        total_sessoes = conexao.execute("""
            SELECT COUNT(*)
            FROM sessoes_estudo
        """).fetchone()[0]

        materias_estudadas = conexao.execute("""
            SELECT
                materia,
                COUNT(*) AS total_sessoes,
                SUM(duracao_minutos) AS total_minutos
            FROM sessoes_estudo
            GROUP BY materia
            ORDER BY total_minutos DESC, materia
        """).fetchall()

        estudos_semana = conexao.execute("""
            WITH RECURSIVE dias(data) AS (
                SELECT date('now', 'localtime', 'weekday 0', '-6 days')
                UNION ALL
                SELECT date(data, '+1 day')
                FROM dias
                WHERE data < date('now', 'localtime', 'weekday 0')
            )
            SELECT
                dias.data,
                COALESCE(SUM(sessoes_estudo.duracao_minutos), 0)
                    AS minutos
            FROM dias
            LEFT JOIN sessoes_estudo
                ON sessoes_estudo.data_estudo = dias.data
            GROUP BY dias.data
            ORDER BY dias.data
        """).fetchall()

    nomes_dias = [
        "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
        "Sexta-feira", "Sábado", "Domingo"
    ]
    estudos_semana = [
        {
            "dia_nome": nomes_dias[date.fromisoformat(dia["data"]).weekday()],
            "total_minutos": dia["minutos"]
        }
        for dia in estudos_semana
    ]
    total_semana = sum(dia["total_minutos"] for dia in estudos_semana)

    media_diaria = round(total_semana / 7)

    maior_tempo = max(
        (dia["total_minutos"] for dia in estudos_semana),
        default=0
    )

    melhor_dia = next(
        (
            dia
            for dia in estudos_semana
            if dia["total_minutos"] == maior_tempo and maior_tempo > 0
        ),
        None
    )

    return render_template(
        "historico.html",
        sessoes=sessoes,
        resumo={
            "total_minutos": total_minutos,
            "total_sessoes": total_sessoes
        },
        materias_estudadas=materias_estudadas,
        estudos_semana=estudos_semana,
        total_minutos=total_minutos,
        total_sessoes=total_sessoes,
        total_semana=total_semana,
        media_diaria=media_diaria,
        maior_tempo=maior_tempo,
        melhor_dia=melhor_dia
    )


# ==========================================
# CALENDÁRIO DE ESTUDOS
# ==========================================

@app.route("/calendario", endpoint="calendario")
def calendario_estudos():
    hoje = date.today()

    ano_atual = validar_inteiro(
        request.args.get("ano", str(hoje.year)),
        2000,
        2100
    )

    mes_atual = validar_inteiro(
        request.args.get("mes", str(hoje.month)),
        1,
        12
    )

    if ano_atual is None or mes_atual is None:
        ano_atual = hoje.year
        mes_atual = hoje.month

    calendario = calendar.Calendar(
        firstweekday=0
    ).monthdayscalendar(ano_atual, mes_atual)

    nomes_meses = [
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro"
    ]

    nome_mes = nomes_meses[mes_atual - 1]

    if mes_atual == 1:
        mes_anterior = 12
        ano_anterior = ano_atual - 1
    else:
        mes_anterior = mes_atual - 1
        ano_anterior = ano_atual

    if mes_atual == 12:
        mes_proximo = 1
        ano_proximo = ano_atual + 1
    else:
        mes_proximo = mes_atual + 1
        ano_proximo = ano_atual

    data_selecionada = request.args.get(
        "data",
        ""
    ).strip()
    data_selecionada_objeto = None

    try:
        data_objeto = date.fromisoformat(data_selecionada)

        if (
            data_objeto.year != ano_atual
            or data_objeto.month != mes_atual
        ):
            data_selecionada = ""
        else:
            data_selecionada_objeto = data_objeto
    except (ValueError, TypeError):
        data_selecionada = ""

    with conexao_aberta() as conexao:
        registros_por_dia = conexao.execute("""
            SELECT
                data_estudo,
                SUM(duracao_minutos) AS minutos,
                COUNT(*) AS quantidade_sessoes
            FROM sessoes_estudo
            WHERE strftime('%Y', data_estudo) = ?
              AND strftime('%m', data_estudo) = ?
            GROUP BY data_estudo
        """, (
            str(ano_atual),
            f"{mes_atual:02d}"
        )).fetchall()

        sessoes_por_data = {
            registro["data_estudo"]: {
                "minutos": registro["minutos"],
                "quantidade_sessoes": registro["quantidade_sessoes"]
            }
            for registro in registros_por_dia
        }

        sessoes_dia_selecionado = []

        if data_selecionada:
            sessoes_dia_selecionado = conexao.execute("""
                SELECT
                    id,
                    materia,
                    duracao_minutos,
                    data_estudo,
                    criado_em
                FROM sessoes_estudo
                WHERE data_estudo = ?
                ORDER BY id DESC
            """, (data_selecionada,)).fetchall()

    total_mes = sum(
        registro["minutos"] for registro in registros_por_dia
    )
    total_sessoes_mes = sum(
        registro["quantidade_sessoes"] for registro in registros_por_dia
    )
    dias_estudados = len(registros_por_dia)
    lista_dias = [
        {
            "data_formatada": date.fromisoformat(
                registro["data_estudo"]
            ).strftime("%d/%m/%Y"),
            "sessoes": registro["quantidade_sessoes"],
            "minutos": registro["minutos"]
        }
        for registro in sorted(
            registros_por_dia,
            key=lambda item: item["data_estudo"],
            reverse=True
        )
    ]

    return render_template(
        "calendario.html",
        ano=ano_atual,
        mes=mes_atual,
        hoje=hoje.isoformat(),
        nomes_dias=["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
        semanas=calendario,
        nome_mes=nome_mes,
        mes_anterior={"mes": mes_anterior, "ano": ano_anterior},
        proximo_mes={"mes": mes_proximo, "ano": ano_proximo},
        registros_dias=sessoes_por_data,
        data_selecionada=data_selecionada_objeto,
        sessoes_dia=sessoes_dia_selecionado,
        total_mes=total_mes,
        dias_estudados=dias_estudados,
        total_sessoes_mes=total_sessoes_mes,
        lista_dias=lista_dias
    )


# ==========================================
# INICIALIZAÇÃO DO APLICATIVO
# ==========================================

if __name__ == "__main__":
    _garantir_base_inicial()

    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )
