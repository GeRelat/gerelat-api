import mimetypes

from rest_framework import serializers

from .constants import DOCX_ALLOWED_MIME
from .models import (
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
