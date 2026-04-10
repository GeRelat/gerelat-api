from rest_framework import viewsets

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
from .serializers import (
    ClasseEventoSerializer,
    EquipeProgramaSerializer,
    EquipeProjetoSerializer,
    EventoSerializer,
    ProgramaCampoSerializer,
    ProgramaSerializer,
    ProjetoCampoSerializer,
    ProjetoSerializer,
    RelatorioSerializer,
    TemplateClasseEventoSerializer,
    TemplateSerializer,
)


class ProgramaViewSet(viewsets.ModelViewSet):
    queryset = Programa.objects.all()
    serializer_class = ProgramaSerializer


class ProgramaCampoViewSet(viewsets.ModelViewSet):
    queryset = ProgramaCampo.objects.all()
    serializer_class = ProgramaCampoSerializer


class EquipeProgramaViewSet(viewsets.ModelViewSet):
    queryset = EquipePrograma.objects.all()
    serializer_class = EquipeProgramaSerializer


class ProjetoViewSet(viewsets.ModelViewSet):
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer


class ProjetoCampoViewSet(viewsets.ModelViewSet):
    queryset = ProjetoCampo.objects.all()
    serializer_class = ProjetoCampoSerializer


class EquipeProjetoViewSet(viewsets.ModelViewSet):
    queryset = EquipeProjeto.objects.all()
    serializer_class = EquipeProjetoSerializer


class ClasseEventoViewSet(viewsets.ModelViewSet):
    queryset = ClasseEvento.objects.all()
    serializer_class = ClasseEventoSerializer


class EventoViewSet(viewsets.ModelViewSet):
    queryset = Evento.objects.all()
    serializer_class = EventoSerializer


class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer


class TemplateClasseEventoViewSet(viewsets.ModelViewSet):
    queryset = TemplateClasseEvento.objects.all()
    serializer_class = TemplateClasseEventoSerializer


class RelatorioViewSet(viewsets.ModelViewSet):
    queryset = Relatorio.objects.all()
    serializer_class = RelatorioSerializer
