from rest_framework import serializers
from .models import Relatorio

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


class TemplateClasseEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateClasseEvento
        fields = "__all__"


class RelatorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relatorio
        fields = "__all__"

        read_only_fields = [
            'id_relatorio',
            'status',
            'arqquivo_gerado',
            'bloqueado_por',
            'bloqueado_em',
            'evento'

        ]
