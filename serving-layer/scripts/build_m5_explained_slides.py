"""Build the 14-slide explanatory M5 deck by reusing the user's PowerPoint template.

Run with python-pptx and Pillow installed. The original deck is never modified.
Native shapes keep the data flow, architecture, document and calculation editable.
"""
from copy import deepcopy
from pathlib import Path
import json

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'serving-layer/logs/m5_slides'
OUT = ROOT / 'serving-layer/doc_guide/M5_14_SLIDES_THUYET_MINH.pptx'
TEMPLATE = ROOT / 'RIVF paper review.pptx'
R, O, G = 'C00000', 'E88917', 'A67710'
INK, MUTED, LINE = '292929', '666666', 'DDD5CC'
CREAM, LIGHT, GREEN = 'FFF5E8', 'F5F5F5', '258052'
WHITE = 'FFFFFF'
FONT = 'Lato'

prs = Presentation(TEMPLATE)
original = list(prs.slides)
inventory = []


def color(value):
    return RGBColor.from_string(value)


def rect(slide, x, y, w, h, fill=WHITE, stroke=None, radius=False):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color(fill)
    if stroke:
        shape.line.color.rgb = color(stroke)
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    if radius:
        shape.adjustments[0] = .12
    return shape


def style_paragraph(p, size=18, bold=False, fill=INK, align=PP_ALIGN.LEFT):
    p.alignment = align
    p.space_before = Pt(0)
    p.space_after = Pt(0)
    p.line_spacing = 1.04
    pp = p._p.get_or_add_pPr()
    for tag in ('a:buChar', 'a:buAutoNum', 'a:buBlip', 'a:buNone'):
        for el in list(pp.findall(tag, pp.nsmap)):
            pp.remove(el)
    bullet = OxmlElement('a:buNone')
    following = pp.find('a:tabLst', pp.nsmap)
    if following is None:
        following = pp.find('a:defRPr', pp.nsmap)
    if following is None:
        following = pp.find('a:extLst', pp.nsmap)
    if following is None:
        pp.append(bullet)
    else:
        following.addprevious(bullet)
    for run in p.runs:
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color(fill)
        rp = run._r.get_or_add_rPr()
        rp.set('lang', 'vi-VN')
        for tag in ('a:ea', 'a:cs'):
            f = rp.find(tag, rp.nsmap)
            if f is None:
                f = OxmlElement(tag)
                rp.append(f)
            f.set('typeface', FONT)


def write(shape, text, size=18, bold=False, fill=INK, align=PP_ALIGN.LEFT,
          valign=MSO_ANCHOR.TOP, margin=0):
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    # Explicit sizing prevents text from silently shrinking in PowerPoint.
    tf.auto_size = None
    for i, line in enumerate(text.split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        style_paragraph(p, size, bold, fill, align)
    return shape


def text(slide, x, y, w, h, value, size=18, bold=False, fill=INK,
         align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    box.name = 'M5 text ' + value[:35].replace('\n', ' ')
    return write(box, value, size, bold, fill, align, valign)


def arrow(slide, x, y, w=.36, h=.22, fill=O, down=False):
    sh = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW if down else MSO_SHAPE.RIGHT_ARROW,
                               Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color(fill)
    sh.line.fill.background()
    return sh


def line(slide, x1, y1, x2, y2, fill=LINE, width=1.4):
    sh = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1),
                                     Inches(x2), Inches(y2))
    sh.line.color.rgb = color(fill)
    sh.line.width = Pt(width)
    return sh


