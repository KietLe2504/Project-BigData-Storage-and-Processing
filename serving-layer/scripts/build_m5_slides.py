"""Build the Vietnamese M5 deck by reusing the user's PowerPoint template.

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
OUT = ROOT / 'serving-layer/doc_guide/M5_6_TASKS_PRESENTATION.pptx'
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


# 01 — preserve the cover's logo and illustration exactly.
s = clone(2, 1)
shapes = {sh.shape_id: sh for sh in s.shapes}
heading = shapes[3]
heading.top, heading.height = Inches(2.05), Inches(1.75)
write(heading, 'TASK M5\nTừ output M2 đến MongoDB\nvà dashboard', 36, True, R)
style_paragraph(heading.text_frame.paragraphs[0], 26, False, R)
subtitle = shapes[4]
subtitle.top, subtitle.width, subtitle.height = Inches(3.98), Inches(9.4), Inches(.9)
write(subtitle, '6 nhiệm vụ để đưa KPI lịch sử lên web\nBig Data Storage & Processing · BTS', 22, False, INK)
file_icon(s, .53, 5.17, 2.5, 1.03, 'KPI từ M2')
arrow(s, 3.2, 5.57, .48, .26)
db(s, 3.9, 5.08, 2.5, 1.22, 'MongoDB')
arrow(s, 6.57, 5.57, .48, .26)
mini_chart(s, 7.28, 5.08, 2.6, 1.22, title='Dashboard')
notes(s, '''M5 là phần NoSQL và dashboard của project. M2 đã dùng Spark để làm sạch dữ liệu BTS và tính KPI. M5 tiếp nhận các bảng đã tổng hợp, kiểm tra rồi đưa vào MongoDB để truy vấn và hiển thị trên web. Người xem cuối cùng muốn trả lời các câu hỏi như: có bao nhiêu chuyến, tỷ lệ đúng giờ là bao nhiêu, tuyến nào đông, độ trễ phân bố thế nào. Bài trình bày đi theo đúng sáu nhiệm vụ, từ dữ liệu đầu vào tới giao diện. Phạm vi ở đây là lịch sử từ M2; tích hợp streaming M4 là công việc riêng khi có hợp đồng dữ liệu. Các sơ đồ là shape PowerPoint có thể sửa; ảnh giao diện được chụp từ dashboard thật. Template giữ nguyên nguồn RIVF paper review.pptx.''')

# 02 — overview of six tasks.
s = base(2, 'M5 gồm 6 task nối tiếp nhau', 'Bức tranh chung',
         'Mục tiêu: dữ liệu đúng, nạp lại an toàn và người dùng tra cứu được trên web.')
for x, title, sub in [(.6, 'M2 · dữ liệu tổng hợp', 'JSONL / KPI Parquet'),
                      (4.55, 'M5 · lớp phục vụ dữ liệu', 'Kiểm tra → lưu → truy vấn'),
                      (8.5, 'Người dùng · dashboard', 'Bộ lọc + KPI + biểu đồ')]:
    rect(s, x, 1.95, 3.05, .92, CREAM, radius=True)
    text(s, x+.12, 2.07, 2.81, .32, title, 18, True, R, PP_ALIGN.CENTER)
    text(s, x+.12, 2.49, 2.81, .25, sub, 15, False, MUTED, PP_ALIGN.CENTER)
arrow(s, 3.83, 2.31, .44, .25)
arrow(s, 7.78, 2.31, .44, .25)
items = [('Nhận & kiểm tra', 'Hiểu bảng, khóa\nvà khoảng thời gian.'),
         ('Thiết kế MongoDB', 'Collection, document,\nkhóa duy nhất, index.'),
         ('Dựng môi trường', 'MongoDB + loader + web\nchạy bằng Docker.'),
         ('Xây bộ nạp', 'Nạp, kiểm tra lại,\nrồi công bố dữ liệu.'),
         ('Truy vấn & tính KPI', 'Lọc đúng mức;\ngộp và tính KPI đúng.'),
         ('Xây dashboard', 'Xem KPI, biểu đồ\nvà tải dữ liệu.')]
for i, (heading, body) in enumerate(items):
    x, y = .6+(i%3)*3.95, 3.25+(i//3)*1.57
    rect(s, x, y, 3.05, 1.36, LIGHT, LINE, True)
    badge(s, x+.15, y+.15, i+1, diameter=.34)
    text(s, x+.61, y+.16, 2.3, .31, heading, 18, True, R)
    text(s, x+.17, y+.65, 2.7, .61, body, 17)
notes(s, '''Có thể đọc M5 như một dây chuyền sáu bước. Đầu tiên phải hiểu và kiểm tra sản phẩm M2. Tiếp theo thiết kế cách lưu, rồi dựng môi trường chạy. Khi có hai phần đó mới nạp và công bố dữ liệu. Sau đó xây các truy vấn đúng mức tổng hợp, cuối cùng trình bày kết quả bằng dashboard. Đầu vào chính hiện tại là snapshot JSONL kèm manifest xuất từ M2. Nhánh đọc KPI Parquet trên HDFS cũng dùng chung cơ chế ghi. Đầu ra không chỉ là một trang web: còn có dữ liệu MongoDB, index, chương trình nạp, báo cáo kiểm chứng, cấu hình triển khai và hướng dẫn vận hành. Mỗi nhiệm vụ ở các slide sau đều có đầu vào, thao tác và kết quả cụ thể.''')

# 03 — actual input and grain.
s = base(3, '1. Tiếp nhận: nhận đúng dữ liệu từ M2', 'Task 1 / 6 · Đầu vào',
         'Snapshot = một bộ file M2 đã xuất; mỗi dòng KPI đại diện cho một nhóm.')
rect(s, .6, 1.95, 4.1, 3.5, CREAM, LINE, True)
text(s, .82, 2.16, 3.65, .36, 'Thư mục snapshot M2', 21, True, R)
file_icon(s, .9, 2.83, 1.35, 1.04, 'manifest\n.json', size=16)
text(s, 2.47, 2.89, 1.98, .95, 'Danh sách bảng,\nkhóa, schema, số dòng', 17)
file_icon(s, .9, 4.15, 1.35, 1.03, '20 file\nJSONL', size=16)
text(s, 2.47, 4.2, 1.98, .89, '13 bảng KPI\n+ 7 bảng box plot', 17)
arrow(s, 4.94, 3.55, .48, .26)
text(s, 5.72, 2.13, 5.7, .35, 'Đọc “mỗi dòng là gì” trước khi nạp', 21, True, R)
for y, name, grain in [(2.86, 'month_overall', '1 dòng = 1 năm + 1 tháng'),
                        (3.67, 'year_carrier', '1 dòng = 1 năm + 1 hãng bay'),
                        (4.48, 'year_route', '1 dòng = 1 năm + sân bay đi + đến')]:
    label(s, 5.72, y, 2.43, name, size=16)
    text(s, 8.4, y+.02, 3.12, .61, grain, 17)
for x, big, small in [(.6, '20 bảng', 'Bộ đầu vào đầy đủ'), (4.55, '74.921 dòng', 'KPI và phân phối đã tổng hợp'),
                       (8.5, '51 tháng', '01/2022 → 03/2026')]:
    text(s, x, 5.78, 3.05, .47, big, 27, True, R, PP_ALIGN.CENTER)
    text(s, x, 6.35, 3.05, .3, small, 15, False, MUTED, PP_ALIGN.CENTER)
notes(s, '''Snapshot được dùng trong project là batch-layer/spark_jobs/export/m2_to_m5/20261107T042703414867Z. Nó gồm manifest.json, các file JSONL và CSV phục vụ bàn giao. Loader hiện tại đọc JSONL và manifest; CSV có thể xem bằng Excel nhưng không phải đầu vào nạp chính. Manifest là bản mô tả: có những bảng nào, mỗi bảng bao nhiêu dòng, khóa là gì và kiểu dữ liệu ra sao. Có 13 bảng KPI, 7 bảng phân phối, tổng cộng 74.921 dòng đã tổng hợp. Đây không phải 74.921 chuyến: số chuyến sau cleaning là 29.328.846. Ví dụ month_overall có mỗi dòng cho một năm–tháng, year_carrier có mỗi dòng cho một năm–hãng. Phải hiểu đúng mức này để tránh cộng chồng các bảng về sau. Dữ liệu bao phủ 51 tháng từ 01/2022 đến 03/2026; năm 2026 chỉ có quý I. Nguồn: manifest và m5/contracts.py.''')

# 04 — validation gates.
s = base(4, '1. Kiểm tra: dữ liệu đủ và đúng mới được nạp', 'Task 1 / 6 · Kiểm tra',
         'Chạy CheckOnly để phát hiện lỗi đầu vào trước khi ghi vào MongoDB.')
checks = [('Đủ file & bảng', '13 KPI + 7 box.\nCác file có đủ.'),
          ('Đúng cấu trúc', 'Đúng cột và kiểu;\nkhóa không null.'),
          ('Đúng số dòng', 'Khớp số dòng;\nkhông trùng khóa.'),
          ('Đúng phạm vi', 'Đủ 51 tháng;\nđúng tổng chuyến.')]
for i, (h, b) in enumerate(checks):
    x = .6+i*2.85
    rect(s, x, 2.18, 2.57, 2.56, LIGHT, LINE, True)
    badge(s, x+.98, 2.42, i+1, diameter=.5)
    text(s, x+.13, 3.12, 2.31, .4, h, 19, True, R, PP_ALIGN.CENTER)
    text(s, x+.17, 3.73, 2.23, .85, b, 17, False, INK, PP_ALIGN.CENTER)
    if i < 3:
        arrow(s, x+2.65, 3.35, .16, .21)
rect(s, .6, 5.17, 7.8, 1.23, CREAM, radius=True)
text(s, .85, 5.35, 7.3, .3, 'PowerShell · $M5Snapshot là đường dẫn thư mục snapshot', 14, True, G)
text(s, .85, 5.83, 7.3, .35, '.\\scripts\\load_m2.ps1 -SnapshotPath $M5Snapshot -CheckOnly', 17, False, R)
label(s, 8.76, 5.17, 2.97, 'PASS → sang bước nạp', GREEN, 'ECF5EF', 17)
text(s, 8.84, 5.84, 2.75, .61, 'Có lỗi → sửa nguồn,\nrồi kiểm tra lại.', 17)
notes(s, '''Bước này là cổng kiểm soát đầu vào. Chạy .\\scripts\\load_m2.ps1 -SnapshotPath $M5Snapshot -CheckOnly trong PowerShell tại serving-layer. Trước đó đặt $M5Snapshot bằng đường dẫn thư mục chứa manifest.json; xem hướng dẫn chi tiết để có câu lệnh đầy đủ. CheckOnly kiểm tra mà không ghi MongoDB và có thể chạy không cần MongoDB đang bật. Chương trình kiểm tra đúng 20 bảng, cấu trúc schema, kiểu scalar, khóa không null, không trùng khóa nghiệp vụ, số dòng, khoảng thời gian và tổng chuyến. Nó cũng tính fingerprint nội dung phục vụ đối chiếu về sau. Nếu có lỗi, phải sửa file xuất hoặc chạy lại phần export M2; không bỏ qua lỗi để nạp tiếp. PASS xác nhận tuân thủ hợp đồng bàn giao và tính toàn vẹn, không thay thế việc chứng minh công thức Spark ở M2 là đúng. Nguồn: m5/contracts.py và scripts/load_m2.ps1.''')

# 05 — design database/document.
s = base(5, '2. Thiết kế MongoDB: bảng → collection → document', 'Task 2 / 6 · Lưu trữ',
         'Giữ nguyên trường và giá trị của M2; thêm snapshot_id để phân biệt mỗi phiên bản.')
file_icon(s, .6, 2.09, 3.2, .97, 'kpi__month_overall.jsonl', size=17)
arrow(s, 1.93, 3.23, .38, .36, down=True)
db(s, .92, 3.85, 2.56, 1.28, 'kpi_month_overall', font_size=17)
text(s, .65, 5.43, 3.1, .82, '1 bảng → 1 collection\n1 dòng → 1 document', 20, True, R, PP_ALIGN.CENTER)
arrow(s, 3.95, 4.28, .43, .25)
rect(s, 4.72, 1.99, 6.99, 3.42, LIGHT, LINE, True)
text(s, 4.96, 2.18, 6.49, .3, 'Document thực tế · rút gọn để minh họa', 15, True, MUTED)
text(s, 5.02, 2.73, 6.32, 2.48,
     '{\n  snapshot_id: "633c62bf…",\n  year: 2025, month: 1,\n  flights: 539747,\n  on_time: 424139, arr_n: 522269,\n  otp_operated: 0.812108…\n}', 19)
label(s, 4.72, 5.69, 6.99, 'Khóa duy nhất: snapshot_id + year + month', size=17)
text(s, 4.83, 6.22, 6.72, .35, 'Index hỗ trợ bộ lọc theo năm, hãng, sân bay và tuyến.', 17)
notes(s, '''Collection có thể hiểu gần giống một bảng; document giống một dòng được lưu dưới dạng cặp tên trường–giá trị. Mỗi bảng M2 ánh xạ sang một collection, ví dụ file kpi__month_overall.jsonl vào kpi_month_overall. Database mặc định là aero_m5, có 13 collection KPI và 7 collection box, cộng các collection quản lý. Ví dụ bên phải là dòng tháng 01/2025, rút gọn một số trường; snapshot_id được rút ngắn khi trình bày nhưng lưu đầy đủ trong MongoDB. Unique index gồm snapshot_id và toàn bộ keys trong manifest. Với bảng theo hãng thì thêm carrier; bảng box thêm cả var và population. Nhờ vậy cùng một nhóm trong cùng snapshot không bị ghi trùng. Các index bổ sung hỗ trợ truy vấn thực tế; muốn kết luận nhanh tới đâu cần đo explain, không khẳng định mọi truy vấn đều được tăng tốc. Tỷ lệ lưu 0–1; chỉ nhân 100 ở giao diện. Nguồn: m5/mongo.py, contracts.py, snapshot tháng 01/2025.''')

# 06 — infrastructure diagram.
s = base(6, '3. Dựng môi trường: MongoDB, loader và dashboard', 'Task 3 / 6 · Hạ tầng chạy',
         'Docker Compose khởi động các dịch vụ và nối chúng trong cùng một mạng.')
rect(s, 3.63, 1.98, 8.08, 3.69, LIGHT, LINE, True)
text(s, 3.85, 2.12, 7.56, .3, 'DOCKER DESKTOP · Compose project: aero-serving', 15, True, G)
rect(s, .6, 2.62, 2.55, 1.23, CREAM, radius=True)
text(s, .78, 2.8, 2.19, .43, 'Trình duyệt', 22, True, R, PP_ALIGN.CENTER)
text(s, .72, 3.29, 2.31, .32, 'localhost:8501', 18, False, INK, PP_ALIGN.CENTER)
arrow(s, 3.25, 3.11, .25, .24)
card(s, 4, 2.68, 2.88, 1.87, 'Dashboard', 'Streamlit + Plotly\nTruy vấn và vẽ biểu đồ', size=16)
arrow(s, 7.1, 3.37, .4, .25)
db(s, 7.8, 2.71, 3.38, 1.84, 'MongoDB\naero_m5', font_size=22)
file_icon(s, .6, 4.4, 2.55, 1.03, 'Snapshot JSONL', size=17)
arrow(s, 3.25, 4.81, .25, .24)
rect(s, 4, 4.88, 2.88, .57, CREAM, radius=True)
write(s.shapes[-1], 'Loader · chạy khi cần nạp', 16, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
line(s, 7.08, 5.14, 9.48, 5.14, O, 1.5)
arrow(s, 9.3, 4.64, .35, .4, down=True).rotation = 180
rect(s, 8.04, 5.87, 3.42, .65, CREAM, LINE, True)
write(s.shapes[-1], 'Volume: m5_mongo_data', 17, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
arrow(s, 9.48, 5.49, .28, .28, down=True)
text(s, .63, 5.9, 6.98, .69, 'Volume giữ dữ liệu sau khi dừng container.\nMongoDB có thể xem qua mongosh hoặc Compass.', 17)
notes(s, '''Máy Windows cần Docker Desktop đang chạy. Compose tạo MongoDB, dashboard và công cụ loader. Dashboard là ứng dụng Streamlit sử dụng Plotly để vẽ biểu đồ; nó đọc dữ liệu từ MongoDB qua tên dịch vụ mongo:27017 bên trong mạng Docker. Trình duyệt ở máy người dùng vào http://localhost:8501. Cổng MongoDB mặc định 127.0.0.1:27017 dành cho Compass hoặc công cụ trên máy; không cần cài riêng MongoDB Server trên Windows vì server đã ở container. Loader được chạy theo nhu cầu, không phải dịch vụ web thường trực. Nó đọc snapshot được mount chỉ đọc và ghi vào MongoDB. Named volume m5_mongo_data ánh xạ tới /data/db để dữ liệu tồn tại khi container dừng hoặc tạo lại; lệnh down -v sẽ xóa volume nên không dùng để dừng thường ngày. Khởi động bằng .\\scripts\\start_m5.ps1 trong PowerShell tại serving-layer, rồi kiểm tra hai dịch vụ healthy. Sơ đồ thể hiện quan hệ đọc/ghi, không phải vị trí vật lý của file. Nguồn: compose.yml, Dockerfile và scripts/start_m5.ps1.''')

# 07 — loader.
s = base(7, '4. Bộ nạp: đọc → kiểm tra → ghi → đối chiếu → công bố', 'Task 4 / 6 · Nạp dữ liệu',
         'Chỉ công bố dữ liệu cho dashboard sau khi kết quả trong MongoDB khớp nguồn.')
for x, title, body in [(.6, 'JSONL + manifest', 'Luồng đang dùng'), (4.55, 'KPI Parquet / HDFS', 'Luồng thay thế qua Spark')]:
    file_icon(s, x, 1.98, 3.05, 1.08, title, size=18)
    text(s, x, 3.18, 3.05, .3, body, 15, False, MUTED, PP_ALIGN.CENTER)
text(s, 3.76, 2.42, .62, .32, 'hoặc', 17, True, G, PP_ALIGN.CENTER)
text(s, 8.56, 2.15, 3.06, .95, '2 nguồn đọc thay thế,\n1 bộ ghi MongoDB', 20, True, R)
steps = [('Đọc', 'Hiểu schema\nvà khóa nhóm'), ('Kiểm tra', 'Xác nhận nguồn\nđủ và đúng'),
         ('Upsert', 'Có thì cập nhật;\nchưa có thì thêm'), ('Đối chiếu', 'So số dòng\nvà nội dung'),
         ('Công bố', 'Chọn bản mới\ncho dashboard')]
for i, (h, b) in enumerate(steps):
    x = .6+i*2.25
    rect(s, x, 3.9, 2.02, 1.61, CREAM if i == 4 else LIGHT, LINE, True)
    text(s, x+.09, 4.12, 1.84, .34, h, 21, True, R, PP_ALIGN.CENTER)
    text(s, x+.1, 4.72, 1.82, .64, b, 16, False, INK, PP_ALIGN.CENTER)
    if i < 4:
        arrow(s, x+2.07, 4.6, .14, .2)
rect(s, .6, 5.91, 11.12, .64, CREAM, radius=True)
write(s.shapes[-1], 'Kết quả: 20 collection dữ liệu + báo cáo nạp + snapshot được phép phục vụ',
      19, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
notes(s, '''Luồng chính trong project đọc snapshot JSONL. Nếu đọc trực tiếp KPI Parquet trên HDFS thì dùng adapter Spark trong m5/load_parquet.py và cấu hình compose.hdfs.yml; không đọc lại 29 triệu dòng raw trong luồng phục vụ thông thường. Cả hai đi qua bộ ghi chung. Loader kiểm tra toàn bộ đầu vào trước khi ghi, tạo snapshot_id từ fingerprint nội dung, dùng upsert theo snapshot_id và khóa nghiệp vụ. Dữ liệu được gửi theo lô 1.000 thao tác. Sau khi nạp, chương trình đọc lại dữ liệu MongoDB và so digest từng scalar cùng số dòng. Chỉ khi tất cả khớp mới cập nhật serving_state để dashboard nhìn thấy snapshot mới. Lệnh PowerShell chạy ở serving-layer là .\\scripts\\load_m2.ps1 -SnapshotPath $M5Snapshot, sau khi CheckOnly PASS. Báo cáo và log là bằng chứng ingest; verifier độc lập chạy bằng .\\scripts\\verify_m5.ps1. Nguồn: load_batch.py, load_parquet.py, batch_writer.py, verify_batch.py.''')

# 08 — safe publication.
s = base(8, '4. Nạp an toàn: không trùng, không phục vụ bản dở', 'Task 4 / 6 · Tính nhất quán',
         'Dashboard tiếp tục dùng bản A trong khi bản B đang được nạp và kiểm tra.')
db(s, .8, 2.22, 2.71, 1.6, 'Snapshot A\nĐã công bố', font_size=21)
db(s, 5.03, 2.22, 2.71, 1.6, 'Snapshot B\nĐang nạp', font_size=21)
mini_chart(s, 9.11, 2.23, 2.47, 1.4)
text(s, 9.11, 3.84, 2.47, .32, 'Dashboard', 19, True, R, PP_ALIGN.CENTER)
line(s, 2.14, 4.06, 10.31, 4.06, GREEN, 2)
text(s, 3.04, 4.25, 6.8, .37, 'Bản đang phục vụ (active) → A', 19, True, GREEN, PP_ALIGN.CENTER)
arrow(s, 7.95, 2.89, .71, .27)
label(s, 7.99, 2.35, .85, 'PASS', GREEN, 'ECF5EF', 14)
text(s, 4.88, 5.1, 3.0, .71, 'B kiểm tra thành công\n→ active chuyển sang B', 18, True, GREEN, PP_ALIGN.CENTER)
text(s, 8.7, 5.1, 2.96, .71, 'B bị lỗi\n→ vẫn giữ bản A', 18, True, R, PP_ALIGN.CENTER)
rect(s, .6, 5.04, 3.47, 1.35, CREAM, radius=True)
text(s, .8, 5.22, 3.07, .93, 'Nạp lại cùng dữ liệu\nKhông tạo thêm bản ghi\nKhông tự quay về bản cũ', 18, True, R)
notes(s, '''snapshot_id là định danh theo nội dung, giúp phân biệt các phiên bản dữ liệu. Trong lúc đang nạp B, serving_state vẫn trỏ A nên dashboard không nhìn thấy B đang dở. Nếu kiểm tra B thành công thì con trỏ mới chuyển tới B; nếu thất bại thì vẫn dùng A. Mỗi lượt chạy dashboard lấy con trỏ một lần và lọc đúng snapshot cho các truy vấn trong lượt đó. Unique index và upsert tránh trùng theo khóa. Snapshot đã công bố được coi là bất biến: nạp lại cùng nội dung trả ALREADY_LOADED và không tạo document trùng. Nạp lại một snapshot cũ đã công bố cũng không tự chuyển con trỏ active ngược về quá khứ. Snapshot thất bại có thể thử lại. Loader có lease để tránh hai lần nạp xung đột; không tự xóa bản cũ. Đây là lý do M5 cần thêm metadata ngoài 20 collection dữ liệu. Sơ đồ A/B là minh họa cơ chế, không khẳng định hiện tại đang có hai snapshot trong database. Nguồn: batch_writer.py, mongo.py.''')

# 09 — correct queries and actual example.
s = base(9, '5. Truy vấn: từ câu hỏi tới đúng bảng và bộ lọc', 'Task 5 / 6 · Tra cứu',
         'Ví dụ: “Tháng 01/2025 có bao nhiêu chuyến và tỷ lệ đúng giờ là bao nhiêu?”')
card(s, .6, 2.05, 3.13, 2.13, '1 · Chọn đúng mức', 'kpi_month_overall\nMỗi dòng = năm + tháng', size=18)
arrow(s, 3.94, 2.98, .37, .24)
card(s, 4.53, 2.05, 3.13, 2.13, '2 · Lọc đúng bản', 'snapshot_id = active\nyear = 2025; month = 1', size=18)
arrow(s, 7.88, 2.98, .37, .24)
card(s, 8.47, 2.05, 3.13, 2.13, '3 · Đọc kết quả', 'Số chuyến, số đúng giờ\nvà mẫu số hợp lệ', size=18)
for x, big, small in [(.6, '539.747', 'chuyến trong tháng'), (4.55, '424.139 / 522.269', 'đúng giờ / chuyến đến hợp lệ'),
                       (8.5, '81,21%', 'tỷ lệ đúng giờ')]:
    text(s, x, 4.67, 3.13, .58, big, 26 if x != 4.55 else 24, True, R, PP_ALIGN.CENTER)
    text(s, x, 5.38, 3.13, .46, small, 16, False, MUTED, PP_ALIGN.CENTER)
rect(s, .6, 6.03, 11.1, .51, CREAM, radius=True)
write(s.shapes[-1], 'Bảng tuyến chỉ có mức năm → không giả lập bộ lọc tháng hoặc hãng.', 18,
      True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
notes(s, '''Với câu hỏi tháng 01/2025, dùng kpi_month_overall chứ không cộng bảng overall với bảng carrier hay origin vì các bảng đó mô tả lại cùng tập chuyến. Lấy snapshot active từ serving_state và lọc year=2025, month=1. Dữ liệu thật cho biết flights=539747, on_time=424139, arr_n=522269. Tỷ lệ đúng giờ là on_time/arr_n = 0,812108… và giao diện hiển thị 81,21%. Tổng chuyến khác mẫu số chuyến đến hợp lệ, do đó không lấy flights thay arr_n. Các màn hình khác phải chọn bảng có đúng chiều dữ liệu mà nguồn cung cấp. Ví dụ KPI tuyến có mức năm, origin và dest; không có chiều tháng hay hãng, nên giao diện không được ngầm áp dụng các bộ lọc không tồn tại. Với hãng hoặc sân bay, dùng bảng carrier/origin tương ứng. Nguồn số liệu: kpi__month_overall.jsonl trong snapshot; nguồn logic: queries.py, metrics.py, app.py.''')

# 10 — weighted arithmetic; explicit illustrative example.
s = base(10, '5. Tính KPI: cộng số đếm rồi mới chia', 'Task 5 / 6 · Tính toán hiển thị',
         'Ví dụ minh họa: hai nhóm có quy mô khác nhau nên không lấy trung bình tỷ lệ.')
for x, heading, count, rate, fraction in [(.6, 'Nhóm A', '9 / 10 chuyến đúng giờ', '90%', .9),
                                         (4.1, 'Nhóm B', '50 / 100 chuyến đúng giờ', '50%', .5)]:
    rect(s, x, 2.02, 3.03, 2.12, LIGHT, LINE, True)
    text(s, x+.15, 2.2, 2.73, .35, heading, 21, True, R)
    text(s, x+.15, 2.85, 2.73, .35, count, 17)
    rect(s, x+.15, 3.5, 2.04, .23, 'E5E1DD')
    rect(s, x+.15, 3.5, 2.04*fraction, .23, O)
    text(s, x+2.28, 3.43, .64, .4, rate, 18, True, R)
text(s, 7.54, 2.07, 4.05, .33, 'TỶ LỆ ĐÚNG KHI GỘP NHÓM', 16, True, GREEN)
text(s, 7.54, 2.71, 4.05, .43, '(9 + 50) / (10 + 100)', 25, True, GREEN)
text(s, 7.54, 3.35, 4.05, .64, '= 53,6%', 36, True, GREEN)
rect(s, .6, 4.63, 6.56, .67, 'FBEDED', radius=True)
write(s.shapes[-1], 'Sai: (90% + 50%) / 2 = 70%', 21, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
for x, h, b in [(.6, 'Tỷ lệ lưu 0–1', 'Hiển thị %: nhân 100.'),
                 (4.55, 'Null không phải 0', 'Thiếu dữ liệu phải giữ null.'),
                 (8.5, 'Delay có thể âm', 'Đến sớm vẫn là giá trị hợp lệ.')]:
    text(s, x, 5.75, 3.14, .34, h, 20, True, R)
    text(s, x, 6.24, 3.14, .4, b, 16)
notes(s, '''Đây là số minh họa cho công thức, không phải một thống kê BTS thật. Nhóm A có 9 chuyến đúng giờ trên 10 chuyến hợp lệ, tỷ lệ 90%. Nhóm B có 50 trên 100, tỷ lệ 50%. Lấy trung bình 90 và 50 ra 70% là sai vì nhóm A chỉ có 10 chuyến trong khi B có 100 chuyến. Phải cộng tử số và mẫu số: 59/110=53,636…%, làm tròn 53,6%. Trong code, OTP tổng là sum(on_time)/sum(arr_n), hủy chuyến là sum(cancelled)/sum(flights); các chỉ tiêu khác dùng đúng mẫu số hợp đồng. Không cộng các bảng khác mức để tránh đếm lặp. Không lấy trung bình percentile/median để suy ra percentile tổng, vì phân vị không có tính cộng. Nếu cần box của nhóm lớn thì dùng đúng bảng box đã tính sẵn. Giá trị tỷ lệ lưu dưới dạng fraction 0–1; null không tự biến thành 0; delay âm thể hiện đến sớm. Nguồn: m5/metrics.py và hợp đồng M2.''')

# 11 — actual overview screenshot, preserve source wide-image layout.
s = base(11, '6. Dashboard: đọc nhanh KPI và xu hướng', 'Task 6 / 6 · Giao diện tổng quan',
         'Web đọc dữ liệu đã công bố trong MongoDB, rồi vẽ KPI và biểu đồ tương tác.', exemplar=8)
old_pic = next(sh for sh in s.shapes if sh.shape_type == 13)
fit_image(s, ASSETS/'dashboard_overview_focus.png', .6, 2.04, 11.08, 4.1, old_pic)
for x, n, caption in [(.64, 1, 'Lọc năm / tháng'), (4.42, 2, 'Đọc KPI và xu hướng'), (8.27, 3, 'Hover · zoom · tải dữ liệu')]:
    badge(s, x, 6.27, n, diameter=.33)
    text(s, x+.45, 6.28, 3.05, .35, caption, 16, True, R)
notes(s, '''Đây là ảnh dashboard thật trên localhost:8501, không phải bản mockup. Ảnh chụp phần tổng quan ở phạm vi toàn bộ lịch sử 01/2022–03/2026. Các thẻ phía trên hiển thị 29.328.846 chuyến sau cleaning, 78,8% đúng giờ, 21,2% trễ từ 15 phút, 1,8% hủy và delay đến trung bình 7,3 phút theo định nghĩa hiện tại. Biểu đồ trái cho biết lưu lượng thay đổi theo tháng; donut bên phải phân chia các nhóm chuyến đến có dữ liệu hợp lệ. Mỗi chỉ tiêu phải đọc kèm mẫu số, chú giải và phạm vi nguồn. Bộ lọc được đặt phía trên vùng được chụp; ảnh này tập trung vào kết quả. Mở web bằng trình duyệt tại http://localhost:8501 sau khi MongoDB và dashboard healthy. Người dùng chọn phạm vi, đọc KPI, rồi hover/zoom hoặc dùng xuất dữ liệu theo chức năng từng màn hình. Năm 2026 chỉ có quý I nên không so cả năm với năm đầy đủ mà thiếu chú thích. Nguồn ảnh: dashboard thực tế của project, chụp ngày 08/11/2026.''')

# 12 — visual questions and delivery criteria.
s = base(12, '6. Dashboard: mỗi biểu đồ trả lời một câu hỏi', 'Task 6 / 6 · Khám phá & bàn giao',
         'Chọn cách nhìn theo câu hỏi: lưu lượng tuyến, so sánh nhóm hay phân phối độ trễ.', exemplar=8)
old_pic = next(sh for sh in s.shapes if sh.shape_type == 13)
text(s, .6, 1.98, 6.9, .35, 'Tuyến nào có nhiều chuyến?', 21, True, R)
fit_image(s, ASSETS/'dashboard_routes_focus.png', .6, 2.55, 6.9, 2.36, old_pic)
text(s, .65, 5.08, 6.8, .68, 'Sankey thật · Top 15 tuyến năm 2026 (Q1).\nDải rộng hơn biểu thị nhiều chuyến hơn.', 16)
text(s, 8.02, 1.98, 3.61, .65, 'Độ trễ phân bố thế nào?', 21, True, R)
rect(s, 8.02, 2.87, 3.61, 2.04, LIGHT, LINE, True)
text(s, 8.2, 3.05, 3.25, .29, 'Box plot · minh họa cách đọc', 14, False, MUTED)
line(s, 8.4, 4.05, 11.26, 4.05, O, 2)
line(s, 8.4, 3.8, 8.4, 4.3, O, 2)
line(s, 11.26, 3.8, 11.26, 4.3, O, 2)
rect(s, 9.08, 3.65, 1.42, .8, CREAM, O)
line(s, 9.7, 3.65, 9.7, 4.45, R, 2.6)
text(s, 8.53, 4.57, 2.98, .27, 'Q1       Trung vị       Q3', 14, False, MUTED, PP_ALIGN.CENTER)
text(s, 8.06, 5.08, 3.55, .68, 'Hộp chứa 50% giá trị giữa.\nVạch trong hộp là trung vị.', 16)
rect(s, .6, 6.04, 11.08, .57, CREAM, radius=True)
write(s.shapes[-1], 'M5 hoàn thành: nạp đúng & không trùng  •  truy vấn đúng KPI  •  web chạy và có hướng dẫn',
      17, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
notes(s, '''Sankey bên trái là ảnh thật của màn hình Tuyến bay: top 15 tuyến có nhiều chuyến nhất, năm mặc định 2026, chỉ bao phủ tháng 1–3. Độ rộng dải theo số chuyến; đây không phải toàn bộ mạng bay. Origin bên trái, destination bên phải. Nếu muốn so năm nên chọn cùng kỳ hoặc ghi rõ giới hạn mức tổng hợp; bảng tuyến chỉ có năm nên không có bộ lọc tháng. Box plot bên phải là sơ đồ minh họa cách đọc, không phải ảnh hay số đo BTS. Hộp từ Q1 tới Q3 chứa 50% giá trị giữa, vạch là trung vị; râu cần đọc theo định nghĩa dữ liệu xuất M2. Không lấy trung bình các phân vị để gộp box. Dashboard còn có các trang thời gian, hãng bay, sân bay và phân phối. Khi bàn giao, phải có môi trường chạy được, nguồn đầu vào đã kiểm tra, dữ liệu MongoDB được xác minh, nạp lại không trùng, các truy vấn đúng, giao diện và hướng dẫn để thành viên khác tự khởi động. Tài liệu thao tác: serving-layer/doc_guide/HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md. Luồng streaming và triển khai Kubernetes là phạm vi mở rộng, chưa phải điều kiện của sáu task dùng output M2 này.''')

# Remove the original content slides, leaving their template/layout parts intact.
for _ in original:
    sid = prs.slides._sldIdLst[0]
    prs.part.drop_rel(sid.rId)
    prs.slides._sldIdLst.remove(sid)

prs.core_properties.title = 'M5 — Từ output M2 đến MongoDB và dashboard'
prs.core_properties.subject = 'Sáu nhiệm vụ của lớp NoSQL và dashboard'
prs.core_properties.author = 'Project BigData — M5'
prs.core_properties.keywords = 'M5, M2, MongoDB, Docker, dashboard, BTS'
prs.core_properties.comments = 'Template: RIVF paper review.pptx. Editable diagrams; actual project screenshots.'
OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
(ASSETS/'slide_inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Saved {len(prs.slides)} slides: {OUT}')
