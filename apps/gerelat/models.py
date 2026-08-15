from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

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
    logomarca = models.ForeignKey(
        "Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clientes_logomarca",
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    @property
    def logomarca_url(self) -> str:
        if self.logomarca and self.logomarca.arquivo:
            return self.logomarca.arquivo.url
        return ""

    def __str__(self):
        return self.nome


class MembroGeRelat(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membro_gerelat",
    )

    def __str__(self):
        return f"GeRelat: {self.user}"


class MembroCliente(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membros_cliente",
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name="membros"
    )
    data_promocao = models.DateTimeField(auto_now_add=True)
    promovido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promocoes_cliente",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "cliente"], name="unique_membro_cliente"
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.cliente}"


class SolicitacaoCliente(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_APROVADO = "aprovado"
    STATUS_RECUSADO = "recusado"

    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_RECUSADO, "Recusado"),
    ]

    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name="solicitacoes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solicitacoes_cliente",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE
    )
    data_solicitacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Solicitação {self.user} -> {self.cliente} ({self.status})"


class MembroPrograma(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membros_programa",
    )
    programa = models.ForeignKey(
        "Programa", on_delete=models.CASCADE, related_name="membros"
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "programa"], name="unique_membro_programa"
            )
        ]

    def __str__(self):
        return f"{self.user} @ {self.programa}"


class MembroProjeto(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membros_projeto",
    )
    projeto = models.ForeignKey(
        "Projeto", on_delete=models.CASCADE, related_name="membros"
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "projeto"], name="unique_membro_projeto"
            )
        ]

    def __str__(self):
        return f"{self.user} @ {self.projeto}"


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
    logomarca = models.ForeignKey(
        "Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programas_logomarca",
    )
    rodape = models.TextField(blank=True, default="")

    @property
    def logomarca_url(self) -> str:
        if self.logomarca and self.logomarca.arquivo:
            return self.logomarca.arquivo.url
        return ""

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
    logomarca = models.ForeignKey(
        "Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projetos_logomarca",
    )

    @property
    def logomarca_url(self) -> str:
        if self.logomarca and self.logomarca.arquivo:
            return self.logomarca.arquivo.url
        return ""

    def __str__(self):
        return self.nome


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
                    Q(
                        cliente__isnull=False,
                        programa__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        cliente__isnull=True,
                        programa__isnull=False,
                        projeto__isnull=True,
                    )
                    | Q(
                        cliente__isnull=True,
                        programa__isnull=True,
                        projeto__isnull=False,
                    )
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

        if self.nivel_aplicacao == NivelAplicacao.EVENTO:
            raise ValidationError(
                "Variáveis customizadas não podem ter nivel_aplicacao 'evento'."
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
    """Define uma classe de evento.

    Escopo multi-nível: pode pertencer a Cliente, Programa ou Projeto.
    Exatamente um dos três campos (cliente/programa/projeto) deve ser preenchido.
    """

    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="classes_evento",
        null=True,
        blank=True,
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        related_name="classes_evento",
        null=True,
        blank=True,
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="classes_evento",
        null=True,
        blank=True,
    )
    cliente_id: int | None
    programa_id: int | None
    projeto_id: int | None
    nome_classe = models.CharField(max_length=150)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        cliente__isnull=False,
                        programa__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        programa__isnull=False,
                        cliente__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        projeto__isnull=False,
                        cliente__isnull=True,
                        programa__isnull=True,
                    )
                ),
                name="classe_evento_exactly_one_scope",
            )
        ]

    def __str__(self):
        return self.nome_classe


