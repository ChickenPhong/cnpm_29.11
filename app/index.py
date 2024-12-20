from random import choice
from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify, Response
from sqlalchemy import Nullable, and_
from sqlalchemy.testing.plugin.plugin_base import config
import csv
from app import app, db, dao, login
from datetime import date, datetime

from app.admin import DanhSachLopView
from app.models import NhanVien, HocSinh, UserRole, DanhSachLop, PhongHoc, HocKy, GiaoVienDayHoc, GiaoVien, MonHoc, BangDiem, BangDiemTB, QuyDinh
from flask_login import login_user, logout_user, current_user

app.secret_key = 'secret_key'  # Khóa bảo mật cho session


@app.route('/')
def index():
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login_process():
    err_msg = None
    if request.method == 'POST':
        taiKhoan = request.form['taiKhoan']
        matKhau = request.form['matKhau']

        nv = dao.auth_user(taikhoan=taiKhoan, matkhau=matKhau)

        if nv and nv.get_VaiTro() == UserRole.NHANVIENTIEPNHAN:
            login_user(nv)
            return redirect('/nhan-vien')
        elif nv and nv.get_VaiTro() == UserRole.NGUOIQUANTRI:
            login_user(nv)
            return redirect('/admin')

            # Kiểm tra tài khoản giáo viên
        gv = dao.auth_giao_vien(taiKhoan, matKhau)
        print(taiKhoan)
        print(matKhau)
        print(gv)
        if gv:
            login_user(gv)
            return redirect('/giao-vien')

        err_msg = "Sai tài khoản/ mật khẩu"
    return render_template('layout/login.html', err_msg=err_msg)


@app.route('/nhan-vien')
def dashboard():
    return render_template('layout/nhan_vien.html')

@app.route('/giao-vien')
def giao_vien_dashboard():
    print(current_user)
    return render_template('layout/giao_vien.html')  # Tạo file giao diện cho giáo viên


@app.route('/logout', methods=['get', 'post'])
def logout_process():
    logout_user()
    return redirect('/login')


@login.user_loader
def load_user(user_id):
    return dao.get_nhan_vien_by_id(user_id) or dao.get_giao_vien_by_id(user_id)



# @app.before_request
# def require_login():
#     allowed_routes = ['login', 'logout']
#     if request.endpoint not in allowed_routes and not session.get('logged_in'):
#         return redirect('/login')

@app.route('/nhap-ho-so', methods=['POST'])
def kiem_tra_tuoi():
    quy_dinh = QuyDinh.query.first()  # Lấy quy định từ DB
    min_age = quy_dinh.min_age
    max_age = quy_dinh.max_age

    ngay_sinh = request.form.get('ngaySinh')
    if ngay_sinh:
        # Tính tuổi
        ngay_sinh = datetime.strptime(ngay_sinh, "%Y-%m-%d").date()
        hom_nay = date.today()
        tuoi = hom_nay.year - ngay_sinh.year

        # Kiểm tra tuổi
        if min_age <= tuoi <= max_age:
            flash("Tuổi hợp lệ. Hãy nhập thông tin chi tiết.", "success")
            return render_template('layout/nhap_thong_tin_hoc_sinh.html', ngay_sinh=ngay_sinh)
        else:
            flash(f"Tuổi không phù hợp: {tuoi} tuổi!!!", "warning")
            return redirect('/nhan-vien')
    return "Không nhận được thông tin ngày sinh!"



@app.route('/luu-hoc-sinh', methods=['POST'])
def luu_hoc_sinh():
    # Lấy thông tin từ form
    ho_ten = request.form.get('hoTen')
    gioi_tinh = request.form.get('gioiTinh')  # Nam = 1, Nữ = 0
    ngay_sinh = request.form.get('ngaySinh')
    khoi = request.form.get('khoi')
    dia_chi = request.form.get('diaChi')
    so_dien_thoai = request.form.get('soDienThoai')
    email = request.form.get('email')

    # Tạo đối tượng học sinh mới
    hoc_sinh = HocSinh(
        hoTen=ho_ten,
        gioiTinh=(gioi_tinh == '1'),
        ngaySinh=datetime.strptime(ngay_sinh, "%Y-%m-%d").date(),
        khoi=khoi,
        diaChi=dia_chi,
        SDT=so_dien_thoai,
        eMail=email,
        maDsLop=None
    )
    db.session.add(hoc_sinh)
    db.session.commit()

    flash("Học sinh đã được lưu thành công!", "success")
    return redirect("/nhan-vien")


@app.route('/danh-sach-lop')
def show_ds_lop():
    dsLop = DanhSachLop.query.filter(DanhSachLop.active == True)
    return render_template('layout/danh_sach_lop.html', danh_sach_lop=dsLop)

