
from app import validar_inteiro, validar_texto


def test_duracao_valida():
    assert validar_inteiro("30", 1, 1440) == 30


def test_duracao_zero_rejeitada():
    assert validar_inteiro("0", 1, 1440) is None


def test_duracao_negativa_rejeitada():
    assert validar_inteiro("-10", 1, 1440) is None


def test_duracao_acima_do_limite_rejeitada():
    assert validar_inteiro("1441", 1, 1440) is None


def test_duracao_com_texto_rejeitada():
    assert validar_inteiro("trinta", 1, 1440) is None


def test_texto_remove_espacos():
    assert validar_texto("  Python  ", 60) == "Python"


def test_texto_vazio_rejeitado():
    assert validar_texto("   ", 60) is None


def test_texto_acima_do_limite_rejeitado():
    assert validar_texto("A" * 101, 100) is None
