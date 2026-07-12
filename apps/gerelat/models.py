from django.db import models
from django.db.models import Q

from .document_engine import validate_document_value
from .enums import CampoTipo
from .utils.uploads import asset_upload_to


class Cliente(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=150)
    cnpj = models.CharField(max_length=20)
    nome_contato = models.CharField(max_length=150)
    email_contato = models.EmailField(max_length=150)
    fone_contato = models.CharField(max_length=20)
    numero_contrato = models.CharField(max_length=100)
    data_termino_contrato = models.DateField()
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome


class Programa(models.Model):
    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="programas",
        null=True,
        blank=True,
    )
    nome = models.CharField(max_length=150)
    lei_criacao = models.CharField(max_length=150)
    convenio_dados = models.CharField(max_length=150)
    logomarca = models.CharField(max_length=255, blank=True, default="")
    rodape = models.TextField(blank=True, default="")

    def __str__(self):
        return self.nome


class EquipePrograma(models.Model):
    id = models.AutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa, on_delete=models.CASCADE, related_name="equipe_programa"
    )
    nome = models.CharField(max_length=150)
    cargo = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nome} ({self.cargo})"


class Projeto(models.Model):
    id = models.AutoField(primary_key=True)
    programa = models.ForeignKey(
        Programa, on_delete=models.CASCADE, related_name="projetos"
    )
    nome = models.CharField(max_length=150)
    parceira = models.CharField(max_length=150, blank=True, default="")
    sigla = models.CharField(max_length=30, blank=True, default="")
    logomarca = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return self.nome


class ProjetoCampo(models.Model):
    id = models.AutoField(primary_key=True)
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="campos_projeto"
    )
    referencia = models.CharField(max_length=100)
    descricao = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50, choices=CampoTipo.choices)
    obrigatorio = models.BooleanField(default=False)
    valor = models.JSONField(default=dict, blank=True)

    def clean(self) -> None:
        super().clean()
        validate_document_value(self.tipo, self.valor)

    def __str__(self):
        return f"{self.projeto.nome} - {self.referencia}"


class EquipeProjeto(models.Model):
    id = models.AutoField(primary_key=True)
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="equipes_projeto"
    )
    nome_equipe = models.CharField(max_length=150)
    nome = models.CharField(max_length=150)
    cargo = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nome_equipe} - {self.nome} ({self.cargo})"


class ClasseEvento(models.Model):
    id = models.AutoField(primary_key=True)
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="classes_evento"
    )
    nome_classe = models.CharField(max_length=150)

    def __str__(self):
        return self.nome_classe


class Evento(models.Model):
    id = models.AutoField(primary_key=True)
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="eventos"
    )
    projeto_id: int
    classe_evento = models.ForeignKey(
        ClasseEvento, on_delete=models.CASCADE, related_name="eventos"
    )
    nome = models.CharField(max_length=150)
    local = models.CharField(max_length=150, blank=True, default="")
    endereco = models.CharField(max_length=255, blank=True, default="")
    data = models.DateField()
    objetivo = models.TextField(blank=True, default="")

    def __str__(self):
        return self.nome


class Template(models.Model):
    id = models.AutoField(primary_key=True)
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="templates",
        null=False,
        blank=False,
    )
    projeto_id: int
    nome = models.CharField(max_length=150)
    modelo_arquivo_base = models.CharField(max_length=255)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)
    modelo_json = models.JSONField(default=dict, blank=False, null=False)
    is_locked = models.BooleanField(default=False)
    locked_by = models.CharField(max_length=150, null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nome


class TemplateClasseEvento(models.Model):
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="template_classe_evento"
    )
    classe_evento = models.ForeignKey(
        ClasseEvento,
        on_delete=models.CASCADE,
        related_name="template_classe_evento",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["template", "classe_evento"],
                name="unique_template_classe_evento",
            )
        ]

    def __str__(self):
        return f"{self.template.nome} - {self.classe_evento.nome_classe}"


class AssinaturaTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        related_name="assinaturas_template",
    )
    equipe_programa = models.ForeignKey(
        EquipePrograma,
        on_delete=models.SET_NULL,
        related_name="assinaturas_template",
        null=True,
        blank=True,
    )
    equipe_projeto = models.ForeignKey(
        EquipeProjeto,
        on_delete=models.SET_NULL,
        related_name="assinaturas_template",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.template.nome} - Assinatura {self.id}"

    class Meta:
        indexes = [
            models.Index(fields=["template", "equipe_programa"]),
            models.Index(fields=["template", "equipe_projeto"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(equipe_programa__isnull=False, equipe_projeto__isnull=True)
                    | Q(equipe_programa__isnull=True, equipe_projeto__isnull=False)
                ),
                name="assinatura_template_exactly_one_equipe",
            )
        ]


class Asset(models.Model):
    descricao = models.CharField(max_length=255, blank=True, default="")

    def _upload_to(self, filename: str) -> str:
        return asset_upload_to(filename)

    arquivo = models.ImageField(upload_to=_upload_to)

    def __str__(self) -> str:
        return str(self.arquivo)


class Relatorio(models.Model):
    id = models.AutoField(primary_key=True)
    evento = models.ForeignKey(
        Evento,
        on_delete=models.SET_NULL,
        related_name="relatorios",
        null=True,
        blank=True,
    )
    template = models.ForeignKey(
        Template, on_delete=models.PROTECT, related_name="relatorios"
    )
    arquivo_gerado = models.CharField(max_length=255)
    nome = models.CharField(max_length=150, blank=True, default="")
    status = models.CharField(max_length=50)
    metadados = models.JSONField(default=dict, blank=True)
    documento_json = models.JSONField(default=dict, blank=False, null=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Relatorio {self.id} - {self.status}"