@app.route('/tao-danh-sach-lop')
def create_auto_classes():
    try:
        # Lấy toàn bộ danh sách học sinh chưa được gán lớp
        students = HocSinh.query.filter(HocSinh.maDsLop == None).all()
        if not students:
            flash("Không có học sinh nào để tạo lớp!", "error")
            return redirect('/admin')

        # Nhóm học sinh theo khối
        grade_groups = {
            "10": [],
            "11": [],
            "12": []
        }
        for student in students:
            if student.khoi == "Khối 10":
                grade_groups["10"].append(student)
            elif student.khoi == "Khối 11":
                grade_groups["11"].append(student)
            elif student.khoi == "Khối 12":
                grade_groups["12"].append(student)

        # Lấy học kỳ hiện tại (mặc định là Học kỳ 1)
        hoc_ky = HocKy.query.filter(HocKy.hocKy == "1").order_by(HocKy.idHocKy.desc()).first()
        if not hoc_ky:
            return redirect('/admin')

        # Lấy danh sách giáo viên và phân loại theo môn học
        giao_vien_all = GiaoVien.query.all()
        giao_vien_by_mon = {mon.idMonHoc: [] for mon in MonHoc.query.all()}
        for gv in giao_vien_all:
            giao_vien_by_mon[gv.idMonHoc].append(gv)

        giao_vien_kha_dung = GiaoVien.query.all()
        giao_vien_da_chu_nhiem = {gv_cn.giaoVienChuNhiem_id for gv_cn in DanhSachLop.query.filter(DanhSachLop.giaoVienChuNhiem_id != None)}
        giao_vien_kha_dung = [gv for gv in giao_vien_kha_dung if gv.idGiaoVien not in giao_vien_da_chu_nhiem]

        quy_dinh = QuyDinh.query.first()

        for khoi, group_students in grade_groups.items():
            siSo = quy_dinh.si_so  # Số lượng học sinh mỗi lớp
            for i in range(0, len(group_students), siSo):
                class_students = group_students[i:i + siSo]

                # Gán giáo viên chủ nhiệm ngẫu nhiên
                gv_chu_nhiem = choice(giao_vien_kha_dung)

                # Tạo lớp mới
                new_class = DanhSachLop(
                    tenLop=f"{khoi}A{i + 1}",
                    khoi = f"Khối {khoi}",
                    giaoVienChuNhiem_id=gv_chu_nhiem.idGiaoVien,
                    siSoHienTai=len(class_students),
                    siSo=siSo,
                    hocKy_id=hoc_ky.idHocKy
                )
                db.session.add(new_class)
                db.session.commit()

                # Gán giáo viên chủ nhiệm vào bảng GiaoVienChuNhiem
                giao_vien_day_hoc = GiaoVienDayHoc(
                    idGiaoVien=gv_chu_nhiem.idGiaoVien,
                    idDsLop=new_class.maDsLop
                )
                db.session.add(giao_vien_day_hoc)
                db.session.commit()



                # Xác định các môn học còn thiếu
                missing_subjects = [mon for mon in MonHoc.query.all() if mon.idMonHoc != gv_chu_nhiem.idMonHoc]

                # Gán giáo viên cho các môn học còn thiếu
                for mon in missing_subjects:
                    available_gvs = giao_vien_by_mon[mon.idMonHoc]
                    if available_gvs:
                        gv = choice(available_gvs)
                        # Gán giáo viên dạy môn này cho lớp
                        new_class.giaoVienDayHocs.append(GiaoVienDayHoc(
                            idGiaoVien=gv.idGiaoVien,
                            idDsLop=new_class.maDsLop
                        ))
                        db.session.commit()

                # Ghi nhận giáo viên đã làm chủ nhiệm
                giao_vien_kha_dung.remove(gv_chu_nhiem)

                # Gán học sinh vào lớp
                for student in class_students:
                    student.maDsLop = new_class.maDsLop
                    db.session.add(student)

        db.session.commit()
        flash("Danh sách lớp đã được tạo thành công!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Lỗi khi tạo danh sách lớp: {str(e)}", "error")

    return redirect('/admin')


