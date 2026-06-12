import mimetypes

from rest_framework import serializers

from .constants import DOCX_ALLOWED_MIME
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
        fields = "__all__"


class TemplateCreateRequestSerializer(serializers.Serializer):
    nome_template = serializers.CharField(max_length=150)
    modelo_arquivo_base = serializers.FileField()
    projeto = serializers.PrimaryKeyRelatedField(
        queryset=Projeto.objects.all(),
        required=True,
    )

    def validate_modelo_arquivo_base(self, value):
        if not value.name.lower().endswith(".docx"):
            raise serializers.ValidationError("Envie o template no formato .docx")

        detected_content_type = (
            getattr(value, "content_type", None) or mimetypes.guess_type(value.name)[0]
        )
        if detected_content_type != DOCX_ALLOWED_MIME:
            raise serializers.ValidationError("Tipo de arquivo invalido para upload.")

        return value


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


class TemplateFromJsonSerializer(serializers.Serializer):
    nome_template = serializers.CharField(max_length=150)
    projeto = serializers.PrimaryKeyRelatedField(queryset=Projeto.objects.all())
    modelo_json = serializers.JSONField()

    def validate_modelo_json(self, value):
        if not isinstance(value, dict) or value.get("type") != "doc":
            raise serializers.ValidationError(
                "modelo_json deve ser um documento ProseMirror válido com type='doc'."
            )
        return value


class RelatorioGenerateRequestSerializer(serializers.Serializer):
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
