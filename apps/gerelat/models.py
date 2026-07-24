from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .document_engine import validate_document_value
from .enums import NIVEL_ORDEM, CampoTipo, NivelAplicacao, NivelTemplate
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


def _nivel_of_scope(*, cliente_id, programa_id, projeto_id) -> str:
    if cliente_id is not None:
        return NivelAplicacao.CLIENTE
    if programa_id is not None:
        return NivelAplicacao.PROGRAMA
    if projeto_id is not None:
        return NivelAplicacao.PROJETO
    raise ValueError("Nenhum escopo/alvo informado.")


# Caminho de atributos para subir de uma instância de um nível até o id do
# ancestral de um nível mais raso (usado para validar CampoValor.alvo contra
# o escopo de CampoDefinicao, que pode estar vários níveis acima).
_ANCESTOR_ATTR_PATH = {
    ("programa", "cliente"): ("cliente_id",),
    ("projeto", "cliente"): ("programa", "cliente_id"),
    ("projeto", "programa"): ("programa_id",),
    ("evento", "cliente"): ("projeto", "programa", "cliente_id"),
    ("evento", "programa"): ("projeto", "programa_id"),
    ("evento", "projeto"): ("projeto_id",),
}


def _ancestor_id(instance, from_level: str, to_level: str):
    if from_level == to_level:
        return instance.pk
    path = _ANCESTOR_ATTR_PATH[(from_level, to_level)]
    value = instance
    for attr in path:
        value = getattr(value, attr)
        if value is None:
            return None
    return value


class CampoDefinicao(models.Model):
    """Define o schema de uma variável (referência, tipo, obrigatoriedade) para
    um nível de entidade (nivel_aplicacao), declarada sob um escopo (cliente,
    programa ou projeto) — ex.: escopo=Programa X + nivel_aplicacao=PROJETO
    significa "todo Projeto do Programa X terá este campo"."""

    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="campo_definicoes",
        null=True,
        blank=True,
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        related_name="campo_definicoes",
        null=True,
        blank=True,
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="campo_definicoes",
        null=True,
        blank=True,
    )
    cliente_id: int | None
    programa_id: int | None
    projeto_id: int | None
    nivel_aplicacao = models.CharField(max_length=20, choices=NivelAplicacao.choices)
    referencia = models.CharField(max_length=100)
    descricao = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50, choices=CampoTipo.choices)
    obrigatorio = models.BooleanField(default=False)
    escopo_key = models.CharField(max_length=20, editable=False)
    legacy_projeto_campo_id = models.IntegerField(null=True, blank=True, editable=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(cliente__isnull=False, programa__isnull=True, projeto__isnull=True)
                    | Q(cliente__isnull=True, programa__isnull=False, projeto__isnull=True)
                    | Q(cliente__isnull=True, programa__isnull=True, projeto__isnull=False)
                ),
                name="campodef_exactly_one_escopo",
            ),
            models.CheckConstraint(
                condition=(
                    Q(cliente__isnull=False)
                    | Q(
                        programa__isnull=False,
                        nivel_aplicacao__in=[
                            NivelAplicacao.PROGRAMA,
                            NivelAplicacao.PROJETO,
                            NivelAplicacao.EVENTO,
                        ],
                    )
                    | Q(
                        projeto__isnull=False,
                        nivel_aplicacao__in=[
                            NivelAplicacao.PROJETO,
                            NivelAplicacao.EVENTO,
                        ],
                    )
                ),
                name="campodef_nivel_geq_escopo",
            ),
            models.UniqueConstraint(
                fields=["escopo_key", "referencia"],
                name="campodef_unique_referencia_per_escopo",
            ),
        ]

    def escopo_nivel(self) -> str:
        return _nivel_of_scope(
            cliente_id=self.cliente_id,
            programa_id=self.programa_id,
            projeto_id=self.projeto_id,
        )

    def escopo_instance(self):
        return self.cliente or self.programa or self.projeto

    def clean(self) -> None:
        super().clean()

        if self.referencia and self.referencia.startswith("sistema."):
            raise ValidationError(
                "referencia não pode usar o prefixo reservado 'sistema.'."
            )

        escopo_nivel = self.escopo_nivel()
        if NIVEL_ORDEM[self.nivel_aplicacao] < NIVEL_ORDEM[escopo_nivel]:
            raise ValidationError(
                "nivel_aplicacao deve ser igual ou mais profundo que o escopo da definição."
            )

    def save(self, *args, **kwargs):
        self.escopo_key = f"{self.escopo_nivel()}:{self.escopo_instance().pk}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.escopo_key} - {self.referencia}"


