import mimetypes

from rest_framework import serializers

from .constants import DOCX_ALLOWED_MIME
from .models import (
    Asset,
    ClasseEvento,
    EquipePrograma,
    EquipeProjeto,
    Evento,
    Programa,
    ProgramaCampo,
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


class ProgramaCampoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramaCampo
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
    programa = serializers.PrimaryKeyRelatedField(
        queryset=Programa.objects.all(),
        required=True,
    )
    projeto = serializers.PrimaryKeyRelatedField(
        queryset=Projeto.objects.all(),
        required=False,
        allow_null=True,
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

    def validate(self, attrs):
        programa = attrs["programa"]
        projeto = attrs.get("projeto")

        if projeto and projeto.programa_id != programa.id_programa:
            raise serializers.ValidationError(
                "O projeto informado não pertence ao programa selecionado."
            )

        return attrs


class TemplateClasseEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateClasseEvento
        fields = "__all__"


class RelatorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relatorio
        fields = "__all__"


class RelatorioGenerateRequestSerializer(serializers.Serializer):
    evento = serializers.PrimaryKeyRelatedField(
        queryset=Evento.objects.all(),
        required=False,
        allow_null=True,
    )
    template = serializers.PrimaryKeyRelatedField(
        queryset=Template.objects.all(),
        required=True,
    )

    def validate(self, attrs):
        evento = attrs.get("evento")
        template = attrs["template"]

        if evento:
            if template.projeto_id and template.projeto_id != evento.projeto_id:
                raise serializers.ValidationError(
                    "O template informado não pertence ao projeto do evento."
                )

            if template.programa_id != evento.projeto.programa_id:
                raise serializers.ValidationError(
                    "O template informado não pertence ao programa do evento."
                )

        if not evento and not template.projeto_id:
            raise serializers.ValidationError(
                "Informe um evento ou use um template vinculado a um projeto."
            )

        return attrs
