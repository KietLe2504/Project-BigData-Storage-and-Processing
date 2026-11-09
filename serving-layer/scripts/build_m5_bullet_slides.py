"""Build the bullet-and-illustration M5 deck by reusing the user's PowerPoint template.

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
OUT = ROOT / 'serving-layer/doc_guide/M5_6_TASKS_BULLET.pptx'
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


SPEAKER_NOTES = [
    'M5 là phần NoSQL và dashboard của project. M2 đã dùng Spark để làm sạch dữ liệu BTS và tính KPI. M5 tiếp nhận các bảng đã tổng hợp, kiểm tra rồi đưa vào MongoDB để truy vấn và hiển thị trên web. Người xem cuối cùng muốn trả lời các câu hỏi như: có bao nhiêu chuyến, tỷ lệ đúng giờ là bao nhiêu, tuyến nào đông, độ trễ phân bố thế nào. Bài trình bày đi theo đúng sáu nhiệm vụ, từ dữ liệu đầu vào tới giao diện. Phạm vi ở đây là lịch sử từ M2; tích hợp streaming M4 là công việc riêng khi có hợp đồng dữ liệu. Các sơ đồ là shape PowerPoint có thể sửa; ảnh giao diện được chụp từ dashboard thật. Template giữ nguyên nguồn RIVF paper review.pptx.',
    'Có thể đọc M5 như một dây chuyền sáu bước. Đầu tiên phải hiểu và kiểm tra sản phẩm M2. Tiếp theo thiết kế cách lưu, rồi dựng môi trường chạy. Khi có hai phần đó mới nạp và công bố dữ liệu. Sau đó xây các truy vấn đúng mức tổng hợp, cuối cùng trình bày kết quả bằng dashboard. Đầu vào chính hiện tại là snapshot JSONL kèm manifest xuất từ M2. Nhánh đọc KPI Parquet trên HDFS cũng dùng chung cơ chế ghi. Đầu ra không chỉ là một trang web: còn có dữ liệu MongoDB, index, chương trình nạp, báo cáo kiểm chứng, cấu hình triển khai và hướng dẫn vận hành. Mỗi nhiệm vụ ở các slide sau đều có đầu vào, thao tác và kết quả cụ thể.',
    'Snapshot được dùng trong project là batch-layer/spark_jobs/export/m2_to_m5/20261107T042703414867Z. Nó gồm manifest.json, các file JSONL và CSV phục vụ bàn giao. Loader hiện tại đọc JSONL và manifest; CSV có thể xem bằng Excel nhưng không phải đầu vào nạp chính. Manifest là bản mô tả: có những bảng nào, mỗi bảng bao nhiêu dòng, khóa là gì và kiểu dữ liệu ra sao. Có 13 bảng KPI, 7 bảng phân phối, tổng cộng 74.921 dòng đã tổng hợp. Đây không phải 74.921 chuyến: số chuyến sau cleaning là 29.328.846. Ví dụ month_overall có mỗi dòng cho một năm–tháng, year_carrier có mỗi dòng cho một năm–hãng. Phải hiểu đúng mức này để tránh cộng chồng các bảng về sau. Dữ liệu bao phủ 51 tháng từ 01/2022 đến 03/2026; năm 2026 chỉ có quý I. Nguồn: manifest và m5/contracts.py.',
    'Bước này là cổng kiểm soát đầu vào. Chạy .\\scripts\\load_m2.ps1 -SnapshotPath $M5Snapshot -CheckOnly trong PowerShell tại serving-layer. Trước đó đặt $M5Snapshot bằng đường dẫn thư mục chứa manifest.json; xem hướng dẫn chi tiết để có câu lệnh đầy đủ. CheckOnly kiểm tra mà không ghi MongoDB và có thể chạy không cần MongoDB đang bật. Chương trình kiểm tra đúng 20 bảng, cấu trúc schema, kiểu scalar, khóa không null, không trùng khóa nghiệp vụ, số dòng, khoảng thời gian và tổng chuyến. Nó cũng tính fingerprint nội dung phục vụ đối chiếu về sau. Nếu có lỗi, phải sửa file xuất hoặc chạy lại phần export M2; không bỏ qua lỗi để nạp tiếp. PASS xác nhận tuân thủ hợp đồng bàn giao và tính toàn vẹn, không thay thế việc chứng minh công thức Spark ở M2 là đúng. Nguồn: m5/contracts.py và scripts/load_m2.ps1.',
    'Collection có thể hiểu gần giống một bảng; document giống một dòng được lưu dưới dạng cặp tên trường–giá trị. Mỗi bảng M2 ánh xạ sang một collection, ví dụ file kpi__month_overall.jsonl vào kpi_month_overall. Database mặc định là aero_m5, có 13 collection KPI và 7 collection box, cộng các collection quản lý. Ví dụ bên phải là dòng tháng 01/2025, rút gọn một số trường; snapshot_id được rút ngắn khi trình bày nhưng lưu đầy đủ trong MongoDB. Unique index gồm snapshot_id và toàn bộ keys trong manifest. Với bảng theo hãng thì thêm carrier; bảng box thêm cả var và population. Nhờ vậy cùng một nhóm trong cùng snapshot không bị ghi trùng. Các index bổ sung hỗ trợ truy vấn thực tế; muốn kết luận nhanh tới đâu cần đo explain, không khẳng định mọi truy vấn đều được tăng tốc. Tỷ lệ lưu 0–1; chỉ nhân 100 ở giao diện. Nguồn: m5/mongo.py, contracts.py, snapshot tháng 01/2025.',
    'Máy Windows cần Docker Desktop đang chạy. Compose tạo MongoDB, dashboard và công cụ loader. Dashboard là ứng dụng Streamlit sử dụng Plotly để vẽ biểu đồ; nó đọc dữ liệu từ MongoDB qua tên dịch vụ mongo:27017 bên trong mạng Docker. Trình duyệt ở máy người dùng vào http://localhost:8501. Cổng MongoDB mặc định 127.0.0.1:27017 dành cho Compass hoặc công cụ trên máy; không cần cài riêng MongoDB Server trên Windows vì server đã ở container. Loader được chạy theo nhu cầu, không phải dịch vụ web thường trực. Nó đọc snapshot được mount chỉ đọc và ghi vào MongoDB. Named volume m5_mongo_data ánh xạ tới /data/db để dữ liệu tồn tại khi container dừng hoặc tạo lại; lệnh down -v sẽ xóa volume nên không dùng để dừng thường ngày. Khởi động bằng .\\scripts\\start_m5.ps1 trong PowerShell tại serving-layer, rồi kiểm tra hai dịch vụ healthy. Sơ đồ thể hiện quan hệ đọc/ghi, không phải vị trí vật lý của file. Nguồn: compose.yml, Dockerfile và scripts/start_m5.ps1.',
    'Luồng chính trong project đọc snapshot JSONL. Nếu đọc trực tiếp KPI Parquet trên HDFS thì dùng adapter Spark trong m5/load_parquet.py và cấu hình compose.hdfs.yml; không đọc lại 29 triệu dòng raw trong luồng phục vụ thông thường. Cả hai đi qua bộ ghi chung. Loader kiểm tra toàn bộ đầu vào trước khi ghi, tạo snapshot_id từ fingerprint nội dung, dùng upsert theo snapshot_id và khóa nghiệp vụ. Dữ liệu được gửi theo lô 1.000 thao tác. Sau khi nạp, chương trình đọc lại dữ liệu MongoDB và so digest từng scalar cùng số dòng. Chỉ khi tất cả khớp mới cập nhật serving_state để dashboard nhìn thấy snapshot mới. Lệnh PowerShell chạy ở serving-layer là .\\scripts\\load_m2.ps1 -SnapshotPath $M5Snapshot, sau khi CheckOnly PASS. Báo cáo và log là bằng chứng ingest; verifier độc lập chạy bằng .\\scripts\\verify_m5.ps1. Nguồn: load_batch.py, load_parquet.py, batch_writer.py, verify_batch.py.',
    'snapshot_id là định danh theo nội dung, giúp phân biệt các phiên bản dữ liệu. Trong lúc đang nạp B, serving_state vẫn trỏ A nên dashboard không nhìn thấy B đang dở. Nếu kiểm tra B thành công thì con trỏ mới chuyển tới B; nếu thất bại thì vẫn dùng A. Mỗi lượt chạy dashboard lấy con trỏ một lần và lọc đúng snapshot cho các truy vấn trong lượt đó. Unique index và upsert tránh trùng theo khóa. Snapshot đã công bố được coi là bất biến: nạp lại cùng nội dung trả ALREADY_LOADED và không tạo document trùng. Nạp lại một snapshot cũ đã công bố cũng không tự chuyển con trỏ active ngược về quá khứ. Snapshot thất bại có thể thử lại. Loader có lease để tránh hai lần nạp xung đột; không tự xóa bản cũ. Đây là lý do M5 cần thêm metadata ngoài 20 collection dữ liệu. Sơ đồ A/B là minh họa cơ chế, không khẳng định hiện tại đang có hai snapshot trong database. Nguồn: batch_writer.py, mongo.py.',
    'Với câu hỏi tháng 01/2025, dùng kpi_month_overall chứ không cộng bảng overall với bảng carrier hay origin vì các bảng đó mô tả lại cùng tập chuyến. Lấy snapshot active từ serving_state và lọc year=2025, month=1. Dữ liệu thật cho biết flights=539747, on_time=424139, arr_n=522269. Tỷ lệ đúng giờ là on_time/arr_n = 0,812108… và giao diện hiển thị 81,21%. Tổng chuyến khác mẫu số chuyến đến hợp lệ, do đó không lấy flights thay arr_n. Các màn hình khác phải chọn bảng có đúng chiều dữ liệu mà nguồn cung cấp. Ví dụ KPI tuyến có mức năm, origin và dest; không có chiều tháng hay hãng, nên giao diện không được ngầm áp dụng các bộ lọc không tồn tại. Với hãng hoặc sân bay, dùng bảng carrier/origin tương ứng. Nguồn số liệu: kpi__month_overall.jsonl trong snapshot; nguồn logic: queries.py, metrics.py, app.py.',
    'Đây là số minh họa cho công thức, không phải một thống kê BTS thật. Nhóm A có 9 chuyến đúng giờ trên 10 chuyến hợp lệ, tỷ lệ 90%. Nhóm B có 50 trên 100, tỷ lệ 50%. Lấy trung bình 90 và 50 ra 70% là sai vì nhóm A chỉ có 10 chuyến trong khi B có 100 chuyến. Phải cộng tử số và mẫu số: 59/110=53,636…%, làm tròn 53,6%. Trong code, OTP tổng là sum(on_time)/sum(arr_n), hủy chuyến là sum(cancelled)/sum(flights); các chỉ tiêu khác dùng đúng mẫu số hợp đồng. Không cộng các bảng khác mức để tránh đếm lặp. Không lấy trung bình percentile/median để suy ra percentile tổng, vì phân vị không có tính cộng. Nếu cần box của nhóm lớn thì dùng đúng bảng box đã tính sẵn. Giá trị tỷ lệ lưu dưới dạng fraction 0–1; null không tự biến thành 0; delay âm thể hiện đến sớm. Nguồn: m5/metrics.py và hợp đồng M2.',
    'Đây là ảnh dashboard thật trên localhost:8501, không phải bản mockup. Ảnh chụp phần tổng quan ở phạm vi toàn bộ lịch sử 01/2022–03/2026. Các thẻ phía trên hiển thị 29.328.846 chuyến sau cleaning, 78,8% đúng giờ, 21,2% trễ từ 15 phút, 1,8% hủy và delay đến trung bình 7,3 phút theo định nghĩa hiện tại. Biểu đồ trái cho biết lưu lượng thay đổi theo tháng; donut bên phải phân chia các nhóm chuyến đến có dữ liệu hợp lệ. Mỗi chỉ tiêu phải đọc kèm mẫu số, chú giải và phạm vi nguồn. Bộ lọc được đặt phía trên vùng được chụp; ảnh này tập trung vào kết quả. Mở web bằng trình duyệt tại http://localhost:8501 sau khi MongoDB và dashboard healthy. Người dùng chọn phạm vi, đọc KPI, rồi hover/zoom hoặc dùng xuất dữ liệu theo chức năng từng màn hình. Năm 2026 chỉ có quý I nên không so cả năm với năm đầy đủ mà thiếu chú thích. Nguồn ảnh: dashboard thực tế của project, chụp ngày 08/11/2026. Bản bullet minh họa bằng ảnh crop hai thẻ KPI và donut từ màn hình tổng quan; không phải ảnh toàn trang.',
    'Sankey bên trái là ảnh thật của màn hình Tuyến bay: top 15 tuyến có nhiều chuyến nhất, năm mặc định 2026, chỉ bao phủ tháng 1–3. Độ rộng dải theo số chuyến; đây không phải toàn bộ mạng bay. Origin bên trái, destination bên phải. Nếu muốn so năm nên chọn cùng kỳ hoặc ghi rõ giới hạn mức tổng hợp; bảng tuyến chỉ có năm nên không có bộ lọc tháng. Box plot bên phải là sơ đồ minh họa cách đọc, không phải ảnh hay số đo BTS. Hộp từ Q1 tới Q3 chứa 50% giá trị giữa, vạch là trung vị; râu cần đọc theo định nghĩa dữ liệu xuất M2. Không lấy trung bình các phân vị để gộp box. Dashboard còn có các trang thời gian, hãng bay, sân bay và phân phối. Khi bàn giao, phải có môi trường chạy được, nguồn đầu vào đã kiểm tra, dữ liệu MongoDB được xác minh, nạp lại không trùng, các truy vấn đúng, giao diện và hướng dẫn để thành viên khác tự khởi động. Tài liệu thao tác: serving-layer/doc_guide/HUONG_DAN_CHAY_TU_DAU_DEN_OUTPUT_M5.md. Luồng streaming và triển khai Kubernetes là phạm vi mở rộng, chưa phải điều kiện của sáu task dùng output M2 này.',
]

# Presentation revision: native bullets left, one illustration panel right.
def bullets(shape, items, size=18, gap=10):
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = None
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    for i, item in enumerate(items):
        lead, body = item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = lead + ': '
        r = p.add_run()
        r.text = body
        style_paragraph(p, size, False, INK)
        p.runs[0].font.bold = True
        p.space_after = Pt(gap)
        pp = p._p.get_or_add_pPr()
        pp.set('marL', str(Inches(.2)))
        pp.set('indent', str(-Inches(.19)))
        for child in list(pp):
            if child.tag.endswith('}buNone'):
                pp.remove(child)
        # Native PowerPoint bullet, not a Unicode bullet inside a plain string.
        bufont = OxmlElement('a:buFont')
        bufont.set('typeface', FONT)
        bullet = OxmlElement('a:buChar')
        bullet.set('char', '•')
        following = pp.find('a:defRPr', pp.nsmap)
        if following is None:
            pp.append(bufont)
            pp.append(bullet)
        else:
            following.addprevious(bufont)
            following.addprevious(bullet)


def columns(number, title, section, items, visual_heading):
    slide = clone(4, number)
    title_shape = next(sh for sh in slide.shapes if sh.is_placeholder and sh.placeholder_format.idx == 0)
    write(title_shape, title, 28, True, R)
    text(slide, .47, .81, 11.2, .3, section.upper(), 13, True, G)
    body = next(sh for sh in slide.shapes if sh.name.startswith('Content Placeholder'))
    body.left, body.top = Inches(.55), Inches(1.42)
    body.width, body.height = Inches(5.35), Inches(5.13)
    bullets(body, items)
    line(slide, 6.14, 1.39, 6.14, 6.49, LINE, .8)
    text(slide, 6.46, 1.42, 5.08, .6, visual_heading, 20, True, R)
    inventory[-1].update(title=title, section=section, layout='bullet left / illustration right', bullets=len(items))
    return slide


def visual_box(slide, x, y, w, h, heading, sub='', fill=LIGHT, size=18):
    rect(slide, x, y, w, h, fill, LINE, True)
    write(slide.shapes[-1], heading, size, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE, .09)
    if sub:
        text(slide, x+.1, y+h+.09, w-.2, .5, sub, 15, False, MUTED, PP_ALIGN.CENTER)


def native_table(slide, x, y, widths, rows, row_heights, font_size=17):
    for r, row in enumerate(rows):
        cx = x
        for c, val in enumerate(row):
            h = row_heights[r]
            sh = rect(slide, cx, y, widths[c], h, CREAM if r == 0 else (WHITE if r % 2 == 0 else LIGHT), LINE)
            write(sh, val, font_size, r == 0, R if r == 0 else INK, PP_ALIGN.LEFT, MSO_ANCHOR.MIDDLE, .07)
            cx += widths[c]
        y += row_heights[r]


# 1 — cover; retain original cover logo/background.
s = clone(2, 1)
shapes = {sh.shape_id: sh for sh in s.shapes}
heading = shapes[3]
heading.top, heading.height = Inches(2.05), Inches(1.75)
write(heading, 'TASK M5\nTừ output M2 đến MongoDB\nvà dashboard', 36, True, R)
style_paragraph(heading.text_frame.paragraphs[0], 26, False, R)
subtitle = shapes[4]
subtitle.top, subtitle.width, subtitle.height = Inches(4.03), Inches(9.1), Inches(1.1)
bullets(subtitle, [('Phạm vi', '6 task sử dụng dữ liệu lịch sử từ M2.'),
                   ('Mục tiêu', 'Lưu đúng, nạp an toàn và hiển thị rõ.')], size=21, gap=8)
file_icon(s, .53, 5.43, 2.5, .87, 'KPI từ M2')
arrow(s, 3.2, 5.77, .48, .26)
db(s, 3.9, 5.34, 2.5, 1.05, 'MongoDB')
arrow(s, 6.57, 5.77, .48, .26)
mini_chart(s, 7.28, 5.34, 2.6, 1.05, title='Dashboard')

# 2 — overview and task list.
s = columns(2, 'Tổng quan: M5 cần làm gì và đạt kết quả gì?', 'M5 · NoSQL & dashboard', [
    ('Vai trò', 'Biến KPI lịch sử M2 thành dữ liệu có thể tra cứu và hiển thị trên web.'),
    ('Đầu vào', 'KPI đã tổng hợp; luồng chính dùng JSONL kèm manifest.json.'),
    ('Phạm vi', 'Làm việc với bảng thống kê, không cần nạp lại 29 triệu dòng raw.'),
    ('Yêu cầu dữ liệu', 'Giữ đúng khóa, kiểu dữ liệu, đơn vị và phạm vi thời gian.'),
    ('Yêu cầu vận hành', 'Nạp lại không trùng; chỉ công bố bản đã kiểm tra thành công.'),
    ('Đầu ra', 'MongoDB + loader + truy vấn + dashboard + bằng chứng và hướng dẫn.')
], '6 task lớn trong M5')
task_names = ['Tiếp nhận và kiểm tra output M2', 'Thiết kế lưu trữ MongoDB', 'Chuẩn bị môi trường Docker',
              'Xây dựng và chạy bộ nạp dữ liệu', 'Xây dựng truy vấn, tính KPI', 'Xây dựng dashboard']
for i, name in enumerate(task_names):
    y = 2.12+i*.68
    badge(s, 6.5, y+.07, i+1, diameter=.37)
    rect(s, 7.06, y, 4.47, .55, CREAM if i % 2 == 0 else LIGHT, radius=True)
    write(s.shapes[-1], name, 18, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    if i < 5:
        arrow(s, 9.15, y+.58, .22, .09, down=True)

# 3 — source package and data grain.
s = columns(3, '1. Tiếp nhận output M2: hiểu đúng dữ liệu đầu vào', 'Task 1 / 6 · Nhận dữ liệu', [
    ('Nhận snapshot', 'Một bộ file M2 xuất tại một thời điểm, có manifest.json và JSONL.'),
    ('Nhận đúng bảng', '13 bảng KPI và 7 bảng phân phối delay; tổng cộng 20 bảng.'),
    ('Hiểu mỗi dòng', 'Mỗi dòng là một nhóm thống kê như tháng, hãng, sân bay hoặc tuyến.'),
    ('Đọc khóa nhóm', 'Ví dụ year + month xác định duy nhất một dòng KPI tháng.'),
    ('Đọc đơn vị', 'Tỷ lệ lưu 0–1; delay tính bằng phút; giữ nguyên giá trị null.'),
    ('Chốt phạm vi', '51 tháng từ 01/2022 đến 03/2026; năm 2026 chỉ có quý I.')
], 'Bộ bàn giao và mức tổng hợp')
file_icon(s, 6.49, 2.15, 2.32, .86, 'manifest.json', size=18)
file_icon(s, 9.08, 2.15, 2.32, .86, '20 file JSONL', size=18)
native_table(s, 6.48, 3.37, [2.24, 2.77], [
    ['Bảng KPI', 'Một dòng đại diện'],
    ['month_overall', '1 năm + 1 tháng'],
    ['year_carrier', '1 năm + 1 hãng'],
    ['year_route', '1 năm + sân bay đi/đến']
], [.53, .64, .64, .81], 17)
text(s, 6.55, 6.07, 4.86, .45, '74.921 dòng tổng hợp ≠ 29.328.846 chuyến', 17, True, R, PP_ALIGN.CENTER)

# 4 — validation.
s = columns(4, '1. Kiểm tra output M2 trước khi nạp', 'Task 1 / 6 · Kiểm soát đầu vào', [
    ('Đủ file', 'Các file trong manifest tồn tại và có đủ 13 bảng KPI + 7 bảng box.'),
    ('Đúng cấu trúc', 'Tên cột, kiểu số/chuỗi và các trường bắt buộc phải khớp schema.'),
    ('Đúng khóa', 'Khóa nhóm không null và không trùng trong cùng một bảng.'),
    ('Đúng số liệu', 'Số dòng khớp manifest; tổng chuyến và 51 tháng phải khớp nguồn.'),
    ('Chạy CheckOnly', 'Kiểm tra toàn bộ snapshot, chưa ghi dữ liệu vào MongoDB.'),
    ('Xử lý kết quả', 'PASS thì sang bước nạp; có lỗi thì sửa hoặc xuất lại dữ liệu M2.')
], 'Cổng kiểm tra dữ liệu')
file_icon(s, 7.73, 2.11, 2.5, .73, 'Snapshot M2', size=19)
arrow(s, 8.86, 2.94, .26, .26, down=True)
for i, title in enumerate(['File + bảng + schema', 'Khóa + kiểu dữ liệu', 'Số dòng + thời gian']):
    visual_box(s, 6.72, 3.35+i*.65, 4.52, .5, title, size=18)
arrow(s, 8.86, 5.33, .26, .27, down=True)
label(s, 6.76, 5.83, 2.02, 'PASS → nạp', GREEN, 'ECF5EF', 17)
label(s, 9.07, 5.83, 2.02, 'FAIL → sửa M2', R, 'FBEDED', 17)

# 5 — MongoDB mapping.
s = columns(5, '2. Thiết kế cách lưu và truy vấn trong MongoDB', 'Task 2 / 6 · Collection, document, index', [
    ('Collection', 'Một bảng M2 tương ứng một collection; có 20 collection dữ liệu.'),
    ('Document', 'Mỗi dòng thành một document; giữ trường M2 và thêm snapshot_id.'),
    ('Khóa duy nhất', 'Gồm snapshot_id + khóa nhóm; bảng box thêm var và population.'),
    ('Index', 'Tạo chỉ mục hỗ trợ lọc theo năm, hãng, sân bay hoặc tuyến.'),
    ('Metadata', 'batch_runs lưu lần nạp; serving_state chỉ phiên bản đang được dùng.'),
    ('Mục tiêu', 'Tránh bản ghi trùng, giữ nguyên dữ liệu và tra cứu đúng phiên bản.')
], 'Ví dụ collection và document')
label(s, 6.49, 2.13, 5.0, 'Collection: kpi_month_overall', size=18)
rect(s, 6.49, 2.77, 5.0, 2.63, LIGHT, LINE, True)
text(s, 6.7, 2.95, 4.58, 2.26,
     '{\n  snapshot_id: "633c62bf…",\n  year: 2025, month: 1,\n  flights: 539747,\n  otp_operated: 0.812108…\n}', 18)
text(s, 6.59, 5.66, 4.8, .73, 'Unique index\nsnapshot_id + year + month', 19, True, R, PP_ALIGN.CENTER)

# 6 — runtime infrastructure.
s = columns(6, '3. Chuẩn bị môi trường chạy bằng Docker', 'Task 3 / 6 · Hạ tầng triển khai', [
    ('Docker Desktop', 'Bật Docker; Compose dựng và kết nối các dịch vụ M5.'),
    ('MongoDB', 'Chạy server trong container; không cần cài server riêng trên Windows.'),
    ('Loader', 'Chạy khi cần nạp; đọc snapshot và ghi dữ liệu vào MongoDB.'),
    ('Dashboard', 'Streamlit + Plotly; truy cập trình duyệt tại localhost:8501.'),
    ('Volume', 'm5_mongo_data giữ dữ liệu MongoDB sau khi dừng container.'),
    ('Khởi động', 'Ở serving-layer, chạy .\\scripts\\start_m5.ps1; kiểm tra healthy.')
], 'Các dịch vụ phối hợp thế nào?')
visual_box(s, 7.69, 2.07, 2.53, .61, 'Trình duyệt :8501', size=18)
arrow(s, 8.85, 2.78, .24, .29, down=True)
rect(s, 6.49, 3.19, 5.0, 2.37, LIGHT, LINE, True)
text(s, 6.68, 3.34, 4.62, .35, 'Mạng Docker Compose', 17, True, G, PP_ALIGN.CENTER)
visual_box(s, 6.7, 3.99, 2.12, .57, 'Dashboard', fill=CREAM, size=18)
visual_box(s, 6.7, 4.79, 2.12, .57, 'Loader', fill=CREAM, size=18)
arrow(s, 8.96, 4.19, .28, .2)
arrow(s, 8.96, 4.99, .28, .2)
db(s, 9.41, 4.03, 1.84, 1.27, 'MongoDB\n:27017', font_size=18)
arrow(s, 10.19, 5.63, .24, .26, down=True)
visual_box(s, 8.13, 6.01, 3.37, .5, 'Volume: m5_mongo_data', fill=CREAM, size=16)

# 7 — load pipeline.
s = columns(7, '4. Xây dựng và chạy chương trình nạp dữ liệu', 'Task 4 / 6 · Từ file tới database', [
    ('Đọc nguồn', 'Luồng chính đọc JSONL + manifest; có nhánh đọc KPI Parquet/HDFS.'),
    ('Kiểm tra trước', 'Chạy CheckOnly; chỉ nạp khi toàn bộ dữ liệu hợp lệ.'),
    ('Xác định phiên bản', 'Tạo snapshot_id từ nội dung để nhận diện bộ dữ liệu.'),
    ('Ghi theo lô', 'Upsert theo khóa: có thì cập nhật, chưa có thì thêm; lô 1.000.'),
    ('Đối chiếu', 'Đọc lại MongoDB để so số dòng và mã kiểm tra nội dung với nguồn.'),
    ('Công bố', 'Chỉ đổi snapshot active sau khi đối chiếu thành công; lưu log nạp.')
], 'Quy trình nạp dùng chung')
visual_box(s, 6.49, 2.14, 5.0, .62, 'JSONL hoặc KPI Parquet', fill=CREAM, size=19)
flow = [('1', 'Đọc và kiểm tra nguồn'), ('2', 'Tính snapshot_id'), ('3', 'Upsert vào MongoDB'),
        ('4', 'Đối chiếu số dòng, nội dung'), ('5', 'Công bố cho dashboard')]
for i, (n, title) in enumerate(flow):
    y = 3.07+i*.64
    badge(s, 6.59, y+.05, n, diameter=.34)
    visual_box(s, 7.12, y, 4.2, .47, title, fill=CREAM if i == 4 else LIGHT, size=17)
    if i < 4:
        arrow(s, 9.13, y+.5, .19, .1, down=True)

# 8 — idempotence and snapshot safety.
s = columns(8, '4. Đảm bảo nạp lại an toàn và không bị trùng', 'Task 4 / 6 · Chất lượng vận hành', [
    ('Chống trùng', 'Unique index + upsert bảo đảm một khóa chỉ có một document.'),
    ('Nạp lại cùng dữ liệu', 'Dùng cùng snapshot_id; không sinh thêm bản ghi trùng.'),
    ('Tách phiên bản', 'Bản A tiếp tục phục vụ khi bản B còn đang được nạp.'),
    ('Chỉ đổi sau PASS', 'B khớp nguồn thì chuyển active sang B; B lỗi thì giữ A.'),
    ('Tránh xung đột', 'Loader dùng khóa/lease; snapshot đã công bố không sửa tại chỗ.'),
    ('Bằng chứng', 'Giữ log, báo cáo nạp và kết quả verify để kiểm tra, bàn giao.')
], 'Ví dụ hai phiên bản A và B')
db(s, 6.61, 2.26, 2.13, 1.25, 'Bản A\nĐã công bố', font_size=19)
db(s, 9.23, 2.26, 2.13, 1.25, 'Bản B\nĐang nạp', font_size=19)
label(s, 6.67, 3.82, 4.63, 'Trong lúc nạp B: dashboard vẫn dùng A', GREEN, 'ECF5EF', 16)
arrow(s, 8.85, 4.35, .26, .27, down=True)
native_table(s, 6.53, 4.88, [2.1, 2.86], [
    ['Kiểm tra B', 'Dashboard dùng'], ['PASS', 'Chuyển sang bản B'], ['FAIL', 'Giữ nguyên bản A']
], [.47, .62, .62], 17)

# 9 — queries and actual result.
s = columns(9, '5. Xây dựng truy vấn theo đúng nhu cầu xem', 'Task 5 / 6 · Lọc đúng bảng, đúng phiên bản', [
    ('Bắt đầu từ câu hỏi', 'Ví dụ: tháng 01/2025 có bao nhiêu chuyến, OTP bao nhiêu?'),
    ('Chọn đúng bảng', 'KPI tháng dùng kpi_month_overall; hãng, sân bay dùng bảng riêng.'),
    ('Lọc đúng phiên bản', 'Mọi truy vấn đều kèm snapshot_id đang active.'),
    ('Lọc đúng chiều', 'Chọn năm, tháng, hãng hoặc sân bay mà bảng đó thực sự có.'),
    ('Không đếm lặp', 'Không cộng đồng thời overall + carrier + origin của cùng tập chuyến.'),
    ('Giới hạn nguồn', 'KPI tuyến chỉ ở mức năm; không áp dụng lọc tháng hoặc hãng.')
], 'Kết quả thật: tháng 01/2025')
label(s, 6.51, 2.13, 4.98, 'kpi_month_overall', size=19)
text(s, 6.63, 2.75, 4.74, .65, 'snapshot_id = active\nyear = 2025; month = 1', 18, False, INK, PP_ALIGN.CENTER)
native_table(s, 6.51, 3.72, [2.75, 2.23], [
    ['Chỉ tiêu', 'Giá trị'], ['Tổng chuyến', '539.747'], ['Đúng giờ', '424.139'],
    ['Đến hợp lệ', '522.269'], ['OTP hiển thị', '81,21%']
], [.47, .47, .47, .47, .55], 18)
text(s, 6.57, 6.33, 4.86, .28, 'OTP = 424.139 / 522.269', 16, True, R, PP_ALIGN.CENTER)

# 10 — calculation conventions.
s = columns(10, '5. Tính KPI hiển thị đúng cách', 'Task 5 / 6 · Gộp số đếm trước, tính tỷ lệ sau', [
    ('Tỷ lệ đúng giờ', 'OTP = tổng on_time / tổng arr_n; dùng đúng mẫu số hợp lệ.'),
    ('Tỷ lệ hủy', 'Tổng chuyến hủy / tổng flights; không dùng mẫu số của OTP.'),
    ('Khi gộp nhóm', 'Cộng tử số và mẫu số rồi chia; không lấy trung bình các tỷ lệ.'),
    ('Phân vị, box plot', 'Dùng bảng M2 đúng mức; không lấy trung bình median hoặc Q1/Q3.'),
    ('Phần trăm', 'Tỷ lệ lưu 0–1, chỉ nhân 100 khi hiển thị trên giao diện.'),
    ('Giá trị đặc biệt', 'Null không tự đổi thành 0; delay âm thể hiện đến sớm.')
], 'Ví dụ minh họa: hai nhóm khác quy mô')
native_table(s, 6.5, 2.13, [1.2, 2.5, 1.28], [
    ['Nhóm', 'Đúng giờ / hợp lệ', 'OTP'], ['A', '9 / 10', '90%'], ['B', '50 / 100', '50%']
], [.75, .61, .61], 17)
rect(s, 6.5, 4.42, 4.98, 1.03, 'ECF5EF', radius=True)
text(s, 6.67, 4.57, 4.64, .8, 'Đúng: (9 + 50) / (10 + 100)\n= 53,6%', 22, True, GREEN, PP_ALIGN.CENTER)
rect(s, 6.5, 5.78, 4.98, .61, 'FBEDED', radius=True)
write(s.shapes[-1], 'Sai: (90% + 50%) / 2 = 70%', 19, True, R, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)

# 11 — overview images with bullet explanation.
s = columns(11, '6. Xây dựng dashboard: KPI và biểu đồ tổng quan', 'Task 6 / 6 · Từ database tới giao diện', [
    ('Công nghệ', 'Streamlit dựng giao diện; Plotly vẽ biểu đồ; MongoDB cung cấp dữ liệu.'),
    ('Bộ lọc', 'Cho chọn năm, tháng và nhóm hãng/sân bay theo từng màn hình.'),
    ('Thẻ KPI', 'Hiển thị lưu lượng, đúng giờ, trễ từ 15 phút, hủy và delay trung bình.'),
    ('Xu hướng', 'Biểu đồ đường/cột cho thấy lưu lượng thay đổi qua các tháng.'),
    ('Cơ cấu', 'Donut phân biệt đúng giờ, trễ 15–59 phút và trễ từ 60 phút.'),
    ('Tương tác', 'Hover, zoom, tải CSV/ảnh; luôn hiển thị phạm vi và chú giải.')
], 'Ảnh dashboard thực tế')
fit_image(s, ASSETS/'bullet_metrics.png', 6.49, 2.11, 5.02, 1.15)
fit_image(s, ASSETS/'bullet_donut.png', 6.92, 3.43, 4.16, 2.6)
text(s, 6.55, 6.16, 4.9, .43, 'Toàn kỳ 01/2022–03/2026 · 2026 chỉ quý I', 16, False, MUTED, PP_ALIGN.CENTER)

# 12 — diversity of views and handoff.
s = columns(12, '6. Dashboard: khám phá dữ liệu và bàn giao M5', 'Task 6 / 6 · Các góc nhìn và điều kiện hoàn thành', [
    ('So sánh nhóm', 'Dùng cột, heatmap, treemap để xem hãng, sân bay và mùa vụ.'),
    ('Luồng tuyến', 'Sankey cho thấy các tuyến nổi bật; dải rộng hơn là nhiều chuyến hơn.'),
    ('Phân phối delay', 'Box plot cho biết trung vị, khoảng Q1–Q3 và mức phân tán.'),
    ('Đọc đúng phạm vi', 'Ghi rõ năm, tháng, quần thể; năm 2026 chỉ có tháng 1–3.'),
    ('Kiểm chứng', 'Dữ liệu đủ, không trùng, verify PASS; KPI trên web khớp MongoDB.'),
    ('Bàn giao', 'Code, cấu hình Docker, log/báo cáo và hướng dẫn để team tự chạy lại.')
], 'Minh họa cách đọc biểu đồ')
fit_image(s, ASSETS/'dashboard_routes_focus.png', 6.5, 2.16, 4.99, 1.7)
text(s, 6.53, 4.0, 4.92, .47, 'Sankey thật: Top 15 tuyến · 2026 (Q1)', 16, True, R, PP_ALIGN.CENTER)
rect(s, 6.51, 4.74, 4.98, 1.25, LIGHT, LINE, True)
line(s, 6.84, 5.31, 11.16, 5.31, O, 2)
line(s, 6.84, 5.1, 6.84, 5.52, O, 2)
line(s, 11.16, 5.1, 11.16, 5.52, O, 2)
rect(s, 7.83, 5.0, 2.06, .63, CREAM, O)
line(s, 8.73, 5.0, 8.73, 5.63, R, 3)
text(s, 7.72, 5.68, 2.35, .28, 'Q1      Trung vị      Q3', 15, False, MUTED, PP_ALIGN.CENTER)
text(s, 6.56, 6.16, 4.88, .41, 'Box plot minh họa: hộp chứa 50% giá trị giữa', 16, False, MUTED, PP_ALIGN.CENTER)

for slide, speech in zip(list(prs.slides)[len(original):], SPEAKER_NOTES):
    notes(slide, speech)

for _ in original:
    sid = prs.slides._sldIdLst[0]
    prs.part.drop_rel(sid.rId)
    prs.slides._sldIdLst.remove(sid)

prs.core_properties.title = 'M5 — Sáu task từ output M2 đến MongoDB và dashboard'
prs.core_properties.subject = 'Bản bullet: nội dung bên trái, sơ đồ/bảng/ảnh bên phải'
prs.core_properties.author = 'Project BigData — M5'
prs.core_properties.keywords = 'M5, M2, MongoDB, Docker, dashboard, bullet'
prs.core_properties.comments = 'Template: RIVF paper review.pptx; native bullet paragraphs and editable illustrations.'
OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
(ASSETS/'bullet_inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Saved {len(prs.slides)} slides: {OUT}')
