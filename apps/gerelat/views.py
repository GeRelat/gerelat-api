import uuid
from pathlib import Path
from typing import Any, cast

from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
)
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError as DRFValidationError,
)
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import (
    permissions as perms,
)
from .constants import DOCX_ALLOWED_MIME
from .document_engine.converters import (
    convert_docx_to_prosemirror,
    replace_placeholders,
)
from .document_engine.renderer import (
    assinaturas_de_metadados,
    logos_cabecalho_de_metadados,
    prosemirror_to_docx,
)
from .document_engine.scope import scan_required_nivel
from .document_engine.system_fields import get_system_fields_for_level
from .document_engine.utils import (
    build_docx_filename_and_content_disposition,
)
from .document_engine.variables import build_variables_context
from .enums import NivelTemplate
from .models import (
    AgendamentoRelatorio,
    Asset,
    AssinaturaTemplate,
    CampoDefinicao,
    CampoValor,
    ClasseEvento,
    Cliente,
    EquipePrograma,
    EquipeProjeto,
    Evento,
    MembroCliente,
    MembroGeRelat,
    MembroPrograma,
    MembroProjeto,
    Programa,
    Projeto,
    Relatorio,
    SolicitacaoCliente,
    Template,
    TemplateClasseEvento,
)
from .serializers import (
    AgendamentoRelatorioSerializer,
    AssetCreateRequestSerializer,
    AssetSerializer,
    AssetUsoSerializer,
    AssinaturaTemplateSerializer,
    CampoDefinicaoSerializer,
    CampoValorSerializer,
    ClasseEventoSerializer,
    ClienteSerializer,
    EquipeProgramaSerializer,
    EquipeProjetoSerializer,
    EventoSerializer,
    MembroClienteSerializer,
    MembroGeRelatSerializer,
    MembroProgramaSerializer,
    MembroProjetoSerializer,
    ProgramaSerializer,
    ProjetoSerializer,
    RelatorioGenerateRequestSerializer,
    RelatorioSerializer,
    SolicitacaoClienteSerializer,
    TaskAcceptedSerializer,
    TaskStatusSerializer,
    TemplateClasseEventoSerializer,
    TemplateCreateRequestSerializer,
    TemplateSerializer,
)
from .services.agendamento_relatorio import (
    remover_periodic_task,
    sincronizar_periodic_task,
)
from .services.assinaturas_relatorio import resolver_assinaturas
from .services.autorizacao import (
    get_nivel_acesso,
    get_nivel_acesso_programa,
    invalidar_cache as invalidar_cache_autorizacao,
)
from .services.eventos_relatorio import eventos_disponiveis_para_relatorio
from .services.gestao_acesso import (
    ConflitoDeAcessoError,
    adicionar_membro_programa,
    adicionar_membro_projeto,
    remover_usuario_do_cliente,
    sincronizar_acessos_cliente,
)
from .services.listagem_usuarios import listar_usuarios_cliente
from .services.variaveis_escopo import resolver_campos_definicao_escopo
from .tasks import create_template, generate_relatorio

User = get_user_model()


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [perms.PodeAcessarConteudoPorEscopo]
    parser_classes = [JSONParser]

    def get_serializer_class(self):
        if self.action == "create":
            return AssetCreateRequestSerializer
        return AssetSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = serializer.save()
        output_serializer = AssetSerializer(asset, context={"request": request})
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(output_serializer.data),
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.usos.exists():
            return Response(
                {
                    "detail": "Este asset não pode ser excluído pois está em uso por uma ou mais entidades (logomarcas ou variáveis)."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return Asset.objects.none()
        if perms.is_platform_admin(user):
            return (
                Asset.objects.all()
                .select_related("cliente", "programa", "projeto")
                .prefetch_related(
                    "usos",
                    "usos__cliente",
                    "usos__programa",
                    "usos__projeto",
                    "usos__campo_valor__definicao",
                )
            )

        return (
            Asset.objects.filter(
                Q(cliente__membros__user=user)
                | Q(programa__membros__user=user)
                | Q(projeto__membros__user=user)
                | Q(cliente__programas__membros__user=user)
                | Q(cliente__programas__projetos__membros__user=user)
                | Q(programa__projetos__membros__user=user)
            )
            .distinct()
            .select_related("cliente", "programa", "projeto")
            .prefetch_related(
                "usos",
                "usos__cliente",
                "usos__programa",
                "usos__projeto",
                "usos__campo_valor__definicao",
            )
        )

    @action(detail=False, methods=["post"], url_path="presigned-url")
    def presigned_url(self, request):
        """Gera uma URL assinada (S3/MinIO) para upload direto do frontend."""
        filename = (
            request.data.get("nome_arquivo")
            or request.data.get("filename")
            or "upload.jpg"
        )
        content_type = request.data.get("content_type", "image/jpeg")

        cliente_id = request.data.get("cliente_id") or request.data.get("cliente")
        programa_id = request.data.get("programa_id") or request.data.get("programa")
        projeto_id = request.data.get("projeto_id") or request.data.get("projeto")

        scopes = [x for x in [cliente_id, programa_id, projeto_id] if x is not None]
        if len(scopes) != 1:
            return Response(
                {
                    "detail": "Informe exatamente um escopo (cliente, programa ou projeto)."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ext = Path(filename).suffix or ".jpg"
        unique_name = f"{uuid.uuid4()}{ext}"
        storage_path = f"assets/{unique_name}"

        import boto3
        from botocore.config import Config

        endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None) or os.getenv(
            "S3_ENDPOINT_URL", "http://localhost:9000"
        )
        access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None) or os.getenv(
            "S3_ACCESS_KEY", "minioadmin"
        )
        secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None) or os.getenv(
            "S3_SECRET_KEY", "minioadmin"
        )
        region_name = getattr(settings, "AWS_S3_REGION_NAME", None) or os.getenv(
            "S3_REGION_NAME", "us-east-1"
        )
        bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or os.getenv(
            "S3_BUCKET_NAME", "gerelat"
        )

        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        upload_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": storage_path,
                "ContentType": content_type,
            },
            ExpiresIn=3600,
        )
        return Response(
            {
                "presigned": True,
                "upload_url": upload_url,
                "caminho_arquivo": storage_path,
                "headers": {"Content-Type": content_type},
                "method": "PUT",
            }
        )

    @action(detail=True, methods=["get"], url_path="usos")
    def usos(self, request, pk=None):
        """Retorna os vínculos de uso deste asset."""
        asset = self.get_object()
        serializer = AssetUsoSerializer(asset.usos.all(), many=True)
        return Response(serializer.data)


