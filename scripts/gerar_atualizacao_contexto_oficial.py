from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE
import matplotlib.pyplot as plt

OUT = Path('/home/ubuntu/palaciomental-current/docs')
OUT.mkdir(exist_ok=True)
chart = OUT / 'grafico-sustentabilidade-pm.png'
docx_path = OUT / 'contexto-mestre-oficial-atualizacao-plano-sustentabilidade.docx'

PURPLE = '321943'
GREEN = '1FAE6D'
BEIGE = 'F7F4EE'
LIGHT_PURPLE = 'EEE8F1'
GRAY = '5B5660'

# Gráfico qualitativo: não representa orçamento ou dados medidos.
labels = ['Infraestrutura', 'Suporte', 'Implantação', 'Desenvolvimento\ne segurança', 'Armazenamento\ne tráfego']
values = [30, 25, 20, 15, 10]
plt.figure(figsize=(8.5, 4.2), facecolor='#F7F4EE')
ax = plt.axes(facecolor='#F7F4EE')
bars = ax.barh(labels[::-1], values[::-1], color=['#A8DCC3','#75C89D','#1FAE6D','#69447A','#321943'])
ax.set_xlim(0, 35)
ax.set_xlabel('Peso qualitativo para planejamento — não é orçamento', color='#321943', fontsize=9)
ax.set_title('Mapa qualitativo das pressões de custo', color='#321943', fontsize=13, weight='bold', pad=12)
ax.grid(axis='x', alpha=0.18, color='#321943')
ax.set_axisbelow(True)
for b, v in zip(bars, values[::-1]):
    ax.text(v + 0.7, b.get_y() + b.get_height()/2, f'{v}', va='center', color='#321943', fontsize=9)
for spine in ax.spines.values(): spine.set_visible(False)
ax.tick_params(axis='both', length=0, colors='#321943', labelsize=9)
plt.tight_layout()
plt.savefig(chart, dpi=220, bbox_inches='tight', facecolor='#F7F4EE')
plt.close()


def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn('w:shd'))
    if shd is None:
        shd = OxmlElement('w:shd')
        tcPr.append(shd)
    shd.set(qn('w:fill'), fill)


def set_cell_border(cell, **kwargs):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.first_child_found_in('w:tcBorders')
    if tcBorders is None:
        tcBorders = OxmlElement('w:tcBorders')
        tcPr.append(tcBorders)
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        if edge in kwargs:
            tag = 'w:{}'.format(edge)
            element = tcBorders.find(qn(tag))
            if element is None:
                element = OxmlElement(tag)
                tcBorders.append(element)
            for key in ['val', 'sz', 'space', 'color']:
                if key in kwargs[edge]: element.set(qn('w:'+key), str(kwargs[edge][key]))


def set_cell_margins(cell, top=90, start=100, bottom=90, end=100):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = tcPr.first_child_found_in('w:tcMar')
    if tcMar is None:
        tcMar = OxmlElement('w:tcMar')
        tcPr.append(tcMar)
    for m, v in [('top', top), ('start', start), ('bottom', bottom), ('end', end)]:
        node = tcMar.find(qn('w:'+m))
        if node is None:
            node = OxmlElement('w:'+m); tcMar.append(node)
        node.set(qn('w:w'), str(v)); node.set(qn('w:type'), 'dxa')


def style_run(run, size=11, bold=False, color='000000', italic=False):
    run.font.name = 'Arial'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), 'Arial')
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)


def add_para(doc, text='', bold_prefix=None, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=6):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(space_after)
    if bold_prefix and text.startswith(bold_prefix):
        style_run(p.add_run(bold_prefix), bold=True, color=PURPLE)
        style_run(p.add_run(text[len(bold_prefix):]))
    else:
        style_run(p.add_run(text))
    return p


def add_bullet(doc, text):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.left_indent = Inches(0.35)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(2)
    style_run(p.add_run(text))
    return p


