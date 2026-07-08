from django.db import models


class CampoTipo(models.TextChoices):
    TEXT = "text", "Texto"
    RICHTEXT = "richtext", "Texto Rico"
    IMAGE = "image", "Imagem"
    TABLE = "table", "Tabela"