class ProgramaViewSet(viewsets.ModelViewSet):
    queryset = Programa.objects.all()
    serializer_class = ProgramaSerializer
    permission_classes = [perms.PodeAcessarPrograma]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return Programa.objects.none()
        if perms.is_platform_admin(user):
            return Programa.objects.all().select_related("cliente", "logomarca")
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values(
            "projeto__programa"
        )
        return (
            Programa.objects.filter(
                Q(cliente__in=clientes_admin)
                | Q(id__in=programas_membro)
                | Q(id__in=projetos_membro)
            )
            .distinct()
            .select_related("cliente", "logomarca")
        )


class EquipeProgramaViewSet(viewsets.ModelViewSet):
    queryset = EquipePrograma.objects.all()
    serializer_class = EquipeProgramaSerializer
    permission_classes = [perms.PodeAcessarConteudoPrograma]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return EquipePrograma.objects.none()
        if perms.is_platform_admin(user):
            return EquipePrograma.objects.all().select_related(
                "programa", "programa__cliente"
            )
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values(
            "projeto__programa"
        )
        return (
            EquipePrograma.objects.filter(
                Q(programa__cliente__in=clientes_admin)
                | Q(programa__in=programas_membro)
                | Q(programa__in=projetos_membro)
            )
            .distinct()
            .select_related("programa", "programa__cliente")
        )

    def perform_create(self, serializer):
        programa = serializer.validated_data.get("programa")
        if programa:
            nivel = perms.get_nivel_acesso_programa(self.request.user, programa)
            if nivel not in ("admin_gerelat", "admin_cliente", "membro_programa"):
                raise PermissionDenied(
                    "Você não tem permissão para adicionar membros à equipe deste programa."
                )
        serializer.save()


class ProjetoViewSet(viewsets.ModelViewSet):
    queryset = Projeto.objects.all()
    serializer_class = ProjetoSerializer
    permission_classes = [perms.PodeAcessarProjeto]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return Projeto.objects.none()
        if perms.is_platform_admin(user):
            return Projeto.objects.all().select_related(
                "programa", "programa__cliente", "logomarca"
            )
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
        return (
            Projeto.objects.filter(
                Q(programa__cliente__in=clientes_admin)
                | Q(programa__in=programas_membro)
                | Q(id__in=projetos_membro)
            )
            .distinct()
            .select_related("programa", "programa__cliente", "logomarca")
        )

    def perform_create(self, serializer):
        programa = serializer.validated_data.get("programa")
        if programa:
            nivel = perms.get_nivel_acesso_programa(self.request.user, programa)
            if nivel not in ("admin_gerelat", "admin_cliente", "membro_programa"):
                raise PermissionDenied(
                    "Você não tem permissão para criar projetos neste programa."
                )
        serializer.save()


class CampoDefinicaoViewSet(viewsets.ModelViewSet):
    queryset = CampoDefinicao.objects.all()
    serializer_class = CampoDefinicaoSerializer
    permission_classes = [perms.PodeAcessarConteudoPorEscopo]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return CampoDefinicao.objects.none()
        if perms.is_platform_admin(user):
            return CampoDefinicao.objects.all().select_related(
                "cliente", "programa", "projeto"
            )

        clientes_acesso = Cliente.objects.filter(
            Q(membros__user=user)
            | Q(programas__membros__user=user)
            | Q(programas__projetos__membros__user=user)
        ).distinct()

        programas_acesso = Programa.objects.filter(
            Q(cliente__in=clientes_acesso)
            | Q(membros__user=user)
            | Q(projetos__membros__user=user)
        ).distinct()

        projetos_acesso = Projeto.objects.filter(
            Q(programa__cliente__in=clientes_acesso)
            | Q(programa__in=programas_acesso)
            | Q(membros__user=user)
        ).distinct()

        return (
            CampoDefinicao.objects.filter(
                Q(cliente__in=clientes_acesso)
                | Q(programa__in=programas_acesso)
                | Q(projeto__in=projetos_acesso)
            )
            .distinct()
            .select_related("cliente", "programa", "projeto")
        )


class CampoValorViewSet(viewsets.ModelViewSet):
    queryset = CampoValor.objects.all()
    serializer_class = CampoValorSerializer
    permission_classes = [perms.PodeAcessarConteudoPorEscopo]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return CampoValor.objects.none()
        if perms.is_platform_admin(user):
            return CampoValor.objects.all().select_related(
                "definicao", "cliente", "programa", "projeto", "evento"
            )

        clientes_acesso = Cliente.objects.filter(
            Q(membros__user=user)
            | Q(programas__membros__user=user)
            | Q(programas__projetos__membros__user=user)
        ).distinct()

        programas_acesso = Programa.objects.filter(
            Q(cliente__in=clientes_acesso)
            | Q(membros__user=user)
            | Q(projetos__membros__user=user)
        ).distinct()

        projetos_acesso = Projeto.objects.filter(
            Q(programa__cliente__in=clientes_acesso)
            | Q(programa__in=programas_acesso)
            | Q(membros__user=user)
        ).distinct()

        return (
            CampoValor.objects.filter(
                Q(cliente__in=clientes_acesso)
                | Q(programa__in=programas_acesso)
                | Q(projeto__in=projetos_acesso)
            )
            .distinct()
            .select_related("definicao", "cliente", "programa", "projeto", "evento")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        definicao = serializer.validated_data["definicao"]
        cliente = serializer.validated_data.get("cliente")
        programa = serializer.validated_data.get("programa")
        projeto = serializer.validated_data.get("projeto")
        evento = serializer.validated_data.get("evento")

        filters = {"definicao": definicao}
        if cliente:
            filters["cliente"] = cliente
        elif programa:
            filters["programa"] = programa
        elif projeto:
            filters["projeto"] = projeto
        elif evento:
            filters["evento"] = evento

        instance = CampoValor.objects.filter(**filters).first()
        if instance:
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data, status=status.HTTP_200_OK)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class EquipeProjetoViewSet(viewsets.ModelViewSet):
    queryset = EquipeProjeto.objects.all()
    serializer_class = EquipeProjetoSerializer
    permission_classes = [perms.PodeAcessarConteudoProjeto]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return EquipeProjeto.objects.none()
        if perms.is_platform_admin(user):
            return EquipeProjeto.objects.all().select_related(
                "projeto", "projeto__programa", "projeto__programa__cliente"
            )
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
        return (
            EquipeProjeto.objects.filter(
                Q(projeto__programa__cliente__in=clientes_admin)
                | Q(projeto__programa__in=programas_membro)
                | Q(projeto__in=projetos_membro)
            )
            .distinct()
            .select_related(
                "projeto", "projeto__programa", "projeto__programa__cliente"
            )
        )

    def perform_create(self, serializer):
        projeto = serializer.validated_data.get("projeto")
        if projeto:
            nivel = perms.get_nivel_acesso(self.request.user, projeto)
            if nivel is None:
                raise PermissionDenied(
                    "Você não tem permissão para adicionar membros à equipe deste projeto."
                )
        serializer.save()


