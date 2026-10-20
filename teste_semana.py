
import sqlite3
from database import CAMINHO_BANCO

conexao = sqlite3.connect(CAMINHO_BANCO)

datas = conexao.execute("""
    SELECT
        date('now', 'localtime') AS hoje,
        date('now', 'localtime', 'weekday 0', '-6 days') AS inicio,
        date('now', 'localtime', 'weekday 0') AS fim
""").fetchone()

print("Hoje:", datas[0])
print("Início da semana:", datas[1])
print("Fim da semana:", datas[2])

registros = conexao.execute("""
    SELECT data_estudo, SUM(duracao_minutos)
    FROM sessoes_estudo
    GROUP BY data_estudo
    ORDER BY data_estudo
""").fetchall()

print("\nMinutos registrados por data:")
for registro in registros:
    print(registro[0], "-", registro[1], "minutos")

conexao.close()
