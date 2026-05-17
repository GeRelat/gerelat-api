import os
from django.conf import settings
from django.http import FileResponse
from .utils import gerar_relatorio_docx


from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

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

    @action(detail=True, methods=['get'], url_path='baixar-documento')
    def baixar_documento(self, request, pk=None):
        relatorio = self.get_object()
        
        pasta_destino = os.path.join(settings.MEDIA_ROOT, 'relatorios_gerados')
        os.makedirs(pasta_destino, exist_ok=True)
        
        nome_arquivo = f"Relatorio_{relatorio.id_relatorio}.docx"
        caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)
        
        try:
            gerar_relatorio_docx(relatorio, caminho_arquivo)
            
            if os.path.exists(caminho_arquivo):
                return FileResponse(
                    open(caminho_arquivo, 'rb'), 
                    as_attachment=True, 
                    filename=nome_arquivo
                )
            else:
                return Response(
                    {"erro": "O arquivo não foi encontrado após a geração."}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        except Exception as e:
            return Response(
                {"erro": f"Falha na geração do documento: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['patch'], url_path='salvar-documento')
    def salvar_documento(self, request, pk=None):
        relatorio = self.get_object() 
        
        documento_json = request.data.get('metadados')
        
        if documento_json is None:
            return Response(
                {"erro": "O campo 'metadados' é obrigatório para salvar o documento."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        relatorio.metadados = documento_json
        relatorio.status = "Rascunho Salvo" 
        relatorio.save()
        
        return Response(
            {"mensagem": "Documento salvo com sucesso!"}, 
            status=status.HTTP_200_OK
        )