@app.route('/danh-sach-lop/sua/<int:id>', methods=['GET', 'POST'])
def sua_ds_lop(id):
    lop = DanhSachLop.query.filter(DanhSachLop.maDsLop == id).first()

    # Lấy danh sách phòng học chưa được chọn
    list_phong = PhongHoc.query.all()
    list_phong_da_chon = {l.idPhongHoc for l in DanhSachLop.query.filter(DanhSachLop.idPhongHoc != None)}
    list_phong = [phong for phong in list_phong if
                  phong.idPhongHoc not in list_phong_da_chon or phong.idPhongHoc == lop.idPhongHoc]

    list_hs = {hs for hs in HocSinh.query.filter(HocSinh.maDsLop == lop.maDsLop)}

    if request.method == 'POST':
        try:
            # Cập nhật thông tin
            lop.tenLop = request.form.get("tenLop")
            lop.idPhongHoc = int(request.form.get("phongHoc"))
            db.session.commit()
            flash("Cập nhật thông tin lớp thành công", "success")
            return redirect('/danh-sach-lop')  # Chuyển về trang danh sách lớp
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi khi lưu dữ liệu: {str(e)}", "danger")
            return redirect(request.url)

    return render_template('layout/sua_lop.html', lop=lop, danh_sach_phong=list_phong, danh_sach_hoc_sinh=list_hs)


@app.route('/them-hoc-sinh/<int:id>', methods=['GET', 'POST'])
def them_hoc_sinh(id):
    lop = DanhSachLop.query.filter(DanhSachLop.maDsLop == id).first()

    ds_hs_chua_lop = HocSinh.query.filter(and_(
            HocSinh.maDsLop == None,
            HocSinh.khoi == lop.khoi
        )
    ).all()

    if request.method == 'POST':
        print(request.form)
        try:
            list_hs_ids = request.form.getlist("hocSinh")  # Lấy danh sách ID học sinh
            if not list_hs_ids:
                flash("Vui lòng chọn ít nhất một học sinh!", "danger")
                return redirect(request.url)

            si_so_hien_tai = HocSinh.query.filter(HocSinh.maDsLop == id).count()
            so_hoc_sinh_them = len(list_hs_ids)
            si_so_moi = si_so_hien_tai + so_hoc_sinh_them

            if si_so_moi > lop.siSo:
                flash("Không thể thêm vì vượt quá sĩ số lớp!", "danger")
                return redirect(request.url)
            else:
                lop.siSoHienTai = si_so_moi
                db.session.add(lop)
                db.session.commit()

            for hoc_sinh_id in list_hs_ids:
                hoc_sinh = HocSinh.query.get(hoc_sinh_id)
                hoc_sinh.maDsLop = id
                db.session.add(hoc_sinh)
                db.session.commit()

            flash(f"Đã thêm {so_hoc_sinh_them} học sinh vào lớp!", "success")
            return redirect(f'/danh-sach-lop/sua/{id}')
        except Exception as e:
            db.session.rollback()
            flash(f"Lỗi khi thêm học sinh: {str(e)}", "danger")
            return redirect(request.url)

    return render_template('layout/them_hoc_sinh.html', danh_sach_hoc_sinh=ds_hs_chua_lop, lop=lop)


@app.route('/xoa-hoc-sinh', methods=['POST'])
def xoa_hoc_sinh():
    id_hoc_sinh = request.form.get('idHocSinh')  # Lấy ID từ form
    if id_hoc_sinh:
        print(f"ID học sinh nhận được: {id_hoc_sinh}")  # In ra log kiểm tra
        # Kiểm tra và xóa học sinh khỏi database
        hoc_sinh = HocSinh.query.filter_by(idHocSinh=id_hoc_sinh).first()
        if hoc_sinh:
            lop = DanhSachLop.query.filter(DanhSachLop.maDsLop.__eq__(hoc_sinh.maDsLop)).first()
            lop.siSoHienTai -= 1
            hoc_sinh.maDsLop = None  # Gỡ học sinh khỏi lớp
            db.session.commit()
            flash('Đã xóa học sinh khỏi danh sách lớp thành công!', 'success')
            return redirect(f'/danh-sach-lop/sua/{lop.maDsLop}')  # Chuyển hướng về danh sách lớp
    flash('Không nhận được ID học sinh để xóa!', 'danger')
    return redirect(url_for('show_ds_lop'))


