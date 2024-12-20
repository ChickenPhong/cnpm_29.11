import hashlib

from flask import redirect, flash
from flask_admin import Admin, BaseView, expose
from app import app, db
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user, logout_user
from app.models import NhanVien, HocSinh, DanhSachLop, GiaoVienDayHoc, MonHoc, GiaoVien, UserRole, PhongHoc, QuyDinh

admin = Admin(app=app, name='Người Quản Trị', template_mode='bootstrap4')



class DanhSachLopView(ModelView):
    form_columns = ['tenLop', 'hocKy', 'giaoVienChuNhiem', 'phongHoc', 'siSo']

    # def on_model_change(self, form, model, is_created):
    #     # Kiểm tra nếu phòng học đã được sử dụng
    #     existing_class = DanhSachLop.query.filter(
    #         DanhSachLop.idPhongHoc == model.idPhongHoc,
    #         DanhSachLop.maDsLop != model.maDsLop  # Không kiểm tra chính lớp hiện tại
    #     ).first()
    #
    #     if existing_class:
    #         flash(f"Phòng học {model.phongHoc.tenPhong} đã được sử dụng trong lớp khác.", "error")
    #         raise ValueError(f"Phòng học {model.phongHoc.tenPhong} đã được chọn.")
    #
    #     super(DanhSachLopView, self).on_model_change(form, model, is_created)


class GiaoVienView(ModelView):
    column_list = ['hoTen', 'gioiTinh', 'ngaySinh', 'diaChi', 'SDT', 'eMail', 'monHoc', 'taiKhoan', 'matKhau']
    form_columns = ['hoTen', 'gioiTinh', 'ngaySinh', 'diaChi', 'SDT', 'eMail', 'taiKhoan', 'matKhau', 'monHoc']

    def on_model_change(self, form, model, is_created):
        if form.matKhau.data:
            model.matKhau = hashlib.md5(form.matKhau.data.encode('utf-8')).hexdigest()

        super(GiaoVienView, self).on_model_change(form, model, is_created)



    # def on_model_change(self, form, model, is_created):
    #     dsKhoiPhong = KhoiPhong.query.all()
    #     for khoiphong in dsKhoiPhong:
    #         if(form.KhoiLop.data.__eq__(khoiphong.KhoiLop) and form.PhongHoc.data.__eq__(khoiphong.PhongHoc)
    #             and form.buoiHoc.data.__eq__(khoiphong.buoiHoc)):
    #             flash("Khối phòng đó đã được tạo", "error")
    #             is_created==False
    #             return redirect('/admin/khoiphong/new')
    #
    #     super(GiaoVienView, self).on_model_change(form, model, is_created)
    #
    # def on


class QuiDinhView(ModelView):
    column_labels = {
        'min_age': 'Tuổi thấp nhất',
        'max_age': 'Tuổi cao nhất',
        'si_so': 'Sĩ số'
    }
    can_create = False  # Không cho phép thêm
    can_delete = False  # Không cho phép xóa

    # Chỉ định các cột hiển thị và chỉnh sửa
    form_columns = ['min_age', 'max_age', 'si_so']
    column_list = ['min_age', 'max_age', 'si_so']

admin.add_view(QuiDinhView(QuyDinh, db.session))
admin.add_view(ModelView(MonHoc, db.session))
admin.add_view(ModelView(PhongHoc, db.session))
admin.add_view(ModelView(NhanVien, db.session))
admin.add_view(GiaoVienView(GiaoVien, db.session))
admin.add_view(ModelView(GiaoVienDayHoc, db.session))
admin.add_view(ModelView(HocSinh, db.session))
admin.add_view(DanhSachLopView(DanhSachLop, db.session))

