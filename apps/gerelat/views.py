import os
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.core.files.storage import default_storage
from django.db import connection
from datetime import timedelta
from .utils import gerar_relatorio_docx
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes, action, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .permissions import IsOwnerOrTeamMember
from .utils import gerar_url_pre_assinada_s3
from rest_framework import viewsets, status
from rest_framework.throttling import UserRateThrottle
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

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


class GeracaoRateThrottle(UserRateThrottle):
    rate = '5/minute'

class EdicaoRateThrottle(UserRateThrottle):
    rate = '60/minute'

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

    def get_queryset(self):
        return Relatorio.objects.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save()

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
    @throttle_classes([EdicaoRateThrottle])
    def salvar_documento(self, request, pk=None):
        relatorio = self.get_object() 
        agora = timezone.now()
        tempo_limite = agora - timedelta(minutes=15)
        documento_json = request.data.get('metadados')

        if relatorio.bloqueado_por and relatorio.bloqueado_por != request.user and relatorio.bloqueado_em > tempo_limite:
            return Response(
                {"erro": "Este documento está sendo editado por outro usuário. Tente novamente mais tarde."}, 
                status=status.HTTP_423_LOCKED
            )
        
        if documento_json is None:
            return Response(
                {"erro": "O campo 'metadados' é obrigatório para salvar o documento."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        metadados_limpos = limpar_json_malicioso(documento_json)

        if relatorio.metadados:
            HistoricoRelatorio.objects.create(
                relatorio=relatorio,
                modificado_por=request.user,
                metadados_antigos=relatorio.metadados
            )
        
        relatorio.metadados = metadados_limpos
        relatorio.status = "Rascunho Salvo" 
        relatorio.save()
        
        return Response(
            {"mensagem": "Documento salvo com sucesso!"}, 
            status=status.HTTP_200_OK
        )
    @action(detail=True, methods=['post'], url_path='bloquear')
    def bloquear_documento(self, request, pk=None):
        relatorio = self.get_object()
        agora = timezone.now()
        tempo_limite = agora - timedelta(minutes=15) 

        if relatorio.bloqueado_por and relatorio.bloqueado_por != request.user:
            if relatorio.bloqueado_em > tempo_limite:
                nome_usuario = relatorio.bloqueado_por.get_full_name() or relatorio.bloqueado_por.username
                return Response(
                    {"erro": f"Este documento está sendo editado por {nome_usuario}."}, 
                    status=status.HTTP_423_LOCKED
                )

        relatorio.bloqueado_por = request.user
        relatorio.bloqueado_em = agora
        relatorio.save()
        
        return Response({"mensagem": "Documento trancado para a sua edição."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='desbloquear')
    def desbloquear_documento(self, request, pk=None):
        relatorio = self.get_object()
        
        if relatorio.bloqueado_por == request.user:
            relatorio.bloqueado_por = None
            relatorio.bloqueado_em = None
            relatorio.save()
            return Response({"mensagem": "Documento liberado com sucesso."}, status=status.HTTP_200_OK)
            
        return Response({"erro": "Você não tem permissão para remover o bloqueio de outro usuário."}, status=status.HTTP_403_FORBIDDEN)

class AuditMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            from .models import Auditlog
            usuario = request.user if request.user.is_authenticated else None
            Auditlog.objects.create(
                usuario=usuario,
                acao=request.method,
                endpoint=request.path,
            )

class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_variaveis_disponiveis(request, id_relatorio):
    relatorio = get_object_or_404(Relatorio, pk=id_relatorio)
    evento = relatorio.evento
    projeto = evento.projeto
    programa = projeto.programa
    
    variaveis = {
        "programa.nome": programa.nome,
        "programa.lei_criacao": programa.lei_criacao,
        "projeto.nome": projeto.nome,
        "projeto.parceira": projeto.parceira,
        "projeto.sigla": projeto.sigla,
        "evento.nome": evento.nome,
        "evento.local": evento.local,
        "evento.data": evento.data.strftime('%d/%m/%Y') if evento.data else "",
    }
    
    campos_programa = ProgramaCampo.objects.filter(programa=programa)
    for campo in campos_programa:
        chave = f"programa.{campo.referencia.strip()}"
        variaveis[chave] = campo.valor
        
    campos_projeto = ProjetoCampo.objects.filter(projeto=projeto)
    for campo in campos_projeto:
        chave = f"projeto.{campo.referencia.strip()}"
        variaveis[chave] = campo.valor

    return Response({
        "id_relatorio": id_relatorio,
        "variaveis_disponiveis": variaveis
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOwnerOrTeamMember]) 
def detalhe_relatorio(request, id_relatorio):
    relatorio = get_object_or_404(Relatorio, pk=id_relatorio)
    view = request.versioning_scheme  
    
    permission = IsOwnerOrTeamMember()
    if not permission.has_object_permission(request, None, relatorio):
        return Response(
            {"error": "Acesso negado. Você não faz parte da equipe deste projeto."}, 
            status=status.HTTP_403_FORBIDDEN
        )

    return Response({
        "id_relatorio": relatorio.id_relatorio,
        "metadados": relatorio.metadados,
        "status": relatorio.status
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOwnerOrTeamMember])
def obter_link_download(request, id_relatorio):
    relatorio = get_object_or_404(Relatorio, pk=id_relatorio)
    permission = IsOwnerOrTeamMember()
    if not permission.has_object_permission(request, None, relatorio):
        return Response({"error": "Acesso negado ao projeto."}, status=status.HTTP_403_FORBIDDEN)

    if not relatorio.arquivo_gerado or relatorio.status != "Concluído":
        return Response({"error": "O documento ainda não foi gerado ou está em processamento."}, status=status.HTTP_404_NOT_FOUND)
    
    link_temporario = gerar_url_pre_assinada_s3(relatorio.arquivo_gerado)
    
    if not link_temporario:
        return Response({"error": "Falha de comunicação com o servidor de arquivos AWS."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        "mensagem": "Link gerado com sucesso. Expira em 5 minutos.",
        "download_url": link_temporario
    }, status=status.HTTP_200_OK)


#endpoint para upload de imagens do editor de texto
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_imagem_editor(request):
    request.parsers = [MultiPartParser(), FormParser()]
    
    arquivo = request.FILES.get('imagem')
    
    if not arquivo:
        return Response(
            {"erro": "Nenhum arquivo de imagem foi enviado na requisição."}, 
            status=status.HTTP_400_BAD_REQUEST
        )
        
    if not arquivo.content_type.startswith('image/'):
        return Response(
            {"erro": "O arquivo enviado não é uma imagem válida."}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    caminho_salvo = default_storage.save(f"editor_imagens/{arquivo.name}", arquivo)
    
    url_imagem = default_storage.url(caminho_salvo)
    
    return Response({
        "mensagem": "Upload concluído",
        "url": url_imagem
    }, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([AllowAny])
def healthcheck(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return Response({
            "api": "online",
            "banco_de_dados":"conectado"
            }, status=200)
    
    except Exception as e:
        return Response({
            "api": "online",
            "banco_de_dados":"erro",
            "detalhe": str(e)
            }, status=500)