@app.route('/thong-ke-bao-cao', methods=['GET', 'POST'])
def thong_ke_bao_cao():
    try:
        if request.method == 'POST':
            # Lấy thông tin từ form
            mon_hoc_id = request.form.get('monHoc')
            hoc_ky_id = request.form.get('hocKy')

            # Kiểm tra xem môn học và học kỳ có hợp lệ không
            if not mon_hoc_id or not hoc_ky_id:
                flash("Vui lòng chọn môn học và học kỳ!", "warning")
                return redirect('/thong-ke-bao-cao')

            # Lấy danh sách lớp
            danh_sach_lop = DanhSachLop.query.all()
            data = []

            for lop in danh_sach_lop:
                # Tính sĩ số của lớp
                si_so = HocSinh.query.filter(HocSinh.maDsLop == lop.maDsLop).count()

                # Tính số lượng học sinh đạt
                so_luong_dat = db.session.query(BangDiem.hocSinh_id).filter(
                    BangDiem.monHoc_id == mon_hoc_id,
                    BangDiem.hocKy_id == hoc_ky_id,
                    BangDiem.diem >= 5,
                    BangDiem.hocSinh_id.in_(
                        HocSinh.query.with_entities(HocSinh.idHocSinh)
                        .filter(HocSinh.maDsLop == lop.maDsLop)
                    )
                ).distinct().count()

                # Tính tỷ lệ đạt
                ty_le = round((so_luong_dat / si_so) * 100, 2) if si_so > 0 else 0

                # Thêm dữ liệu vào danh sách
                data.append({
                    "lop": lop.tenLop,
                    "si_so": si_so,
                    "so_luong_dat": so_luong_dat,
                    "ty_le": ty_le
                })

            # Gửi dữ liệu đến giao diện để hiển thị
            return render_template(
                'layout/thong_ke_bao_cao.html',
                data=data,
                danh_sach_mon_hoc=MonHoc.query.all(),
                danh_sach_hoc_ky=HocKy.query.all(),
                enumerate=enumerate
            )

        # Hiển thị giao diện chọn môn học và học kỳ
        return render_template(
            'layout/thong_ke_bao_cao.html',
            danh_sach_mon_hoc=MonHoc.query.all(),
            danh_sach_hoc_ky=HocKy.query.all()
        )

    except Exception as e:
        flash(f"Đã xảy ra lỗi: {str(e)}", "danger")
        return redirect('/admin')



@app.route('/danh-sach-lop-day')
def danh_sach_lop_day():
    # Lấy danh sách lớp mà giáo viên đang dạy
    danh_sach_lop_ids = db.session.query(GiaoVienDayHoc.idDsLop).filter(
        GiaoVienDayHoc.idGiaoVien == current_user.idGiaoVien
    ).distinct()

    danh_sach_lop = DanhSachLop.query.filter(DanhSachLop.maDsLop.in_(danh_sach_lop_ids)).all()

    return render_template('/layout/danh_sach_lop_gv.html', danh_sach_lop=danh_sach_lop)