class Evento(models.Model):
    """Representa um evento.

    Escopo multi-nível: pode pertencer a Cliente, Programa ou Projeto.
    Exatamente um dos três campos (cliente/programa/projeto) deve ser preenchido.
    """

    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="eventos",
        null=True,
        blank=True,
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        related_name="eventos",
        null=True,
        blank=True,
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="eventos",
        null=True,
        blank=True,
    )
    cliente_id: int | None
    programa_id: int | None
    projeto_id: int | None
    classe_evento = models.ForeignKey(
        ClasseEvento, on_delete=models.CASCADE, related_name="eventos"
    )
    nome = models.CharField(max_length=150)
    local = models.CharField(max_length=150, blank=True, default="")
    endereco = models.CharField(max_length=255, blank=True, default="")
    data = models.DateField()
    objetivo = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        cliente__isnull=False,
                        programa__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        programa__isnull=False,
                        cliente__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        projeto__isnull=False,
                        cliente__isnull=True,
                        programa__isnull=True,
                    )
                ),
                name="evento_exactly_one_scope",
            )
        ]

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
    """Representa um asset (imagem/arquivo).

    Escopo multi-nível: pode pertencer a Cliente, Programa ou Projeto.
    Exatamente um dos três campos (cliente/programa/projeto) deve ser preenchido.
    """

    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="assets",
        null=True,
        blank=True,
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        related_name="assets",
        null=True,
        blank=True,
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name="assets",
        null=True,
        blank=True,
    )
    cliente_id: int | None
    programa_id: int | None
    projeto_id: int | None
    descricao = models.CharField(max_length=255, blank=True, default="")

    def _upload_to(self, filename: str) -> str:
        return asset_upload_to(filename)

    arquivo = models.ImageField(upload_to=_upload_to)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        cliente__isnull=False,
                        programa__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        programa__isnull=False,
                        cliente__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        projeto__isnull=False,
                        cliente__isnull=True,
                        programa__isnull=True,
                    )
                ),
                name="asset_exactly_one_scope",
            )
        ]

    def delete(self, *args, **kwargs):
        if self.usos.exists():
            raise ValidationError(
                "Este asset não pode ser excluído pois está em uso por uma ou mais entidades (logomarcas ou variáveis)."
            )
        super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.arquivo)


