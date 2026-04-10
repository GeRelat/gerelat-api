from docxtpl import DocxTemplate


def task_relatorio_exemplo(data):
    doc = DocxTemplate(data["template_path"])

    context = {
        "empresa": "BRISA",
        "parceira": "FURG",
        "assunto": "Acompanhamento da execução do Projeto",
        "data": "13/03/2026",
        "horario": "16h - 17h",
        "coord_local": {"nome": "João Silva", "funcao": "Coordenador Local Geral"},
    }
    doc.render(context)
    doc.save(data["output_path"])
