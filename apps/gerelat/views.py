import uuid
from typing import Any, cast

from celery.result import AsyncResult
from django.core.files.storage import default_storage
from django.http import FileResponse
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .constants import DOCX_ALLOWED_MIME
from .document_engine.utils import build_render_context, render_docx_from_template
from .models import (
    Asset,
    ClasseEvento,
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
from .serializers import (
    AssetCreateRequestSerializer,
    AssetSerializer,
    ClasseEventoSerializer,
    EquipeProgramaSerializer,
    EquipeProjetoSerializer,
    EventoSerializer,
    ProgramaSerializer,
    ProjetoCampoSerializer,
    ProjetoSerializer,
    RelatorioGenerateRequestSerializer,
    RelatorioSerializer,
    TemplateClasseEventoSerializer,
    TemplateCreateRequestSerializer,
    TemplateSerializer,
)
from .tasks import create_template, generate_relatorio


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == "create":
            return AssetCreateRequestSerializer
        return AssetSerializer


class ProgramaViewSet(viewsets.ModelViewSet):
    queryset = Programa.objects.all()
    serializer_class = ProgramaSerializer


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
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        template = self.get_object()
        stored_path = template.modelo_arquivo_base

        if not default_storage.exists(stored_path):
            return Response(
                {"detail": "Arquivo não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        file_obj = default_storage.open(stored_path, "rb")

        filename = f"{template.nome_template}.docx"
        return FileResponse(
            file_obj,
            content_type=DOCX_ALLOWED_MIME,
            as_attachment=True,
            filename=filename,
        )

    def create(self, request, *args, **kwargs):
        serializer = TemplateCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        arquivo_base = validated_data["modelo_arquivo_base"]
        programa = validated_data["programa"]
        projeto = validated_data.get("projeto")

        arquivo_base.content_type = DOCX_ALLOWED_MIME

        object_name = f"{uuid.uuid4()}.docx"
        stored_path = default_storage.save(object_name, arquivo_base)

        task = cast(Any, create_template).delay(
            stored_path=stored_path,
            nome_template=validated_data["nome_template"],
            programa_id=programa.pk,
            projeto_id=projeto.pk if projeto else None,
        )

        return Response(
            {
                "detail": "Solicitação recebida e enviada para processamento.",
                "task_id": task.id,
                "task_status": "PENDING",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"], url_path=r"tasks/(?P<task_id>[^/.]+)")
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


class TemplateClasseEventoViewSet(viewsets.ModelViewSet):
    queryset = TemplateClasseEvento.objects.all()
    serializer_class = TemplateClasseEventoSerializer


class RelatorioViewSet(viewsets.ModelViewSet):
    queryset = Relatorio.objects.all()
    serializer_class = RelatorioSerializer

    @extend_schema(
        request=RelatorioGenerateRequestSerializer,
        examples=[
            OpenApiExample(
                "Gerar relatório",
                value={"template": 1},
                request_only=True,
            )
        ],
        description="Gera relatório a partir de um template.",
    )
    @action(detail=False, methods=["post"], url_path="gerar")
    def gerar(self, request):
        serializer = RelatorioGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        evento = serializer.validated_data.get("evento")
        template = serializer.validated_data["template"]

        task = cast(Any, generate_relatorio).delay(
            evento_id=evento.id_evento if evento else None,
            template_id=template.id_template,
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
        raw_context = relatorio.metadados if relatorio.metadados else None

        if not raw_context:
            return Response(
                {"detail": "Metadados do relatório não encontrados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        context = build_render_context(raw_context)
        output_buffer = render_docx_from_template(
            template.modelo_arquivo_base,
            context,
        )

        filename = f"{relatorio.nome}.docx"
        return FileResponse(
            output_buffer,
            content_type=DOCX_ALLOWED_MIME,
            as_attachment=True,
            filename=filename,
        )