class CampoValor(models.Model):
    """Valor concreto de uma CampoDefinicao para uma instância específica
    (cliente/programa/projeto/evento) de nível == definicao.nivel_aplicacao."""

    id = models.AutoField(primary_key=True)
    definicao = models.ForeignKey(
        CampoDefinicao, on_delete=models.CASCADE, related_name="valores"
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="campo_valores",
        null=True,
        blank=True,
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        related_name="campo_valores",
        null=True,
        blank=True,
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="campo_valores",
        null=True,
        blank=True,
    )
    evento = models.ForeignKey(
        "Evento",
        on_delete=models.CASCADE,
        related_name="campo_valores",
        null=True,
        blank=True,
    )
    cliente_id: int | None
    programa_id: int | None
    projeto_id: int | None
    evento_id: int | None
    alvo_key = models.CharField(max_length=20, editable=False)
    valor = models.JSONField(default=dict, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        cliente__isnull=False,
                        programa__isnull=True,
                        projeto__isnull=True,
                        evento__isnull=True,
                    )
                    | Q(
                        cliente__isnull=True,
                        programa__isnull=False,
                        projeto__isnull=True,
                        evento__isnull=True,
                    )
                    | Q(
                        cliente__isnull=True,
                        programa__isnull=True,
                        projeto__isnull=False,
                        evento__isnull=True,
                    )
                    | Q(
                        cliente__isnull=True,
                        programa__isnull=True,
                        projeto__isnull=True,
                        evento__isnull=False,
                    )
                ),
                name="campovalor_exactly_one_alvo",
            ),
            models.UniqueConstraint(
                fields=["definicao", "alvo_key"],
                name="campovalor_unique_definicao_alvo",
            ),
        ]

    def alvo_nivel(self) -> str:
        if self.cliente_id is not None:
            return NivelAplicacao.CLIENTE
        if self.programa_id is not None:
            return NivelAplicacao.PROGRAMA
        if self.projeto_id is not None:
            return NivelAplicacao.PROJETO
        if self.evento_id is not None:
            return NivelAplicacao.EVENTO
        raise ValueError("Nenhum alvo informado.")

    def alvo_instance(self):
        return self.cliente or self.programa or self.projeto or self.evento

    def clean(self) -> None:
        super().clean()

        alvo_nivel = self.alvo_nivel()
        if alvo_nivel != self.definicao.nivel_aplicacao:
            raise ValidationError(
                "O alvo informado não corresponde ao nivel_aplicacao da definição."
            )

        escopo_nivel = self.definicao.escopo_nivel()
        ancestor_id = _ancestor_id(self.alvo_instance(), alvo_nivel, escopo_nivel)
        if ancestor_id != self.definicao.escopo_instance().pk:
            raise ValidationError(
                "O alvo informado não pertence ao escopo da definição da variável."
            )

        validate_document_value(self.definicao.tipo, self.valor)

    def save(self, *args, **kwargs):
        self.alvo_key = f"{self.alvo_nivel()}:{self.alvo_instance().pk}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.definicao.referencia} @ {self.alvo_key}"


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
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="templates",
        null=True,
        blank=True,
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        related_name="templates",
        null=True,
        blank=True,
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="templates",
        null=True,
        blank=True,
    )
    projeto_id: int
    nivel = models.CharField(max_length=20, choices=NivelTemplate.choices)
    nome = models.CharField(max_length=150)
    modelo_arquivo_base = models.CharField(max_length=255)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)
    modelo_json = models.JSONField(default=dict, blank=False, null=False)
    is_locked = models.BooleanField(default=False)
    locked_by = models.CharField(max_length=150, null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        nivel=NivelTemplate.CLIENTE,
                        cliente__isnull=False,
                        programa__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        nivel=NivelTemplate.PROGRAMA,
                        programa__isnull=False,
                        cliente__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        nivel=NivelTemplate.PROJETO,
                        projeto__isnull=False,
                        cliente__isnull=True,
                        programa__isnull=True,
                    )
                ),
                name="template_owner_matches_nivel",
            )
        ]

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
