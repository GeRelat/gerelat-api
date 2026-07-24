from rest_framework import serializers

from .document_engine.scope import scan_required_nivel
from .document_engine.validators import validate_prosemirror_doc
from .enums import NivelTemplate
from .models import (
    Asset,
    AssinaturaTemplate,
    CampoDefinicao,
    CampoValor,
    ClasseEvento,
    Cliente,
    EquipePrograma,
    EquipeProjeto,
    Evento,
    Programa,
    Projeto,
    ProjetoCampo,
    Relatorio,
    Template,
    TemplateClasseEvento,
)


def _validate_owner_matches_nivel(attrs: dict, *, instance=None) -> None:
    """Compartilhado por TemplateSerializer/TemplateCreateRequestSerializer:
    exige exatamente um de cliente/programa/projeto, coerente com `nivel`."""

    def _get(field):
        if field in attrs:
            return attrs[field]
        return getattr(instance, field, None) if instance is not None else None

    nivel = _get("nivel")
    cliente = _get("cliente")
    programa = _get("programa")
    projeto = _get("projeto")

    owners = {
        NivelTemplate.CLIENTE: cliente,
        NivelTemplate.PROGRAMA: programa,
        NivelTemplate.PROJETO: projeto,
    }

    if sum(1 for owner in owners.values() if owner is not None) != 1:
        raise serializers.ValidationError(
            "Informe exatamente um dos campos: cliente, programa ou projeto."
        )

    if owners.get(nivel) is None:
        raise serializers.ValidationError(
            "O campo informado (cliente/programa/projeto) não corresponde ao nivel."
        )


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = "__all__"


class AssetCreateRequestSerializer(serializers.Serializer):
    arquivo = serializers.ImageField()
    descricao = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_arquivo(self, value):
        max_size = 50 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("Tamanho máximo permitido: 50MB.")

        detected_content_type = getattr(value, "content_type", None)
        if detected_content_type and not detected_content_type.startswith("image/"):
            raise serializers.ValidationError("Tipo de arquivo inválido para upload.")

        return value

    def create(self, validated_data):
        return Asset.objects.create(**validated_data)


class ProgramaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Programa
        fields = "__all__"


class EquipeProgramaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipePrograma
        fields = "__all__"


class ProjetoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projeto
        fields = "__all__"


class ProjetoCampoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjetoCampo
        fields = "__all__"


class EquipeProjetoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipeProjeto
        fields = "__all__"


class ClasseEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClasseEvento
        fields = "__all__"


class EventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        fields = "__all__"


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = [
            "id",
            "nome",
            "nivel",
            "cliente",
            "programa",
            "projeto",
            "ultima_atualizacao",
            "data_criacao",
            "modelo_json",
        ]
        extra_kwargs = {
            "cliente": {"required": False, "allow_null": True},
            "programa": {"required": False, "allow_null": True},
            "projeto": {"required": False, "allow_null": True},
        }

    def validate_modelo_json(self, value):
        return validate_prosemirror_doc(value)

    def validate(self, attrs):
        _validate_owner_matches_nivel(attrs, instance=self.instance)
        return attrs


class TemplateCreateRequestSerializer(serializers.Serializer):
    """Serializer de request para criar um template."""

    nome = serializers.CharField(max_length=150)
    nivel = serializers.ChoiceField(choices=NivelTemplate.choices)
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True
    )
    programa = serializers.PrimaryKeyRelatedField(
        queryset=Programa.objects.all(), required=False, allow_null=True
    )
    projeto = serializers.PrimaryKeyRelatedField(
        queryset=Projeto.objects.all(), required=False, allow_null=True
    )
    modelo_json = serializers.JSONField()

    def validate_modelo_json(self, value):
        return validate_prosemirror_doc(value)

    def validate(self, attrs):
        _validate_owner_matches_nivel(attrs)
        return attrs


class CampoDefinicaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampoDefinicao
        fields = [
            "id",
            "cliente",
            "programa",
            "projeto",
            "nivel_aplicacao",
            "referencia",
            "descricao",
            "tipo",
            "obrigatorio",
            "data_criacao",
            "ultima_atualizacao",
        ]
        read_only_fields = ["data_criacao", "ultima_atualizacao"]

    def validate(self, attrs):
        instance = CampoDefinicao(
            **{
                **{
                    "cliente": getattr(self.instance, "cliente", None),
                    "programa": getattr(self.instance, "programa", None),
                    "projeto": getattr(self.instance, "projeto", None),
                    "nivel_aplicacao": getattr(self.instance, "nivel_aplicacao", None),
                    "referencia": getattr(self.instance, "referencia", None),
                },
                **attrs,
            }
        )
        instance.full_clean(exclude=["id", "escopo_key"])
        return attrs


class CampoValorSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampoValor
        fields = [
            "id",
            "definicao",
            "cliente",
            "programa",
            "projeto",
            "evento",
            "valor",
            "data_criacao",
            "ultima_atualizacao",
        ]
        read_only_fields = ["data_criacao", "ultima_atualizacao"]

    def validate(self, attrs):
        instance = CampoValor(
            **{
                **{
                    "definicao": getattr(self.instance, "definicao", None),
                    "cliente": getattr(self.instance, "cliente", None),
                    "programa": getattr(self.instance, "programa", None),
                    "projeto": getattr(self.instance, "projeto", None),
                    "evento": getattr(self.instance, "evento", None),
                },
                **attrs,
            }
        )
        instance.full_clean(exclude=["id", "alvo_key"])
        return attrs


class TaskAcceptedSerializer(serializers.Serializer):
    """Serializer para respostas 202 de operações enfileiradas."""

    detail = serializers.CharField()
    task_id = serializers.UUIDField()
    task_status = serializers.CharField()


class TaskStatusSerializer(serializers.Serializer):
    """Serializer para respostas do endpoint de consulta de status de task."""

    task_id = serializers.UUIDField()
    task_status = serializers.CharField()
    result = serializers.JSONField(
        required=False,
        help_text="Presente quando task_status='SUCCESS'.",
    )
    error = serializers.CharField(
        required=False,
        help_text="Presente quando task_status='FAILURE'.",
    )


class AssinaturaTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssinaturaTemplate
        fields = "__all__"

    def validate(self, attrs):
        equipe_programa = attrs.get(
            "equipe_programa",
            getattr(self.instance, "equipe_programa", None),
        )
        equipe_projeto = attrs.get(
            "equipe_projeto",
            getattr(self.instance, "equipe_projeto", None),
        )

        if bool(equipe_programa) == bool(equipe_projeto):
            raise serializers.ValidationError(
                "Informe exatamente um dos campos: equipe_programa ou equipe_projeto."
            )

        return attrs


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = "__all__"


class TemplateClasseEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateClasseEvento
        fields = "__all__"


class RelatorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relatorio
        fields = "__all__"


class RelatorioGenerateRequestSerializer(serializers.Serializer):
    nome = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        help_text="Nome opcional para o relatório (substitui o nome do template)",
    )
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID do cliente (opcional, necessário se o template usar gaps de nível cliente)",
    )
    programa = serializers.PrimaryKeyRelatedField(
        queryset=Programa.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID do programa (opcional, necessário se o template usar gaps de nível programa)",
    )
    projeto = serializers.PrimaryKeyRelatedField(
        queryset=Projeto.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID do projeto (opcional, necessário se o template usar gaps de nível projeto)",
    )
    evento = serializers.PrimaryKeyRelatedField(
        queryset=Evento.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID do evento (opcional, necessário se o template usar gaps de nível evento)",
    )
    template = serializers.PrimaryKeyRelatedField(
        queryset=Template.objects.all(),
        required=True,
        help_text="ID do template (obrigatório)",
    )
    documento_json = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Documento ProseMirror já resolvido e editado pelo usuário (opcional)",
    )

    def validate(self, attrs):
        template = attrs["template"]
        cliente = attrs.get("cliente")
        programa = attrs.get("programa")
        projeto = attrs.get("projeto")
        evento = attrs.get("evento")

        # Resolve a cadeia completa a partir do elo mais profundo informado,
        # validando consistência com qualquer elo mais raso já informado.
        if evento:
            if projeto and projeto.id != evento.projeto_id:
                raise serializers.ValidationError(
                    "O evento informado não pertence ao projeto informado."
                )
            projeto = projeto or evento.projeto

        if projeto:
            if programa and programa.id != projeto.programa_id:
                raise serializers.ValidationError(
                    "O projeto informado não pertence ao programa informado."
                )
            programa = programa or projeto.programa

        if programa:
            if (
                cliente
                and programa.cliente_id is not None
                and cliente.id != programa.cliente_id
            ):
                raise serializers.ValidationError(
                    "O programa informado não pertence ao cliente informado."
                )
            cliente = cliente or programa.cliente

        documento_json = attrs.get("documento_json")
        if documento_json is not None and (
            not isinstance(documento_json, dict) or documento_json.get("type") != "doc"
        ):
            raise serializers.ValidationError(
                "documento_json deve ser um documento ProseMirror válido."
            )

        required_nivel = scan_required_nivel(
            documento_json or template.modelo_json,
            cliente=cliente,
            programa=programa,
            projeto=projeto,
        )
        resolved = {
            "cliente": cliente,
            "programa": programa,
            "projeto": projeto,
            "evento": evento,
        }
        if required_nivel is not None and resolved.get(required_nivel) is None:
            raise serializers.ValidationError(
                f"Este template exige informar {required_nivel} para gerar o relatório."
            )

        attrs["cliente"] = cliente
        attrs["programa"] = programa
        attrs["projeto"] = projeto
        attrs["evento"] = evento
        return attrs
