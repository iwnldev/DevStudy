# DevStudy 📚

O **DevStudy** é uma aplicação web desenvolvida em Python com Flask para auxiliar na organização dos estudos. O projeto reúne ferramentas para registrar conteúdos estudados, acompanhar metas e manter uma rotina de aprendizado.

## ✨ Funcionalidades

- 📝 Cadastro, edição e exclusão de anotações.
- 🔎 Busca e favoritos para organizar as anotações.
- 🎯 Definição de metas diárias de estudo.
- ⏱️ Registro de sessões de estudo.
- 📊 Acompanhamento do histórico de estudos e visualização semanal.
- 🍅 Temporizador Pomodoro para auxiliar na concentração.
- 🗄️ Armazenamento de dados em banco de dados SQLite.
- 🧪 Testes automatizados com pytest.

## 🛠️ Tecnologias utilizadas

- Python
- Flask
- SQLite
- HTML e CSS
- pytest
- Git e GitHub

## 🚀 Como executar o projeto

### 1. Clone o repositório

```bash
git clone https://github.com/iwnldev/DevStudy
```

Entre na pasta do projeto:

```bash
cd DevStudy
```

### 2. Crie um ambiente virtual

```bash
python -m venv .venv
```

Ative o ambiente virtual no Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Instale as dependências

```bash
python -m pip install -r requirements.txt
```

### 4. Configure a chave secreta

Se o projeto estiver configurado para ler `DEVSTUDY_SECRET_KEY` de uma variável de ambiente, defina uma chave local no PowerShell:

```powershell
$env:DEVSTUDY_SECRET_KEY = "sua-chave-local"
```

Use uma chave secreta própria e não a publique no GitHub.

### 5. Execute a aplicação

```bash
python app.py
```

Abra no navegador o endereço local indicado pelo Flask no terminal.

## 🧪 Executando os testes

Com o ambiente virtual ativado, execute na pasta raiz do projeto:

```powershell
$env:PYTHONPATH = (Get-Location).Path
pytest -v
```

O comando executa os testes automatizados do projeto.

## 🎯 Objetivo do projeto

O DevStudy é um projeto de aprendizado e portfólio, desenvolvido para praticar programação em Python, desenvolvimento web, persistência de dados, validações e testes automatizados.

## 👨‍💻 Autor

Desenvolvido como projeto de estudo em Análise e Desenvolvimento de Sistemas.
