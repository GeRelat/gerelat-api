from django.utils import timezone
from rest_framework import serializers

from .document_engine.scope import scan_required_nivel
from .document_engine.validators import validate_prosemirror_doc
from .enums import NivelTemplate
from .models import (
    AgendamentoRelatorio,
    Asset,
    AssetUso,
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
from .permissions import is_cliente_admin, is_platform_admin
from .services.eventos_relatorio import (
    eventos_disponiveis_para_relatorio,
    validar_classe_evento_mesmo_escopo,
)


def _validate_owner_matches_nivel(attrs: dict, *, instance=None) -> None:
    """Compartilhado por TemplateSerializer/TemplateCreateRequestSerializer:
    exige exatamente um de cliente/programa/projeto, coerente com `nivel`."""

    def _get(field):
        if field in attrs:
            return attrs[field]
        return getattr(instance, field, None) if instance is not None else None

    nivel = _get("nivel")
    cliente = _get("cliente")
    programa = _get("programa")
    projeto = _get("projeto")

    owners = {
        NivelTemplate.CLIENTE: cliente,
        NivelTemplate.PROGRAMA: programa,
        NivelTemplate.PROJETO: projeto,
    }

    if sum(1 for owner in owners.values() if owner is not None) != 1:
        raise serializers.ValidationError(
            "Informe exatamente um dos campos: cliente, programa ou projeto."
        )

    if owners.get(nivel) is None:
        raise serializers.ValidationError(
            "O campo informado (cliente/programa/projeto) não corresponde ao nivel."
        )


class AssetUsoSerializer(serializers.ModelSerializer):
    entidade_nome = serializers.SerializerMethodField()

    class Meta:
        model = AssetUso
        fields = [
            "id",
            "asset",
            "tipo_uso",
            "cliente",
            "programa",
            "projeto",
            "campo_valor",
            "data_criacao",
            "entidade_nome",
        ]

    def get_entidade_nome(self, obj) -> str:
        if obj.cliente:
            return f"Cliente: {obj.cliente.nome}"
        if obj.programa:
            return f"Programa: {obj.programa.nome}"
        if obj.projeto:
            return f"Projeto: {obj.projeto.nome}"
        if obj.campo_valor:
            return f"Variável: {obj.campo_valor.definicao.referencia}"
        return ""


class AssetSerializer(serializers.ModelSerializer):
    usos = AssetUsoSerializer(many=True, read_only=True)

    class Meta:
        model = Asset
        fields = "__all__"


class AssetCreateRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    caminho_arquivo = serializers.CharField(required=True, write_only=True)
    descricao = serializers.CharField(max_length=255, required=False, allow_blank=True)
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True
    )
    programa = serializers.PrimaryKeyRelatedField(
        queryset=Programa.objects.all(), required=False, allow_null=True
    )
    projeto = serializers.PrimaryKeyRelatedField(
        queryset=Projeto.objects.all(), required=False, allow_null=True
    )

    def validate(self, attrs):
        scopes = [attrs.get("cliente"), attrs.get("programa"), attrs.get("projeto")]
        filled = [s for s in scopes if s is not None]
        if len(filled) != 1:
            raise serializers.ValidationError(
                "Informe exatamente um escopo (cliente, programa ou projeto)."
            )
        if not attrs.get("caminho_arquivo"):
            raise serializers.ValidationError(
                "O caminho_arquivo gerado via URL preassinada é obrigatório."
            )
        return attrs

    def create(self, validated_data):
        caminho = validated_data.pop("caminho_arquivo")
        asset = Asset.objects.create(**validated_data)
        asset.arquivo.name = caminho
        asset.save()
        return asset


class ProgramaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Programa
        fields = "__all__"


class EquipeProgramaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipePrograma
        fields = "__all__"


class ProjetoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Projeto
        fields = "__all__"


class EquipeProjetoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipeProjeto
        fields = "__all__"


class ClasseEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClasseEvento
        fields = "__all__"
        extra_kwargs = {
            "cliente": {"required": False, "allow_null": True},
            "programa": {"required": False, "allow_null": True},
            "projeto": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        cliente = (
            attrs.get("cliente")
            if "cliente" in attrs
            else getattr(self.instance, "cliente", None)
        )
        programa = (
            attrs.get("programa")
            if "programa" in attrs
            else getattr(self.instance, "programa", None)
        )
        projeto = (
            attrs.get("projeto")
            if "projeto" in attrs
            else getattr(self.instance, "projeto", None)
        )
        scopes = [cliente, programa, projeto]
        filled = [s for s in scopes if s is not None]
        if len(filled) != 1:
            raise serializers.ValidationError(
                "Informe exatamente um escopo (cliente, programa ou projeto)."
            )
        return attrs


class EventoSerializer(serializers.ModelSerializer):
    classe_evento_nome = serializers.ReadOnlyField(source="classe_evento.nome_classe")

    class Meta:
        model = Evento
        fields = "__all__"
        extra_kwargs = {
            "cliente": {"required": False, "allow_null": True},
            "programa": {"required": False, "allow_null": True},
            "projeto": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        cliente = (
            attrs.get("cliente")
            if "cliente" in attrs
            else getattr(self.instance, "cliente", None)
        )
        programa = (
            attrs.get("programa")
            if "programa" in attrs
            else getattr(self.instance, "programa", None)
        )
        projeto = (
            attrs.get("projeto")
            if "projeto" in attrs
            else getattr(self.instance, "projeto", None)
        )
        scopes = [cliente, programa, projeto]
        filled = [s for s in scopes if s is not None]
        if len(filled) != 1:
            raise serializers.ValidationError(
                "Informe exatamente um escopo (cliente, programa ou projeto)."
            )
        return attrs


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = [
            "id",
            "nome",
            "nivel",
            "cliente",
            "programa",
            "projeto",
            "ultima_atualizacao",
            "data_criacao",
            "modelo_json",
        ]
        extra_kwargs = {
            "cliente": {"required": False, "allow_null": True},
            "programa": {"required": False, "allow_null": True},
            "projeto": {"required": False, "allow_null": True},
        }

    def validate_modelo_json(self, value):
        return validate_prosemirror_doc(value)

    def validate(self, attrs):
        _validate_owner_matches_nivel(attrs, instance=self.instance)
        return attrs


class TemplateCreateRequestSerializer(serializers.Serializer):
    """Serializer de request para criar um template."""

    nome = serializers.CharField(max_length=150)
    nivel = serializers.ChoiceField(choices=NivelTemplate.choices)
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True
    )
    programa = serializers.PrimaryKeyRelatedField(
        queryset=Programa.objects.all(), required=False, allow_null=True
    )
    projeto = serializers.PrimaryKeyRelatedField(
        queryset=Projeto.objects.all(), required=False, allow_null=True
    )
    modelo_json = serializers.JSONField()

    def validate_modelo_json(self, value):
        return validate_prosemirror_doc(value)

    def validate(self, attrs):
        _validate_owner_matches_nivel(attrs)
        return attrs


class CampoDefinicaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampoDefinicao
        fields = [
            "id",
            "cliente",
            "programa",
            "projeto",
            "nivel_aplicacao",
            "referencia",
            "descricao",
            "tipo",
            "obrigatorio",
            "data_criacao",
            "ultima_atualizacao",
        ]
        read_only_fields = ["data_criacao", "ultima_atualizacao"]

    def validate(self, attrs):
        instance = CampoDefinicao(
            **{
                **{
                    "cliente": getattr(self.instance, "cliente", None),
                    "programa": getattr(self.instance, "programa", None),
                    "projeto": getattr(self.instance, "projeto", None),
                    "nivel_aplicacao": getattr(self.instance, "nivel_aplicacao", None),
                    "referencia": getattr(self.instance, "referencia", None),
                },
                **attrs,
            }
        )
        instance.full_clean(exclude=["id", "escopo_key"])
        return attrs


class CampoValorSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampoValor
        fields = [
            "id",
            "definicao",
            "cliente",
            "programa",
            "projeto",
            "evento",
            "valor",
            "data_criacao",
            "ultima_atualizacao",
        ]
        read_only_fields = ["data_criacao", "ultima_atualizacao"]

    def validate(self, attrs):
        instance = CampoValor(
            **{
                **{
                    "definicao": getattr(self.instance, "definicao", None),
                    "cliente": getattr(self.instance, "cliente", None),
                    "programa": getattr(self.instance, "programa", None),
                    "projeto": getattr(self.instance, "projeto", None),
                    "evento": getattr(self.instance, "evento", None),
                },
                **attrs,
            }
        )
        instance.full_clean(exclude=["id", "alvo_key"])
        return attrs


class TaskAcceptedSerializer(serializers.Serializer):
    """Serializer para respostas 202 de operações enfileiradas."""

    detail = serializers.CharField()
    task_id = serializers.UUIDField()
    task_status = serializers.CharField()


class TaskStatusSerializer(serializers.Serializer):
    """Serializer para respostas do endpoint de consulta de status de task."""

    task_id = serializers.UUIDField()
    task_status = serializers.CharField()
    result = serializers.JSONField(
        required=False,
        help_text="Presente quando task_status='SUCCESS'.",
    )
    error = serializers.CharField(
        required=False,
        help_text="Presente quando task_status='FAILURE'.",
    )


class AssinaturaTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssinaturaTemplate
        fields = "__all__"

    def validate(self, attrs):
        equipe_programa = attrs.get(
            "equipe_programa",
            getattr(self.instance, "equipe_programa", None),
        )
        equipe_projeto = attrs.get(
            "equipe_projeto",
            getattr(self.instance, "equipe_projeto", None),
        )

        if bool(equipe_programa) == bool(equipe_projeto):
            raise serializers.ValidationError(
                "Informe exatamente um dos campos: equipe_programa ou equipe_projeto."
            )

        return attrs


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = "__all__"

    def validate(self, attrs):
        request = self.context.get("request")
        if self.instance and request and hasattr(request, "user"):
            if not is_platform_admin(request.user):
                if (
                    "numero_contrato" in attrs
                    and attrs["numero_contrato"] != self.instance.numero_contrato
                ):
                    raise serializers.ValidationError(
                        {
                            "numero_contrato": "Apenas Administradores do GeRelat podem alterar o número do contrato."
                        }
                    )
                if (
                    "data_termino_contrato" in attrs
                    and attrs["data_termino_contrato"]
                    != self.instance.data_termino_contrato
                ):
                    raise serializers.ValidationError(
                        {
                            "data_termino_contrato": "Apenas Administradores do GeRelat podem alterar o término do contrato."
                        }
                    )
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            if not is_cliente_admin(request.user, instance):
                data.pop("numero_contrato", None)
                data.pop("data_termino_contrato", None)
        return data


class TemplateClasseEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateClasseEvento
        fields = "__all__"

    def validate(self, attrs):
        template = attrs.get("template") or (
            self.instance.template if self.instance else None
        )
        classe_evento = attrs.get("classe_evento") or (
            self.instance.classe_evento if self.instance else None
        )
        if template and classe_evento:
            validar_classe_evento_mesmo_escopo(template, classe_evento)
        return attrs


class RelatorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relatorio
        fields = "__all__"


class AgendamentoRelatorioSerializer(serializers.ModelSerializer):
    template_nome = serializers.CharField(source="template.nome", read_only=True)
    criado_por_nome = serializers.CharField(
        source="criado_por.get_full_name", read_only=True
    )
    cliente_nome = serializers.CharField(
        source="cliente.nome", read_only=True, default=""
    )
    programa_nome = serializers.CharField(
        source="programa.nome", read_only=True, default=""
    )
    projeto_nome = serializers.CharField(
        source="projeto.nome", read_only=True, default=""
    )

    class Meta:
        model = AgendamentoRelatorio
        fields = [
            "id",
            "nome",
            "template",
            "template_nome",
            "cliente",
            "cliente_nome",
            "programa",
            "programa_nome",
            "projeto",
            "projeto_nome",
            "evento",
            "criado_por",
            "criado_por_nome",
            "documento_json",
            "tipo_agendamento",
            "data_hora_execucao",
            "recorrencia",
            "horario_execucao",
            "dia_semana",
            "dia_mes",
            "ativo",
            "data_criacao",
            "ultima_atualizacao",
            "ultima_execucao",
            "proxima_execucao",
        ]
        read_only_fields = [
            "id",
            "criado_por",
            "data_criacao",
            "ultima_atualizacao",
            "ultima_execucao",
            "proxima_execucao",
        ]

    def validate(self, attrs):
        template = attrs.get(
            "template", self.instance.template if self.instance else None
        )
        if template:
            # Verifica apenas o campo de escopo relevante para o template.
            # Campos de escopo que o template não usa (None) são ignorados no
            # payload — o frontend pode enviá-los como conveniência sem causar erro.
            if template.cliente is not None:
                if "cliente" in attrs and attrs["cliente"] != template.cliente:
                    raise serializers.ValidationError(
                        {
                            "cliente": "O cliente informado não coincide com o escopo do Template."
                        }
                    )
            if template.programa is not None:
                if "programa" in attrs and attrs["programa"] != template.programa:
                    raise serializers.ValidationError(
                        {
                            "programa": "O programa informado não coincide com o escopo do Template."
                        }
                    )
            if template.projeto is not None:
                if "projeto" in attrs and attrs["projeto"] != template.projeto:
                    raise serializers.ValidationError(
                        {
                            "projeto": "O projeto informado não coincide com o escopo do Template."
                        }
                    )

            # O escopo do agendamento é sempre derivado do template.
            attrs["cliente"] = template.cliente
            attrs["programa"] = template.programa
            attrs["projeto"] = template.projeto

        cliente = attrs.get("cliente", self.instance.cliente if self.instance else None)
        programa = attrs.get(
            "programa", self.instance.programa if self.instance else None
        )
        projeto = attrs.get("projeto", self.instance.projeto if self.instance else None)

        scopes = [s for s in (cliente, programa, projeto) if s is not None]
        if len(scopes) != 1:
            raise serializers.ValidationError(
                "Informe exatamente um escopo (cliente, programa ou projeto)."
            )

        evento = attrs.get("evento", self.instance.evento if self.instance else None)
        if evento and template:
            evento_scope = (evento.cliente_id, evento.programa_id, evento.projeto_id)
            template_scope = (
                template.cliente_id,
                template.programa_id,
                template.projeto_id,
            )
            if evento_scope != template_scope:
                if self.instance and "template" in attrs and "evento" not in attrs:
                    attrs["evento"] = None
                else:
                    raise serializers.ValidationError(
                        {
                            "evento": "O Evento do agendamento deve pertencer ao mesmo escopo do Template."
                        }
                    )

        tipo = attrs.get(
            "tipo_agendamento",
            self.instance.tipo_agendamento
            if self.instance
            else AgendamentoRelatorio.TIPO_PONTUAL,
        )
        if tipo == AgendamentoRelatorio.TIPO_PONTUAL:
            data_hora = attrs.get(
                "data_hora_execucao",
                self.instance.data_hora_execucao if self.instance else None,
            )
            if not data_hora:
                raise serializers.ValidationError(
                    {
                        "data_hora_execucao": (
                            "Data e hora de execução são obrigatórias para agendamentos"
                            " pontuais."
                        )
                    }
                )
            ativo = attrs.get("ativo", self.instance.ativo if self.instance else True)
            if ativo and data_hora and data_hora < timezone.now():
                raise serializers.ValidationError(
                    {
                        "ativo": (
                            "Não é possível ativar um agendamento pontual cuja data e hora de execução já passaram. Escolha uma nova data e hora."
                        )
                    }
                )
        elif tipo == AgendamentoRelatorio.TIPO_RECORRENTE:
            recorrencia = attrs.get(
                "recorrencia", self.instance.recorrencia if self.instance else None
            )
            if not recorrencia:
                raise serializers.ValidationError(
                    {
                        "recorrencia": (
                            "Frequência de recorrência é obrigatória para agendamentos"
                            " recorrentes."
                        )
                    }
                )
            horario = attrs.get(
                "horario_execucao",
                self.instance.horario_execucao if self.instance else None,
            )
            if not horario:
                raise serializers.ValidationError(
                    {
                        "horario_execucao": (
                            "Horário de execução é obrigatório para agendamentos"
                            " recorrentes."
                        )
                    }
                )

            if recorrencia == AgendamentoRelatorio.RECORRENCIA_SEMANAL:
                dia_semana = attrs.get(
                    "dia_semana",
                    self.instance.dia_semana if self.instance else None,
                )
                if dia_semana is None:
                    raise serializers.ValidationError(
                        {
                            "dia_semana": (
                                "Dia da semana (1-7) é obrigatório para recorrência semanal."
                            )
                        }
                    )
                if not (1 <= dia_semana <= 7):
                    raise serializers.ValidationError(
                        {
                            "dia_semana": (
                                "Dia da semana deve ser um valor entre 1 (Segunda) e 7 (Domingo)."
                            )
                        }
                    )

            if recorrencia == AgendamentoRelatorio.RECORRENCIA_MENSAL:
                dia_mes = attrs.get(
                    "dia_mes",
                    self.instance.dia_mes if self.instance else None,
                )
                if dia_mes is None:
                    raise serializers.ValidationError(
                        {
                            "dia_mes": (
                                "Dia do mês (1-31) é obrigatório para recorrência mensal."
                            )
                        }
                    )
                if not (1 <= dia_mes <= 31):
                    raise serializers.ValidationError(
                        {"dia_mes": ("Dia do mês deve ser um valor entre 1 e 31.")}
                    )
        return attrs


# Serializers de Autorização


class MembroGeRelatSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_nome = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = MembroGeRelat
        fields = ["id", "user", "user_email", "user_nome"]
        read_only_fields = ["id"]


class MembroClienteSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_nome = serializers.CharField(source="user.full_name", read_only=True)
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    promovido_por_email = serializers.EmailField(
        source="promovido_por.email", read_only=True, allow_null=True
    )
    promovido_por_nome = serializers.CharField(
        source="promovido_por.full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = MembroCliente
        fields = [
            "id",
            "user",
            "user_email",
            "user_nome",
            "cliente",
            "cliente_nome",
            "data_promocao",
            "promovido_por",
            "promovido_por_email",
            "promovido_por_nome",
        ]
        read_only_fields = ["id", "data_promocao"]


class SolicitacaoClienteSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_nome = serializers.CharField(source="user.full_name", read_only=True)
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    # Alias para compatibilidade com o frontend (que usa `created_at`)
    created_at = serializers.DateTimeField(source="data_solicitacao", read_only=True)

    class Meta:
        model = SolicitacaoCliente
        fields = [
            "id",
            "user",
            "user_email",
            "user_nome",
            "cliente",
            "cliente_nome",
            "status",
            "data_solicitacao",
            "created_at",
        ]
        read_only_fields = ["id", "user", "data_solicitacao", "created_at", "status"]


class MembroProgramaSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_nome = serializers.CharField(source="user.full_name", read_only=True)
    programa_nome = serializers.CharField(source="programa.nome", read_only=True)
    cliente_id = serializers.IntegerField(
        source="programa.cliente_id", read_only=True, allow_null=True
    )
    cliente_nome = serializers.CharField(
        source="programa.cliente.nome", read_only=True, allow_null=True
    )

    class Meta:
        model = MembroPrograma
        fields = [
            "id",
            "user",
            "user_email",
            "user_nome",
            "programa",
            "programa_nome",
            "cliente_id",
            "cliente_nome",
            "data_criacao",
        ]
        read_only_fields = ["id", "data_criacao"]


class MembroProjetoSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_nome = serializers.CharField(source="user.full_name", read_only=True)
    projeto_nome = serializers.CharField(source="projeto.nome", read_only=True)
    programa_id = serializers.IntegerField(source="projeto.programa_id", read_only=True)
    programa_nome = serializers.CharField(
        source="projeto.programa.nome", read_only=True
    )
    cliente_id = serializers.IntegerField(
        source="projeto.programa.cliente_id", read_only=True, allow_null=True
    )
    cliente_nome = serializers.CharField(
        source="projeto.programa.cliente.nome", read_only=True, allow_null=True
    )

    class Meta:
        model = MembroProjeto
        fields = [
            "id",
            "user",
            "user_email",
            "user_nome",
            "projeto",
            "projeto_nome",
            "programa_id",
            "programa_nome",
            "cliente_id",
            "cliente_nome",
            "data_criacao",
        ]
        read_only_fields = ["id", "data_criacao"]


class RelatorioGenerateRequestSerializer(serializers.Serializer):
    nome = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        help_text="Nome opcional para o relatório (substitui o nome do template)",
    )
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID do cliente (opcional, necessário se o template usar gaps de nível cliente)",
    )
    programa = serializers.PrimaryKeyRelatedField(
        queryset=Programa.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID do programa (opcional, necessário se o template usar gaps de nível programa)",
    )
    projeto = serializers.PrimaryKeyRelatedField(
        queryset=Projeto.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID do projeto (opcional, necessário se o template usar gaps de nível projeto)",
    )
    evento = serializers.PrimaryKeyRelatedField(
        queryset=Evento.objects.all(),
        required=False,
        allow_null=True,
        help_text="ID do evento (opcional, necessário se o template usar gaps de nível evento)",
    )
    template = serializers.PrimaryKeyRelatedField(
        queryset=Template.objects.all(),
        required=True,
        help_text="ID do template (obrigatório)",
    )
    documento_json = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Documento ProseMirror já resolvido e editado pelo usuário (opcional)",
    )

    def validate(self, attrs):
        template = attrs["template"]
        cliente = attrs.get("cliente")
        programa = attrs.get("programa")
        projeto = attrs.get("projeto")
        evento = attrs.get("evento")

        # Resolve a cadeia completa a partir do elo mais profundo informado,
        # validando consistência com qualquer elo mais raso já informado.
        if evento:
            if (
                not eventos_disponiveis_para_relatorio(template)
                .filter(id=evento.id)
                .exists()
            ):
                raise serializers.ValidationError(
                    "O evento selecionado não é elegível para este template (escopo ou classe de evento incompatível)."
                )
            if evento.projeto_id:
                if projeto and projeto.id != evento.projeto_id:
                    raise serializers.ValidationError(
                        "O evento informado não pertence ao projeto informado."
                    )
                projeto = projeto or evento.projeto
            elif evento.programa_id:
                if programa and programa.id != evento.programa_id:
                    raise serializers.ValidationError(
                        "O evento informado não pertence ao programa informado."
                    )
                programa = programa or evento.programa
            elif evento.cliente_id:
                if cliente and cliente.id != evento.cliente_id:
                    raise serializers.ValidationError(
                        "O evento informado não pertence ao cliente informado."
                    )
                cliente = cliente or evento.cliente

        if projeto:
            if programa and programa.id != projeto.programa_id:
                raise serializers.ValidationError(
                    "O projeto informado não pertence ao programa informado."
                )
            programa = programa or projeto.programa

        if programa:
            if (
                cliente
                and programa.cliente_id is not None
                and cliente.id != programa.cliente_id
            ):
                raise serializers.ValidationError(
                    "O programa informado não pertence ao cliente informado."
                )
            cliente = cliente or programa.cliente

        documento_json = attrs.get("documento_json")
        if documento_json is not None and (
            not isinstance(documento_json, dict) or documento_json.get("type") != "doc"
        ):
            raise serializers.ValidationError(
                "documento_json deve ser um documento ProseMirror válido."
            )

        required_nivel = scan_required_nivel(
            documento_json or template.modelo_json,
            cliente=cliente,
            programa=programa,
            projeto=projeto,
        )
        resolved = {
            "cliente": cliente,
            "programa": programa,
            "projeto": projeto,
            "evento": evento,
        }
        if required_nivel is not None and resolved.get(required_nivel) is None:
            raise serializers.ValidationError(
                f"Este template exige informar {required_nivel} para gerar o relatório."
            )

        attrs["cliente"] = cliente
        attrs["programa"] = programa
        attrs["projeto"] = projeto
        attrs["evento"] = evento
        return attrs