@app.route('/danh-sach-lop-chu-nhiem')
def danh_sach_lop_chu_nhiem():
    # Kiểm tra giáo viên có chủ nhiệm lớp nào không
    lop_chu_nhiem = DanhSachLop.query.filter_by(giaoVienChuNhiem_id=current_user.idGiaoVien).first()

    if lop_chu_nhiem:
        # Lấy danh sách học kỳ
        danh_sach_hoc_ky = HocKy.query.order_by(HocKy.idHocKy).all()

        # Lấy học kỳ được chọn hoặc mặc định là học kỳ hiện tại của lớp
        hoc_ky_id = request.args.get('hocKy', lop_chu_nhiem.hocKy_id, type=int)
        hoc_ky = HocKy.query.get(hoc_ky_id)

        # Lấy danh sách học sinh trong lớp chủ nhiệm
        danh_sach_hoc_sinh = HocSinh.query.filter_by(maDsLop=lop_chu_nhiem.maDsLop).all()
        danh_sach_mon_hoc = MonHoc.query.all()  # Lấy tất cả các môn học

        # Lấy bảng điểm theo môn và loại điểm
        bang_diem = {}
        for hs in danh_sach_hoc_sinh:
            bang_diem[hs.idHocSinh] = {
                "15p": {mon.tenMonHoc: None for mon in danh_sach_mon_hoc},
                "1_tiet": {mon.tenMonHoc: None for mon in danh_sach_mon_hoc},
                "thi": {mon.tenMonHoc: None for mon in danh_sach_mon_hoc},
                "tb_mon": {mon.tenMonHoc: None for mon in danh_sach_mon_hoc}  # Thêm điểm trung bình môn
            }
            diem_cua_hoc_sinh = BangDiem.query.filter_by(hocSinh_id=hs.idHocSinh, hocKy_id=hoc_ky_id).all()

            # Tính điểm trung bình môn
            for diem in diem_cua_hoc_sinh:
                loai_diem = diem.loai_diem
                ten_mon = diem.mon_hoc.tenMonHoc
                bang_diem[hs.idHocSinh][loai_diem][ten_mon] = diem.diem

            for mon in danh_sach_mon_hoc:
                ten_mon = mon.tenMonHoc
                if (
                    bang_diem[hs.idHocSinh]["15p"][ten_mon] is not None
                    and bang_diem[hs.idHocSinh]["1_tiet"][ten_mon] is not None
                    and bang_diem[hs.idHocSinh]["thi"][ten_mon] is not None
                ):
                    tb_mon = (
                        bang_diem[hs.idHocSinh]["15p"][ten_mon]
                        + bang_diem[hs.idHocSinh]["1_tiet"][ten_mon] * 2
                        + bang_diem[hs.idHocSinh]["thi"][ten_mon] * 3
                    ) / 6
                    bang_diem[hs.idHocSinh]["tb_mon"][ten_mon] = round(tb_mon, 2)

            # Kiểm tra điều kiện nhập đủ điểm Toán, Văn, Anh trước khi tính điểm trung bình toàn bộ môn
            mon_can_thiet = ["Toán", "Văn", "Anh"]
            if all(
                bang_diem[hs.idHocSinh]["tb_mon"].get(mon) is not None
                for mon in mon_can_thiet
            ):
                # Tính điểm trung bình toàn bộ môn
                diem_tb_cac_mon = [
                    bang_diem[hs.idHocSinh]["tb_mon"][mon.tenMonHoc]
                    for mon in danh_sach_mon_hoc
                    if bang_diem[hs.idHocSinh]["tb_mon"][mon.tenMonHoc] is not None
                ]
                hs.diem_trung_binh = round(sum(diem_tb_cac_mon) / len(diem_tb_cac_mon), 2) if diem_tb_cac_mon else None

                # Xếp loại
                diem_toan = bang_diem[hs.idHocSinh]["tb_mon"].get("Toán", 0)
                diem_van = bang_diem[hs.idHocSinh]["tb_mon"].get("Văn", 0)
                if (diem_toan >= 8.0 or diem_van >= 8.0) and all(d >= 6.5 for d in diem_tb_cac_mon):
                    hs.xep_loai = "Giỏi"
                elif (diem_toan >= 6.5 or diem_van >= 6.5) and all(d >= 5.0 for d in diem_tb_cac_mon):
                    hs.xep_loai = "Khá"
                elif (diem_toan >= 3.5 or diem_van >= 3.5) and all(d >= 2.0 for d in diem_tb_cac_mon):
                    hs.xep_loai = "Yếu"
                else:
                    hs.xep_loai = "Kém"
            else:
                # Nếu chưa nhập đủ điểm thì để trống
                hs.diem_trung_binh = None
                hs.xep_loai = None

        return render_template(
            'layout/danh_sach_lop_chu_nhiem.html',
            lop=lop_chu_nhiem,
            danh_sach_hoc_sinh=danh_sach_hoc_sinh,
            danh_sach_mon_hoc=danh_sach_mon_hoc,
            bang_diem=bang_diem,
            hoc_ky=hoc_ky,
            danh_sach_hoc_ky=danh_sach_hoc_ky
        )
    else:
        # Nếu không chủ nhiệm lớp nào
        return render_template('layout/khong_chu_nhiem.html')


