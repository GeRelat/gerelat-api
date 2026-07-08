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
from .document_engine.converters import convert_docx_to_prosemirror, replace_placeholders
from .document_engine.renderer import prosemirror_to_docx
from .document_engine.utils import build_render_context, render_docx_from_template
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
from .serializers import (
    AssetCreateRequestSerializer,
    AssetSerializer,
    AssinaturaTemplateSerializer,
    ClasseEventoSerializer,
    ClienteSerializer,
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
    TemplateFromJsonSerializer,
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
        projeto = validated_data["projeto"]

        arquivo_base.content_type = DOCX_ALLOWED_MIME

        object_name = f"{uuid.uuid4()}.docx"
        stored_path = default_storage.save(object_name, arquivo_base)

        task = cast(Any, create_template).delay(
            stored_path=stored_path,
            nome_template=validated_data["nome_template"],
            projeto_id=projeto.pk,
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
        Resolve as variáveis do projeto no template e retorna o documento_json
        pronto para edição/preview no front-end.
        """
        template = self.get_object()
        if not template.modelo_json:
            return Response(
                {"detail": "Template não possui modelo_json. Use um template criado pelo editor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        evento_id = request.query_params.get("evento_id")
        projeto_id = template.projeto_id

        if evento_id:
            try:
                evento = Evento.objects.get(id_evento=evento_id)
                projeto_id = evento.projeto_id
            except Evento.DoesNotExist:
                return Response({"detail": "Evento não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        campos = ProjetoCampo.objects.filter(projeto_id=projeto_id)
        variables = {c.referencia: c.valor for c in campos}

        documento_json = replace_placeholders(template.modelo_json, variables)
        return Response({"documento_json": documento_json})

    @action(detail=False, methods=["post"], url_path="from-json", parser_classes=[JSONParser])
    def from_json(self, request):
        """Create a template from a ProseMirror JSON document (no .docx upload needed)."""
        serializer = TemplateFromJsonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        template = Template.objects.create(
            nome_template=data["nome_template"],
            projeto=data["projeto"],
            modelo_json=data["modelo_json"],
            modelo_arquivo_base="",
        )
        return Response(TemplateSerializer(template).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="update-json", parser_classes=[JSONParser])
    def update_json(self, request, pk=None):
        """Replace the modelo_json of an existing template."""
        template = self.get_object()
        modelo_json = request.data.get("modelo_json")
        if not isinstance(modelo_json, dict) or modelo_json.get("type") != "doc":
            return Response(
                {"detail": "modelo_json deve ser um documento ProseMirror válido com type='doc'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        template.modelo_json = modelo_json
        template.save(update_fields=["modelo_json", "ultima_atualizacao"])
        return Response(TemplateSerializer(template).data)

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
            return Response({"detail": "Arquivo obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
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


class AssinaturaTemplateViewSet(viewsets.ModelViewSet):
    queryset = AssinaturaTemplate.objects.all()
    serializer_class = AssinaturaTemplateSerializer

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
        documento_json = serializer.validated_data.get("documento_json") or None
        nome = serializer.validated_data.get("nome")

        task = cast(Any, generate_relatorio).delay(
            evento_id=evento.id_evento if evento else None,
            template_id=template.id_template,
            documento_json=documento_json,
            nome=nome,
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

        if relatorio.documento_json:
            # ── Documento já resolvido e editado pelo usuário ──
            output_buffer = prosemirror_to_docx(relatorio.documento_json)
        elif template.modelo_json:
            # ── Resolução automática de variáveis ──────────────
            rendered = replace_placeholders(template.modelo_json, variables)
            output_buffer = prosemirror_to_docx(rendered)
        else:
            # ── Legacy pipeline: docxtpl ───────────────────────
            context = build_render_context(variables)
            output_buffer = render_docx_from_template(template.modelo_arquivo_base, context)

        filename = f"{relatorio.nome}.docx"
        return FileResponse(
            output_buffer,
            content_type=DOCX_ALLOWED_MIME,
            as_attachment=True,
            filename=filename,
        )