class ClasseEventoViewSet(viewsets.ModelViewSet):
    queryset = ClasseEvento.objects.all()
    serializer_class = ClasseEventoSerializer
    permission_classes = [perms.PodeAcessarConteudoPorEscopo]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return ClasseEvento.objects.none()
        if perms.is_platform_admin(user):
            return ClasseEvento.objects.all().select_related(
                "cliente", "programa", "projeto"
            )
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
        return (
            ClasseEvento.objects.filter(
                Q(cliente__in=clientes_admin)
                | Q(programa__in=programas_membro)
                | Q(programa__cliente__in=clientes_admin)
                | Q(projeto__in=projetos_membro)
                | Q(projeto__programa__in=programas_membro)
                | Q(projeto__programa__cliente__in=clientes_admin)
            )
            .distinct()
            .select_related("cliente", "programa", "projeto")
        )


class EventoViewSet(viewsets.ModelViewSet):
    queryset = Evento.objects.all()
    serializer_class = EventoSerializer
    permission_classes = [perms.PodeAcessarConteudoPorEscopo]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return Evento.objects.none()
        if perms.is_platform_admin(user):
            return Evento.objects.all().select_related(
                "classe_evento", "cliente", "programa", "projeto"
            )
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
        return (
            Evento.objects.filter(
                Q(cliente__in=clientes_admin)
                | Q(programa__in=programas_membro)
                | Q(programa__cliente__in=clientes_admin)
                | Q(projeto__in=projetos_membro)
                | Q(projeto__programa__in=programas_membro)
                | Q(projeto__programa__cliente__in=clientes_admin)
            )
            .distinct()
            .select_related("classe_evento", "cliente", "programa", "projeto")
        )