@app.route('/nhap-diem/<int:lop_id>', methods=['GET', 'POST'])
def nhap_diem(lop_id):
    lop = DanhSachLop.query.get(lop_id)

    # Lấy danh sách học sinh của lớp
    danh_sach_hoc_sinh = HocSinh.query.filter(HocSinh.maDsLop == lop_id).all()

    # Lấy môn học và giáo viên hiện tại
    giao_vien_id = current_user.idGiaoVien
    mon_hoc_id = current_user.idMonHoc  # Mỗi giáo viên chỉ dạy một môn

    # Lấy học kỳ từ lớp
    hoc_ky = HocKy.query.get(lop.hocKy_id)

    # Kiểm tra xem giáo viên có dạy môn học này trong lớp không
    giao_vien_day_lop = GiaoVienDayHoc.query.filter_by(idGiaoVien=giao_vien_id, idDsLop=lop_id).first()
    if not giao_vien_day_lop:
        flash("Bạn không có quyền nhập điểm cho lớp này!", "danger")
        return redirect('/giao-vien')

    # Lấy bảng điểm hiện tại của học sinh
    for hoc_sinh in danh_sach_hoc_sinh:
        hoc_sinh.diem_15p = next((d.diem for d in hoc_sinh.bang_diem if d.loai_diem == '15p' and d.monHoc_id == mon_hoc_id and d.hocKy_id == hoc_ky.idHocKy), '')
        hoc_sinh.diem_1_tiet = next((d.diem for d in hoc_sinh.bang_diem if d.loai_diem == '1_tiet' and d.monHoc_id == mon_hoc_id and d.hocKy_id == hoc_ky.idHocKy), '')
        hoc_sinh.diem_thi = next((d.diem for d in hoc_sinh.bang_diem if d.loai_diem == 'thi' and d.monHoc_id == mon_hoc_id and d.hocKy_id == hoc_ky.idHocKy), '')

    if request.method == 'POST':
        data = request.form
        # Lưu điểm cho học kỳ hiện tại
        hoc_ky_id = hoc_ky.idHocKy
        diem_15p_list = data.getlist('diem_15p[]')
        diem_1_tiet_list = data.getlist('diem_1_tiet[]')
        diem_thi_list = data.getlist('diem_thi[]')

        # Lưu dữ liệu điểm
        for i, hoc_sinh in enumerate(danh_sach_hoc_sinh):
            diem_15p = diem_15p_list[i] if i < len(diem_15p_list) and diem_15p_list[i] else None
            diem_1_tiet = diem_1_tiet_list[i] if i < len(diem_1_tiet_list) and diem_1_tiet_list[i] else None
            diem_thi = diem_thi_list[i] if i < len(diem_thi_list) and diem_thi_list[i] else None

            # Lưu điểm 15 phút
            if diem_15p:
                bang_diem_15p = BangDiem.query.filter_by(
                    hocSinh_id=hoc_sinh.idHocSinh, loai_diem='15p', monHoc_id=mon_hoc_id, hocKy_id=hoc_ky_id
                ).first()
                if not bang_diem_15p:
                    bang_diem_15p = BangDiem(
                        hocSinh_id=hoc_sinh.idHocSinh,
                        loai_diem='15p',
                        diem=diem_15p,
                        monHoc_id=mon_hoc_id,
                        giaoVien_id=giao_vien_id,
                        hocKy_id=hoc_ky_id
                    )
                    db.session.add(bang_diem_15p)
                else:
                    bang_diem_15p.diem = diem_15p

            # Lưu điểm 1 tiết
            if diem_1_tiet:
                bang_diem_1_tiet = BangDiem.query.filter_by(
                    hocSinh_id=hoc_sinh.idHocSinh, loai_diem='1_tiet', monHoc_id=mon_hoc_id, hocKy_id=hoc_ky_id
                ).first()
                if not bang_diem_1_tiet:
                    bang_diem_1_tiet = BangDiem(
                        hocSinh_id=hoc_sinh.idHocSinh,
                        loai_diem='1_tiet',
                        diem=diem_1_tiet,
                        monHoc_id=mon_hoc_id,
                        giaoVien_id=giao_vien_id,
                        hocKy_id=hoc_ky_id
                    )
                    db.session.add(bang_diem_1_tiet)
                else:
                    bang_diem_1_tiet.diem = diem_1_tiet

            # Lưu điểm thi
            if diem_thi:
                bang_diem_thi = BangDiem.query.filter_by(
                    hocSinh_id=hoc_sinh.idHocSinh, loai_diem='thi', monHoc_id=mon_hoc_id, hocKy_id=hoc_ky_id
                ).first()
                if not bang_diem_thi:
                    bang_diem_thi = BangDiem(
                        hocSinh_id=hoc_sinh.idHocSinh,
                        loai_diem='thi',
                        diem=diem_thi,
                        monHoc_id=mon_hoc_id,
                        giaoVien_id=giao_vien_id,
                        hocKy_id=hoc_ky_id
                    )
                    db.session.add(bang_diem_thi)
                else:
                    bang_diem_thi.diem = diem_thi

        db.session.commit()

        flash("Điểm đã được lưu thành công!", "success")
        return redirect(f'/xem-lop/{lop_id}')

    return render_template('layout/nhap_diem.html', lop=lop, danh_sach_hoc_sinh=danh_sach_hoc_sinh,  hoc_ky=hoc_ky)