class AssetUso(models.Model):
    """Representa a vinculação do uso de um Asset como logomarca ou variável de imagem.

    Respeita as regras de hierarquia de escopo.
    """

    TIPO_USO_LOGOMARCA_CLIENTE = "logomarca_cliente"
    TIPO_USO_LOGOMARCA_PROGRAMA = "logomarca_programa"
    TIPO_USO_LOGOMARCA_PROJETO = "logomarca_projeto"
    TIPO_USO_CAMPO_VALOR = "campo_valor_imagem"

    TIPO_USO_CHOICES = [
        (TIPO_USO_LOGOMARCA_CLIENTE, "Logomarca de Cliente"),
        (TIPO_USO_LOGOMARCA_PROGRAMA, "Logomarca de Programa"),
        (TIPO_USO_LOGOMARCA_PROJETO, "Logomarca de Projeto"),
        (TIPO_USO_CAMPO_VALOR, "Variável de Imagem"),
    ]

    id = models.AutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="usos")
    tipo_uso = models.CharField(max_length=50, choices=TIPO_USO_CHOICES)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="asset_usos",
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="asset_usos",
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="asset_usos",
    )
    campo_valor = models.ForeignKey(
        "CampoValor",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="asset_usos",
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Uso de Asset"
        verbose_name_plural = "Usos de Asset"

    def clean(self):
        super().clean()
        asset_cliente_id = self.asset.cliente_id
        asset_programa_id = self.asset.programa_id
        asset_projeto_id = self.asset.projeto_id

        if self.tipo_uso == self.TIPO_USO_LOGOMARCA_CLIENTE or self.cliente_id:
            if self.cliente_id and asset_cliente_id != self.cliente_id:
                raise ValidationError(
                    "Asset do escopo cliente não pertence ao cliente informado."
                )
        elif self.tipo_uso == self.TIPO_USO_LOGOMARCA_PROGRAMA or self.programa_id:
            if self.programa:
                allowed = (asset_programa_id == self.programa_id) or (
                    asset_cliente_id == self.programa.cliente_id
                )
                if not allowed:
                    raise ValidationError(
                        "Asset incompatível com o escopo do programa informado."
                    )
        elif self.tipo_uso == self.TIPO_USO_LOGOMARCA_PROJETO or self.projeto_id:
            if self.projeto:
                allowed = (
                    (asset_projeto_id == self.projeto_id)
                    or (asset_programa_id == self.projeto.programa_id)
                    or (asset_cliente_id == self.projeto.programa.cliente_id)
                )
                if not allowed:
                    raise ValidationError(
                        "Asset incompatível com o escopo do projeto informado."
                    )

    def __str__(self) -> str:
        return f"{self.asset} -> {self.tipo_uso}"


@receiver(post_delete, sender=Asset)
def _ao_excluir_asset(sender, instance, **kwargs):
    if instance.arquivo:
        instance.arquivo.delete(save=False)


@receiver(post_save, sender=Programa)
def _ao_salvar_programa(sender, instance, **kwargs):
    sincronizar_asset_uso_logomarca(instance, AssetUso.TIPO_USO_LOGOMARCA_PROGRAMA)


@receiver(post_save, sender=Cliente)
def _ao_salvar_cliente(sender, instance, **kwargs):
    sincronizar_asset_uso_logomarca(instance, AssetUso.TIPO_USO_LOGOMARCA_CLIENTE)


@receiver(post_save, sender=Projeto)
def _ao_salvar_projeto(sender, instance, **kwargs):
    sincronizar_asset_uso_logomarca(instance, AssetUso.TIPO_USO_LOGOMARCA_PROJETO)


@receiver(post_save, sender=CampoValor)
def _ao_salvar_campo_valor(sender, instance, **kwargs):
    AssetUso.objects.filter(campo_valor=instance).delete()
    if instance.definicao.tipo != CampoTipo.IMAGE:
        return

    valor = instance.valor
    if not valor:
        return

    asset = None

    if isinstance(valor, dict):
        asset_id = valor.get("asset_id")
        if asset_id and isinstance(asset_id, int):
            asset = Asset.objects.filter(id=asset_id).first()

        if not asset:
            url = (
                valor.get("url")
                or valor.get("src")
                or valor.get("arquivo")
                or valor.get("path")
            )
            if url and isinstance(url, str):
                nome_arquivo = url.split("?")[0].split("#")[0].split("/")[-1].strip()
                if nome_arquivo:
                    asset = Asset.objects.filter(
                        Q(arquivo__icontains=nome_arquivo) | Q(arquivo=url)
                    ).first()
    elif isinstance(valor, str):
        url = valor.strip()
        if url:
            nome_arquivo = url.split("?")[0].split("#")[0].split("/")[-1].strip()
            if nome_arquivo:
                asset = Asset.objects.filter(
                    Q(arquivo__icontains=nome_arquivo) | Q(arquivo=url)
                ).first()

    if asset:
        AssetUso.objects.create(
            asset=asset,
            tipo_uso=AssetUso.TIPO_USO_CAMPO_VALOR,
            campo_valor=instance,
            cliente=instance.cliente,
            programa=instance.programa,
            projeto=instance.projeto,
        )


def sincronizar_asset_uso_logomarca(entidade, tipo_uso: str):
    filter_kwargs = {"tipo_uso": tipo_uso}
    if tipo_uso == AssetUso.TIPO_USO_LOGOMARCA_PROGRAMA:
        filter_kwargs["programa"] = entidade
    elif tipo_uso == AssetUso.TIPO_USO_LOGOMARCA_PROJETO:
        filter_kwargs["projeto"] = entidade
    elif tipo_uso == AssetUso.TIPO_USO_LOGOMARCA_CLIENTE:
        filter_kwargs["cliente"] = entidade
    else:
        return

    AssetUso.objects.filter(**filter_kwargs).delete()

    asset = getattr(entidade, "logomarca", None)
    if not asset:
        return

    if (
        tipo_uso == AssetUso.TIPO_USO_LOGOMARCA_PROGRAMA
        and asset.programa_id != entidade.id
    ):
        asset.programa = entidade
        asset.cliente = None
        asset.projeto = None
        asset.save()
    elif (
        tipo_uso == AssetUso.TIPO_USO_LOGOMARCA_PROJETO
        and asset.projeto_id != entidade.id
    ):
        asset.projeto = entidade
        asset.cliente = None
        asset.programa = None
        asset.save()
    elif (
        tipo_uso == AssetUso.TIPO_USO_LOGOMARCA_CLIENTE
        and asset.cliente_id != entidade.id
    ):
        asset.cliente = entidade
        asset.programa = None
        asset.projeto = None
        asset.save()

    usage = AssetUso(asset=asset, tipo_uso=tipo_uso)
    if tipo_uso == AssetUso.TIPO_USO_LOGOMARCA_PROGRAMA:
        usage.programa = entidade
    elif tipo_uso == AssetUso.TIPO_USO_LOGOMARCA_PROJETO:
        usage.projeto = entidade
    elif tipo_uso == AssetUso.TIPO_USO_LOGOMARCA_CLIENTE:
        usage.cliente = entidade
    usage.save()


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


class AgendamentoRelatorio(models.Model):
    TIPO_PONTUAL = "pontual"
    TIPO_RECORRENTE = "recorrente"
    TIPO_CHOICES = [
        (TIPO_PONTUAL, "Pontual"),
        (TIPO_RECORRENTE, "Recorrente"),
    ]

    RECORRENCIA_DIARIO = "diario"
    RECORRENCIA_SEMANAL = "semanal"
    RECORRENCIA_MENSAL = "mensal"
    RECORRENCIA_CHOICES = [
        (RECORRENCIA_DIARIO, "Diário"),
        (RECORRENCIA_SEMANAL, "Semanal"),
        (RECORRENCIA_MENSAL, "Mensal"),
    ]

    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=255)
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="agendamentos"
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agendamentos",
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agendamentos",
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agendamentos",
    )
    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agendamentos",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agendamentos_relatorio",
    )
    documento_json = models.JSONField(default=dict, blank=True)
    tipo_agendamento = models.CharField(
        max_length=20, choices=TIPO_CHOICES, default=TIPO_PONTUAL
    )
    data_hora_execucao = models.DateTimeField(null=True, blank=True)
    recorrencia = models.CharField(
        max_length=20, choices=RECORRENCIA_CHOICES, null=True, blank=True
    )
    horario_execucao = models.TimeField(null=True, blank=True)
    dia_semana = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="Dia da semana (1=Segunda-feira, 7=Domingo)",
    )
    dia_mes = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Dia do mês (1 a 31)",
    )
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)
    ultima_execucao = models.DateTimeField(null=True, blank=True)
    proxima_execucao = models.DateTimeField(null=True, blank=True)
    periodic_task = models.OneToOneField(
        "django_celery_beat.PeriodicTask",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agendamento_relatorio",
    )

    def __str__(self):
        return f"Agendamento {self.nome} ({self.tipo_agendamento})"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        cliente__isnull=False,
                        programa__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        programa__isnull=False,
                        cliente__isnull=True,
                        projeto__isnull=True,
                    )
                    | Q(
                        projeto__isnull=False,
                        cliente__isnull=True,
                        programa__isnull=True,
                    )
                ),
                name="agendamento_relatorio_exactly_one_scope",
            )
        ]

    def calcular_proxima_execucao(self, a_partir_de=None):
        """Calcula a próxima data/hora de execução deste agendamento."""

        from .services.agendamento_relatorio.recurrence import (
            calcular_proxima_execucao as _calcular,
        )

        return _calcular(self, a_partir_de=a_partir_de)

    def save(self, *args, **kwargs):
        """Persiste o agendamento e recalcula `proxima_execucao`."""

        recalculate = kwargs.pop("recalculate_proxima", True)
        if not self.ativo:
            self.proxima_execucao = None
        elif recalculate or self.proxima_execucao is None or self._state.adding:
            self.proxima_execucao = self.calcular_proxima_execucao()
        super().save(*args, **kwargs)