class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    permission_classes = [perms.PodeAcessarConteudoPorEscopo]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return Template.objects.none()
        if perms.is_platform_admin(user):
            return Template.objects.all().select_related(
                "cliente", "programa", "projeto"
            )
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
        programas_via_projetos = MembroProjeto.objects.filter(user=user).values(
            "projeto__programa"
        )
        return (
            Template.objects.filter(
                Q(cliente__in=clientes_admin)
                | Q(programa__in=programas_membro)
                | Q(programa__in=programas_via_projetos)
                | Q(programa__cliente__in=clientes_admin)
                | Q(projeto__in=projetos_membro)
                | Q(projeto__programa__in=programas_membro)
                | Q(projeto__programa__cliente__in=clientes_admin)
            )
            .distinct()
            .select_related("cliente", "programa", "projeto")
        )

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        template = self.get_object()

        if not template.modelo_json:
            return Response(
                {"detail": "Template não possui modelo_json."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente = (
            template.cliente
            or (template.programa.cliente if template.programa_id else None)
            or (template.projeto.programa.cliente if template.projeto_id else None)
        )
        extras = {
            "logo_cliente_id": cliente.logomarca_id if cliente else None,
            "logo_parceira_id": (
                template.projeto.logomarca_id if template.projeto_id else None
            ),
            "assinaturas": resolver_assinaturas(template.id),
        }

        rendered = replace_placeholders(template.modelo_json, {})
        output_buffer = prosemirror_to_docx(rendered, **extras)

        content_disp = build_docx_filename_and_content_disposition(template.nome)
        response = FileResponse(output_buffer, content_type=DOCX_ALLOWED_MIME)
        response["Content-Disposition"] = content_disp
        return response

    @extend_schema(
        request=TemplateCreateRequestSerializer,
        responses={202: TaskAcceptedSerializer},
    )
    def create(self, request, *args, **kwargs):
        """Crie um template a partir de um documento JSON do ProseMirror."""
        serializer = TemplateCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        cliente = validated_data.get("cliente")
        programa = validated_data.get("programa")
        projeto = validated_data.get("projeto")

        task = cast(Any, create_template).delay(
            nome=validated_data.get("nome"),
            nivel=validated_data.get("nivel"),
            cliente_id=cliente.pk if cliente else None,
            programa_id=programa.pk if programa else None,
            projeto_id=projeto.pk if projeto else None,
            modelo_json=validated_data.get("modelo_json"),
        )

        return Response(
            {
                "detail": "Solicitação recebida e enviada para processamento.",
                "task_id": task.id,
                "task_status": "PENDING",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request, pk=None):
        """
        Resolve as variáveis (campos nativos + customizadas) visíveis para a
        cadeia de instâncias informada e retorna o documento_json pronto para
        edição/preview no front-end.
        """
        template = self.get_object()
        if not template.modelo_json:
            return Response(
                {
                    "detail": "Template não possui modelo_json. Use um template criado pelo editor."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente_id = request.query_params.get("cliente_id") or template.cliente_id
        programa_id = request.query_params.get("programa_id") or template.programa_id
        projeto_id = request.query_params.get("projeto_id") or template.projeto_id
        evento_id = request.query_params.get("evento_id")

        variables = build_variables_context(
            cliente_id=cliente_id,
            programa_id=programa_id,
            projeto_id=projeto_id,
            evento_id=evento_id,
        )

        documento_json = replace_placeholders(template.modelo_json, variables)
        return Response({"documento_json": documento_json})

    @action(detail=True, methods=["get"], url_path="nivel-exigido")
    def nivel_exigido(self, request, pk=None):
        """
        Nível mais profundo (cliente/programa/projeto/evento) exigido para
        resolver todos os gaps do template dada a cadeia de instâncias já
        conhecida — inclusive os usados apenas transitivamente, dentro do
        valor de variáveis de texto rico citadas pelo template
        (`document_engine.scope.scan_required_nivel`).

        Usado pelo front-end para decidir quais seletores mostrar como
        obrigatórios *antes* de tentar gerar o relatório, sem precisar
        replicar a varredura de `scan_required_nivel` no cliente.
        """
        template = self.get_object()
        if not template.modelo_json:
            return Response(
                {
                    "detail": "Template não possui modelo_json. Use um template criado pelo editor."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente = programa = projeto = None
        cliente_id = request.query_params.get("cliente_id")
        programa_id = request.query_params.get("programa_id")
        projeto_id = request.query_params.get("projeto_id")

        if projeto_id:
            projeto = Projeto.objects.select_related("programa__cliente").get(
                id=projeto_id
            )
            programa = projeto.programa
            cliente = programa.cliente
        elif programa_id:
            programa = Programa.objects.select_related("cliente").get(id=programa_id)
            cliente = programa.cliente
        elif cliente_id:
            cliente = Cliente.objects.get(id=cliente_id)

        nivel = scan_required_nivel(
            template.modelo_json, cliente=cliente, programa=programa, projeto=projeto
        )
        return Response({"nivel_exigido": nivel})

    @action(detail=False, methods=["get"], url_path="variaveis-disponiveis")
    def variaveis_disponiveis(self, request):
        """Lista campos nativos + variáveis customizadas visíveis para autocompletar
        a criação de um template no nível/instância informados."""
        nivel = request.query_params.get("nivel")
        if nivel not in NivelTemplate.values:
            return Response(
                {"detail": "Informe um nivel válido: cliente, programa ou projeto."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cliente = programa = projeto = None
        cliente_id = request.query_params.get("cliente_id")
        programa_id = request.query_params.get("programa_id")
        projeto_id = request.query_params.get("projeto_id")

        if projeto_id:
            projeto = Projeto.objects.select_related("programa__cliente").get(
                id=projeto_id
            )
            programa = projeto.programa
            cliente = programa.cliente
        elif programa_id:
            programa = Programa.objects.select_related("cliente").get(id=programa_id)
            cliente = programa.cliente
        elif cliente_id:
            cliente = Cliente.objects.get(id=cliente_id)

        definicoes = resolver_campos_definicao_escopo(
            cliente=cliente, programa=programa, projeto=projeto
        ).select_related("cliente", "programa", "projeto")

        resultado = []
        for d in definicoes:
            escopo_nome = ""
            ref = d.referencia
            if d.projeto:
                escopo_nome = d.projeto.nome
                ref = ref.removeprefix("projeto.")
            elif d.programa:
                escopo_nome = d.programa.nome
                ref = ref.removeprefix("programa.")
                if projeto:
                    ref = f"programa.{ref}"
            elif d.cliente:
                escopo_nome = d.cliente.nome
                ref = ref.removeprefix("cliente.")
                if projeto or programa:
                    ref = f"cliente.{ref}"

            resultado.append(
                {
                    "referencia": ref,
                    "descricao": d.descricao,
                    "tipo": d.tipo,
                    "nivel_aplicacao": d.nivel_aplicacao,
                    "origem": "customizado",
                    "obrigatorio": d.obrigatorio,
                    "escopo_nome": escopo_nome,
                }
            )

        for nivel_sistema in list(NivelTemplate.values) + ["evento"]:
            for referencia, tipo, descricao in get_system_fields_for_level(
                nivel_sistema
            ):
                resultado.append(
                    {
                        "referencia": referencia,
                        "descricao": descricao,
                        "tipo": tipo,
                        "nivel_aplicacao": nivel_sistema,
                        "origem": "sistema",
                        "obrigatorio": False,
                    }
                )

        return Response(resultado)

    @action(detail=True, methods=["get"], url_path="eventos-disponiveis")
    def eventos_disponiveis(self, request, pk=None):
        """Retorna os Eventos elegíveis para gerar um Relatório a partir deste Template."""
        template = self.get_object()
        eventos = eventos_disponiveis_para_relatorio(template)
        serializer = EventoSerializer(eventos, many=True)
        return Response(serializer.data)

    @extend_schema(
        request=TemplateSerializer,
        responses={200: TemplateSerializer},
        description=(
            "Atualização parcial do template. Pode ser incluído mais de um campo."
        ),
        examples=[
            OpenApiExample(
                "Atualizar somente nome do template",
                value={"nome": "Template de Relatório"},
                request_only=True,
            ),
            OpenApiExample(
                "Atualizar somente projeto",
                value={"projeto": 2},
                request_only=True,
            ),
            OpenApiExample(
                "Atualizar modelo_json",
                value={"modelo_json": {"type": "doc", "content": []}},
                request_only=True,
            ),
        ],
    )
    def partial_update(self, request, pk=None):
        if "modelo_json" in request.data:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        return super().partial_update(request, pk=pk)

    @action(
        detail=False,
        methods=["post"],
        url_path="convert-docx",
        parser_classes=[MultiPartParser, FormParser],
    )
    def convert_docx(self, request):
        """Upload a .docx file and receive its ProseMirror JSON representation."""
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            return Response(
                {"detail": "Arquivo obrigatório."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not arquivo.name.lower().endswith(".docx"):
            return Response(
                {"detail": "Envie um arquivo .docx"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            pm_json = convert_docx_to_prosemirror(arquivo)
        except Exception as exc:
            return Response(
                {"detail": f"Erro na conversão: {exc}"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response({"modelo_json": pm_json})


class AssinaturaTemplateViewSet(viewsets.ModelViewSet):
    queryset = AssinaturaTemplate.objects.all()
    serializer_class = AssinaturaTemplateSerializer
    permission_classes = [perms.PodeAcessarAssinaturaTemplate]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return AssinaturaTemplate.objects.none()
        if perms.is_platform_admin(user):
            return AssinaturaTemplate.objects.all().select_related(
                "template", "equipe_programa", "equipe_projeto"
            )
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
        return (
            AssinaturaTemplate.objects.filter(
                Q(equipe_programa__programa__cliente__in=clientes_admin)
                | Q(equipe_programa__programa__in=programas_membro)
                | Q(equipe_projeto__projeto__programa__cliente__in=clientes_admin)
                | Q(equipe_projeto__projeto__programa__in=programas_membro)
                | Q(equipe_projeto__projeto__in=projetos_membro)
            )
            .distinct()
            .select_related("template", "equipe_programa", "equipe_projeto")
        )

    @extend_schema(
        request=AssinaturaTemplateSerializer,
        responses={201: AssinaturaTemplateSerializer},
        examples=[
            OpenApiExample(
                "Assinatura com equipe do programa",
                value={
                    "template": 1,
                    "equipe_programa": 1,
                    "equipe_projeto": None,
                },
                request_only=True,
            ),
            OpenApiExample(
                "Assinatura com equipe do projeto",
                value={
                    "template": 1,
                    "equipe_programa": None,
                    "equipe_projeto": 1,
                },
                request_only=True,
            ),
        ],
        description=(
            "Cria uma assinatura de template. Informe exatamente um dos campos: "
            "equipe_programa ou equipe_projeto."
        ),
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_classes = [perms.PodeAcessarCliente]

    def get_queryset(self):
        """
        Scoped list:
        - Platform admin: all clients.
        - Other authenticated users: clients where they are admin (MembroCliente) OR
          have access to a programa (AcessoPrograma) OR project (AcessoProjeto).
        """
        user = self.request.user
        if not perms.is_authenticated(user):
            return Cliente.objects.none()
        if perms.is_platform_admin(user):
            return Cliente.objects.all().select_related("logomarca")
        return (
            Cliente.objects.filter(
                Q(membros__user=user)
                | Q(programas__membros__user=user)
                | Q(programas__projetos__membros__user=user)
            )
            .distinct()
            .select_related("logomarca")
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="publicos",
        permission_classes=[permissions.AllowAny],
    )
    def publicos(self, request):
        """Lista pública de clientes (sem autenticação) para fluxo de cadastro/solicitação."""
        clientes = Cliente.objects.values("id", "nome").order_by("nome")
        return Response(list(clientes))

    @action(
        detail=True,
        methods=["get"],
        url_path="usuarios",
        permission_classes=[perms.PodeAcessarCliente],
    )
    def usuarios(self, request, pk=None):
        """
        Retorna TODOS os usuários com qualquer acesso neste cliente,
        agregados por usuário — independente da fonte do acesso.

        Cada item inclui:
          - is_admin_cliente: bool
          - membro_cliente_id: int | null
          - membros_programa: [{id, programa_id, programa_nome}]
          - membros_projeto: [{id, projeto_id, projeto_nome}]
        """

        cliente = self.get_object()
        usuarios_agregados = listar_usuarios_cliente(cliente)
        return Response(usuarios_agregados)

    @action(
        detail=True,
        methods=["post"],
        url_path="remover-usuario",
        permission_classes=[perms.PodeAcessarCliente],
    )
    def remover_usuario(self, request, pk=None):
        """
        Remove TODOS os acessos de um usuário neste cliente:
          - Deleta MembroCliente (admin) se existir
          - Deleta MembroPrograma de todos os programas deste cliente
          - Deleta MembroProjeto de todos os projetos deste cliente

        Body: { "user_id": <int> }
        """

        cliente = self.get_object()
        user_id = request.data.get("user_id")

        if not user_id:
            raise DRFValidationError("O campo 'user_id' é obrigatório.")

        remover_usuario_do_cliente(cliente, user_id, request.user)
        return Response({"detail": "Usuário removido do cliente com sucesso."})

    @action(
        detail=True,
        methods=["post"],
        url_path="atualizar-permissoes",
        permission_classes=[perms.PodeAcessarCliente],
    )
    def atualizar_permissoes(self, request, pk=None):
        """
        Substitui as permissões de um usuário neste cliente.

        Body:
          user_id: int                  — usuário alvo
          e_admin_cliente: bool         — se True, concede MembroCliente e remove MembroPrograma/MembroProjeto do cliente
          programas: [int, ...] ou [{id}, ...]  — lista de programa IDs
          projetos: [int, ...] ou [{id}, ...]   — lista de projeto IDs
        """

        cliente = self.get_object()
        req_user = request.user

        # Validar campos obrigatórios
        user_id = request.data.get("user_id")
        if not user_id:
            raise DRFValidationError("O campo 'user_id' é obrigatório.")

        e_admin_cliente = bool(request.data.get("e_admin_cliente", False))
        programas_ids = [
            (item["id"] if isinstance(item, dict) else item)
            for item in request.data.get("programas", [])
        ]
        projetos_ids = [
            (item["id"] if isinstance(item, dict) else item)
            for item in request.data.get("projetos", [])
        ]

        # Verificar se req_user tem permissão para conceder admin
        is_plat_admin = perms.is_platform_admin(req_user)
        is_cli_admin = perms.is_cliente_admin(req_user, cliente)

        if e_admin_cliente and not (is_plat_admin or is_cli_admin):
            raise PermissionDenied(
                "Apenas administradores podem conceder o papel de Administrador do Cliente."
            )

        # Buscar usuário alvo
        alvo_user = User.objects.filter(id=user_id).first()
        if not alvo_user:
            raise DRFValidationError("Usuário não encontrado.")

        # Validar programas/projetos pertencem ao cliente
        if programas_ids:
            count = Programa.objects.filter(
                id__in=programas_ids, cliente=cliente
            ).count()
            if count != len(programas_ids):
                raise DRFValidationError(
                    "Um ou mais programas não pertencem a este cliente."
                )

        if projetos_ids:
            count = Projeto.objects.filter(
                id__in=projetos_ids, programa__cliente=cliente
            ).count()
            if count != len(projetos_ids):
                raise DRFValidationError(
                    "Um ou mais projetos não pertencem a este cliente."
                )

        # Delegar sincronização ao serviço
        sincronizar_acessos_cliente(
            cliente, alvo_user, e_admin_cliente, programas_ids, projetos_ids, req_user
        )
        # Invalida o cache de autorização do usuário cujos papéis foram alterados,
        # para que qualquer checagem subsequente neste request reflita o novo estado.
        invalidar_cache_autorizacao(alvo_user)

        return Response({"detail": "Permissões atualizadas com sucesso."})


class TemplateClasseEventoViewSet(viewsets.ModelViewSet):
    queryset = TemplateClasseEvento.objects.all()
    serializer_class = TemplateClasseEventoSerializer
    permission_classes = [perms.PodeAcessarConteudoPorEscopo]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return TemplateClasseEvento.objects.none()
        if perms.is_platform_admin(user):
            return TemplateClasseEvento.objects.all().select_related(
                "template", "classe_evento"
            )
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
        return (
            TemplateClasseEvento.objects.filter(
                Q(template__cliente__in=clientes_admin)
                | Q(template__programa__in=programas_membro)
                | Q(template__programa__cliente__in=clientes_admin)
                | Q(template__projeto__in=projetos_membro)
                | Q(template__projeto__programa__in=programas_membro)
                | Q(template__projeto__programa__cliente__in=clientes_admin)
            )
            .distinct()
            .select_related("template", "classe_evento")
        )


class RelatorioViewSet(viewsets.ModelViewSet):
    queryset = Relatorio.objects.all()
    serializer_class = RelatorioSerializer
    permission_classes = [perms.PodeAcessarConteudoProjeto]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return Relatorio.objects.none()
        if perms.is_platform_admin(user):
            return Relatorio.objects.all().select_related(
                "template", "evento", "projeto"
            )
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
        return (
            Relatorio.objects.filter(
                Q(projeto__in=projetos_membro)
                | Q(projeto__programa__in=programas_membro)
                | Q(projeto__programa__cliente__in=clientes_admin)
                | Q(evento__projeto__programa__cliente__in=clientes_admin)
                | Q(evento__projeto__programa__in=programas_membro)
                | Q(evento__projeto__in=projetos_membro)
                | Q(evento__programa__cliente__in=clientes_admin)
                | Q(evento__programa__in=programas_membro)
                | Q(evento__cliente__in=clientes_admin)
            )
            .distinct()
            .select_related("template", "evento", "projeto")
        )

    @extend_schema(
        request=RelatorioGenerateRequestSerializer,
        examples=[
            OpenApiExample(
                "Gerar relatório",
                value={
                    "nome": "Relatório Financeiro Q2",
                    "evento": 2,
                    "template": 1,
                    "documento_json": {"type": "doc", "content": []},
                },
                request_only=True,
            )
        ],
        description="Gera relatório a partir de um template.",
        responses={202: TaskAcceptedSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = RelatorioGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        nome = serializer.validated_data.get("nome")
        cliente = serializer.validated_data.get("cliente")
        programa = serializer.validated_data.get("programa")
        projeto = serializer.validated_data.get("projeto")
        evento = serializer.validated_data.get("evento")
        template = serializer.validated_data["template"]
        documento_json = serializer.validated_data.get("documento_json") or None
        assinaturas = serializer.validated_data.get("assinaturas") or None

        task = cast(Any, generate_relatorio).delay(
            cliente_id=cliente.id if cliente else None,
            programa_id=programa.id if programa else None,
            projeto_id=projeto.id if projeto else None,
            evento_id=evento.id if evento else None,
            template_id=template.id,
            documento_json=documento_json,
            nome=nome,
            assinaturas=assinaturas,
        )

        return Response(
            {
                "detail": "Solicitação recebida e enviada para processamento.",
                "task_id": task.id,
                "task_status": "PENDING",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        relatorio = self.get_object()
        template = relatorio.template
        variables = relatorio.metadados or {}

        if not variables:
            return Response(
                {"detail": "Metadados do relatório não encontrados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        extras = {
            **logos_cabecalho_de_metadados(variables),
            "assinaturas": assinaturas_de_metadados(variables),
        }

        if relatorio.documento_json:
            # ── Documento já resolvido e editado pelo usuário ──
            output_buffer = prosemirror_to_docx(relatorio.documento_json, **extras)
        elif template.modelo_json:
            # ── Resolução automática de variáveis ──────────────
            rendered = replace_placeholders(template.modelo_json, variables)
            output_buffer = prosemirror_to_docx(rendered, **extras)
        else:
            return Response(
                {
                    "detail": "Relatório não possui documento_json ou modelo_json válido para download."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_disp = build_docx_filename_and_content_disposition(
            relatorio.nome, fallback="relatorio"
        )
        response = FileResponse(output_buffer, content_type=DOCX_ALLOWED_MIME)
        response["Content-Disposition"] = content_disp
        return response


class AgendamentoRelatorioViewSet(viewsets.ModelViewSet):
    queryset = AgendamentoRelatorio.objects.all()
    serializer_class = AgendamentoRelatorioSerializer
    permission_classes = [perms.PodeAcessarConteudoProjeto]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return AgendamentoRelatorio.objects.none()

        qs = AgendamentoRelatorio.objects.select_related(
            "template",
            "cliente",
            "programa",
            "projeto",
            "evento",
            "criado_por",
            "periodic_task",
        )
        if not perms.is_platform_admin(user):
            clientes_admin = Cliente.objects.filter(membros__user=user)
            programas_membro = MembroPrograma.objects.filter(user=user).values(
                "programa"
            )
            projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
            qs = qs.filter(
                Q(cliente__in=clientes_admin)
                | Q(programa__cliente__in=clientes_admin)
                | Q(programa__in=programas_membro)
                | Q(projeto__programa__cliente__in=clientes_admin)
                | Q(projeto__programa__in=programas_membro)
                | Q(projeto__in=projetos_membro)
                | Q(evento__projeto__programa__cliente__in=clientes_admin)
                | Q(evento__projeto__programa__in=programas_membro)
                | Q(evento__projeto__in=projetos_membro)
                | Q(evento__programa__cliente__in=clientes_admin)
                | Q(evento__programa__in=programas_membro)
                | Q(evento__cliente__in=clientes_admin)
            ).distinct()

        cliente_id = self.request.query_params.get("cliente_id")
        if cliente_id:
            qs = qs.filter(
                Q(cliente_id=cliente_id)
                | Q(programa__cliente_id=cliente_id)
                | Q(projeto__programa__cliente_id=cliente_id)
                | Q(evento__projeto__programa__cliente_id=cliente_id)
                | Q(evento__programa__cliente_id=cliente_id)
                | Q(evento__cliente_id=cliente_id)
            )

        return qs

    def perform_create(self, serializer):
        agendamento = serializer.save(criado_por=self.request.user)
        sincronizar_periodic_task(agendamento)

    def perform_update(self, serializer):
        agendamento = serializer.save()
        sincronizar_periodic_task(agendamento)

    def perform_destroy(self, instance):
        agendamento_id = instance.id
        periodic_task = instance.periodic_task
        with transaction.atomic():
            instance.delete()
            remover_periodic_task(agendamento_id, periodic_task)


class TaskViewSet(viewsets.ViewSet):
    """Endpoint para consultar o status de tasks do Celery."""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="task_id",
                description="ID da task do Celery",
                required=True,
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.PATH,
            )
        ],
        responses={200: TaskStatusSerializer},
    )
    @action(detail=False, methods=["get"], url_path=r"(?P<task_id>[^/.]+)")
    def task_status(self, request, task_id=None):
        async_result = AsyncResult(task_id)
        response_payload = {
            "task_id": task_id,
            "task_status": async_result.state,
        }

        if async_result.state == "SUCCESS":
            response_payload["result"] = async_result.result
        elif async_result.state == "FAILURE":
            response_payload["error"] = str(async_result.result)

        return Response(response_payload, status=status.HTTP_200_OK)


# =============================================================================
# ViewSets de Autorização
# =============================================================================


class MembroGeRelatViewSet(viewsets.ModelViewSet):
    """Gestão de Admins da Plataforma GeRelat.

    Apenas Admins GeRelat podem criar/deletar membros.
    Não pode remover o último admin.
    """

    queryset = MembroGeRelat.objects.all().select_related("user")
    serializer_class = MembroGeRelatSerializer

    def get_queryset(self):
        if not perms.is_platform_admin(self.request.user):
            return MembroGeRelat.objects.none()
        return super().get_queryset()

    def perform_create(self, serializer):
        if not perms.is_platform_admin(self.request.user):
            raise PermissionDenied("Apenas Admins GeRelat podem criar novos admins.")
        serializer.save()

    def perform_destroy(self, instance):
        if not perms.is_platform_admin(self.request.user):
            raise PermissionDenied("Apenas Admins GeRelat podem remover admins.")
        if MembroGeRelat.objects.count() <= 1:
            raise DRFValidationError(
                "Não é possível remover o último Admin GeRelat do sistema."
            )
        instance.delete()

    @action(detail=False, methods=["get"], url_path="usuarios-disponiveis")
    def usuarios_disponiveis(self, request):
        if not perms.is_platform_admin(self.request.user):
            raise PermissionDenied("Apenas Admins GeRelat podem listar usuários.")
        User = get_user_model()
        admins_ids = MembroGeRelat.objects.values_list("user_id", flat=True)
        usuarios = User.objects.exclude(id__in=admins_ids).order_by(
            "full_name", "email"
        )
        dados = [
            {
                "id": u.id,
                "email": u.email,
                "nome": u.full_name or u.email,
            }
            for u in usuarios
        ]
        return Response(dados)


class MembroClienteViewSet(viewsets.ModelViewSet):
    """Gestão de Admins de Cliente.

    Admins GeRelat ou Admins do Cliente podem gerenciar membros.
    """

    queryset = MembroCliente.objects.all().select_related(
        "user", "cliente", "promovido_por"
    )
    serializer_class = MembroClienteSerializer

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return MembroCliente.objects.none()
        if perms.is_platform_admin(user):
            qs = super().get_queryset()
        else:
            qs = MembroCliente.objects.filter(
                cliente__in=Cliente.objects.filter(membros__user=user)
            ).select_related("user", "cliente", "promovido_por")

        cliente_id = self.request.query_params.get(
            "cliente"
        ) or self.request.query_params.get("cliente_id")
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        cliente = serializer.validated_data["cliente"]
        if not perms.is_cliente_admin(user, cliente):
            raise PermissionDenied(
                "Apenas Admins GeRelat ou Admins deste Cliente podem adicionar novos admins."
            )
        serializer.save(promovido_por=user)

    def perform_destroy(self, instance):
        user = self.request.user
        if not perms.is_cliente_admin(user, instance.cliente):
            raise PermissionDenied(
                "Apenas Admins GeRelat ou Admins deste Cliente podem remover admins."
            )
        instance.delete()


class SolicitacaoClienteViewSet(viewsets.ModelViewSet):
    """Gestão de solicitações de acesso a Cliente.

    Usuários autenticados podem criar.
    Admins GeRelat/Cliente ou Moderadores podem aprovar/recusar.
    """

    queryset = SolicitacaoCliente.objects.all().select_related("user", "cliente")
    serializer_class = SolicitacaoClienteSerializer
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return SolicitacaoCliente.objects.none()
        if perms.is_platform_admin(user):
            qs = super().get_queryset()
        else:
            clientes_admin = Cliente.objects.filter(membros__user=user)
            qs = SolicitacaoCliente.objects.filter(
                Q(cliente__in=clientes_admin) | Q(user=user)
            ).select_related("user", "cliente")

        cliente_id = self.request.query_params.get("cliente")
        if cliente_id:
            qs = qs.filter(cliente_id=cliente_id)

        status_param = self.request.query_params.get("status")
        if status_param and status_param.lower() != "all":
            qs = qs.filter(status=status_param)
        elif status_param is None:
            qs = qs.filter(status=SolicitacaoCliente.STATUS_PENDENTE)

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        cliente = serializer.validated_data["cliente"]
        if MembroCliente.objects.filter(user=user, cliente=cliente).exists():
            raise DRFValidationError("Você já é administrador deste cliente.")
        if SolicitacaoCliente.objects.filter(
            user=user, cliente=cliente, status=SolicitacaoCliente.STATUS_PENDENTE
        ).exists():
            raise DRFValidationError(
                "Você já possui uma solicitação pendente para este cliente."
            )
        serializer.save(user=user)

    @action(detail=True, methods=["post"])
    def aprovar(self, request, pk=None):
        """
        Aprova uma solicitação e concede acesso ao usuário.

        Body esperado:
          e_admin_cliente: bool              — concede MembroCliente (admin total)
          programas: [id, ...] ou [{id}]      — lista de programas a adicionar
          projetos:  [id, ...] ou [{id}]      — lista de projetos a adicionar
        """

        solicitacao = self.get_object()
        user = request.user

        if solicitacao.status != SolicitacaoCliente.STATUS_PENDENTE:
            raise DRFValidationError("Esta solicitação já foi processada.")

        e_admin_cliente = bool(request.data.get("e_admin_cliente", False))
        programas_payload = request.data.get("programas", [])
        projetos_payload = request.data.get("projetos", [])

        # Extrair IDs (aceita int ou {"id": int})
        programas_ids = [
            (item["id"] if isinstance(item, dict) else item)
            for item in programas_payload
        ]
        projetos_ids = [
            (item["id"] if isinstance(item, dict) else item)
            for item in projetos_payload
        ]

        # ── Determine permission ──────────────────────────────────────────────
        is_plat_admin = perms.is_platform_admin(user)
        is_cli_admin = perms.is_cliente_admin(user, solicitacao.cliente)

        pode_aprovar = is_plat_admin or is_cli_admin

        # Moderadores de programa/projeto podem aprovar apenas para seus escopos
        if not pode_aprovar and not e_admin_cliente:
            for prog_id in programas_ids:
                prog = Programa.objects.filter(
                    id=prog_id, cliente=solicitacao.cliente
                ).first()
                if prog and get_nivel_acesso_programa(user, prog) in (
                    "admin_gerelat",
                    "admin_cliente",
                    "membro_programa",
                ):
                    pode_aprovar = True
                    break

            if not pode_aprovar:
                for proj_id in projetos_ids:
                    proj = Projeto.objects.filter(
                        id=proj_id, programa__cliente=solicitacao.cliente
                    ).first()
                    if proj and get_nivel_acesso(user, proj) in (
                        "admin_gerelat",
                        "admin_cliente",
                        "membro_programa",
                    ):
                        pode_aprovar = True
                        break

        if not pode_aprovar:
            raise PermissionDenied(
                "Você não tem permissão para aprovar esta solicitação."
            )

        if e_admin_cliente and not (is_plat_admin or is_cli_admin):
            raise PermissionDenied(
                "Apenas administradores podem conceder o papel de Administrador do Cliente."
            )

        if not e_admin_cliente and not programas_ids and not projetos_ids:
            raise DRFValidationError(
                "Selecione ao menos um nível de acesso (Administrador do Cliente, Programa ou Projeto) para aprovar."
            )

        # Validar que programas/projetos pertencem ao cliente
        if programas_ids:
            count = Programa.objects.filter(
                id__in=programas_ids, cliente=solicitacao.cliente
            ).count()
            if count != len(programas_ids):
                raise DRFValidationError(
                    "Um ou mais programas não pertencem a este cliente."
                )

        if projetos_ids:
            count = Projeto.objects.filter(
                id__in=projetos_ids, programa__cliente=solicitacao.cliente
            ).count()
            if count != len(projetos_ids):
                raise DRFValidationError(
                    "Um ou mais projetos não pertencem a este cliente."
                )

        # Marcar como aprovado
        solicitacao.status = SolicitacaoCliente.STATUS_APROVADO
        solicitacao.save()

        # ── Grant access via service ──────────────────────────────────────────
        sincronizar_acessos_cliente(
            solicitacao.cliente,
            solicitacao.user,
            e_admin_cliente,
            programas_ids,
            projetos_ids,
            user,  # promovido_por
        )
        # Invalida o cache de autorização do usuário cujos papéis foram alterados.
        invalidar_cache_autorizacao(solicitacao.user)

        return Response(self.get_serializer(solicitacao).data)

    @action(detail=True, methods=["post"])
    def recusar(self, request, pk=None):
        """Recusa uma solicitação."""

        solicitacao = self.get_object()
        user = request.user

        if solicitacao.status != SolicitacaoCliente.STATUS_PENDENTE:
            raise DRFValidationError("Esta solicitação já foi processada.")

        if not (
            perms.is_platform_admin(user)
            or perms.is_cliente_admin(user, solicitacao.cliente)
        ):
            raise PermissionDenied(
                "Você não tem permissão para recusar esta solicitação."
            )

        solicitacao.status = SolicitacaoCliente.STATUS_RECUSADO
        solicitacao.save()
        return Response(self.get_serializer(solicitacao).data)


class AdicionarMembroProgramaView(APIView):
    """POST /api/programas/{programa_id}/membros/"""

    permission_classes = [permissions.IsAuthenticated, perms.PodeGerenciarMembros]

    def post(self, request, programa_id):
        programa = get_object_or_404(Programa, id=programa_id)
        self.check_object_permissions(request, programa)

        user_id = request.data.get("usuario_id") or request.data.get("user_id")
        if not user_id:
            raise DRFValidationError("O campo 'usuario_id' é obrigatório.")
        usuario = get_object_or_404(User, id=user_id)
        adicionar_membro_programa(usuario, programa)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdicionarMembroProjetoView(APIView):
    """POST /api/programas/{programa_id}/projetos/{projeto_id}/membros/"""

    permission_classes = [permissions.IsAuthenticated, perms.PodeGerenciarMembros]

    def post(self, request, programa_id, projeto_id):
        projeto = get_object_or_404(Projeto, id=projeto_id, programa_id=programa_id)
        self.check_object_permissions(request, projeto)

        user_id = request.data.get("usuario_id") or request.data.get("user_id")
        if not user_id:
            raise DRFValidationError("O campo 'usuario_id' é obrigatório.")
        usuario = get_object_or_404(User, id=user_id)
        forcar = request.data.get("confirmar_rebaixamento", False)

        try:
            adicionar_membro_projeto(usuario, projeto, forcar_rebaixamento=forcar)
        except ConflitoDeAcessoError as e:
            return Response(
                {"detail": str(e), "requer_confirmacao": True},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class MembroProgramaViewSet(viewsets.ModelViewSet):
    queryset = MembroPrograma.objects.all().select_related(
        "user", "programa", "programa__cliente"
    )
    serializer_class = MembroProgramaSerializer
    permission_classes = [permissions.IsAuthenticated, perms.PodeGerenciarMembros]
    http_method_names = ["get", "delete"]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return MembroPrograma.objects.none()
        if perms.is_platform_admin(user):
            return super().get_queryset()
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        return MembroPrograma.objects.filter(
            Q(programa__cliente__in=clientes_admin) | Q(programa__in=programas_membro)
        ).select_related("user", "programa", "programa__cliente")


class MembroProjetoViewSet(viewsets.ModelViewSet):
    queryset = MembroProjeto.objects.all().select_related(
        "user", "projeto", "projeto__programa", "projeto__programa__cliente"
    )
    serializer_class = MembroProjetoSerializer
    permission_classes = [permissions.IsAuthenticated, perms.PodeGerenciarMembros]
    http_method_names = ["get", "delete"]

    def get_queryset(self):
        user = self.request.user
        if not perms.is_authenticated(user):
            return MembroProjeto.objects.none()
        if perms.is_platform_admin(user):
            return super().get_queryset()
        clientes_admin = Cliente.objects.filter(membros__user=user)
        programas_membro = MembroPrograma.objects.filter(user=user).values("programa")
        projetos_membro = MembroProjeto.objects.filter(user=user).values("projeto")
        return MembroProjeto.objects.filter(
            Q(projeto__programa__cliente__in=clientes_admin)
            | Q(projeto__programa__in=programas_membro)
            | Q(projeto__in=projetos_membro)
        ).select_related(
            "user", "projeto", "projeto__programa", "projeto__programa__cliente"
        )
