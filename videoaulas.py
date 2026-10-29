"""Recomendações públicas de videoaulas organizadas por assunto.

As recomendações diretas foram conferidas em páginas públicas de universidades
e canais educacionais. Para assuntos sem curadoria direta, a função mantém uma
busca temática claramente identificada como sugestão automática.
"""

from urllib.parse import quote_plus


# Chave: trecho que aparece no nome do módulo. Links diretos para aulas públicas.
VIDEOAULAS_CURADAS = {
    # Comunicação e formação geral
    "Público, propósito e clareza": [
        ("Português corporativo: comunicação clara e objetiva", "Flávia Rita — curso público", "https://flaviarita.com/curso/aulas-gratuitas-curso-online-de-portugues-corporativoempresarial-professora-flavia-rita"),
    ],
    "Relatórios e documentação": [
        ("Língua Portuguesa e Redação Oficial — aulas sobre escrita clara", "Escola Superior do Ministério Público da União", "https://escola.mpu.mp.br/plataforma-aprender/acervo-educacional/conteudo/lingua-portuguesa-e-redacao-oficial"),
    ],
    "Apresentação e revisão": [
        ("A apresentação oral — planejamento, execução e avaliação", "Estudo Autónomo / DGE Portugal", "https://estudoautonomo.dge.mec.pt/index.php/recurso/apresentacao-oral"),
    ],
    "Tecnologia e sociedade": [
        ("Novas tecnologias de informação e comunicação", "TV Unesp", "https://youtu.be/dUnMYUmyvOs"),
        ("Tecnologia em Perspectiva — impactos e desafios", "TV UERJ", "https://www.cte.uerj.br/tvuerj/programas/tecnologia-em-perspectiva"),
    ],
    "Impactos e argumentação baseada em evidências": [
        ("Algoritmos e sociedade — debate público", "CIDAD / UFSC", "https://cidad.bu.ufsc.br/cidad-convida/"),
        ("ITS ao Vivo — debates sobre tecnologia e sociedade", "ITS Rio", "https://itsrio.org/pt/videos/its-ao-vivo/"),
    ],
    "Dimensões da sustentabilidade": [
        ("Economia circular e transformação digital para a sustentabilidade", "UFF / eduCAPES", "https://www.youtube.com/live/Fv_GLUKPdMA"),
    ],
    "Impacto do ciclo de vida digital": [
        ("Economia circular e transformação digital para a sustentabilidade", "UFF / eduCAPES", "https://www.youtube.com/live/Fv_GLUKPdMA"),
    ],
    "Projeto inclusivo e avaliação": [
        ("Acessibilidade em produtos e serviços digitais — recursos do W3C", "W3C WAI", "https://www.w3.org/WAI/videos/standards-and-benefits/"),
    ],
    "Objetivos, escopo e riscos": [
        ("Gestão de projetos — escopo, tempo e custos (módulo 2)", "ENAP", "https://www.youtube.com/watch?v=7lfeEgieQm8"),
    ],
    "Experimentos e validação": [
        ("Construindo e testando MVPs de forma eficiente", "Anprotec / Sebrae", "https://sebraetecni.anprotec.org.br/biblioteca/como-desenvolver-mvps-eficientes-para-fortalecer-sua-startup/"),
    ],
    "Entrega, métricas e retrospectiva": [
        ("Webinares de gestão de projetos — métricas, entrega e riscos", "Projetos e TI", "https://projetoseti.com.br/webinares/"),
    ],
    "Memória e processador": [
        ("Introdução à hierarquia de memória e suas tecnologias", "e-Aulas USP", "https://eaulas.usp.br/portal/vmsresources/videos/video.action?idItem=22597"),
    ],
    "Disponibilidade, custos e segurança": [
        ("Amazon S3 Deep Dive — disponibilidade, custos e segurança", "AWS", "https://aws.amazon.com/pt/video/watch/65acaf1dec0/"),
    ],
    "Rede, armazenamento e identidade": [
        ("Amazon S3 — políticas de acesso com IAM", "AWS", "https://aws.amazon.com/pt/s3/security/"),
    ],
    "Experiência e navegação móvel": [
        ("Android Studio — navegação entre telas com Kotlin", "Stack Mobile", "https://www.youtube.com/watch?v=McvhwErPivA"),
    ],
    "Dados, permissões e conectividade": [
        ("Permissões em tempo de execução no Android — tutorial com vídeo", "Thiengo", "https://www.thiengo.com.br/sistema-de-permissoes-em-tempo-de-execucao-android-m"),
        ("Conectar à rede — permissões e operações de conectividade", "Android Developers", "https://developer.android.com/develop/connectivity/network-ops/connecting?hl=pt-br"),
    ],
    "Testes, acessibilidade e distribuição": [
        ("Acessibilidade em produtos e serviços digitais — recursos do W3C", "W3C WAI", "https://www.w3.org/WAI/videos/standards-and-benefits/"),
    ],
    "Projeto, implementação e revisão": [
        ("Projeto de Software — videoaulas de graduação", "Canal CECIERJ", "https://canal.cecierj.edu.br/busca/?area=computacao&busca=Projeto+de+Software&tipo=videoaula-interativa"),
    ],
    "Testes, entrega e manutenção": [
        ("Entrega e Manutenção do Software — videoaula de graduação", "Canal CECIERJ", "https://canal.cecierj.edu.br/busca/?area=computacao&busca=Entrega+e+Manuten%C3%A7%C3%A3o+do+Software&tipo=videoaula-interativa"),
    ],
    "Decisões, laços e funções": [
        ("Python básico — condicionais, laços e funções", "FEI", "https://python.fei.edu.br/basico"),
    ],
    "Depuração e programa integrado": [
        ("Python básico — curso com aulas e exercícios", "FEI", "https://python.fei.edu.br/basico"),
    ],
    "Serviços de rede e diagnóstico": [
        ("Redes de Computadores — videoaulas de graduação", "Canal CECIERJ", "https://canal.cecierj.edu.br/busca/?area=computacao&busca=Redes+de+Computadores&tipo=videoaula-interativa"),
    ],
    "Sistemas e componentes": [
        ("Introdução ao Curso Tecnologia em Sistemas de Computação", "Fundação CECIERJ", "https://canal.cecierj.edu.br/recurso/10105"),
    ],
    "Diagnóstico e integração": [
        ("Introdução ao Curso Tecnologia em Sistemas de Computação", "Fundação CECIERJ", "https://canal.cecierj.edu.br/recurso/10105"),
    ],
    "HTTP, URLs e navegador": [
        ("Estrutura da Internet — recurso audiovisual", "Fundação CECIERJ", "https://canal.cecierj.edu.br/busca/?area=computacao&busca=Estrutura+da+Internet&tipo=videoaula-interativa"),
    ],
    "Casos de teste e níveis": [
        ("Testes de software — aulas sobre desenvolvimento, release e usuário", "UFABC", "https://youtu.be/zqhWpmoX-z4"),
        ("Desenvolvimento dirigido a testes", "UFABC", "https://youtu.be/iuHhjWFr224"),
    ],
    "Grafos, busca e projeto": [
        ("Busca em largura em grafos", "e-Aulas USP", "https://eaulas.usp.br/portal/video.action/video?idItem=21392"),
        ("Grafos: representação", "UNIVESP", "https://www.youtube.com/watch?v=9m8wDGYWlXA"),
    ],
    "Levantamento de requisitos": [
        ("Engenharia de Software — Processo de engenharia de requisitos", "UNIVESP", "https://www.youtube.com/watch?v=KT8HIqryUV8"),
        ("Engenharia de Software — Tipos de requisitos", "UNIVESP", "https://www.youtube.com/watch?v=Pn93e2fgIro"),
    ],
    "Validação e especificação": [
        ("Engenharia de Software — Processo de engenharia de requisitos", "UNIVESP", "https://www.youtube.com/watch?v=KT8HIqryUV8"),
    ],
    "Casos de uso e modelos UML": [
        ("Programação Orientada a Objetos — Interfaces e Classes Abstratas", "UNIVESP", "https://www.youtube.com/watch?v=bOZQ9q7WhaY"),
    ],
    "Normalização e mini projeto": [
        ("Banco de Dados: Normalização — Parte 1", "UNIVESP", "https://www.youtube.com/watch?v=OsebNaYQpk8"),
    ],
    "Modelagem relacional e SQL": [
        ("Modelo Entidade-Relacionamento: entidades, atributos e chaves", "UNIVESP", "https://www.youtube.com/watch?v=IpFn-KsWPW0"),
    ],
    "Consultas, junções e integridade": [
        ("SQL: consultas combinadas com JOIN", "UNIVESP", "https://www.youtube.com/watch?v=Ksspjd07UoU"),
    ],
    "Estruturas lineares e árvores": [
        ("Estruturas de Dados — curso e videoaulas", "UNIVESP", "https://integra.univesp.br/courses/2639/modules"),
    ],
    "Análise de complexidade": [
        ("Análise de Algoritmos — aulas do IME-USP", "IME-USP", "https://www.ime.usp.br/~pf/analise_de_algoritmos/lectures.html"),
    ],
    "Proposta de valor": [
        ("Proposta de valor — ferramentas", "e-Aulas USP", "https://eaulas.usp.br/portal/video.action/video?idItem=38748"),
    ],
    "Custos, receitas e modelo de negócio": [
        ("Como criar um modelo de negócios com Canvas", "Sebrae PR", "https://www.youtube.com/watch?v=lmWS6c3LonM"),
    ],
    "Planejamento adaptativo e Scrum": [
        ("Introdução ao Scrum", "Aula pública", "https://www.youtube.com/watch?v=W6e2xAqAZCI"),
        ("Como o Scrum organiza projetos e entregas ágeis", "Professor Arnaldo Junior", "https://www.youtube.com/watch?v=zDt6FZvKDpQ"),
    ],
    "HTML semântico e acessibilidade": [
        ("Aprenda a criar HTML semântico", "Dev em Dobro", "https://www.youtube.com/watch?v=4BQ3V9D6Okg"),
        ("Semântica na HTML5 é importante", "Curso em Vídeo", "https://www.youtube.com/watch?v=HaSgt1hK2Fs"),
    ],
    "CSS responsivo": [
        ("Responsividade para sites", "Curso em Vídeo", "https://www.youtube.com/watch?v=WcGPSeuJDJ0"),
    ],
    "Classes, objetos e encapsulamento": [
        ("Python orientado a objetos: classes e objetos", "Curso em Vídeo", "https://www.youtube.com/watch?v=dJyZmwLpxnE"),
    ],
    "Polimorfismo e projeto": [
        ("Polimorfismo em Python", "Curso em Vídeo", "https://www.youtube.com/watch?v=qFW7s4WjNNg"),
    ],
    "Composição e interfaces": [
        ("Programação Orientada a Objetos — Interfaces e Classes Abstratas", "UNIVESP", "https://www.youtube.com/watch?v=bOZQ9q7WhaY"),
        ("Aula sobre composição de objetos", "IMD/UFRN", "https://materialpublic.imd.ufrn.br/curso/disciplina/5/8/6"),
    ],
    "Provas, indução e combinatória": [
        ("Matemática Discreta — método da indução", "Universidade Federal do Ceará", "https://disciplinas.dc.ufc.br/md/aula12/"),
        ("Matemática Discreta e Lógica — aulas gravadas", "PETComp/UFMA", "https://petcompufma.org/repositorio-educacional/monitorias/video-aula?aula=5&monitoria=matematica-discreta-e-logica&semestre=2024.1"),
    ],
    "Lógica, conjuntos e relações": [
        ("Matemática Discreta e Lógica — aulas gravadas", "PETComp/UFMA", "https://petcompufma.org/repositorio-educacional/monitorias/video-aula?aula=5&monitoria=matematica-discreta-e-logica&semestre=2024.1"),
    ],
    "Grafos, probabilidade e aplicações": [
        ("Matemática Discreta e Lógica — aulas gravadas", "PETComp/UFMA", "https://petcompufma.org/repositorio-educacional/monitorias/video-aula?aula=5&monitoria=matematica-discreta-e-logica&semestre=2024.1"),
        ("Busca em largura em grafos", "e-Aulas USP", "https://eaulas.usp.br/portal/video.action/video?idItem=21392"),
    ],
    "JavaScript e interfaces": [
        ("JavaScript — Eventos e manipulação do DOM", "Aula pública", "https://www.youtube.com/watch?v=V86a67tGfnY"),
    ],
    "Algoritmos, tipos e expressões": [
        ("Introdução à programação com Python — funções e variáveis", "CS50P / estude.org", "https://www.youtube.com/watch?v=wBGwawV8YiQ"),
    ],
    "Mecânica e prototipagem": [
        ("Curso gratuito: Godot 4 e programação em GDScript — 19 aulas", "Desenvolvendo Jogos", "https://www.youtube.com/watch?v=VHDbUqXcSpU"),
    ],
    "Cenas, entrada e física": [
        ("Curso gratuito: Godot 4 e programação em GDScript — 19 aulas", "Desenvolvendo Jogos", "https://www.youtube.com/watch?v=VHDbUqXcSpU"),
    ],
    "Polimento, testes e publicação": [
        ("Curso gratuito: Godot 4 e programação em GDScript — 19 aulas", "Desenvolvendo Jogos", "https://www.youtube.com/watch?v=VHDbUqXcSpU"),
    ],
    "Modelos, IP e protocolos": [
        ("Redes de Computadores — Protocolos e Camadas", "UNIVESP", "https://www.youtube.com/watch?v=6-RzPthCSns"),
        ("Fundamentos de Redes — modelos OSI e TCP/IP", "JB", "https://www.youtube.com/watch?v=TWfqf-0gBgM"),
    ],
    "Ameaças, controles e segurança": [
        ("Segurança da Informação — Introdução", "UNIVESP", "https://www.youtube.com/watch?v=JrVS7YsGw8w"),
    ],
    "Modelos de serviço e implantação": [
        ("Infraestrutura para sistemas de software — Computação em nuvem", "UNIVESP", "https://www.youtube.com/watch?v=zmsR2XmxPC8"),
        ("Introdução à computação em nuvem: IaaS, PaaS e SaaS", "Aula pública", "https://www.youtube.com/watch?v=I_bP06BSbPY"),
    ],
    "Processos e threads": [
        ("Sistemas Operacionais — Threads", "UNIVESP", "https://www.youtube.com/watch?v=Tbwu55Iov5s"),
    ],
    "Memória e sistema de arquivos": [
        ("Sistemas Operacionais — Introdução ao sistema de arquivos", "UNIVESP", "https://www.youtube.com/watch?v=PKox6AlVTT8"),
    ],
    "Concorrência e segurança": [
        ("Sistemas Operacionais — Tratamento de deadlocks I", "UNIVESP", "https://www.youtube.com/watch?v=o9wbX9vAlfA"),
        ("Sistemas Operacionais — Tratamento de deadlocks II", "UNIVESP", "https://www.youtube.com/watch?v=nsAVa0cMgAc"),
    ],
    "Bits e lógica digital": [
        ("Sistemas digitais — Álgebra booleana e portas lógicas", "AUTOMAPLAY", "https://www.youtube.com/watch?v=wKI0vSnhO5c"),
    ],
    "Representação de dados e hardware": [
        ("Sistemas digitais — Álgebra booleana e portas lógicas", "AUTOMAPLAY", "https://www.youtube.com/watch?v=wKI0vSnhO5c"),
    ],
    "Conjunto de instruções e integração": [
        ("Arquitetura de Computadores — Conjunto de instruções: características e funções", "Prof. Santiago — Programação e Ciência", "https://www.youtube.com/watch?v=LfGdcjG_xTI"),
    ],
    "Ética, privacidade e IA": [
        ("Preocupações éticas em Inteligência Artificial", "UFG", "https://www.youtube.com/watch?v=dQ8E0f4i5uc"),
    ],
    "Requisitos e controle de versão": [
        ("Engenharia de Software — Processo de engenharia de requisitos", "UNIVESP", "https://www.youtube.com/watch?v=KT8HIqryUV8"),
        ("Engenharia de Software — Tipos de requisitos", "UNIVESP", "https://www.youtube.com/watch?v=Pn93e2fgIro"),
    ],
    "Rotas e validação": [
        ("Como criar uma API REST do zero com Python e Flask", "Aula pública", "https://www.youtube.com/watch?v=levz4eumJ98"),
    ],
    "Autenticação, segurança e APIs": [
        ("Python REST — Segurança e autenticação em APIs", "Aula pública", "https://www.youtube.com/watch?v=yLtpR0fSitc"),
    ],
    "APIs, dados e sessões": [
        ("Como criar uma API REST do zero com Python e Flask", "Aula pública", "https://www.youtube.com/watch?v=levz4eumJ98"),
    ],
    "Persistência e regras de negócio": [
        ("Como criar uma API REST com Flask, SQLite e SQLAlchemy", "Aula pública", "https://www.youtube.com/watch?v=b6wzCMH6-tY"),
    ],
    "Segurança e aplicação web": [
        ("Python REST — Segurança e autenticação em APIs", "Aula pública", "https://www.youtube.com/watch?v=yLtpR0fSitc"),
    ],
    "Automação e pytest": [
        ("Testes automatizados com Pytest — guia introdutório", "SatellaSoft", "https://www.youtube.com/watch?v=uVM9vPu2z0g"),
    ],
    "Regressão, cobertura e qualidade contínua": [
        ("Cobertura de testes no Python com pytest-cov", "SatellaSoft", "https://www.youtube.com/watch?v=ejK8IO6adZI"),
    ],
}