@app.route('/xem-lop/<int:lop_id>')
def xem_lop(lop_id):
    lop = DanhSachLop.query.get(lop_id)
    danh_sach_hoc_sinh = HocSinh.query.filter(HocSinh.maDsLop == lop_id).all()
    # Lấy học kỳ từ lớp
    hoc_ky = HocKy.query.get(lop.hocKy_id)

    mon_hoc_id = current_user.idMonHoc  # Giáo viên chỉ xem điểm của môn học mình dạy

    for hoc_sinh in danh_sach_hoc_sinh:
        hoc_sinh.tb_15p = next(
            (d.diem for d in hoc_sinh.bang_diem if d.loai_diem == '15p' and d.monHoc_id == mon_hoc_id and d.hocKy_id == hoc_ky.idHocKy), None)
        hoc_sinh.tb_1_tiet = next(
            (d.diem for d in hoc_sinh.bang_diem if d.loai_diem == '1_tiet' and d.monHoc_id == mon_hoc_id and d.hocKy_id == hoc_ky.idHocKy), None)
        hoc_sinh.diem_thi = next(
            (d.diem for d in hoc_sinh.bang_diem if d.loai_diem == 'thi' and d.monHoc_id == mon_hoc_id and d.hocKy_id == hoc_ky.idHocKy), None)

        if hoc_sinh.tb_15p is not None and hoc_sinh.tb_1_tiet is not None and hoc_sinh.diem_thi is not None:
            print(hoc_sinh.tb_15p)
            print(hoc_sinh.tb_1_tiet)
            print(hoc_sinh.diem_thi)
            hoc_sinh.diem_trung_binh = round(
                ((hoc_sinh.tb_15p) + (hoc_sinh.tb_1_tiet * 2) + (hoc_sinh.diem_thi * 3)) / 6, 2)
        else:
            hoc_sinh.diem_trung_binh = None

    return render_template('/layout/danh_sach_hs.html', lop=lop, danh_sach_hoc_sinh=danh_sach_hoc_sinh, hoc_ky=hoc_ky)

@app.route('/chuyen-diem-hoc-ky', methods=['POST'])
def chuyen_diem_hoc_ky():
    hoc_ky_hien_tai = HocKy.query.order_by(HocKy.idHocKy.desc()).first()
    hoc_ky_tiep_theo = HocKy.query.filter(HocKy.namHoc == hoc_ky_hien_tai.namHoc, HocKy.hocKy != hoc_ky_hien_tai.hocKy).first()

    if not hoc_ky_tiep_theo:
        flash('Không tìm thấy học kỳ tiếp theo!', 'danger')
        return redirect('/admin')

    bang_diem_cu = BangDiem.query.filter_by(hocKy_id=hoc_ky_hien_tai.idHocKy).all()

    for diem in bang_diem_cu:
        bang_diem_moi = BangDiem(
            hocSinh_id=diem.hocSinh_id,
            loai_diem=diem.loai_diem,
            monHoc_id=diem.monHoc_id,
            giaoVien_id=diem.giaoVien_id,
            hocKy_id=hoc_ky_tiep_theo.idHocKy
        )
        db.session.add(bang_diem_moi)

    db.session.commit()
    flash('Đã chuyển điểm sang học kỳ tiếp theo!', 'success')
    return redirect('/admin')

def tinh_diem_trung_binh(hoc_sinh_id, hoc_ky_id):
    danh_sach_mon_hoc = MonHoc.query.all()
    diem_trung_binh = 0
    so_mon_hoc = 0

    for mon_hoc in danh_sach_mon_hoc:
        # Lấy điểm từ bảng `BangDiem`
        diem_15p = BangDiem.query.filter_by(hocSinh_id=hoc_sinh_id, hocKy_id=hoc_ky_id, monHoc_id=mon_hoc.idMonHoc, loai_diem='15p').first()
        diem_1_tiet = BangDiem.query.filter_by(hocSinh_id=hoc_sinh_id, hocKy_id=hoc_ky_id, monHoc_id=mon_hoc.idMonHoc, loai_diem='1_tiet').first()
        diem_thi = BangDiem.query.filter_by(hocSinh_id=hoc_sinh_id, hocKy_id=hoc_ky_id, monHoc_id=mon_hoc.idMonHoc, loai_diem='thi').first()

        if diem_15p is not None and diem_1_tiet is not None and diem_thi is not None:
            # Tính điểm trung bình môn
            diem_tb_mon = (diem_15p.diem + diem_1_tiet.diem * 2 + diem_thi.diem * 3) / 6
            diem_trung_binh += diem_tb_mon
            so_mon_hoc += 1

    if so_mon_hoc > 0:
        return round(diem_trung_binh / so_mon_hoc, 2)  # Trả về điểm trung bình
    return None  # Nếu không có điểm, trả về None

