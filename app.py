
from flask import Flask, render_template, request, redirect, url_for, abort, flash
from flask_wtf.csrf import CSRFProtect
import os
import uuid
import calendar
from datetime import date
import unicodedata

from database import conexao_aberta, criar_tabelas

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("DEVSTUDY_SECRET_KEY")

csrf = CSRFProtect(app)

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

MATERIAS_ESTUDO = [
    "Python",
    "JavaScript",
    "Banco de dados",
    "Redes de computadores",
    "Faculdade - ADS",
    "Geral"
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
        SELECT id, nome, descricao
        FROM materias
        ORDER BY nome COLLATE NOCASE
    """).fetchall()


def normalizar_nome_materia(nome):
    """Normaliza um nome para comparação sem diferenças de caixa."""
    return unicodedata.normalize("NFC", nome).casefold()


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
        materias = buscar_materias(conexao)

    return render_template(
        "materias.html",
        materias=materias,
        erro=erro
    )


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

    sql = "SELECT * FROM anotacoes"
    condicoes = []
    parametros = []

    if pesquisa:
        condicoes.append(
            "(titulo LIKE ? OR conteudo LIKE ? OR materia LIKE ?)"
        )
        termo = f"%{pesquisa}%"
        parametros.extend([termo, termo, termo])

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

    sql += " ORDER BY id DESC"

    with conexao_aberta() as conexao:
        anotacoes = conexao.execute(sql, parametros).fetchall()

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

    progresso_cursos = (
        round(aulas_concluidas / total_aulas * 100)
        if total_aulas > 0 else 0
    )

    progresso = (
        min(round(minutos_estudados / minutos_meta * 100), 100)
        if minutos_meta > 0 else 0
    )

    minutos_restantes = max(minutos_meta - minutos_estudados, 0)

    return render_template(
        "index.html",
        anotacoes=anotacoes,
        materias=materias,
        categorias=CATEGORIAS,
        pesquisa=pesquisa,
        materia_selecionada=materia_selecionada,
        categoria_selecionada=categoria_selecionada,
        somente_favoritas=somente_favoritas,
        total_anotacoes=total_anotacoes,
        total_materias=total_materias,
        total_favoritas=total_favoritas,
        total_categorias=total_categorias,
        minutos_meta=minutos_meta,
        minutos_estudados=minutos_estudados,
        progresso=progresso,
        minutos_restantes=minutos_restantes,
        total_cursos=total_cursos,
        total_modulos=total_modulos,
        total_aulas=total_aulas,
        aulas_concluidas=aulas_concluidas,
        progresso_cursos=progresso_cursos,
        cursos_painel=cursos_painel
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

    if (
        titulo is None
        or materia is None
        or conteudo is None
        or categoria not in CATEGORIAS
    ):
        flash("Confira os campos da anotação e tente novamente.", "erro")
        return redirect(url_for("inicio"))

    with conexao_aberta() as conexao:
        conexao.execute("""
            INSERT INTO anotacoes
                (titulo, materia, conteudo, categoria)
            VALUES (?, ?, ?, ?)
        """, (titulo, materia, conteudo, categoria))

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

    if materia not in MATERIAS_ESTUDO:
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

            if materia not in MATERIAS_ESTUDO or duracao is None:
                return render_template(
                    "editar_sessao.html",
                    sessao=sessao,
                    materias=MATERIAS_ESTUDO,
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
        materias=MATERIAS_ESTUDO,
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
                    erro="Confira os campos e tente novamente."
                ), 400

            conexao.execute("""
                UPDATE anotacoes
                SET titulo = ?,
                    materia = ?,
                    conteudo = ?,
                    categoria = ?
                WHERE id = ?
            """, (
                titulo,
                materia,
                conteudo,
                categoria,
                id
            ))

            flash("Anotação atualizada com sucesso!", "sucesso")
            return redirect(url_for("inicio"))

    return render_template(
        "editar.html",
        anotacao=anotacao,
        categorias=CATEGORIAS,
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

        resumo_materias = conexao.execute("""
            SELECT
                materia,
                COUNT(*) AS quantidade_sessoes,
                SUM(duracao_minutos) AS total_minutos
            FROM sessoes_estudo
            GROUP BY materia
            ORDER BY total_minutos DESC, materia
        """).fetchall()

        ultimos_sete_dias = conexao.execute("""
            WITH RECURSIVE dias(data) AS (
                SELECT date('now', 'localtime', '-6 days')
                UNION ALL
                SELECT date(data, '+1 day')
                FROM dias
                WHERE data < date('now', 'localtime')
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

    total_semana = sum(
        dia["minutos"] for dia in ultimos_sete_dias
    )

    media_diaria = round(total_semana / 7)

    maior_tempo = max(
        (dia["minutos"] for dia in ultimos_sete_dias),
        default=0
    )

    melhor_dia = next(
        (
            dia["data"]
            for dia in ultimos_sete_dias
            if dia["minutos"] == maior_tempo and maior_tempo > 0
        ),
        None
    )

    return render_template(
        "historico.html",
        sessoes=sessoes,
        total_minutos=total_minutos,
        total_sessoes=total_sessoes,
        resumo_materias=resumo_materias,
        ultimos_sete_dias=ultimos_sete_dias,
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

    try:
        data_objeto = date.fromisoformat(data_selecionada)

        if (
            data_objeto.year != ano_atual
            or data_objeto.month != mes_atual
        ):
            data_selecionada = ""
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

    return render_template(
        "calendario.html",
        ano_atual=ano_atual,
        mes_atual=mes_atual,
        calendario=calendario,
        nome_mes=nome_mes,
        mes_anterior=mes_anterior,
        ano_anterior=ano_anterior,
        mes_proximo=mes_proximo,
        ano_proximo=ano_proximo,
        sessoes_por_data=sessoes_por_data,
        data_selecionada=data_selecionada,
        sessoes_dia_selecionado=sessoes_dia_selecionado
    )


# ==========================================
# INICIALIZAÇÃO DO APLICATIVO
# ==========================================

if __name__ == "__main__":
    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "A variável DEVSTUDY_SECRET_KEY não está configurada. "
            "Configure a chave antes de iniciar o aplicativo."
        )

    criar_tabelas()

    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )
