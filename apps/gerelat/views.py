from typing import Any, cast

from celery.result import AsyncResult
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .constants import DOCX_ALLOWED_MIME
from .document_engine.converters import (
    convert_docx_to_prosemirror,
    replace_placeholders,
)
from .document_engine.renderer import prosemirror_to_docx
from .document_engine.utils import (
    build_docx_filename_and_content_disposition,
    build_render_context,
    render_docx_from_template,
)
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
    TaskAcceptedSerializer,
    TaskStatusSerializer,
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
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        template = self.get_object()

        if template.modelo_json:
            rendered = replace_placeholders(template.modelo_json, {})
            output_buffer = prosemirror_to_docx(rendered)

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

        task = cast(Any, create_template).delay(
            nome=validated_data.get("nome"),
            projeto_id=validated_data.get("projeto").pk,
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
        Resolve as variáveis do projeto no template e retorna o documento_json
        pronto para edição/preview no front-end.
        """
        template = self.get_object()
        if not template.modelo_json:
            return Response(
                {
                    "detail": "Template não possui modelo_json. Use um template criado pelo editor."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        evento_id = request.query_params.get("evento_id")
        projeto_id = template.projeto_id

        if evento_id:
            try:
                evento = Evento.objects.get(id=evento_id)
                projeto_id = evento.projeto_id
            except Evento.DoesNotExist:
                return Response(
                    {"detail": "Evento não encontrado."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        campos = ProjetoCampo.objects.filter(projeto_id=projeto_id)
        variables = {c.referencia: c.valor for c in campos}

        documento_json = replace_placeholders(template.modelo_json, variables)
        return Response({"documento_json": documento_json})

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
                value={
                    "template": 1,
                    "evento": 2,
                    "documento_json": {"type": "doc", "content": []},
                    "nome": "Relatório Financeiro Q2",
                },
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
            evento_id=evento.id if evento else None,
            template_id=template.id,
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
            output_buffer = render_docx_from_template(
                template.modelo_arquivo_base, context
            )

        content_disp = build_docx_filename_and_content_disposition(
            relatorio.nome, fallback="relatorio"
        )
        response = FileResponse(output_buffer, content_type=DOCX_ALLOWED_MIME)
        response["Content-Disposition"] = content_disp
        return response