def add_heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(14 if level == 1 else 9)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    r = p.add_run(text)
    style_run(r, size=14 if level == 1 else 12, bold=True, color=PURPLE)
    return p


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        set_cell_shading(hdr[i], PURPLE)
        set_cell_margins(hdr[i])
        hdr[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = hdr[i].paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.0
        style_run(p.add_run(h), size=9, bold=True, color='FFFFFF')
    for ridx, row in enumerate(rows):
        cells = table.add_row().cells
        for i, val in enumerate(row):
            set_cell_shading(cells[i], BEIGE if ridx % 2 == 0 else 'FFFFFF')
            set_cell_margins(cells[i])
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cells[i].paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.0
            style_run(p.add_run(str(val)), size=9, color='000000')
    for row in table.rows:
        for cell in row.cells:
            set_cell_border(cell, top={'val':'single','sz':4,'color':'D6CBDC'}, bottom={'val':'single','sz':4,'color':'D6CBDC'}, left={'val':'single','sz':4,'color':'D6CBDC'}, right={'val':'single','sz':4,'color':'D6CBDC'})
    if widths:
        for row in table.rows:
            for i, width in enumerate(widths): row.cells[i].width = Inches(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    style_run(p.add_run(text), size=9, italic=True, color=GRAY)


doc = Document()
sec = doc.sections[0]
sec.page_width = Inches(8.27); sec.page_height = Inches(11.69)
sec.top_margin = Inches(1.18); sec.bottom_margin = Inches(0.79)
sec.left_margin = Inches(1.18); sec.right_margin = Inches(0.79)

styles = doc.styles
normal = styles['Normal']
normal.font.name = 'Arial'; normal._element.rPr.rFonts.set(qn('w:eastAsia'), 'Arial'); normal.font.size = Pt(11)
normal.paragraph_format.line_spacing = 1.5
for name in ['Heading 1','Heading 2']:
    styles[name].font.name = 'Arial'; styles[name]._element.rPr.rFonts.set(qn('w:eastAsia'), 'Arial')

# Capa
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before = Pt(80)
style_run(p.add_run('PALÁCIO MENTAL'), size=20, bold=True, color=PURPLE)
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(p.add_run('ATUALIZAÇÃO ESTRATÉGICA DO CONTEXTO MESTRE'), size=14, bold=True, color=GREEN)
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before = Pt(28)
style_run(p.add_run('Arquitetura de planos, sustentabilidade e ecossistema'), size=12, color=PURPLE)
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before = Pt(120)
style_run(p.add_run('Documento de apoio para revisão da equipe'), size=11, color=GRAY)
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(p.add_run('Outubro de 2026'), size=11, color=GRAY)
doc.add_page_break()

add_heading(doc, '1. Finalidade e status', 1)
add_para(doc, 'Este documento resume as atualizações recentes do Palácio Mental a partir do Contexto Mestre oficial. Ele não substitui nem altera o documento oficial; serve como material de revisão para que pessoas técnicas e não técnicas entendam as decisões de produto, negócio e arquitetura.')
add_para(doc, 'As definições abaixo combinam decisões já estruturadas com hipóteses que ainda precisam ser validadas por uso real, pilotos, entrevistas e acompanhamento de custos.', bold_prefix='As definições abaixo')

add_heading(doc, '2. Síntese do produto', 1)
add_para(doc, 'O Palácio Mental é uma plataforma para transformar ideias em projetos compreensíveis e persistentes. Ela preserva contexto, autoria e evolução para que as criações possam ser descobertas, apresentadas, reutilizadas ou continuadas.')
add_para(doc, 'A plataforma possui dois caminhos complementares: projetos autorais de pessoas e ambientes institucionais para organizações. O núcleo de valor é o mesmo; mudam o contexto de acesso, a governança e a responsabilidade sobre os projetos.')

add_heading(doc, '3. Ambiente institucional', 1)
add_para(doc, 'O ambiente institucional é um espaço próprio de uma ONG, escola, faculdade, empresa, programa ou laboratório. No caso inicial, o CAMPPG terá uma vitrine própria, projetos, membros, programas, grupos e permissões. Seus projetos não são misturados automaticamente à vitrine global.')
add_para(doc, 'A arquitetura será multi-tenant com banco compartilhado e isolamento por linhas. O subdomínio identifica o ambiente, por exemplo, camppg.palaciomental.com.br. O PostgreSQL mantém os dados oficiais; Redis acelera cache, sessões, rankings derivados e eventos transitórios.')

add_heading(doc, '4. Arquitetura de planos', 1)
add_para(doc, 'Os planos devem ampliar profundidade, potência, volume, governança e suporte — não comprar relevância artificial. O valor essencial de criar, contextualizar e descobrir projetos precisa permanecer acessível. Os números abaixo são limites iniciais para teste, não promessa comercial definitiva; devem ser ajustados com telemetria de uso e custo real.')
add_table(doc, ['Plano', 'Potência: o que pode fazer', 'Volume inicial proposto', 'Regra de justiça'], [
    ['Free', 'Criar, contextualizar, explorar, publicar conforme a visibilidade e usar links manuais. Sem automações avançadas.', 'Até 20 projetos pessoais, 10 ativos e até 12 links por projeto.', 'Sem bloqueio do valor central; limite protege operação.'],
    ['Pro', 'Tudo do Free, mais coleções, organização avançada, integrações e automações pessoais.', 'Até 100 projetos pessoais, 50 ativos e maior volume de coleções.', 'Mais potência e conveniência, nunca votos ou posição artificial no ranking.'],
    ['Institucional', 'Ambiente próprio, membros, programas, grupos, permissões, vitrine, relatórios e governança.', 'Piloto CAMPPG: até 100 usuários, 10 programas e 30 grupos; revisar após 8 semanas.', 'Limites por escala e governança, não por acesso ao projeto básico.'],
    ['ONG subsidiada', 'Base Institucional, com recursos compatíveis com a capacidade de suporte da equipe.', 'Mesmo limite operacional do piloto ou menor; sem expansão automática ilimitada.', 'Concessão condicionada a critérios, consentimento e revisão periódica.'],
], widths=[0.95,2.35,2.05,1.45])
add_para(doc, 'A assinatura individual pertence ao usuário e controla recursos pessoais. A assinatura institucional pertence à organização e controla recursos coletivos. Essa separação preserva a autonomia dos projetos autorais e evita que uma conta individual controle todo o ambiente institucional.')
add_heading(doc, '4.1 Regras de potência e volume', 2)
add_table(doc, ['Dimensão', 'Regra', 'Como medir'], [
    ['Potência', 'Diferencia recursos que aumentam capacidade: automações, integrações, coleções, relatórios e governança.', 'Recurso habilitado, frequência de uso e valor percebido; não usar ranking como benefício pago.'],
    ['Volume', 'Diferencia quantidade: projetos, usuários, programas, grupos, armazenamento, chamadas e execuções.', 'Contagem mensal e pico de uso por conta ou organização.'],
    ['Vitrine', 'Projetos públicos devem obedecer à mesma lógica de relevância, independentemente do plano.', 'Distribuição de alcance e cliques por plano; investigar qualquer viés.'],
    ['Proteção operacional', 'Limites devem evitar abuso e custo imprevisível, com aviso antes do bloqueio.', 'Incidentes, custo por tenant, taxa de usuários atingindo o limite.'],
], widths=[1.1,3.4,2.3])
add_para(doc, 'Quando um limite for atingido, o produto deve explicar o motivo, mostrar o consumo e oferecer uma alternativa proporcional: arquivar, reduzir volume, aguardar a renovação ou migrar de plano. O usuário nunca deve perder dados por atingir um limite. Recursos essenciais devem ter exportação e comunicação clara.')

add_heading(doc, '5. Ecossistema', 1)
add_table(doc, ['Camada', 'O que é', 'Situação'], [
    ['PM Plataforma', 'Projetos, contexto, autoria, descoberta e continuidade.', 'Núcleo atual e prioridade do MVP.'],
    ['Ambiente institucional', 'Multi-tenant, membros, permissões, programas, grupos e vitrine própria.', 'Próxima evolução em desenvolvimento.'],
    ['PM Flow', 'Fluxos, tarefas e acompanhamento operacional.', 'Hipótese futura; não bloqueia o MVP.'],
    ['PM VCS', 'Versões, histórico e evolução avançada dos projetos.', 'Hipótese futura; validar antes de ampliar.'],
], widths=[1.45,3.35,2.0])
add_para(doc, 'PM Flow e PM VCS devem ser tratados como módulos ou produtos futuros do ecossistema, não como dependências obrigatórias do MVP institucional. O núcleo compartilhado deve ser capaz de atender diferentes organizações por configuração, sem criar um produto exclusivo para cada cliente.')

add_heading(doc, '6. Sustentabilidade', 1)
add_para(doc, 'A sustentabilidade financeira ainda é uma hipótese, mas já pode ser organizada por economia unitária. O objetivo é crescer conforme o uso real, preservar o acesso essencial e evitar custos ou customizações antes de comprovar valor. A equipe deve separar custo de caixa, custo econômico do trabalho da equipe e custo marginal de cada organização.')
add_heading(doc, '6.1 Custos fixos e variáveis', 2)
add_table(doc, ['Tipo', 'Composição atual', 'Premissa de planejamento'], [
    ['Fixos de infraestrutura', 'Railway, domínio principal, monitoramento mínimo e ferramentas essenciais.', 'Railway Pro custa US$ 20/mês e inclui US$ 20 de uso; o plano Hobby custa US$ 5/mês e inclui US$ 5 de uso. [1]'],
    ['Domínio e DNS', 'Domínio palaciomental.com.br e gestão de DNS/subdomínios.', 'Registro.br informa R$ 40/ano para a maioria dos domínios .br; Cloudflare oferece DNS, SSL e CDN no plano gratuito. [2] [3]'],
    ['Variáveis de infraestrutura', 'CPU, memória, volume, egress e object storage.', 'Railway cobra por segundo; as referências atuais são US$ 20/GB de memória/mês, US$ 20/vCPU/mês, US$ 0,15/GB de volume, US$ 0,05/GB de egress e US$ 0,015/GB-mês de object storage. [1]'],
    ['Variáveis operacionais', 'Suporte, implantação, treinamento, moderação e atendimento.', 'Crescem com organizações e complexidade, não apenas com número de usuários.'],
    ['Custo econômico', 'Horas de desenvolvimento, design, segurança e gestão.', 'Mesmo quando não há salário ou pagamento imediato, registrar horas para conhecer o custo real.'],
], widths=[1.35,3.0,2.45])
add_para(doc, 'O plano Railway não é o custo total do produto. Banco PostgreSQL, Django e Redis consomem recursos dentro do ambiente e devem ser medidos pela fatura real. O valor de US$ 20/mês para Railway Pro é uma referência de plano, não uma garantia de que o uso mensal permanecerá nesse valor.')
add_heading(doc, '6.2 Quanto custa manter um usuário', 2)
add_para(doc, 'Não existe um custo fixo por cadastro. O indicador correto é o custo mensal por usuário ativo, calculado assim: custo variável mensal de infraestrutura dividido por usuários ativos no mês. Usuários cadastrados que nunca entram não devem ser tratados como usuários ativos para medir consumo.')
add_table(doc, ['Cenário de planejamento', 'Usuários ativos/mês', 'Organizações', 'Infraestrutura/mês', 'Infra por usuário', 'Infra por organização'], [
    ['Piloto CAMPPG', '50', '1', 'US$ 30', 'US$ 0,60', 'US$ 30,00'],
    ['Validação inicial', '150', '2', 'US$ 45', 'US$ 0,30', 'US$ 22,50'],
    ['Primeira escala', '500', '5', 'US$ 100', 'US$ 0,20', 'US$ 20,00'],
    ['Escala inicial', '2.000', '10', 'US$ 250', 'US$ 0,125', 'US$ 25,00'],
], widths=[1.35,1.05,0.9,1.15,1.2,1.35])
add_para(doc, 'Esses cenários são premissas de planejamento, não dados medidos nem orçamento aprovado. Eles mostram que o custo de infraestrutura por usuário tende a cair com escala, mas o custo por organização não desaparece: cada tenant pode gerar configuração, suporte, armazenamento, governança e atendimento próprios. O piloto deve substituir essas premissas por fatura, consumo e horas reais.')
add_heading(doc, '6.3 Custo por organização', 2)
add_para(doc, 'O custo mensal de uma organização deve ser calculado em três camadas: (1) infraestrutura incremental, (2) suporte e operação e (3) implantação amortizada. Uma organização pequena pode consumir pouca infraestrutura e ainda ser cara de atender se exigir muitas reuniões, treinamento ou customizações.')
add_table(doc, ['Componente', 'Cálculo recomendado', 'Decisão saudável'], [
    ['Infraestrutura incremental', 'Consumo adicional de CPU, memória, banco, armazenamento e tráfego.', 'Medir por tenant e separar do custo compartilhado.'],
    ['Suporte e operação', 'Horas mensais × custo-hora interno da equipe.', 'Definir nível de suporte incluído e cobrar atendimento especializado.'],
    ['Implantação', 'Horas iniciais de configuração e treinamento ÷ meses do contrato.', 'Evitar implantação gratuita sem limite ou prazo.'],
    ['Margem de segurança', 'Reserva para incidentes, crescimento e inadimplência.', 'Não comprometer toda a receita com custo direto.'],
], widths=[1.55,3.55,2.0])
add_para(doc, 'A fórmula de referência é: custo mensal por organização = infraestrutura incremental + suporte mensal + parcela de implantação + reserva operacional. O custo real só estará validado após o piloto CAMPPG registrar consumo, horas e incidentes durante pelo menos oito semanas.')

doc.add_picture(str(chart), width=Inches(6.35))
add_caption(doc, 'Figura 1 — Mapa qualitativo das pressões de custo. Os pesos são uma ferramenta de planejamento, não uma previsão financeira.')
add_para(doc, 'A personalização institucional deve ocorrer preferencialmente por configuração. Código exclusivo, integrações específicas e fluxos sob medida só devem ser aprovados quando houver valor comprovado, capacidade de suporte e margem suficiente.')
add_heading(doc, '6.4 Como a receita sustenta a plataforma', 2)
add_para(doc, 'A sustentabilidade dos planos depende de separar aquisição, monetização e impacto. A conta Free funciona como porta de entrada e mecanismo de validação. Ela não precisa gerar receita direta no início, desde que o custo variável por usuário permaneça controlado e que o uso gratuito gere projetos, aprendizagem e demanda para os planos pagos. O Free não deve oferecer volume ilimitado nem serviços que gerem custo imprevisível.')
add_para(doc, 'A conta Pro monetiza potência e volume individual. Ela pode incluir organização avançada, coleções, integrações e automações, mas não pode vender votos, posição na vitrine, relevância artificial ou exposição privilegiada. Sua margem deve contribuir para pagar parte dos custos fixos compartilhados e compensar usuários Free que não geram receita direta.')
add_para(doc, 'A conta Institucional é a principal unidade de receita recorrente. Ela deve financiar o custo incremental do tenant, a governança, o suporte incluído, a manutenção do ambiente e uma margem para evolução. O preço precisa considerar usuários, programas, grupos, armazenamento, nível de suporte e complexidade de implantação — não somente o número de contas cadastradas.')
add_para(doc, 'Implantação, treinamento e integrações podem gerar receita adicional, mas não devem esconder uma mensalidade insuficiente. Customizações só devem ser aceitas com escopo, prazo, preço, manutenção e responsável definidos. Uma organização que exige muitas horas de suporte não pode ser tratada financeiramente como um tenant de baixo contato.')
add_para(doc, 'Como regra interna de saúde financeira, cada plano pago deve cobrir seus custos variáveis diretamente atribuíveis e contribuir para os custos fixos. A equipe pode usar como alvo inicial uma margem bruta de planejamento de 60% ou mais após custos diretamente variáveis, mas esse percentual é uma premissa interna a validar, não uma garantia de mercado.')
add_table(doc, ['Fonte de receita', 'Função econômica', 'Limite estratégico'], [
    ['Free', 'Adquire usuários, gera aprendizado e forma demanda.', 'Limites de volume e sem custo operacional ilimitado.'],
    ['Pro', 'Monetiza potência e volume individual e ajuda a absorver custos fixos.', 'Não vender relevância, votos ou exposição.'],
    ['Institucional', 'Financia tenant, governança, escala, suporte e margem recorrente.', 'Preço deve refletir usuários, programas, suporte e complexidade.'],
    ['Implantação e treinamento', 'Recupera custo inicial de configuração e adoção.', 'Escopo fechado; não virar suporte ilimitado.'],
    ['Integrações e automações', 'Monetiza complexidade adicional quando comprovada.', 'Só desenvolver com demanda, preço e manutenção definidos.'],
    ['ONG subsidiada', 'Gera impacto, aprendizado e casos de uso.', 'Subsídio com critério, orçamento e revisão; não é ilimitado.'],
], widths=[1.4,3.35,2.35])
add_table(doc, ['Plano', 'O que precisa pagar', 'Condição de sustentabilidade'], [
    ['Free', 'Custo variável básico de uso.', 'Limitar volume, automações e armazenamento; monitorar custo por usuário ativo.'],
    ['Pro', 'Custo variável pessoal + parcela dos custos fixos.', 'Receita mensal superior ao custo incremental e contribuição positiva para a plataforma.'],
    ['Institucional', 'Tenant + suporte + governança + parcela de implantação.', 'Receita recorrente cobre custo direto e alcança a margem interna definida.'],
    ['ONG subsidiada', 'Custo autorizado pelo orçamento de impacto.', 'Número de organizações e horas de suporte limitados por capacidade real.'],
], widths=[1.1,3.15,2.85])
add_para(doc, 'A startup se torna financeiramente saudável quando o crescimento de receita recorrente é maior que o crescimento do custo de servir cada organização, quando a implantação deixa de consumir trabalho não remunerado e quando o núcleo compartilhado atende novos tenants sem reescritas exclusivas. Escala saudável não é apenas ter mais usuários; é aumentar uso e receita sem aumentar suporte na mesma proporção.')
add_heading(doc, '6.5 Custo de implantação e suporte por organização', 2)
add_para(doc, 'Implantação e suporte devem ser tratados como custos por organização, porque variam muito mais entre tenants do que entre usuários individuais. O cálculo deve registrar horas reais da equipe, consumo adicional de infraestrutura, reuniões, treinamento, configuração, incidentes e pedidos fora do escopo.')
add_table(doc, ['Etapa', 'Atividades incluídas', 'Premissa inicial do piloto'], [
    ['Descoberta e configuração', 'Reunião de contexto, cadastro do tenant, domínio, identidade visual e permissões iniciais.', 'Até 2 horas de equipe.'],
    ['Preparação do ambiente', 'Programas, grupos, usuários iniciais, visibilidade e testes de isolamento.', 'Até 2 horas de equipe.'],
    ['Treinamento e ativação', 'Orientação para gestão, professores/mentores e participantes-chave.', 'Até 1 hora de equipe.'],
    ['Acompanhamento inicial', 'Correções de adoção, dúvidas e ajustes de configuração após a ativação.', 'Até 2 horas por semana durante as duas primeiras semanas.'],
    ['Suporte recorrente incluído', 'Dúvidas operacionais, incidentes básicos e acompanhamento do uso.', 'Até 2 horas por semana no piloto; revisar com dados reais.'],
], widths=[1.45,3.45,2.2])
add_para(doc, 'A premissa inicial é de até cinco horas para configurar o primeiro ambiente e até quatro horas de suporte nas duas primeiras semanas, além de até duas horas semanais de suporte recorrente durante o piloto. Esses limites não são uma promessa comercial; são um teto para testar a capacidade da equipe e descobrir o esforço real.')
add_para(doc, 'O custo econômico de implantação deve ser calculado por: horas de implantação × custo-hora interno + consumo adicional de infraestrutura + despesas externas. O custo de suporte deve ser calculado por: horas mensais de suporte × custo-hora interno + serviços variáveis de atendimento. O custo-hora interno deve incluir remuneração, encargos quando aplicáveis e uma parcela de ferramentas e gestão.')
add_table(doc, ['Indicador por organização', 'Fórmula', 'Sinal saudável'], [
    ['Custo de implantação', 'Horas iniciais × custo-hora + despesas de configuração.', 'Recuperado por taxa de implantação ou contrato com permanência mínima.'],
    ['Custo mensal de suporte', 'Horas de suporte no mês × custo-hora + serviços variáveis.', 'Cresce mais lentamente que a receita recorrente.'],
    ['Custo direto do tenant', 'Infraestrutura incremental + suporte incluído + integrações.', 'Coberto pela mensalidade institucional.'],
    ['Margem bruta institucional', '(receita recorrente − custos diretos) ÷ receita recorrente.', 'Alvo interno inicial de 60% ou mais; validar com dados reais.'],
    ['Tempo de implantação', 'Horas entre aceite e ambiente pronto para uso.', 'Até 5 horas no piloto, sem código exclusivo.'],
], widths=[1.55,3.25,2.3])
add_para(doc, 'Se uma organização ultrapassar o suporte incluído, a equipe deve classificar o motivo: problema de produto, falha de documentação, necessidade de treinamento ou pedido específico. Problemas do produto não devem ser cobrados como customização. Treinamento adicional, integração e desenvolvimento específico precisam de escopo e aprovação próprios.')
add_para(doc, 'A implantação será considerada economicamente viável quando o ambiente puder ser configurado em até cinco horas, quando o suporte recorrente ficar dentro do limite aprovado e quando pelo menos 80% das necessidades do próximo tenant puderem ser atendidas por configuração. O piloto CAMPPG deve medir esses indicadores por oito semanas antes de definir preços finais.')

add_heading(doc, '7. Estratégia de impacto', 1)
add_para(doc, 'ONGs podem receber acesso gratuito ou subsidiado para que o Palácio Mental gere impacto e aprenda com necessidades reais. Isso exige critérios de elegibilidade, proteção de dados, consentimento para divulgação de casos, capacidade operacional e revisão periódica.')
add_para(doc, 'O benefício para a ONG é ter uma estrutura acessível para organizar e preservar projetos. O benefício para o Palácio Mental é construir aprendizado e casos de uso que demonstrem valor para organizações pagantes, sem transformar pessoas ou projetos vulneráveis em recurso de marketing.')

add_heading(doc, '8. Hipóteses a validar', 1)
add_para(doc, 'A validação será feita por ciclos curtos. Cada hipótese precisa ter uma métrica observável, um alvo provisório e uma data de decisão. Os alvos abaixo são critérios de aprendizado, não metas de vaidade nem garantia de sucesso.')
add_table(doc, ['Frente e hipótese', 'Métrica e alvo provisório', 'Método', 'Prazo e decisão'], [
    ['Produto — usuários entendem a proposta.', '70% dos novos usuários completam o primeiro projeto sem ajuda; nota média ≥ 4/5 na compreensão.', 'Teste de primeiro uso + entrevista curta.', 'Até 30/11/2026. Manter se atingir; revisar onboarding se não.'],
    ['Produto — contexto progressivo gera valor.', '60% dos projetos ativados adicionam pelo menos 3 elementos de contexto em 14 dias.', 'Coorte de projetos e análise de eventos.', 'Até 15/12/2026. Simplificar etapas se houver abandono.'],
    ['Produto — Meu Espaço é útil.', '40% dos usuários ativados retornam ao Meu Espaço em 2 semanas diferentes no período de 30 dias.', 'Telemetria de retorno + entrevista com usuários ativos/inativos.', 'Até 22/12/2026. Manter, reposicionar ou reduzir escopo.'],
    ['Produto — ambiente CAMPPG atende uso institucional.', 'Pelo menos 2 perfis institucionais usam o ambiente semanalmente; 70% dos projetos-piloto ficam vinculados ao contexto correto.', 'Piloto com gestão, orientação e participantes.', '8 semanas após ativação. Corrigir fluxo antes de replicar.'],
    ['Produto — relevância melhora descoberta.', '20% dos usuários da vitrine interagem com ranking e a taxa de abertura de projetos relevantes supera a lista cronológica em teste simples.', 'Experimento comparativo e eventos de clique.', 'Após 4 semanas da feature. Manter apenas se não houver viés por plano.'],
    ['Produto — PM Flow e PM VCS têm demanda real.', 'Ao menos 6 de 10 entrevistas descrevem um problema recorrente que o módulo resolveria e aceitam testar um protótipo.', 'Entrevistas sem vender a solução pronta.', 'Até 31/01/2027. Priorizar somente se o problema for recorrente.'],
    ['Negócio — usuários pagam por profundidade.', 'Em 10 entrevistas, ≥3 demonstram disposição concreta: preço aceitável, pré-cadastro ou teste pago.', 'Entrevistas de problema/preço e landing page controlada.', 'Até 31/01/2027. Não lançar plano pago baseado só em opinião.'],
    ['Negócio — organizações pagam por governança.', '5 conversas qualificadas, 2 pilotos interessados e 1 proposta aceita para desenho pago ou patrocinado.', 'Entrevistas com organizações fora do CAMPPG.', 'Até 28/02/2027. Revisar pacote e comprador se não houver avanço.'],
    ['Negócio — ONG subsidiada é sustentável.', 'Custo mensal estimado por ONG e horas de suporte ficam dentro do limite aprovado pela equipe.', 'Registro de custo, horas e infraestrutura do piloto.', 'Revisão mensal por 3 meses. Continuar só com capacidade explícita.'],
    ['Negócio — implantação é viável.', 'Primeiro ambiente configurado em até 5 horas; suporte recorrente ≤ 2 horas por semana no piloto.', 'Cronometragem de implantação e registro de suporte.', 'Durante as 8 semanas do piloto. Productizar o que se repetir.'],
    ['Operação — núcleo compartilhado se replica.', '80% das necessidades do segundo piloto atendidas por configuração, sem código exclusivo.', 'Comparação de requisitos entre CAMPPG e próxima organização.', 'Até 31/03/2027. Recusar customização estrutural sem margem.'],
], widths=[1.75,2.15,1.65,1.55])
add_para(doc, 'As hipóteses de PM Flow, PM VCS e disposição a pagar não serão tratadas como validadas pelo simples uso do MVP. Elas exigem evidência específica. A equipe deve registrar resultado, amostra, limitações e decisão — continuar, ajustar, pausar ou descartar — ao fim de cada prazo.')

add_heading(doc, '9. Próximas decisões da equipe', 1)
for item in [
    'Validar o piloto institucional do CAMPPG antes de ampliar segmentos.',
    'Definir limites reais dos planos Free, Pro e Institucional.',
    'Medir custo por tenant, implantação e suporte durante o piloto.',
    'Implementar o núcleo multi-tenant sem misturar projetos institucionais à vitrine global.',
    'Integrar Redis como camada operacional, mantendo PostgreSQL como fonte oficial.',
    'Tratar PM Flow, PM VCS e automações avançadas como hipóteses posteriores.',
]: add_bullet(doc, item)

add_heading(doc, '10. Nota de governança do documento', 1)
add_para(doc, 'Esta versão foi criada separadamente com base no Contexto Mestre oficial indicado pela equipe. O documento oficial permanece intacto. Antes de incorporar qualquer trecho ao documento principal, a equipe deve revisar as hipóteses, os limites dos planos e a capacidade operacional.')

add_heading(doc, '11. Referências de custos', 1)
add_para(doc, '[1] Railway. Pricing. Consulta em 27 out. 2026. https://railway.com/pricing')
add_para(doc, '[2] Registro.br. Pagamento de domínio. Consulta em 27 out. 2026. https://registro.br/ajuda/pagamento-de-dominio/')
add_para(doc, '[3] Cloudflare. Free Plan Overview. Consulta em 27 out. 2026. https://www.cloudflare.com/plans/free/')

# Rodapé simples
for section in doc.sections:
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_run(footer.add_run('Palácio Mental — documento de revisão estratégica'), size=8, color=GRAY)

doc.save(docx_path)
print(docx_path)