def badge(slide, x, y, number, fill=R, diameter=.4):
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y),
                               Inches(diameter), Inches(diameter))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color(fill)
    sh.line.fill.background()
    write(sh, str(number), 16, True, WHITE, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    return sh


def label(slide, x, y, w, value, fill=R, bg=CREAM, size=15):
    sh = rect(slide, x, y, w, .36, bg, radius=True)
    write(sh, value, size, True, fill, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    return sh


def card(slide, x, y, w, h, heading, body='', accent=R, size=18):
    rect(slide, x, y, w, h, LIGHT, LINE, True)
    rect(slide, x, y+.08, .045, h-.16, accent)
    text(slide, x+.18, y+.16, w-.36, .6, heading, 20, True, accent)
    if body:
        text(slide, x+.18, y+.9, w-.36, h-1, body, size)


def db(slide, x, y, w, h, value, fill=CREAM, font_size=20):
    sh = slide.shapes.add_shape(MSO_SHAPE.CAN, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color(fill)
    sh.line.color.rgb = color(O)
    sh.line.width = Pt(1.4)
    write(sh, value, font_size, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, .1)
    return sh


def file_icon(slide, x, y, w, h, value, fill=CREAM, size=17):
    sh = slide.shapes.add_shape(MSO_SHAPE.FOLDED_CORNER, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color(fill)
    sh.line.color.rgb = color(LINE)
    write(sh, value, size, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, .08)
    return sh


def mini_chart(slide, x, y, w, h, title=None):
    rect(slide, x, y, w, h, LIGHT, LINE, True)
    if title:
        text(slide, x+.1, y+.1, w-.2, .3, title, 17, True, R, PP_ALIGN.CENTER)
    line(slide, x+.2, y+h-.2, x+w-.2, y+h-.2, MUTED)
    for i, val in enumerate([.35, .65, .49, .88]):
        plot_h = h-(.72 if title else .4)
        rect(slide, x+.35+i*(w-.6)/4, y+h-.2-val*plot_h, (w-.7)/6,
             val*plot_h, [R, O, G, R][i])


def fit_image(slide, path, x, y, w, h, replace=None):
    iw, ih = Image.open(path).size
    ratio = min(w/iw, h/ih)
    nw, nh = iw*ratio, ih*ratio
    pic = slide.shapes.add_picture(str(path), Inches(x+(w-nw)/2), Inches(y+(h-nh)/2),
                                   width=Inches(nw), height=Inches(nh))
    pic.name = 'M5 actual dashboard ' + path.name
    if replace is not None:
        # Keep exemplar image's place in the reading order.
        old = replace._element
        old.addprevious(pic._element)
        old.getparent().remove(old)
    return pic


def clone(source_index, number):
    source = original[source_index-1]
    slide = prs.slides.add_slide(source.slide_layout)
    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)
    mapping = {}
    for rel in source.part.rels.values():
        if rel.reltype.endswith(('/slideLayout', '/notesSlide')):
            continue
        target = rel.target_ref if rel.is_external else rel.target_part
        mapping[rel.rId] = slide.part.relate_to(target, rel.reltype, rel.is_external)
    for shape in source.shapes:
        el = deepcopy(shape._element)
        for node in el.iter():
            for key, value in list(node.attrib.items()):
                if key.startswith('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}') and value in mapping:
                    node.set(key, mapping[value])
        slide.shapes._spTree.insert_element_before(el, 'p:extLst')
    for shape in slide.shapes:
        if shape.is_placeholder and shape.placeholder_format.idx == 12:
            write(shape, str(number), 12, False, WHITE, PP_ALIGN.RIGHT)
    inventory.append({'slide': number, 'source_exemplar': source_index})
    return slide


def base(number, title, section, intro, exemplar=4):
    slide = clone(exemplar, number)
    title_shape = next(sh for sh in slide.shapes if sh.is_placeholder and sh.placeholder_format.idx == 0)
    write(title_shape, title, 28, True, R)
    text(slide, .47, .79, 11.2, .28, section.upper(), 13, True, G)
    body = next((sh for sh in slide.shapes if sh.has_text_frame and sh.name.startswith('Content Placeholder')), None)
    if body is not None:
        body.left, body.top, body.width, body.height = Inches(.47), Inches(1.15), Inches(11.15), Inches(.62)
        write(body, intro, 20)
    else:
        text(slide, .47, 1.15, 11.15, .62, intro, 20)
    inventory[-1].update(title=title, section=section)
    return slide


def notes(slide, value):
    slide.notes_slide.notes_text_frame.text = value


SECTION_NAMES = [
    'Tiếp nhận và kiểm tra output M2',
    'Thiết kế cách lưu trong MongoDB',
    'Chuẩn bị môi trường chạy',
    'Xây dựng và chạy chương trình nạp dữ liệu',
    'Xây dựng các truy vấn và phép tính hiển thị',
    'Xây dựng dashboard',
]
SECTION_STARTS = [1, 5, 7, 9, 11, 13]
SPEECHES = []


def prose_bullets(shape, paragraphs, size=18, gap=8):
    """Real bullet paragraphs, with complete sentences and optional bold spans."""
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = None
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    for i, paragraph in enumerate(paragraphs):
        assert paragraph.endswith(('.', '!', '?')), paragraph
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        segments = paragraph.split('**')
        for segment in segments:
            p.add_run().text = segment
        style_paragraph(p, size, False, INK)
        for j, run in enumerate(p.runs):
            run.font.bold = bool(j % 2)
        p.space_after = Pt(gap)
        pp = p._p.get_or_add_pPr()
        pp.set('marL', str(Inches(.21)))
        pp.set('indent', str(-Inches(.2)))
        for el in list(pp):
            if el.tag.endswith(('}buNone', '}buChar', '}buFont')):
                pp.remove(el)
        bufont, bullet = OxmlElement('a:buFont'), OxmlElement('a:buChar')
        bufont.set('typeface', FONT)
        bullet.set('char', '•')
        following = pp.find('a:defRPr', pp.nsmap)
        if following is None:
            pp.append(bufont)
            pp.append(bullet)
        else:
            following.addprevious(bufont)
            following.addprevious(bullet)


def prose_slide(number, section, subtitle, paragraphs, visual_heading=None):
    slide = clone(4, number)
    title = next(sh for sh in slide.shapes if sh.is_placeholder and sh.placeholder_format.idx == 0)
    write(title, f'{section}. {SECTION_NAMES[section-1]}', 28, True, R)
    text(slide, .48, .8, 11.05, .36, subtitle, 16, True, G)
    body = next(sh for sh in slide.shapes if sh.name.startswith('Content Placeholder'))
    body.left, body.top, body.height = Inches(.55), Inches(1.43), Inches(5.15)
    body.width = Inches(5.35 if visual_heading else 11.08)
    prose_bullets(body, paragraphs)
    if visual_heading:
        line(slide, 6.14, 1.4, 6.14, 6.48, LINE, .8)
        text(slide, 6.47, 1.44, 5.06, .61, visual_heading, 20, True, R)
    inventory[-1].update(section=SECTION_NAMES[section-1], subtitle=subtitle,
                         paragraphs=paragraphs, layout='split' if visual_heading else 'full width')
    return slide


def panel(slide, x, y, w, h, value, fill=LIGHT, size=18):
    sh = rect(slide, x, y, w, h, fill, LINE, True)
    write(sh, value, size, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, .07)


def native_table(slide, x, y, widths, rows, heights, size=17):
    for ri, row in enumerate(rows):
        xx = x
        for ci, value in enumerate(row):
            sh = rect(slide, xx, y, widths[ci], heights[ri], CREAM if ri == 0 else (LIGHT if ri % 2 else WHITE), LINE)
            write(sh, value, size, ri == 0, R if ri == 0 else INK, PP_ALIGN.LEFT, MSO_ANCHOR.MIDDLE, .07)
            xx += widths[ci]
        y += heights[ri]


def speech(slide, value):
    notes(slide, value)
    SPEECHES.append(value)


# Slide 1 — original template cover.
s = clone(2, 1)
shapes = {sh.shape_id: sh for sh in s.shapes}
shapes[3].top, shapes[3].height = Inches(2.04), Inches(1.8)
write(shapes[3], 'TASK M5\nTừ output M2 đến MongoDB\nvà dashboard', 36, True, R)
style_paragraph(shapes[3].text_frame.paragraphs[0], 26, False, R)
shapes[4].top, shapes[4].width, shapes[4].height = Inches(4.05), Inches(9.1), Inches(1.02)
write(shapes[4], 'Giải thích 6 nhiệm vụ từ lý thuyết đến công việc thực tế\nProject BigData Storage & Processing', 21)
file_icon(s, .53, 5.38, 2.5, .91, 'KPI từ M2')
arrow(s, 3.2, 5.73, .48, .26)
db(s, 3.9, 5.29, 2.5, 1.1, 'MongoDB')
arrow(s, 6.57, 5.73, .48, .26)
mini_chart(s, 7.28, 5.29, 2.6, 1.1, title='Dashboard')
speech(s, 'Bài trình bày giải thích sáu nhiệm vụ của M5 khi sử dụng output lịch sử từ M2. Mỗi gạch đầu dòng là một đoạn diễn giải hoàn chỉnh, kết nối khái niệm với công việc đã triển khai trong project. M2 cung cấp dữ liệu KPI tổng hợp; M5 tiếp nhận, lưu trữ, nạp và truy vấn để đưa thông tin lên dashboard. Sáu section dùng đúng tên nhiệm vụ đã thống nhất. Phần dashboard chỉ giới thiệu những thông tin người dùng hiện có thể xem, không trình bày quy trình thiết kế giao diện. Template, nền, logo và font Lato được giữ từ RIVF paper review.pptx.')

# Slide 2 — fuller overview; six exact section titles appear in the following slides.
s = clone(4, 2)
write(next(sh for sh in s.shapes if sh.is_placeholder and sh.placeholder_format.idx == 0),
      'M5 kết nối dữ liệu đã xử lý với người sử dụng', 28, True, R)
text(s, .48, .8, 11.1, .35, 'Phạm vi: dữ liệu lịch sử được bàn giao từ M2', 16, True, G)
b = next(sh for sh in s.shapes if sh.name.startswith('Content Placeholder'))
b.left, b.top, b.width, b.height = Inches(.55), Inches(1.43), Inches(11.05), Inches(3.82)
prose_bullets(b, [
    'M2 dùng Spark để làm sạch dữ liệu BTS và tính các bảng KPI. M5 tiếp nhận **những bảng đã tổng hợp** này để phục vụ tra cứu, thay vì tính lại toàn bộ dữ liệu chuyến bay.',
    'Hai nhiệm vụ đầu xác định dữ liệu được bàn giao có ý nghĩa gì, có đầy đủ và hợp lệ hay không, rồi quy định cách chuyển từng bảng thành **collection và document trong MongoDB**.',
    'Hai nhiệm vụ tiếp theo chuẩn bị môi trường Docker và chương trình nạp. Dữ liệu phải được ghi đúng, nạp lại không trùng và chỉ xuất hiện trên dashboard sau khi kiểm tra thành công.',
    'Hai nhiệm vụ cuối xây dựng truy vấn và phép tính KPI đúng với bộ lọc, sau đó cung cấp các góc nhìn về lưu lượng, đúng giờ, trễ, hủy chuyến và phân phối độ trễ trên dashboard.',
    'Kết quả M5 gồm **dữ liệu MongoDB, chương trình nạp, các truy vấn, dashboard và bằng chứng kiểm tra**, kèm hướng dẫn để thành viên khác có thể vận hành lại.'
], size=18, gap=10)
for x, value in [(.69, 'Output M2\nKPI đã tổng hợp'), (4.54, 'MongoDB\nDữ liệu có thể truy vấn'), (8.39, 'Dashboard\nThông tin cho người xem')]:
    panel(s, x, 5.63, 3.09, .85, value, CREAM, 18)
arrow(s, 3.95, 5.94, .37, .24)
arrow(s, 7.8, 5.94, .37, .24)
speech(s, 'Có thể nhìn M5 như lớp serving, nghĩa là đưa dữ liệu đã xử lý tới nơi người dùng có thể tra cứu và hiểu được. Luồng chính hiện tại dùng JSONL và manifest từ M2; nhánh đọc KPI Parquet trên HDFS cũng dùng chung bộ ghi. M5 không chỉ tạo giao diện mà còn cần bảo đảm tính đúng đắn và khả năng vận hành của dữ liệu bên dưới. Các slide sau được chia thành sáu section, mỗi section có hai slide để diễn giải đầy đủ công việc. Bộ dữ liệu minh họa là snapshot 20261107T042703414867Z. Nguồn đối chiếu: contracts.py, mongo.py, batch_writer.py, queries.py, metrics.py, compose.yml và app.py.')

# Section 1, slide 3.
s = prose_slide(3, 1, 'Tiếp nhận bộ bàn giao và hiểu ý nghĩa của từng bảng', [
    'M5 nhận một **snapshot**, là bộ file M2 xuất tại một thời điểm. Trong đó, manifest.json mô tả dữ liệu và các file JSONL chứa bản ghi để nạp.',
    'Bộ bàn giao có **13 bảng KPI và 7 bảng phân phối độ trễ**. M5 cần biết mỗi bảng thống kê theo ngày, tháng, năm, hãng, sân bay hay tuyến.',
    'Mỗi dòng đại diện một nhóm chuyến bay, với khóa như year + month cho KPI tháng hoặc year + carrier cho KPI hãng theo năm.',
    'M5 cần đọc đúng khóa, đơn vị và thời gian. Snapshot có **51 tháng từ 01/2022 đến 03/2026**; tỷ lệ lưu 0–1 và độ trễ tính bằng phút.',
], 'Ví dụ mức tổng hợp của dữ liệu')
file_icon(s, 6.52, 2.13, 2.3, .84, 'manifest.json', size=18)
file_icon(s, 9.1, 2.13, 2.3, .84, '20 file JSONL', size=18)
native_table(s, 6.49, 3.31, [2.24, 2.78], [
    ['Bảng KPI', 'Một dòng đại diện'], ['month_overall', '1 năm + 1 tháng'],
    ['year_carrier', '1 năm + 1 hãng'], ['year_route', '1 năm + sân bay đi/đến']
], [.55, .67, .67, .79], 17)
text(s, 6.54, 6.16, 4.9, .43, '74.921 dòng tổng hợp · 29.328.846 chuyến', 17, True, R, PP_ALIGN.CENTER)
speech(s, 'Snapshot thực tế ở batch-layer/spark_jobs/export/m2_to_m5/20261107T042703414867Z. Có manifest, JSONL và CSV; luồng nạp chính đọc JSONL cùng manifest, còn CSV thuận tiện khi kiểm tra bằng bảng tính. 74.921 là tổng số dòng các bảng tổng hợp, không phải tổng số chuyến. Tổng chuyến sau cleaning là 29.328.846. Trong bảng box, khóa còn có var để phân biệt arrival/departure và population để phân biệt tập hợp hợp lệ với tập trễ từ 15 phút. Năm 2026 chỉ có quý I. Nguồn: manifest và m5/contracts.py.')

# Section 1, slide 4.
s = prose_slide(4, 1, 'Kiểm tra tính đầy đủ, cấu trúc và tính nhất quán trước khi ghi', [
    'M5 đối chiếu manifest để xác nhận đủ 20 bảng và các file đi kèm, sau đó kiểm tra tên cột, kiểu dữ liệu và trường bắt buộc khớp schema.',
    'Khóa nhóm phải không null và không trùng; số dòng phải khớp manifest. M5 cũng đối chiếu 51 tháng và tổng số chuyến bay với nguồn.',
    'Chế độ **CheckOnly** kiểm tra toàn bộ snapshot mà chưa ghi MongoDB. Bước này giúp phát hiện lỗi đầu vào trước khi thay đổi database.',
    'Khi kiểm tra PASS, snapshot được chuyển sang bước nạp. Nếu có lỗi, người vận hành sửa hoặc xuất lại dữ liệu M2 rồi kiểm tra lại.',
], 'Dữ liệu đi qua các cổng kiểm tra')
panel(s, 7.64, 2.14, 2.66, .67, 'Snapshot M2', CREAM, 19)
arrow(s, 8.84, 2.93, .25, .25, down=True)
for i, v in enumerate(['Đủ file và đúng schema', 'Khóa và kiểu dữ liệu hợp lệ', 'Số dòng, thời gian, tổng chuyến khớp']):
    panel(s, 6.64, 3.33+i*.65, 4.71, .48, v, size=17)
arrow(s, 8.84, 5.31, .25, .25, down=True)
label(s, 6.7, 5.83, 2.1, 'PASS → nạp', GREEN, 'ECF5EF', 17)
label(s, 9.04, 5.83, 2.22, 'FAIL → sửa nguồn', R, 'FBEDED', 17)
speech(s, 'Lệnh PowerShell ở serving-layer là .\\scripts\\load_m2.ps1 -SnapshotPath $M5Snapshot -CheckOnly; trước đó gán biến bằng đường dẫn thư mục có manifest.json. CheckOnly có thể chạy không cần MongoDB đang bật. contracts.py kiểm tra cả kiểu scalar và giá trị số hữu hạn, phát hiện trùng khóa và tính digest nội dung. Việc kiểm chứng này xác nhận hợp đồng và tính toàn vẹn của bộ bàn giao; cách tính Spark và chất lượng raw vẫn cần kiểm chứng ở M2. Không coi PASS của ingest là bằng chứng thay thế cho việc kiểm định công thức upstream.')

# Section 2, slide 5.
s = prose_slide(5, 2, 'Chuyển bảng tổng hợp thành mô hình document có thể truy vấn', [
    'Trong MongoDB, **collection** nhóm các bản ghi cùng loại, còn document lưu một bản ghi theo trường và giá trị. Mỗi bảng M2 được lưu riêng.',
    'M5 chuyển mỗi dòng KPI thành một document, giữ nguyên các trường của M2 và thêm **snapshot_id** để phân biệt phiên bản dữ liệu.',
    'Ví dụ, kpi_month_overall chứa KPI tháng với năm, tháng, số chuyến, số đúng giờ, mẫu số hợp lệ và các chỉ tiêu đã được M2 tính.',
    'Khi lưu, M5 giữ đúng kiểu số, chuỗi và null để đối chiếu được với nguồn. Tỷ lệ vẫn ở dạng 0–1 và chỉ đổi thành phần trăm khi hiển thị.',
], 'Document tháng 01/2025, rút gọn')
label(s, 6.51, 2.12, 5.0, 'Collection: kpi_month_overall', size=18)
rect(s, 6.51, 2.77, 5.0, 2.98, LIGHT, LINE, True)
text(s, 6.74, 2.95, 4.54, 2.66,
     '{\n  snapshot_id: "633c62bf…",\n  year: 2025, month: 1,\n  flights: 539747,\n  on_time: 424139, arr_n: 522269,\n  otp_operated: 0.812108…\n}', 18)
text(s, 6.61, 6.04, 4.8, .65, 'Một bảng → một collection\nMột dòng → một document', 17, True, R, PP_ALIGN.CENTER)
speech(s, 'Database mặc định là aero_m5. Các collection dữ liệu gồm 13 kpi_<table> và 7 box_<table>. Ví dụ minh họa lấy từ dòng tháng 01/2025, chỉ bỏ bớt trường để dễ đọc; snapshot_id hiển thị rút gọn nhưng trong database được lưu đầy đủ. Document có thể hiểu gần giống một dòng nhưng sử dụng mô hình trường–giá trị. M5 không tự thay đổi null thành 0 hay biến tỷ lệ thành số phần trăm ở tầng storage. Các nguyên tắc này giúp đối chiếu MongoDB với M2 chính xác. Nguồn: m5/mongo.py, contracts.py và snapshot thực tế.')

# Section 2, slide 6 — full width for explanatory prose.
s = prose_slide(6, 2, 'Xác định khóa duy nhất, chỉ mục và thông tin quản lý phiên bản', [
    'M5 tạo **khóa duy nhất từ snapshot_id và toàn bộ khóa nhóm trong manifest**. Với KPI tháng, khóa gồm snapshot_id, year và month; với KPI hãng, khóa còn chứa carrier để phân biệt từng hãng.',
    'Các bảng phân phối cần giữ cả var và population trong khóa vì độ trễ đến, độ trễ khởi hành và các quần thể thống kê có ý nghĩa khác nhau. Bỏ các trường này có thể làm dữ liệu khác nhóm ghi đè lên nhau.',
    'Bên cạnh khóa duy nhất, M5 tạo **index hỗ trợ các bộ lọc thường dùng** như năm, hãng, sân bay và tuyến. Hiệu quả cụ thể phải được kiểm tra theo truy vấn thực tế, chẳng hạn bằng explain của MongoDB.',
    'Các collection quản lý lưu lịch sử và trạng thái phục vụ. batch_runs ghi thông tin lần nạp; serving_state chỉ snapshot đang được dashboard sử dụng; serving_locks kiểm soát việc nạp đồng thời.',
    'Kết quả của bước thiết kế là một mô hình lưu trữ thống nhất, trong đó M5 vừa tránh được bản ghi trùng, vừa tách được các phiên bản và truy vết dữ liệu về đúng bộ bàn giao từ M2.'
])
speech(s, 'Unique index có tên snapshot_business_key. Bảng box luôn bao gồm var và population; var nhận arr hoặc dep, population nhận all hoặc late. Các index bổ sung được tạo theo chiều dữ liệu, không có nghĩa mọi sort hay truy vấn đều được tăng tốc. serving_locks quản lý lease 10 phút và được gia hạn khi loader làm việc; thao tác kiểm tra khóa thuộc writer. Những collection metadata này không nằm trong con số 20 collection dữ liệu KPI/box. Nguồn: m5/mongo.py, contracts.py, batch_writer.py và doc_guide/MONGODB_COLLECTIONS_QUERIES.md.')

# Section 3, slide 7.
s = prose_slide(7, 3, 'Phân vai các thành phần cần chạy trong môi trường triển khai', [
    'M5 dùng **Docker Compose** để dựng các dịch vụ theo cùng cấu hình. MongoDB, loader và dashboard trao đổi dữ liệu trong một mạng Docker.',
    'MongoDB Server chạy trong container để lưu dữ liệu M5. Thành viên chỉ cần Docker Desktop, không bắt buộc cài thêm server trên Windows.',
    'Loader chạy khi cần nạp snapshot, đọc bộ file được gắn vào container rồi ghi MongoDB. MongoDB và dashboard tiếp tục chạy để phục vụ sử dụng.',
    'Dashboard hiển thị dữ liệu MongoDB đã công bố trên trình duyệt. Trong Docker, ứng dụng kết nối qua tên dịch vụ mongo.',
], 'Sơ đồ hạ tầng M5 bằng Docker')
panel(s, 7.68, 2.13, 2.61, .58, 'Trình duyệt', CREAM, 19)
arrow(s, 8.87, 2.83, .24, .25, down=True)
rect(s, 6.5, 3.21, 5.01, 2.37, LIGHT, LINE, True)
text(s, 6.72, 3.36, 4.57, .35, 'Mạng Docker Compose', 17, True, G, PP_ALIGN.CENTER)
panel(s, 6.72, 4.0, 2.1, .57, 'Dashboard', CREAM)
panel(s, 6.72, 4.81, 2.1, .57, 'Loader', CREAM)
arrow(s, 8.97, 4.2, .28, .2)
arrow(s, 8.97, 5.01, .28, .2)
db(s, 9.4, 4.02, 1.86, 1.3, 'MongoDB', font_size=18)
arrow(s, 10.18, 5.69, .24, .25, down=True)
panel(s, 8.1, 6.05, 3.41, .47, 'Volume giữ dữ liệu', CREAM, 17)
speech(s, 'compose.yml định nghĩa ba service mongo, dashboard và loader. Loader nằm trong profile tools và chỉ chạy khi gọi compose run hoặc script tương ứng. Dashboard và loader dùng chung image aero-m5:local. Trong mạng Docker, MongoDB được truy cập qua mongodb://mongo:27017, không dùng localhost của máy Windows. Streamlit và Plotly là thư viện hiện tại của dashboard; ở section dashboard cuối bài chỉ mô tả thông tin hiện có thể xem. Sơ đồ chỉ quan hệ dịch vụ và lưu trữ, không khẳng định vị trí vật lý từng file trên máy. Nguồn: compose.yml và Dockerfile.')

# Section 3, slide 8.
s = prose_slide(8, 3, 'Cấu hình kết nối, cổng truy cập và lưu trữ bền vững', [
    'M5 cấu hình địa chỉ MongoDB và database aero_m5. Trên máy người dùng, web mở ở **localhost:8501**; Compass hoặc mongosh dùng cổng 27017.',
    'Volume **m5_mongo_data** gắn vào /data/db để giữ dữ liệu sau khi container dừng hoặc tạo lại. Xóa volume sẽ xóa dữ liệu đã lưu.',
    'Người vận hành bật Docker Desktop rồi chạy start_m5.ps1 tại serving-layer. Script dựng dịch vụ và chờ MongoDB cùng dashboard healthy.',
    'Sau đó, cần kiểm tra web truy cập được, database kết nối đúng và loader thấy snapshot. Trạng thái container và log giúp tìm nguyên nhân lỗi.',
], 'Các địa chỉ và vùng lưu trữ chính')
native_table(s, 6.49, 2.17, [2.12, 2.91], [
    ['Thành phần', 'Cấu hình trong project'], ['Web trên Windows', 'http://localhost:8501'],
    ['MongoDB trên máy', '127.0.0.1:27017'], ['MongoDB nội bộ', 'mongodb://mongo:27017'],
    ['Database', 'aero_m5'], ['Volume', 'm5_mongo_data → /data/db']
], [.62, .67, .67, .83, .64, .86], 17)
speech(s, 'Lệnh khởi động trong PowerShell ở serving-layer là .\\scripts\\start_m5.ps1. Các port trên bảng là mặc định và có thể đổi qua biến môi trường. Compose chỉ bind MongoDB và dashboard vào 127.0.0.1. Loader mount nguồn ở chế độ chỉ đọc để không sửa output M2. Dừng thường ngày có thể dùng stop_m5.ps1; không sử dụng down -v để dừng nếu muốn giữ dữ liệu. Healthcheck xác nhận MongoDB đáp ứng ping và web có endpoint sức khỏe, còn kiểm chứng dữ liệu cần bước verify riêng. Nguồn: compose.yml, scripts/start_m5.ps1, common.ps1 và stop_m5.ps1.')

# Section 4, slide 9.
s = prose_slide(9, 4, 'Đọc dữ liệu nguồn và chuyển thành các bản ghi MongoDB', [
    'Luồng chính đọc **JSONL và manifest của M2**; project cũng có nhánh đọc KPI Parquet trên HDFS. Hai luồng dùng chung bộ ghi MongoDB.',
    'Trước khi ghi, chương trình kiểm tra nguồn và tính snapshot_id từ nội dung. Cùng bộ dữ liệu có cùng định danh để nhận biết lần nạp lại.',
    'Loader **upsert theo snapshot_id và khóa nhóm**: có bản ghi thì cập nhật, chưa có thì thêm. Các thao tác được gửi theo lô 1.000.',
    'Sau khi ghi, loader đọc lại MongoDB để so số dòng và mã kiểm tra nội dung với nguồn. Log và báo cáo được giữ lại để truy vết khi có lỗi.',
], 'Luồng xử lý của chương trình nạp')
panel(s, 6.5, 2.13, 5.0, .61, 'JSONL hoặc KPI Parquet', CREAM, 19)
for i, name in enumerate(['Đọc và kiểm tra đầu vào', 'Tính snapshot_id', 'Upsert theo khóa', 'Đọc lại và đối chiếu dữ liệu', 'Lưu báo cáo, chuẩn bị công bố']):
    y = 3.06+i*.65
    badge(s, 6.6, y+.06, i+1, diameter=.34)
    panel(s, 7.13, y, 4.18, .49, name, CREAM if i == 4 else LIGHT, 17)
    if i < 4:
        arrow(s, 9.14, y+.51, .18, .1, down=True)
speech(s, 'Luồng JSONL được thực hiện qua m5/load_batch.py và scripts/load_m2.ps1. Luồng HDFS dùng m5/load_parquet.py cùng compose.hdfs.yml; đầu vào ở đây là KPI Parquet đã tổng hợp. Cả hai sử dụng batch_writer.py. Lệnh nạp chính trong PowerShell là .\\scripts\\load_m2.ps1 -SnapshotPath $M5Snapshot sau khi CheckOnly PASS. Upsert là ghi theo khóa, nhưng snapshot đã công bố được giữ bất biến và không ghi sửa tại chỗ. Việc đọc lại dùng digest các scalar và số dòng, không chỉ kiểm tra một vài ví dụ. Nguồn: contracts.py, load_batch.py, load_parquet.py, batch_writer.py.')

# Section 4, slide 10.
s = prose_slide(10, 4, 'Tránh dữ liệu trùng và chỉ công bố một phiên bản đã kiểm chứng', [
    'Khóa duy nhất và snapshot_id giúp nạp lại **không nhân đôi dữ liệu**. Snapshot đã công bố được giữ nguyên; cùng nội dung được nhận diện là đã có.',
    'Khi bản B đang nạp và đối chiếu, dashboard vẫn đọc bản A đã công bố. Người xem vì thế không nhận một bộ KPI mới đang được ghi dở.',
    'Khi toàn bộ B khớp nguồn, loader mới chuyển active sang B. Nếu B kiểm tra thất bại, hệ thống giữ A để người vận hành sửa và nạp lại.',
    'M5 kiểm soát các lần nạp đồng thời và chạy verify để kiểm chứng MongoDB. Kết quả cần đạt là dữ liệu đủ, không trùng và truy vết được phiên bản.',
], 'Ví dụ cơ chế công bố phiên bản')
db(s, 6.62, 2.2, 2.13, 1.27, 'Bản A\nĐã công bố', font_size=19)
db(s, 9.24, 2.2, 2.13, 1.27, 'Bản B\nĐang nạp', font_size=19)
label(s, 6.68, 3.81, 4.65, 'Đang nạp B → dashboard vẫn dùng A', GREEN, 'ECF5EF', 16)
arrow(s, 8.86, 4.34, .26, .27, down=True)
native_table(s, 6.52, 4.89, [2.1, 2.87], [
    ['Kiểm tra bản B', 'Bản dashboard sử dụng'], ['PASS', 'Chuyển sang B'], ['FAIL', 'Tiếp tục dùng A']
], [.64, .64, .64], 17)
speech(s, 'Con trỏ active nằm trong serving_state với _id=historical. Mỗi lượt chạy dashboard lấy con trỏ một lần và dùng snapshot đó cho các truy vấn trong lượt. Snapshot thất bại có thể retry; nạp lại snapshot đã công bố trả ALREADY_LOADED. Nạp lại một snapshot cũ cũng không tự chuyển active ngược về quá khứ. Writer có lease để kiểm soát nạp đồng thời và không tự xóa snapshot cũ. Verifier độc lập được gọi bằng .\\scripts\\verify_m5.ps1. Sơ đồ A/B là minh họa cơ chế, không khẳng định hiện đang có hai bản trong database. Nguồn: batch_writer.py, mongo.py, verify_batch.py.')

# Section 5, slide 11.
s = prose_slide(11, 5, 'Chọn đúng bảng, chiều dữ liệu và phiên bản để trả lời câu hỏi', [
    'M5 chọn bảng có **đúng mức tổng hợp** theo câu hỏi. KPI tháng dùng bảng tháng; câu hỏi theo hãng hoặc sân bay dùng bảng có chiều tương ứng.',
    'Truy vấn lịch sử luôn gắn snapshot_id đang active rồi mới lọc năm, tháng, hãng hoặc sân bay. Kết quả thuộc cùng một phiên bản đã công bố.',
    'Bộ lọc phải đúng chiều có trong nguồn. Bảng KPI tuyến chỉ có năm, sân bay đi và đến nên không cung cấp lọc theo tháng hoặc hãng.',
    'M5 dùng **một bảng đúng mức** để tránh đếm lặp. Các bảng overall, carrier và origin có thể mô tả lại cùng tập chuyến nên không được cộng chung.',
], 'Ví dụ kết quả thật: tháng 01/2025')
label(s, 6.51, 2.12, 5.0, 'kpi_month_overall', size=19)
text(s, 6.65, 2.74, 4.72, .69, 'snapshot_id = active\nyear = 2025; month = 1', 18, False, INK, PP_ALIGN.CENTER)
native_table(s, 6.51, 3.75, [2.75, 2.25], [
    ['Thông tin', 'Giá trị'], ['Tổng chuyến', '539.747'], ['Đúng giờ', '424.139'],
    ['Đến hợp lệ', '522.269'], ['Tỷ lệ đúng giờ', '81,21%']
], [.5, .5, .5, .5, .61], 18)
speech(s, 'Ví dụ tháng 01/2025 lấy từ kpi__month_overall.jsonl trong snapshot. Tổng flights là 539747, on_time là 424139, arr_n là 522269; OTP bằng 424139/522269≈81,21%. Tổng chuyến khác số chuyến đến hợp lệ nên không thay arr_n bằng flights. m5/queries.py lấy snapshot active và lọc theo hợp đồng bảng. App chỉ sử dụng chiều nguồn có sẵn; giới hạn KPI tuyến theo năm là giới hạn dữ liệu upstream. Không cộng các bảng tóm tắt ở nhiều mức vì sẽ đếm lại các chuyến. Nguồn: queries.py, metrics.py, app.py và snapshot thực tế.')

# Section 5, slide 12.
s = prose_slide(12, 5, 'Tính lại KPI từ số đếm và giữ đúng ý nghĩa thống kê', [
    'Khi gộp nhóm, M5 **cộng tử số và mẫu số rồi mới chia**. Trung bình các tỷ lệ có sẵn sẽ sai nếu quy mô các nhóm khác nhau.',
    'OTP dùng tổng on_time / tổng arr_n, còn tỷ lệ hủy dùng tổng cancelled / tổng flights. Delay trung bình dùng tổng độ trễ và số mẫu phù hợp.',
    'Median, Q1 và Q3 không có tính cộng. M5 lấy đúng bảng phân phối đã được M2 tính cho mức thống kê cần xem, thay vì lấy trung bình các phân vị.',
    'Khi hiển thị, M5 đổi tỷ lệ 0–1 thành phần trăm, giữ null nếu thiếu dữ liệu hoặc mẫu số bằng 0, và cho phép delay âm vì chuyến bay có thể đến sớm.',
], 'Ví dụ minh họa cách gộp tỷ lệ')
native_table(s, 6.51, 2.14, [1.2, 2.51, 1.28], [
    ['Nhóm', 'Đúng giờ / hợp lệ', 'OTP'], ['A', '9 / 10', '90%'], ['B', '50 / 100', '50%']
], [.74, .62, .62], 17)
rect(s, 6.51, 4.43, 4.99, 1.08, 'ECF5EF', radius=True)
text(s, 6.69, 4.57, 4.63, .84, 'Đúng: (9 + 50) / (10 + 100)\n= 53,6%', 22, True, GREEN, PP_ALIGN.CENTER)
rect(s, 6.51, 5.86, 4.99, .62, 'FBEDED', radius=True)
write(s.shapes[-1], 'Sai: (90% + 50%) / 2 = 70%', 19, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
speech(s, 'Hai nhóm A/B ở đây chỉ là số minh họa, không phải thống kê BTS. A có 9/10=90%, B có 50/100=50%; gộp phải là 59/110≈53,6%, không phải 70%. Trong code metrics.py, summarize cộng các sufficient statistics rồi tính lại tỷ lệ và mean theo đúng mẫu số. ratio trả None nếu mẫu số thiếu hoặc bằng 0. Các biểu đồ box lấy trực tiếp bảng thống kê đã có đúng mức. Điểm reliability là chỉ số tự định nghĩa của nhóm từ tỷ lệ trễ/hủy/chuyển hướng, không phải chuẩn bên ngoài. Nguồn: m5/metrics.py và m5/charts.py.')

# Section 6, slide 13 — what the existing dashboard can show, only.
s = prose_slide(13, 6, 'Thông tin hiện có: tổng quan, thời gian, hãng bay và sân bay', [
    'Trang **Tổng quan** cho xem số chuyến sau cleaning, tỷ lệ đúng giờ, trễ từ 15 phút, hủy chuyến và độ trễ đến trung bình theo thời gian đã chọn.',
    'Người xem theo dõi lưu lượng và chất lượng chuyến bay qua các tháng, cùng cơ cấu chuyến đến đúng giờ, trễ 15–59 phút và trễ từ 60 phút.',
    'Trang **Thời gian & mùa vụ** cho xem nhịp bay hằng ngày, trung bình 7 ngày, mùa vụ theo tháng, bản đồ nhiệt ngày lịch và thông tin theo giờ.',
    'Các trang **Hãng bay** và **Sân bay xuất phát** cho xem xếp hạng, tỷ trọng lưu lượng, quy mô và độ trễ, điểm tin cậy cùng diễn biến theo năm.',
], 'Ảnh thật từ trang Tổng quan')
fit_image(s, ASSETS/'bullet_metrics.png', 6.51, 2.12, 5.0, 1.12)
fit_image(s, ASSETS/'bullet_donut.png', 6.94, 3.43, 4.15, 2.6)
text(s, 6.56, 6.16, 4.9, .45, 'Toàn kỳ 01/2022–03/2026 · 2026 chỉ quý I', 16, False, MUTED, PP_ALIGN.CENTER)
speech(s, 'Chỉ trình bày những thông tin hiện có thể xem, không giải thích cách lập trình dashboard. Ảnh thật được crop từ trang tổng quan ở toàn kỳ: 29.328.846 chuyến và 78,8% đúng giờ. Thẻ trễ từ 15 phút là 21,2%, tỷ lệ hủy 1,8%, delay đến trung bình 7,3 phút. Các tỷ lệ phải đọc theo mẫu số của từng chỉ tiêu. Trang hãng/sân bay cho chọn chỉ số flights, delay15_rate, cancel_rate, otp_operated, avg_arr_delay_net hoặc reliability_score; điểm cuối là chỉ số tự định nghĩa. Các góc nhìn toàn kỳ theo mùa vụ/giờ đã gộp năm nên không áp dụng lọc năm. Nguồn: app.py show_overview, show_time, show_ranking; ảnh dashboard thực tế.')

# Section 6, slide 14 — current information, not implementation or delivery tasks.
s = prose_slide(14, 6, 'Thông tin hiện có: tuyến bay, phân phối độ trễ và trạng thái dữ liệu', [
    'Trang **Tuyến bay** cho xem tuyến nhiều chuyến, luồng giữa sân bay đi và đến, cùng lưu lượng và tỷ lệ trễ. KPI tuyến hiện ở mức thống kê theo năm.',
    'Trang **Phân phối delay** cho xem median, Q1–Q3, râu box plot, tỷ lệ ngoại lệ và số mẫu; có thể chọn delay đến/khởi hành và quần thể phù hợp.',
    'Trang **Dữ liệu & vận hành** cho xem snapshot, nguồn ingest, phạm vi thời gian, số document theo manifest, khóa và thời điểm export/kiểm tra.',
    'Người xem có thể tải bảng đang xem thành CSV. Trang **Streaming** đang chờ nguồn M4, nên hiện chưa có KPI thời gian thực để xem.',
], 'Ví dụ góc nhìn tuyến và phân phối')
fit_image(s, ASSETS/'dashboard_routes_focus.png', 6.51, 2.15, 4.99, 1.7)
text(s, 6.56, 4.0, 4.89, .45, 'Sankey thật: Top 15 tuyến năm 2026 (Q1)', 16, True, R, PP_ALIGN.CENTER)
rect(s, 6.51, 4.76, 4.99, 1.24, LIGHT, LINE, True)
line(s, 6.85, 5.32, 11.16, 5.32, O, 2)
line(s, 6.85, 5.1, 6.85, 5.54, O, 2)
line(s, 11.16, 5.1, 11.16, 5.54, O, 2)
rect(s, 7.84, 5.0, 2.06, .65, CREAM, O)
line(s, 8.74, 5.0, 8.74, 5.65, R, 3)
text(s, 7.72, 5.7, 2.38, .28, 'Q1      Trung vị      Q3', 15, False, MUTED, PP_ALIGN.CENTER)
text(s, 6.57, 6.17, 4.87, .4, 'Sơ đồ box plot minh họa cách đọc phân phối', 16, False, MUTED, PP_ALIGN.CENTER)
speech(s, 'Sankey là ảnh thật: mặc định chọn năm 2026, top 15 tuyến, dữ liệu chỉ quý I. Box bên dưới là sơ đồ cách đọc, không phải dữ liệu BTS được vẽ lại. Trang phân phối có thể lọc all hoặc late, arrival hoặc departure theo mức của bảng, và xem tỷ lệ ngoại lệ theo hàng rào Tukey cùng bảng phân vị/số mẫu. Dữ liệu & vận hành hiển thị số document theo manifest, không phải kết quả đếm trực tiếp theo thời gian thực; export/ingest timestamp không phải ngày thu thập BTS. Trang Streaming hiện chưa có nguồn M4 được nối để trình bày KPI thực tế; không suy diễn lịch sử thành dữ liệu live. Nguồn: app.py show_routes, show_boxes, show_status và show_streaming.')

# Remove the original review content; preserve its layouts, master and artwork.
for _ in original:
    sid = prs.slides._sldIdLst[0]
    prs.part.drop_rel(sid.rId)
    prs.slides._sldIdLst.remove(sid)

assert len(prs.slides) == 14
prs.core_properties.title = 'Task M5 — Diễn giải sáu nhiệm vụ từ lý thuyết tới thực tế'
prs.core_properties.subject = '14 slide; các gạch đầu dòng là câu diễn giải hoàn chỉnh'
prs.core_properties.author = 'Project BigData — M5'
prs.core_properties.keywords = 'M5, M2, MongoDB, Docker, serving, dashboard'
prs.core_properties.comments = 'Template RIVF paper review.pptx; Lato; six named sections.'
prs.save(OUT)
(ASSETS/'prose14_inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
(ASSETS/'prose14_sections.json').write_text(json.dumps([{'name':name, 'start':start} for name,start in zip(SECTION_NAMES,SECTION_STARTS)], ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Saved 14 explanatory slides: {OUT}')
