from django.db import models


class CampoTipo(models.TextChoices):
    TEXT = "text", "Texto"
    RICHTEXT = "richtext", "Texto Rico"
    IMAGE = "image", "Imagem"
    TABLE = "table", "Tabela"


class NivelTemplate(models.TextChoices):
    CLIENTE = "cliente", "Cliente"
    PROGRAMA = "programa", "Programa"
    PROJETO = "projeto", "Projeto"


class NivelAplicacao(models.TextChoices):
    CLIENTE = "cliente", "Cliente"
    PROGRAMA = "programa", "Programa"
    PROJETO = "projeto", "Projeto"
    EVENTO = "evento", "Evento"


# Ordem hierárquica usada para comparar profundidade (cliente < programa < projeto < evento).
NIVEL_ORDEM = {
    NivelAplicacao.CLIENTE: 0,
    NivelAplicacao.PROGRAMA: 1,
    NivelAplicacao.PROJETO: 2,
    NivelAplicacao.EVENTO: 3,
}