def canais_para_disciplina(nome):
    texto = (nome or "").casefold()
    if any(palavra in texto for palavra in ("empreendedor", "negócio")):
        return [("Sebrae", "Sebrae"), ("UNIVESP", "UNIVESP")]
    if any(palavra in texto for palavra in ("comunicação", "debates", "sustentabilidade")):
        return [("UNIVESP", "UNIVESP"), ("Fundação Bradesco", "Fundação Bradesco")]
    if any(palavra in texto for palavra in ("matemática", "algoritmo", "estrutura de dados")):
        return [("UNIVESP", "UNIVESP"), ("Bóson Treinamentos", "Bóson Treinamentos")]
    if any(palavra in texto for palavra in ("programação", "linguagem", "front-end", "back-end", "web", "jogos")):
        return [("Curso em Vídeo", "Curso em Vídeo"), ("freeCodeCamp.org (inglês)", "freeCodeCamp.org")]
    if any(palavra in texto for palavra in ("projeto", "engenharia de software", "modelagem", "teste e qualidade")):
        return [("UNIVESP", "UNIVESP"), ("Bóson Treinamentos", "Bóson Treinamentos")]
    return [("Bóson Treinamentos", "Bóson Treinamentos"), ("UNIVESP", "UNIVESP")]


def videoaulas_para_modulo(disciplina, modulo):
    """Retorna links diretos curados quando há correspondência para o assunto."""
    topico = f"{disciplina}: {modulo}".strip(": ")
    for assunto, videos in VIDEOAULAS_CURADAS.items():
        if assunto.casefold() in (modulo or "").casefold():
            return [
                {"canal": canal, "topico": topico, "titulo": titulo,
                 "url": url, "curado": True, "origem": "curadoria"}
                for titulo, canal, url in videos
            ]

    # Busca de apoio enquanto a curadoria daquele módulo não foi feita.
    return [
        {
            "canal": rotulo,
            "topico": topico,
            "titulo": f"Buscar aula sobre {topico}",
            "url": "https://www.youtube.com/results?search_query=" + quote_plus(f'"{topico}" videoaula {canal}'),
            "curado": False,
            "origem": "busca",
        }
        for rotulo, canal in canais_para_disciplina(disciplina)
    ]
