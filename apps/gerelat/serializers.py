from rest_framework import serializers

from .document_engine.validators import validate_prosemirror_doc
from .models import (
    Asset,
    AssinaturaTemplate,
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


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = "__all__"


class AssetCreateRequestSerializer(serializers.Serializer):
    # `read_only`: não é aceito como entrada, só incluído na resposta após a
    # criação — sem isso, o POST /assets/ retorna 201 sem o id do asset
    # criado, e quem chama a API não tem como saber qual registro foi criado.
    id = serializers.IntegerField(read_only=True)
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
            "projeto",
            "ultima_atualizacao",
            "data_criacao",
            "modelo_json",
        ]

    def validate_modelo_json(self, value):
        return validate_prosemirror_doc(value)


class TemplateCreateRequestSerializer(serializers.Serializer):
    """Serializer de request para criar um template. Todos os campos são obrigatórios."""

    nome = serializers.CharField(max_length=150)
    projeto = serializers.PrimaryKeyRelatedField(queryset=Projeto.objects.all())
    modelo_json = serializers.JSONField()

    def validate_modelo_json(self, value):
        return validate_prosemirror_doc(value)


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
    evento = serializers.PrimaryKeyRelatedField(
        queryset=Evento.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID do evento (opcional)",
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
        evento = attrs.get("evento")
        template = attrs["template"]

        if evento:
            if template.projeto_id and template.projeto_id != evento.projeto_id:
                raise serializers.ValidationError(
                    "O template informado não pertence ao projeto do evento."
                )

        documento_json = attrs.get("documento_json")
        if documento_json is not None and (
            not isinstance(documento_json, dict) or documento_json.get("type") != "doc"
        ):
            raise serializers.ValidationError(
                "documento_json deve ser um documento ProseMirror válido."
            )

        return attrs