@app.route('/xac-nhan-bang-diem', methods=['POST'])
def xac_nhan_bang_diem():
    ma_ds_lop = request.form.get('maDsLop')  # Lấy mã lớp từ form
    lop = DanhSachLop.query.get(ma_ds_lop)  # Truy vấn thông tin lớp

    if not lop:
        flash("Lớp không tồn tại!", "danger")
        return redirect('/danh-sach-lop-chu-nhiem')

    # Lấy danh sách học sinh trong lớp
    danh_sach_hoc_sinh = HocSinh.query.filter(HocSinh.maDsLop == ma_ds_lop).all()
    hoc_ky_id = lop.hocKy_id  # Lấy học kỳ hiện tại của lớp

    for hs in danh_sach_hoc_sinh:
        # Tính điểm trung bình của học sinh
        diem_tb = tinh_diem_trung_binh(hs.idHocSinh, hoc_ky_id)

        if diem_tb is not None:
            # Kiểm tra xem đã có điểm trung bình trong bảng bang_diem_tb chưa
            bang_diem_tb = BangDiemTB.query.filter_by(hocSinh_id=hs.idHocSinh, hocKy_id=hoc_ky_id).first()

            if not bang_diem_tb:
                # Tạo bản ghi mới nếu chưa có
                bang_diem_tb = BangDiemTB(
                    hocSinh_id=hs.idHocSinh,
                    hocKy_id=hoc_ky_id,
                    diem_trung_binh=diem_tb
                )
                db.session.add(bang_diem_tb)
            else:
                # Cập nhật điểm trung bình nếu đã tồn tại
                bang_diem_tb.diem_trung_binh = diem_tb

    # Lưu tất cả thay đổi vào cơ sở dữ liệu
    db.session.commit()
    flash("Bảng điểm đã được xác nhận và lưu thành công!", "success")
    return redirect('/danh-sach-lop-chu-nhiem')



@app.route('/bang-diem-tong-ket', methods=['GET'])
def bang_diem_tong_ket():
    danh_sach_hoc_sinh = HocSinh.query.all()
    bang_diem_tong_ket = []

    for hs in danh_sach_hoc_sinh:
        lop_hoc = DanhSachLop.query.get(hs.maDsLop)

        # Lấy điểm trung bình từ bảng bang_diem_TB
        diem_tb_hk1 = BangDiemTB.query.filter_by(hocSinh_id=hs.idHocSinh, hocKy_id=1).first()
        diem_tb_hk2 = BangDiemTB.query.filter_by(hocSinh_id=hs.idHocSinh, hocKy_id=2).first()

        bang_diem_tong_ket.append({
            'ho_ten': hs.hoTen,
            'lop': lop_hoc.tenLop if lop_hoc else "",
            'diem_tb_hk1': diem_tb_hk1.diem_trung_binh if diem_tb_hk1 else "",
            'diem_tb_hk2': diem_tb_hk2.diem_trung_binh if diem_tb_hk2 else "",
        })

    return render_template(
        'layout/bang_diem_tong_ket.html',
        bang_diem_tong_ket=bang_diem_tong_ket,
        enumerate=enumerate
    )



@app.route('/xuat-bang-diem-tong-ket', methods=['POST'])
def xuat_bang_diem_tong_ket():
    danh_sach_hoc_sinh = HocSinh.query.all()
    bang_diem_tong_ket = []
    thong_bao_loi = []

    for hs in danh_sach_hoc_sinh:
        lop_hoc = DanhSachLop.query.get(hs.maDsLop)
        diem_tb_hk1 = tinh_diem_trung_binh(hs.idHocSinh, hoc_ky_id=1)
        diem_tb_hk2 = tinh_diem_trung_binh(hs.idHocSinh, hoc_ky_id=2)

        # Kiểm tra nếu học sinh nào chưa đủ điểm TB
        if diem_tb_hk1 is None or diem_tb_hk2 is None:
            thong_bao_loi.append(f"Học sinh {hs.hoTen} chưa đủ điểm trung bình HK1/HK2")

        bang_diem_tong_ket.append({
            'ho_ten': hs.hoTen,
            'lop': lop_hoc.tenLop if lop_hoc else "",
            'diem_tb_hk1': diem_tb_hk1 if diem_tb_hk1 is not None else "",
            'diem_tb_hk2': diem_tb_hk2 if diem_tb_hk2 is not None else "",
        })

    # Nếu bất kỳ học sinh nào chưa đủ điểm, trả về thông báo lỗi
    if thong_bao_loi:
        flash("Chưa đủ điểm Trung Bình HK1/HK2. Không thể xuất bảng điểm!", "danger")
        return redirect('/bang-diem-tong-ket')

    # Tạo file CSV nếu tất cả học sinh đã đủ điểm
    def generate_csv():
        data = ["STT,Họ Tên,Lớp,Điểm TB HK1,Điểm TB HK2\n"]
        for idx, diem in enumerate(bang_diem_tong_ket):
            data.append(f"{idx + 1},{diem['ho_ten']},{diem['lop']},{diem['diem_tb_hk1']},{diem['diem_tb_hk2']}\n")
        return data

    response = Response(generate_csv(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename="bang_diem_tong_ket.csv")
    return response


if __name__ == '__main__':
    from app import admin

    app.run(debug=True)
